# -*- coding: utf-8 -*-
"""DBLB 手动预计算（强制重算并入库；暂不挂 cron）。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


def run_dblb_precompute(
    *,
    config_id: Optional[int] = None,
    trade_date: Optional[str] = None,
    status_filter: Optional[str] = None,
    stock_pool_mode: str = "stocks",
    industry_board_codes: Optional[Sequence[Any]] = None,
    concept_board_codes: Optional[Sequence[Any]] = None,
    stock_codes: Optional[Sequence[Any]] = None,
    universe_limit: Optional[int] = None,
    max_results: Optional[int] = None,
    force_recompute: bool = True,
) -> Dict[str, Any]:
    from backend_api.database import SessionLocal

    from .config import DblbConfigManager
    from .signal_storage import delete_traces_not_in_codes, upsert_signal_traces
    from .strategy_engine import DblbStrategyEngine

    cm = DblbConfigManager()
    cid = int(config_id) if config_id is not None else cm.get_default_config_id()
    cfg = cm.get_config(cid)
    engine = DblbStrategyEngine(config=cfg)

    db = SessionLocal()
    try:
        result = engine.screen(
            db,
            trade_date=trade_date,
            config_id=cid,
            status_filter=status_filter,
            stock_pool_mode=stock_pool_mode,
            industry_board_codes=industry_board_codes,
            concept_board_codes=concept_board_codes,
            stock_codes=stock_codes,
            universe_limit=universe_limit,
            max_results=max_results,
            force_recompute=force_recompute,
        )
        items: List[Dict[str, Any]] = list(result.get("items") or [])
        date_s = str(result.get("trade_date") or trade_date or "")
        saved = upsert_signal_traces(
            db,
            items,
            config_id=cid,
            trade_date=date_s,
        )
        deleted = 0
        if force_recompute:
            deleted = delete_traces_not_in_codes(
                db,
                trade_date=date_s,
                config_id=cid,
                scope_codes=list(result.get("scope_codes") or []),
                keep_codes=[str(r.get("code") or "") for r in items],
            )
        return {
            "ok": True,
            "trade_date": result.get("trade_date"),
            "config_id": cid,
            "status_filter": result.get("status_filter"),
            "scope_meta": result.get("scope_meta") or {},
            "screened": result.get("screened"),
            "hit_count": result.get("hit_count"),
            "saved": saved,
            "deleted_stale": deleted,
            "force_recompute": bool(force_recompute),
            "reused": result.get("reused"),
            "computed": result.get("computed"),
        }
    except Exception as e:
        logger.exception("DBLB precompute failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        raise
    finally:
        db.close()
