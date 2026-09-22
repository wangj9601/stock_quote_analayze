# -*- coding: utf-8 -*-
"""ZHAB 信号落库。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def upsert_signal_traces(
    db,
    rows: List[Dict[str, Any]],
    *,
    config_id: int,
    trade_date: str,
) -> int:
    from backend_api.models import ZhabSignalTrace

    n = 0
    date_s = str(trade_date)[:10]
    try:
        d = datetime.strptime(date_s, "%Y-%m-%d").date()
    except ValueError:
        return 0

    for r in rows:
        code = str(r.get("code") or "").strip()
        if not code:
            continue
        existing = (
            db.query(ZhabSignalTrace)
            .filter(
                ZhabSignalTrace.code == code,
                ZhabSignalTrace.trade_date == d,
                ZhabSignalTrace.config_id == int(config_id),
            )
            .first()
        )
        payload = dict(
            name=r.get("name"),
            signal_type=str(r.get("signal_type") or "")[:32] or None,
            setup_ok=bool(r.get("setup_ok")),
            entry_signal=bool(r.get("entry_signal")),
            score=r.get("score"),
            zt_date=str(r.get("zt_date") or "")[:10] or None,
            consol_days=r.get("consol_days"),
            zt_mid=r.get("zt_mid"),
            box_low=r.get("box_low"),
            box_high=r.get("box_high"),
            close_price=r.get("close_price") if r.get("close_price") is not None else r.get("close"),
            detail=r.get("detail") if isinstance(r.get("detail"), dict) else {},
            updated_at=datetime.now(),
        )
        if existing:
            for k, v in payload.items():
                setattr(existing, k, v)
        else:
            db.add(
                ZhabSignalTrace(
                    code=code,
                    trade_date=d,
                    config_id=int(config_id),
                    created_at=datetime.now(),
                    **payload,
                )
            )
        n += 1
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("ZHAB upsert_signal_traces failed: %s", e)
        raise
    return n
