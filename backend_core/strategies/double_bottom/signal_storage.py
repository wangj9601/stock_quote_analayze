# -*- coding: utf-8 -*-
"""DBLB 信号落库 / 查询。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def upsert_signal_traces(
    db,
    rows: List[Dict[str, Any]],
    *,
    config_id: int,
    trade_date: str,
) -> int:
    from backend_api.models import DblbSignalTrace

    n = 0
    for r in rows:
        code = str(r.get("code") or "").strip()
        if not code:
            continue
        date_s = str(r.get("date") or trade_date)[:10]
        try:
            d = datetime.strptime(date_s, "%Y-%m-%d").date()
        except ValueError:
            continue
        existing = (
            db.query(DblbSignalTrace)
            .filter(
                DblbSignalTrace.code == code,
                DblbSignalTrace.trade_date == d,
                DblbSignalTrace.config_id == int(config_id),
            )
            .first()
        )
        payload = dict(
            name=r.get("name"),
            status=str(r.get("status") or ""),
            l1_date=str(r.get("l1_date") or "")[:10] or None,
            l2_date=str(r.get("l2_date") or "")[:10] or None,
            l1_price=r.get("l1_price"),
            l2_price=r.get("l2_price"),
            neckline=r.get("neckline"),
            neck_date=str(r.get("neck_date") or "")[:10] or None,
            last_close=r.get("last_close"),
            confirm_date=str(r.get("confirm_date") or "")[:10] or None,
            board_labels=r.get("board_labels") or None,
            detail={
                **(r.get("detail") or {}),
                "boards": r.get("boards") or [],
            },
            updated_at=datetime.now(),
        )
        if existing:
            for k, v in payload.items():
                setattr(existing, k, v)
        else:
            db.add(
                DblbSignalTrace(
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
        logger.exception("DBLB upsert_signal_traces failed: %s", e)
        raise
    return n


def load_traces(
    db,
    *,
    trade_date: str,
    config_id: Optional[int] = None,
    status: Optional[str] = None,
    code: Optional[str] = None,
    limit: int = 500,
    offset: int = 0,
) -> Dict[str, Any]:
    from backend_api.models import DblbSignalTrace

    d = datetime.strptime(trade_date[:10], "%Y-%m-%d").date()
    q = db.query(DblbSignalTrace).filter(DblbSignalTrace.trade_date == d)
    if config_id is not None:
        q = q.filter(DblbSignalTrace.config_id == int(config_id))
    if status and status.strip().lower() in ("forming", "confirmed"):
        q = q.filter(DblbSignalTrace.status == status.strip().lower())
    if code:
        q = q.filter(DblbSignalTrace.code == str(code).strip().zfill(6))
    total = q.count()
    rows = (
        q.order_by(
            DblbSignalTrace.status.asc(),
            DblbSignalTrace.code.asc(),
        )
        .offset(max(0, int(offset)))
        .limit(max(1, int(limit)))
        .all()
    )
    items = []
    for r in rows:
        items.append(
            {
                "code": r.code,
                "name": r.name,
                "date": r.trade_date.isoformat() if r.trade_date else trade_date,
                "config_id": r.config_id,
                "status": r.status,
                "l1_date": r.l1_date,
                "l2_date": r.l2_date,
                "l1_price": r.l1_price,
                "l2_price": r.l2_price,
                "neckline": r.neckline,
                "neck_date": r.neck_date,
                "last_close": r.last_close,
                "confirm_date": r.confirm_date,
                "board_labels": r.board_labels,
                "detail": r.detail or {},
            }
        )
    return {"total": total, "items": items}
