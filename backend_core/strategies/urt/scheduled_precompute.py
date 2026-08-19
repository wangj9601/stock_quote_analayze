# -*- coding: utf-8 -*-
"""
URT 信号定时预计算：写入 urt_signal_trace（A 股 / 港股）。
由 backend_core/data_collectors/main.py 注册。
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import List, Optional

from sqlalchemy import func

logger = logging.getLogger(__name__)


def _env_bool(key: str, default: bool = True) -> bool:
    raw = (os.getenv(key) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "y", "on")


def resolve_urt_trade_date(db, *, market: str = "CN") -> str:
    mkt = str(market or "CN").strip().upper()
    if mkt == "HK":
        from backend_api.models import HistoricalQuotesHK

        latest = db.query(func.max(HistoricalQuotesHK.date)).scalar()
    else:
        from backend_api.models import HistoricalQuotes

        latest = db.query(func.max(HistoricalQuotes.date)).scalar()
    if latest:
        if hasattr(latest, "strftime"):
            return latest.strftime("%Y-%m-%d")
        return str(latest).strip()[:10]
    return datetime.now().strftime("%Y-%m-%d")


def list_precompute_config_ids(db) -> List[int]:
    from backend_api.models import URTStrategyConfig

    rows = (
        db.query(URTStrategyConfig.id)
        .filter(
            URTStrategyConfig.is_active.is_(True),
            (
                (URTStrategyConfig.is_default.is_(True))
                | (URTStrategyConfig.precompute_enabled.is_(True))
            ),
        )
        .order_by(URTStrategyConfig.id.asc())
        .all()
    )
    ids = [int(r[0]) for r in rows]
    env_raw = (os.getenv("URT_PRECOMPUTE_CONFIG_IDS") or "").strip()
    if env_raw:
        for p in env_raw.split(","):
            p = p.strip()
            if p.isdigit():
                ids.append(int(p))
    return list(dict.fromkeys(ids))


def run_urt_precompute_for_config(
    config_id: int,
    *,
    trade_date: Optional[str] = None,
    limit: Optional[int] = None,
    market: str = "CN",
) -> dict:
    """对单个参数版本做全市场硬筛+得分并落库（只写 buy_signal=True）。"""
    from backend_api.database import SessionLocal
    from backend_core.strategies.urt.config import URTConfigManager
    from backend_core.strategies.urt.data_loader import URTDataLoader
    from backend_core.strategies.urt.strategy_engine import URTStrategyEngine
    from backend_core.strategies.urt.trace_store import upsert_trace_rows

    mkt = str(market or "CN").strip().upper()
    db = SessionLocal()
    started = datetime.now()
    try:
        try:
            from backend_api.models import URTSignalTrace

            URTSignalTrace.__table__.create(bind=db.get_bind(), checkfirst=True)
        except Exception:
            pass

        cm = URTConfigManager()
        cm.ensure_default_row(db)
        cfg = cm.get_config(config_id, db=db)
        loader = URTDataLoader(db, market=mkt)
        date_s = trade_date or resolve_urt_trade_date(db, market=mkt)
        date_s = URTDataLoader.resolve_effective_history_end_date(db, date_s, market=mkt)

        if mkt == "HK":
            stocks = loader.list_hk_share_candidates(limit=limit)
        else:
            stocks = loader.list_a_share_candidates(limit=limit)
        engine = URTStrategyEngine(loader, cfg)
        hits = engine.screen_universe(stocks, as_of_end_date=date_s)
        written = upsert_trace_rows(db, config_id=config_id, rows=hits)
        elapsed = (datetime.now() - started).total_seconds()
        logger.info(
            "URT 预计算完成 config_id=%s market=%s date=%s candidates=%s hits=%s written=%s elapsed=%.1fs",
            config_id,
            mkt,
            date_s,
            len(stocks),
            len(hits),
            written,
            elapsed,
        )
        return {
            "success": True,
            "config_id": config_id,
            "market": mkt,
            "trade_date": date_s,
            "candidates": len(stocks),
            "hits": len(hits),
            "written": written,
            "elapsed_sec": elapsed,
        }
    except Exception as e:
        logger.exception("URT 预计算失败 config_id=%s market=%s: %s", config_id, mkt, e)
        return {"success": False, "config_id": config_id, "market": mkt, "error": str(e)}
    finally:
        db.close()


def run_urt_precompute_market(
    market: str,
    *,
    trade_date: Optional[str] = None,
    limit: Optional[int] = None,
) -> dict:
    from backend_api.database import SessionLocal

    db = SessionLocal()
    try:
        ids = list_precompute_config_ids(db)
    finally:
        db.close()
    if not ids:
        logger.warning("URT 预计算：无 is_default/precompute_enabled 版本，跳过 market=%s", market)
        return {"success": True, "skipped": True, "message": "no config", "market": market}
    results = [
        run_urt_precompute_for_config(
            cid,
            trade_date=trade_date,
            limit=limit,
            market=market,
        )
        for cid in ids
    ]
    ok = all(r.get("success") for r in results)
    return {"success": ok, "market": market, "results": results}


def run_urt_precompute_ashare(*, trade_date: Optional[str] = None, limit: Optional[int] = None) -> dict:
    return run_urt_precompute_market("CN", trade_date=trade_date, limit=limit)


def run_urt_precompute_hk(*, trade_date: Optional[str] = None, limit: Optional[int] = None) -> dict:
    return run_urt_precompute_market("HK", trade_date=trade_date, limit=limit)


def run_urt_trace_refresh_range(
    config_id: int,
    *,
    start_date: str,
    end_date: str,
    purge_first: bool = True,
    stock_pool: Optional[List[str]] = None,
) -> dict:
    """
    按回测区间强制刷新 urt_signal_trace（A 股全市场或指定股票池）。
    先可选清空该 config_id 全部 trace，再调用与回测相同的区间一次扫描落库。
    """
    from backend_api.database import SessionLocal
    from backend_core.strategies.urt.config import URTConfigManager
    from backend_core.strategies.urt.data_loader import URTDataLoader
    from backend_core.strategies.urt.strategy_engine import URTStrategyEngine
    from backend_core.strategies.urt.trace_store import delete_trace_for_config

    started = datetime.now()
    db = SessionLocal()
    try:
        cm = URTConfigManager()
        cm.ensure_default_row(db)
        row = cm.get_config_row(db, int(config_id))
        if not row:
            return {"success": False, "config_id": config_id, "error": "参数版本不存在"}
        cfg = cm.get_config(int(config_id), db=db)

        purged = 0
        if purge_first:
            purged = delete_trace_for_config(db, config_id=int(config_id))

        from backend_core.strategies.urt.backtest_runner import (
            _ensure_trace_for_backtest_range,
            _trading_dates,
        )

        dates = _trading_dates(db, start_date, end_date)
        if not dates:
            return {
                "success": False,
                "config_id": config_id,
                "error": "区间内无交易日",
                "purged_rows": purged,
            }

        loader = URTDataLoader(db, market="CN")
        engine = URTStrategyEngine(loader, cfg)
        meta = _ensure_trace_for_backtest_range(
            db,
            dates=dates,
            config_id=int(config_id),
            cfg=cfg,
            loader=loader,
            engine=engine,
            stock_pool=stock_pool,
        )
        elapsed = (datetime.now() - started).total_seconds()
        logger.info(
            "URT 区间 trace 刷新完成 config_id=%s %s~%s purged=%s precomputed_days=%s hits=%s elapsed=%.1fs",
            config_id,
            start_date,
            end_date,
            purged,
            meta.get("precomputed_days"),
            meta.get("precompute_hits"),
            elapsed,
        )
        return {
            "success": True,
            "config_id": config_id,
            "start_date": str(start_date)[:10],
            "end_date": str(end_date)[:10],
            "purged_rows": purged,
            "range_days": len(dates),
            "elapsed_sec": elapsed,
            **meta,
        }
    except Exception as e:
        logger.exception("URT 区间 trace 刷新失败 config_id=%s: %s", config_id, e)
        try:
            db.rollback()
        except Exception:
            pass
        return {"success": False, "config_id": config_id, "error": str(e)}
    finally:
        db.close()


def scheduled_urt_signals_cn() -> None:
    """定时入口：工作日 A 股全量预计算。"""
    if datetime.now().weekday() >= 5:
        logger.info("URT 预计算跳过周末")
        return
    if not _env_bool("ENABLE_URT_PRECOMPUTE", True):
        logger.info("URT 预计算已禁用 ENABLE_URT_PRECOMPUTE=false")
        return
    run_urt_precompute_ashare()


def scheduled_urt_signals_hk() -> None:
    """定时入口：工作日港股全量预计算。"""
    if datetime.now().weekday() >= 5:
        logger.info("URT 港股预计算跳过周末")
        return
    if not _env_bool("ENABLE_URT_PRECOMPUTE", True):
        logger.info("URT 预计算已禁用 ENABLE_URT_PRECOMPUTE=false")
        return
    run_urt_precompute_hk()
