"""
GMS 策略信号定时预计算：将全市场/自定义股票池/全量自关注(watchlist 并集)的选股结果写入 gms_signal_trace，
供前端「刷新筛选」时优先走库内缓存，减少实时计算与网关超时风险。

由 backend_core/data_collectors/main.py 的定时任务调用。
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from typing import List, Optional

from sqlalchemy import func

import time

from backend_api.services.gms_job_tracker import record_precompute_run

logger = logging.getLogger(__name__)


def _env(key: str, default: str = "") -> str:
    return (os.getenv(key) or default).strip()


def resolve_gms_trade_date(db) -> str:
    """与选股接口一致：取 A股/港股历史行情表中最新的交易日（字符串 YYYY-MM-DD）。"""
    try:
        from backend_api.models import HistoricalQuotes, HistoricalQuotesHK

        candidates = []
        latest_a = db.query(func.max(HistoricalQuotes.date)).scalar()
        if latest_a:
            d = (
                latest_a.strftime("%Y-%m-%d")
                if hasattr(latest_a, "strftime")
                else str(latest_a).strip()[:10]
            )
            candidates.append(d)
        latest_hk = db.query(func.max(HistoricalQuotesHK.date)).scalar()
        if latest_hk:
            d = str(latest_hk).strip()[:10]
            candidates.append(d)
        if candidates:
            return max(candidates)
    except Exception as e:
        logger.warning("GMS 预计算解析交易日失败，使用当天: %s", e)
    return datetime.now().strftime("%Y-%m-%d")


def parse_gms_custom_stock_codes() -> List[str]:
    """
    从环境变量 GMS_CUSTOM_STOCK_CODES 读取自定义股票池（逗号/空白/分号分隔）。
    A 股尽量 6 位，港股数字代码 5 位补零。
    """
    raw = _env("GMS_CUSTOM_STOCK_CODES")
    if not raw:
        return []
    parts = re.split(r"[,;\s]+", raw)
    out: List[str] = []
    for p in parts:
        s = str(p).strip()
        if not s:
            continue
        if s.isdigit():
            if len(s) <= 5:
                s = s.zfill(5)
            else:
                s = s.zfill(6)
        out.append(s)
    return list(dict.fromkeys(out))


def load_all_watchlist_stock_codes(db) -> List[str]:
    """
    所有用户自关注列表中的股票代码并集（去重），与 watchlist_manage 展示规则一致：
    纯数字且长度<=5 视为港股补零至 5 位，否则 A 股补至 6 位。
    """
    try:
        from backend_api.models import Watchlist

        rows = db.query(Watchlist.stock_code).distinct().all()
        out: List[str] = []
        for r in rows:
            if r[0] is None:
                continue
            s = str(r[0]).strip()
            if not s:
                continue
            if s.isdigit():
                out.append(s.zfill(5) if len(s) <= 5 else s.zfill(6))
            else:
                out.append(s)
        return list(dict.fromkeys(out))
    except Exception as e:
        logger.warning("GMS 预计算加载 watchlist 失败: %s", e)
        return []


def _resolve_precompute_config_ids(
    timeframe: str = "daily",
    *,
    ignore_env_whitelist: bool = False,
) -> List[int]:
    from backend_core.strategies.gms.config import GMSConfigManager

    mgr = GMSConfigManager()
    config_ids = mgr.list_precompute_config_ids(timeframe=timeframe)
    if ignore_env_whitelist:
        return config_ids
    # 周线只用 GMS_WEEKLY_PRECOMPUTE_CONFIG_IDS；勿回退到日线白名单（否则会把 default_weekly 滤空）
    if timeframe == "weekly":
        raw = _env("GMS_WEEKLY_PRECOMPUTE_CONFIG_IDS")
    else:
        raw = _env("GMS_PRECOMPUTE_CONFIG_IDS")
    if raw:
        whitelist = [int(x) for x in re.split(r"[,;\s]+", raw) if x.strip().isdigit()]
        if whitelist:
            config_ids = [cid for cid in config_ids if cid in whitelist]
    return config_ids


def run_gms_precompute_for_config(
    config_id: int,
    market: str,
    stock_pool: Optional[List[str]] = None,
    *,
    timeframe: str = "daily",
    target_date: Optional[str] = None,
) -> None:
    from backend_core.database.db import SessionLocal
    from backend_core.strategies.gms.config import GMSConfigManager
    from backend_core.strategies.gms.frontend_interface import GMSFrontendInterface

    tf = (timeframe or "daily").strip().lower()
    db = SessionLocal()
    t0 = time.perf_counter()
    resolved_date = ""
    try:
        if target_date:
            resolved_date = str(target_date).strip()[:10]
        elif tf == "weekly":
            from backend_core.strategies.gms.week_calendar import (
                resolve_gms_trade_date_fallback,
                resolve_gms_week_end,
            )

            as_of = resolve_gms_trade_date_fallback(db)
            resolved_date = resolve_gms_week_end(db, as_of) or ""
            if not resolved_date:
                raise RuntimeError(f"无法解析已收盘周 as_of={as_of}")
        else:
            resolved_date = resolve_gms_trade_date(db)
        mgr = GMSConfigManager()
        cfg = mgr.get_config(config_id)
        gms = GMSFrontendInterface(db, cfg, config_id=config_id, timeframe=tf)
        # min_score=0：全市场仍算完；入库地板分在 trace 写入侧裁剪（默认 30，只减库）
        gms.set_selection_config(min_score=0, max_results=200000)
        mkt = "all" if stock_pool else market
        results, meta = gms.get_selection_results(
            resolved_date,
            stock_pool,
            mkt,
            trace_only=False,
            return_meta=True,
        )
        from backend_core.strategies.gms.frontend_interface import (
            resolve_gms_trace_storage_min_score,
        )

        floor = resolve_gms_trace_storage_min_score(cfg)
        duration_ms = int((time.perf_counter() - t0) * 1000)
        record_precompute_run(
            db,
            config_id,
            market,
            resolved_date,
            "success",
            stock_count=len(results),
            duration_ms=duration_ms,
            timeframe=tf,
        )
        logger.info(
            "[GMS预计算] 完成 config_id=%s date=%s market=%s tf=%s pool=%s 返回=%s "
            "storage_min_score=%s meta=%s",
            config_id,
            resolved_date,
            market,
            tf,
            "custom" if stock_pool else "full",
            len(results),
            floor,
            meta,
        )
        return {
            "success": True,
            "config_id": config_id,
            "market": market,
            "trade_date": resolved_date,
            "timeframe": tf,
            "signal_count": len(results),
            "written": len(results),
        }
    except Exception as e:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        record_precompute_run(
            db,
            config_id,
            market,
            resolved_date or datetime.now().strftime("%Y-%m-%d"),
            "failed",
            stock_count=0,
            duration_ms=duration_ms,
            error_message=str(e)[:500],
            timeframe=tf,
        )
        logger.error(
            "[GMS预计算] 失败 config_id=%s market=%s tf=%s: %s",
            config_id,
            market,
            tf,
            e,
            exc_info=True,
        )
        return {
            "success": False,
            "config_id": config_id,
            "market": market,
            "trade_date": resolved_date,
            "timeframe": tf,
            "error": str(e),
            "signal_count": 0,
            "written": 0,
        }
    finally:
        db.close()


def run_gms_precompute(
    market: str,
    stock_pool: Optional[List[str]] = None,
    skip_weekend: bool = True,
    *,
    timeframe: str = "daily",
    force: bool = False,
    as_of: Optional[str] = None,
):
    """
    执行一次 GMS 全量扫描并写入 trace。
    对 is_default 或 precompute_enabled 的每个参数版本分别预计算。

    Args:
        market: cn | hk | all（stock_pool 为 None 时有效）
        stock_pool: 非空时按自定义列表计算，market 传 all
        skip_weekend: 周六日跳过（日线与历史采集一致；周线不因周末跳过）
        timeframe: daily | weekly
        force: 强制计算（周线：确保 default_weekly、忽略环境白名单滤空）
        as_of: 可选 as-of 日；周线再解析为已收盘周周五标签
    """
    from backend_core.data_collectors.workflow.signal_count import pack_signal_runs
    from backend_core.strategies.gms.config import GMSConfigManager
    from backend_core.strategies.gms.week_calendar import (
        normalize_date_str,
        resolve_gms_week_end,
    )
    from backend_core.database.db import SessionLocal

    tf = (timeframe or "daily").strip().lower()
    if tf == "daily" and skip_weekend and (not force) and datetime.now().weekday() in (5, 6):
        logger.info("[GMS预计算] 周末跳过 market=%s", market)
        return {"skipped": True, "reason": "周末跳过", "market": market}

    weekly_id: Optional[int] = None
    if tf == "weekly":
        weekly_id = GMSConfigManager().ensure_canonical_weekly_config()

    config_ids = _resolve_precompute_config_ids(
        timeframe=tf,
        ignore_env_whitelist=bool(force and tf == "weekly"),
    )
    if not config_ids and weekly_id is not None:
        config_ids = [int(weekly_id)]
        logger.warning(
            "[GMS预计算] 周线预计算列表为空，回退 canonical config_id=%s force=%s",
            weekly_id,
            force,
        )
    if not config_ids:
        logger.warning("[GMS预计算] 无可用 config_id，跳过 market=%s tf=%s", market, tf)
        return {"skipped": True, "reason": "无预计算版本", "market": market, "timeframe": tf}

    target_date: Optional[str] = None
    if tf == "weekly":
        db = SessionLocal()
        try:
            asof = normalize_date_str(as_of) if as_of else ""
            if not asof:
                from backend_core.strategies.gms.week_calendar import (
                    resolve_gms_trade_date_fallback,
                )

                asof = resolve_gms_trade_date_fallback(db)
            target_date = resolve_gms_week_end(db, asof) or None
            if not target_date:
                return {
                    "skipped": True,
                    "reason": f"无法解析已收盘周 as_of={asof}",
                    "market": market,
                    "timeframe": tf,
                }
        finally:
            db.close()

    return pack_signal_runs(
        [
            run_gms_precompute_for_config(
                cid,
                market,
                stock_pool,
                timeframe=tf,
                target_date=target_date,
            )
            for cid in config_ids
        ]
    )


def scheduled_gms_signals_cn():
    return run_gms_precompute("cn", stock_pool=None, timeframe="daily")


def scheduled_gms_signals_hk():
    return run_gms_precompute("hk", stock_pool=None, timeframe="daily")


def scheduled_weekly_mf_cn():
    """工作流节点：已收盘周周频 MF。"""
    from backend_core.database.db import SessionLocal
    from backend_core.data_collectors.batch_mean_frequency_weekly import (
        run_weekly_mf_cn_for_as_of,
    )

    db = SessionLocal()
    try:
        return run_weekly_mf_cn_for_as_of(db)
    finally:
        db.close()


def scheduled_gms_signals_weekly_cn(
    *,
    force: bool = False,
    as_of: Optional[str] = None,
):
    """工作流节点：A 股 GMS 周线预计算（仅已收盘周）。"""
    return run_gms_precompute(
        "cn",
        stock_pool=None,
        timeframe="weekly",
        skip_weekend=False,
        force=bool(force),
        as_of=as_of,
    )


def scheduled_gms_signals_custom():
    codes = parse_gms_custom_stock_codes()
    if not codes:
        logger.info("[GMS预计算] GMS_CUSTOM_STOCK_CODES 为空，跳过 custom")
        return {"skipped": True, "reason": "自定义股票池为空"}
    return run_gms_precompute("all", stock_pool=codes)


def scheduled_gms_signals_watchlist() -> None:
    from backend_core.database.db import SessionLocal

    db = SessionLocal()
    try:
        codes = load_all_watchlist_stock_codes(db)
    finally:
        db.close()
    if not codes:
        logger.info("[GMS预计算] 全用户 watchlist 为空，跳过")
        return {"skipped": True, "reason": "自选股为空"}
    return run_gms_precompute("all", stock_pool=codes)
