# -*- coding: utf-8 -*-
"""集合竞价落库。"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

FUYAO_SOURCE = "fuyao"


def _norm_code(raw: Any) -> str:
    s = str(raw or "").strip().upper()
    if "." in s:
        s = s.split(".", 1)[0]
    for prefix in ("SH", "SZ", "BJ"):
        if s.startswith(prefix) and s[len(prefix) :].isdigit():
            s = s[len(prefix) :]
            break
    digits = "".join(ch for ch in s if ch.isdigit())
    if not digits:
        return s
    return digits.zfill(6) if len(digits) <= 6 else digits[-6:]


def persist_auction_items(
    trade_date: str,
    auction_phase: str,
    items: List[Dict[str, Any]],
    *,
    data_status: Optional[str] = None,
    response_timestamp: Optional[int] = None,
    db: Optional[Session] = None,
) -> int:
    """Upsert 集合竞价快照。返回写入条数。"""
    day = str(trade_date or "").strip()[:10]
    phase = (auction_phase or "final").strip().lower()
    if not day or not items:
        return 0

    own_session = db is None
    if own_session:
        from backend_api.database import SessionLocal

        db = SessionLocal()
    assert db is not None

    stmt = text(
        """
        INSERT INTO stock_auction_daily (
            trade_date, code, auction_phase, thscode, name, data_status,
            auction_price, auction_pct, auction_volume, auction_volume_shares,
            auction_amount, auction_unmatched, auction_unmatched_shares,
            auction_turnover_pct, auction_yesterday_ratio_pct, auction_volume_ratio,
            pre_close_price, open_price, last_price, float_market_cap,
            source, response_timestamp, updated_at
        ) VALUES (
            :trade_date, :code, :auction_phase, :thscode, :name, :data_status,
            :auction_price, :auction_pct, :auction_volume, :auction_volume_shares,
            :auction_amount, :auction_unmatched, :auction_unmatched_shares,
            :auction_turnover_pct, :auction_yesterday_ratio_pct, :auction_volume_ratio,
            :pre_close_price, :open_price, :last_price, :float_market_cap,
            :source, :response_timestamp, CURRENT_TIMESTAMP
        )
        ON CONFLICT (trade_date, code, auction_phase) DO UPDATE SET
            thscode = EXCLUDED.thscode,
            name = EXCLUDED.name,
            data_status = EXCLUDED.data_status,
            auction_price = EXCLUDED.auction_price,
            auction_pct = EXCLUDED.auction_pct,
            auction_volume = EXCLUDED.auction_volume,
            auction_volume_shares = EXCLUDED.auction_volume_shares,
            auction_amount = EXCLUDED.auction_amount,
            auction_unmatched = EXCLUDED.auction_unmatched,
            auction_unmatched_shares = EXCLUDED.auction_unmatched_shares,
            auction_turnover_pct = EXCLUDED.auction_turnover_pct,
            auction_yesterday_ratio_pct = EXCLUDED.auction_yesterday_ratio_pct,
            auction_volume_ratio = EXCLUDED.auction_volume_ratio,
            pre_close_price = EXCLUDED.pre_close_price,
            open_price = EXCLUDED.open_price,
            last_price = EXCLUDED.last_price,
            float_market_cap = EXCLUDED.float_market_cap,
            source = EXCLUDED.source,
            response_timestamp = EXCLUDED.response_timestamp,
            updated_at = CURRENT_TIMESTAMP
        """
    )

    saved = 0
    try:
        for row in items:
            code = _norm_code(row.get("code") or row.get("ticker"))
            if not code:
                continue
            db.execute(
                stmt,
                {
                    "trade_date": day,
                    "code": code,
                    "auction_phase": phase,
                    "thscode": row.get("thscode"),
                    "name": row.get("name"),
                    "data_status": data_status or row.get("data_status"),
                    "auction_price": row.get("auction_price"),
                    "auction_pct": row.get("auction_pct"),
                    "auction_volume": row.get("auction_volume"),
                    "auction_volume_shares": row.get("auction_volume_shares"),
                    "auction_amount": row.get("auction_amount"),
                    "auction_unmatched": row.get("auction_unmatched"),
                    "auction_unmatched_shares": row.get("auction_unmatched_shares"),
                    "auction_turnover_pct": row.get("auction_turnover_pct"),
                    "auction_yesterday_ratio_pct": row.get("auction_yesterday_ratio_pct"),
                    "auction_volume_ratio": row.get("auction_volume_ratio"),
                    "pre_close_price": row.get("pre_close_price"),
                    "open_price": row.get("open_price"),
                    "last_price": row.get("last_price"),
                    "float_market_cap": row.get("float_market_cap"),
                    "source": row.get("source") or FUYAO_SOURCE,
                    "response_timestamp": response_timestamp,
                },
            )
            saved += 1
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("集合竞价落库失败 trade_date=%s phase=%s", day, phase)
        raise
    finally:
        if own_session:
            db.close()
    return saved


def persist_auction_benchmark(
    trade_date: str,
    items: List[Dict[str, Any]],
    *,
    response_timestamp: Optional[int] = None,
    db: Optional[Session] = None,
) -> int:
    day = str(trade_date or "").strip()[:10]
    if not day or not items:
        return 0

    own_session = db is None
    if own_session:
        from backend_api.database import SessionLocal

        db = SessionLocal()
    assert db is not None

    try:
        db.execute(
            text("DELETE FROM stock_auction_benchmark WHERE trade_date = :trade_date"),
            {"trade_date": day},
        )
        stmt = text(
            """
            INSERT INTO stock_auction_benchmark (
                trade_date, seq, thscode, code, name, auction_pct, tags,
                source, response_timestamp, updated_at
            ) VALUES (
                :trade_date, :seq, :thscode, :code, :name, :auction_pct, CAST(:tags AS JSONB),
                :source, :response_timestamp, CURRENT_TIMESTAMP
            )
            """
        )
        saved = 0
        for seq, row in enumerate(items, 1):
            tags = row.get("tags")
            if tags is not None and not isinstance(tags, str):
                tags = json.dumps(tags, ensure_ascii=False)
            db.execute(
                stmt,
                {
                    "trade_date": day,
                    "seq": seq,
                    "thscode": row.get("thscode"),
                    "code": _norm_code(row.get("code") or row.get("ticker")),
                    "name": row.get("name"),
                    "auction_pct": row.get("auction_pct"),
                    "tags": tags,
                    "source": row.get("source") or FUYAO_SOURCE,
                    "response_timestamp": response_timestamp,
                },
            )
            saved += 1
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("集合竞价基准落库失败 trade_date=%s", day)
        raise
    finally:
        if own_session:
            db.close()
    return saved
