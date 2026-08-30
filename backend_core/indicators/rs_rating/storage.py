"""rs_ratings 表 upsert。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import MARKET_TYPE

logger = logging.getLogger(__name__)

UPSERT_SQL = text(
    """
    INSERT INTO rs_ratings (
        code, date, market_type,
        rs_raw, rs_rating,
        roc_63, roc_126, roc_189, roc_252,
        universe_size, coverage_ratio,
        created_at, updated_at
    ) VALUES (
        :code, :date, :market_type,
        :rs_raw, :rs_rating,
        :roc_63, :roc_126, :roc_189, :roc_252,
        :universe_size, :coverage_ratio,
        :now, :now
    )
    ON CONFLICT (code, date, market_type) DO UPDATE SET
        rs_raw = EXCLUDED.rs_raw,
        rs_rating = EXCLUDED.rs_rating,
        roc_63 = EXCLUDED.roc_63,
        roc_126 = EXCLUDED.roc_126,
        roc_189 = EXCLUDED.roc_189,
        roc_252 = EXCLUDED.roc_252,
        universe_size = EXCLUDED.universe_size,
        coverage_ratio = EXCLUDED.coverage_ratio,
        updated_at = EXCLUDED.updated_at
    """
)


def upsert_rs_ratings(
    session: Session,
    rows: Sequence[Dict[str, Any]],
    *,
    trade_date: str,
    market_type: str = MARKET_TYPE,
    batch_size: int = 500,
) -> int:
    if not rows:
        return 0
    now = datetime.now()
    date_s = trade_date[:10]
    saved = 0
    payload: List[Dict[str, Any]] = []
    for r in rows:
        code = str(r.get("code") or "").strip()
        if not code:
            continue
        payload.append(
            {
                "code": code,
                "date": date_s,
                "market_type": market_type,
                "rs_raw": r.get("rs_raw"),
                "rs_rating": r.get("rs_rating"),
                "roc_63": r.get("roc_63"),
                "roc_126": r.get("roc_126"),
                "roc_189": r.get("roc_189"),
                "roc_252": r.get("roc_252"),
                "universe_size": r.get("universe_size"),
                "coverage_ratio": r.get("coverage_ratio"),
                "now": now,
            }
        )
    for i in range(0, len(payload), batch_size):
        chunk = payload[i : i + batch_size]
        for row in chunk:
            session.execute(UPSERT_SQL, row)
        saved += len(chunk)
    session.commit()
    return saved
