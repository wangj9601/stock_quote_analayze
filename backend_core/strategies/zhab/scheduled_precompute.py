# -*- coding: utf-8 -*-
"""ZHAB 日终预计算入口。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Sequence

logger = logging.getLogger(__name__)


def run_zhab_precompute(
    *,
    trade_date: Optional[str] = None,
    config_id: Optional[int] = None,
    sector: Optional[Dict[str, Any]] = None,
    concept_board_codes: Optional[Sequence[str]] = None,
    season: Any = None,
    gates: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from backend_api.database import SessionLocal
    from backend_core.strategies.zhab.strategy_engine import ensure_zhab_signals

    db = SessionLocal()
    try:
        d = (trade_date or "")[:10]
        if not d:
            from sqlalchemy import text

            row = db.execute(text("SELECT MAX(date)::text FROM historical_quotes")).fetchone()
            d = str(row[0])[:10] if row and row[0] else ""
        if not d:
            return {"ok": False, "reason": "no_trade_date"}
        result = ensure_zhab_signals(
            db,
            d,
            sector=sector,
            concept_board_codes=concept_board_codes,
            season=season,
            gates=gates,
            config_id=config_id,
            persist=True,
        )
        return {"ok": True, **result}
    except Exception as e:
        logger.exception("ZHAB precompute failed: %s", e)
        return {"ok": False, "error": str(e)}
    finally:
        db.close()
