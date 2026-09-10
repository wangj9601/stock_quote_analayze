# -*- coding: utf-8 -*-
"""CSB 信号定时预计算。"""

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


def resolve_csb_trade_date(db) -> str:
    from backend_api.models import HistoricalQuotes

    latest = db.query(func.max(HistoricalQuotes.date)).scalar()
    if latest:
        return latest.strftime("%Y-%m-%d") if hasattr(latest, "strftime") else str(latest)[:10]
    return datetime.now().strftime("%Y-%m-%d")


def list_precompute_config_ids(db) -> List[int]:
    from backend_api.models import CSBStrategyConfig

    rows = (
        db.query(CSBStrategyConfig.id)
        .filter(
            CSBStrategyConfig.is_active.is_(True),
            (
                (CSBStrategyConfig.is_default.is_(True))
                | (CSBStrategyConfig.precompute_enabled.is_(True))
            ),
        )
        .order_by(CSBStrategyConfig.id.asc())
        .all()
    )
    return [int(r[0]) for r in rows]


def run_csb_precompute_for_config(
    config_id: int,
    *,
    trade_date: Optional[str] = None,
    limit: Optional[int] = None,
) -> dict:
    from backend_api.database import SessionLocal
    from backend_core.strategies.csb.config import CSBConfigManager
    from backend_core.strategies.csb.data_loader import CSBDataLoader
    from backend_core.strategies.csb.strategy_engine import CSBStrategyEngine
    from backend_core.strategies.csb.trace_store import mark_date_scanned, upsert_trace_rows

    db = SessionLocal()
    started = datetime.now()
    try:
        cm = CSBConfigManager()
        cm.ensure_default_row(db)
        cfg = cm.get_config(config_id, db=db)
        loader = CSBDataLoader(db)
        date_s = trade_date or resolve_csb_trade_date(db)
        date_s = loader.resolve_effective_trade_date(date_s)
        stocks = loader.list_a_share_candidates(limit=limit)
        engine = CSBStrategyEngine(loader, cfg)
        hits = engine.screen(stocks, as_of_end_date=date_s, require_entry=True)
        written = upsert_trace_rows(db, config_id=config_id, rows=hits)
        mark_date_scanned(
            db,
            config_id=config_id,
            trade_date=date_s,
            extra={"hits": len(hits), "candidates": len(stocks), "scope": "full_market"},
        )
        elapsed = (datetime.now() - started).total_seconds()
        logger.info(
            "CSB 预计算完成 config_id=%s date=%s hits=%s written=%s elapsed=%.1fs",
            config_id, date_s, len(hits), written, elapsed,
        )
        return {
            "success": True,
            "config_id": config_id,
            "trade_date": date_s,
            "candidates": len(stocks),
            "hits": len(hits),
            "written": written,
            "elapsed_sec": elapsed,
        }
    except Exception as e:
        logger.exception("CSB 预计算失败 config_id=%s: %s", config_id, e)
        return {"success": False, "config_id": config_id, "error": str(e)}
    finally:
        db.close()


def run_csb_trace_refresh_range(
    config_id: int,
    *,
    start_date: str,
    end_date: str,
    purge_first: bool = True,
    stock_pool: Optional[List[str]] = None,
) -> dict:
    from backend_api.database import SessionLocal
    from backend_core.strategies.csb.backtest_runner import _ensure_trace_for_backtest_range, _trading_dates
    from backend_core.strategies.csb.config import CSBConfigManager
    from backend_core.strategies.csb.data_loader import CSBDataLoader
    from backend_core.strategies.csb.strategy_engine import CSBStrategyEngine
    from backend_core.strategies.csb.trace_store import delete_trace_for_config

    started = datetime.now()
    db = SessionLocal()
    try:
        cm = CSBConfigManager()
        cm.ensure_default_row(db)
        cfg = cm.get_config(int(config_id), db=db)
        purged = delete_trace_for_config(db, config_id=int(config_id)) if purge_first else 0
        dates = _trading_dates(db, start_date, end_date)
        if not dates:
            return {"success": False, "error": "区间内无交易日", "purged_rows": purged}
        loader = CSBDataLoader(db)
        engine = CSBStrategyEngine(loader, cfg)
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
        return {
            "success": True,
            "config_id": config_id,
            "start_date": str(start_date)[:10],
            "end_date": str(end_date)[:10],
            "purged_rows": purged,
            "elapsed_sec": elapsed,
            **meta,
        }
    except Exception as e:
        logger.exception("CSB 区间 trace 刷新失败: %s", e)
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def scheduled_csb_signals_cn() -> None:
    if datetime.now().weekday() >= 5:
        return
    if not _env_bool("ENABLE_CSB_PRECOMPUTE", True):
        return
    from backend_api.database import SessionLocal

    db = SessionLocal()
    try:
        ids = list_precompute_config_ids(db)
    finally:
        db.close()
    for cid in ids:
        run_csb_precompute_for_config(cid)
