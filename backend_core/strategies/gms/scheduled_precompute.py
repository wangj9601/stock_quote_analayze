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


def _resolve_precompute_config_ids() -> List[int]:
    from backend_core.strategies.gms.config import GMSConfigManager

    mgr = GMSConfigManager()
    config_ids = mgr.list_precompute_config_ids()
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
) -> None:
    from backend_core.database.db import SessionLocal
    from backend_core.strategies.gms.config import GMSConfigManager
    from backend_core.strategies.gms.frontend_interface import GMSFrontendInterface

    db = SessionLocal()
    try:
        target_date = resolve_gms_trade_date(db)
        mgr = GMSConfigManager()
        cfg = mgr.get_config(config_id)
        gms = GMSFrontendInterface(db, cfg, config_id=config_id)
        gms.set_selection_config(min_score=0, max_results=200000)
        mkt = "all" if stock_pool else market
        results, meta = gms.get_selection_results(
            target_date,
            stock_pool,
            mkt,
            trace_only=False,
            return_meta=True,
        )
        logger.info(
            "[GMS预计算] 完成 config_id=%s date=%s market=%s pool=%s 返回=%s meta=%s",
            config_id,
            target_date,
            market,
            "custom" if stock_pool else "full",
            len(results),
            meta,
        )
    except Exception as e:
        logger.error(
            "[GMS预计算] 失败 config_id=%s market=%s: %s",
            config_id,
            market,
            e,
            exc_info=True,
        )
    finally:
        db.close()


def run_gms_precompute(
    market: str,
    stock_pool: Optional[List[str]] = None,
    skip_weekend: bool = True,
) -> None:
    """
    执行一次 GMS 全量扫描并写入 gms_signal_trace（已有记录会跳过计算）。
    对 is_default 或 precompute_enabled 的每个参数版本分别预计算。

    Args:
        market: cn | hk | all（stock_pool 为 None 时有效）
        stock_pool: 非空时按自定义列表计算，market 传 all
        skip_weekend: 周六日跳过（与历史采集任务一致）
    """
    if skip_weekend and datetime.now().weekday() in (5, 6):
        logger.info("[GMS预计算] 周末跳过 market=%s", market)
        return

    config_ids = _resolve_precompute_config_ids()
    if not config_ids:
        logger.warning("[GMS预计算] 无可用 config_id，跳过 market=%s", market)
        return

    for cid in config_ids:
        run_gms_precompute_for_config(cid, market, stock_pool)


def scheduled_gms_signals_cn() -> None:
    run_gms_precompute("cn", stock_pool=None)


def scheduled_gms_signals_hk() -> None:
    run_gms_precompute("hk", stock_pool=None)


def scheduled_gms_signals_custom() -> None:
    codes = parse_gms_custom_stock_codes()
    if not codes:
        logger.info("[GMS预计算] GMS_CUSTOM_STOCK_CODES 为空，跳过 custom")
        return
    run_gms_precompute("all", stock_pool=codes)


def scheduled_gms_signals_watchlist() -> None:
    from backend_core.database.db import SessionLocal

    db = SessionLocal()
    try:
        codes = load_all_watchlist_stock_codes(db)
    finally:
        db.close()
    if not codes:
        logger.info("[GMS预计算] 全用户 watchlist 为空，跳过")
        return
    run_gms_precompute("all", stock_pool=codes)
