# -*- coding: utf-8 -*-
"""CSB 信号落库（csb_signal_trace）。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .config import CSB_TRACE_SCANNED_MARKER
from .json_safe import sanitize_for_pg_json
from .trace_store import _row_to_dict

logger = logging.getLogger(__name__)


def upsert_signal_traces(
    db,
    rows: List[Dict[str, Any]],
    *,
    config_id: int,
    trade_date: Optional[str] = None,
) -> int:
    from backend_api.models import CSBSignalTrace

    n = 0
    for r in rows:
        code = str(r.get("code") or "").strip()
        if not code:
            continue
        date_s = str(r.get("trade_date") or r.get("signal_date") or r.get("date") or trade_date)[:10]
        try:
            d = datetime.strptime(date_s, "%Y-%m-%d").date()
        except ValueError:
            continue

        sig_type = str(r.get("signal_type") or "")
        existing = (
            db.query(CSBSignalTrace)
            .filter(
                CSBSignalTrace.code == code,
                CSBSignalTrace.trade_date == d,
                CSBSignalTrace.config_id == int(config_id),
                CSBSignalTrace.signal_type == sig_type,
            )
            .first()
        )
        payload = dict(
            name=r.get("name"),
            setup_ok=bool(r.get("setup_ok")),
            entry_signal=bool(r.get("entry_signal")),
            score=r.get("score"),
            close_price=r.get("close"),
            channel_lower=r.get("channel_lower"),
            channel_upper=r.get("channel_upper"),
            squeeze_days=r.get("squeeze_days"),
            entry_low=r.get("entry_low"),
            detail=sanitize_for_pg_json(r.get("detail") or {}),
            updated_at=datetime.now(),
        )
        if existing:
            for k, v in payload.items():
                setattr(existing, k, v)
        else:
            db.add(
                CSBSignalTrace(
                    code=code,
                    trade_date=d,
                    config_id=int(config_id),
                    signal_type=sig_type,
                    created_at=datetime.now(),
                    **payload,
                )
            )
        n += 1
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("CSB upsert_signal_traces failed: %s", e)
        raise
    return n


def load_traces(
    db,
    *,
    trade_date: str,
    config_id: int,
    entry_only: bool = False,
    signal_type: Optional[str] = None,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    from backend_api.models import CSBSignalTrace

    d = datetime.strptime(trade_date[:10], "%Y-%m-%d").date()
    q = db.query(CSBSignalTrace).filter(
        CSBSignalTrace.trade_date == d,
        CSBSignalTrace.config_id == int(config_id),
        CSBSignalTrace.code != CSB_TRACE_SCANNED_MARKER,
    )
    if entry_only:
        q = q.filter(CSBSignalTrace.entry_signal.is_(True))
    if signal_type:
        q = q.filter(CSBSignalTrace.signal_type == signal_type)
    rows = q.order_by(CSBSignalTrace.score.desc(), CSBSignalTrace.code.asc()).limit(limit).all()
    return [_row_to_dict(r) for r in rows]
