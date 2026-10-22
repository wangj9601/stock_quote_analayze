# -*- coding: utf-8 -*-
"""LDS 信号落库 / 查询。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _norm_board(v: Any) -> str:
    return str(v or "").strip()


def upsert_signal_traces(
    db,
    rows: List[Dict[str, Any]],
    *,
    config_id: int,
    trade_date: str,
) -> int:
    from backend_api.models import LdsSignalTrace

    n = 0
    for r in rows:
        code = str(r.get("code") or "").strip()
        if not code:
            continue
        date_s = str(r.get("date") or r.get("trade_date") or trade_date)[:10]
        try:
            d = datetime.strptime(date_s, "%Y-%m-%d").date()
        except ValueError:
            continue
        role = str(r.get("role") or "board_leader")[:32]
        board_code = _norm_board(r.get("board_code"))
        existing = (
            db.query(LdsSignalTrace)
            .filter(
                LdsSignalTrace.code == code,
                LdsSignalTrace.trade_date == d,
                LdsSignalTrace.config_id == int(config_id),
                LdsSignalTrace.role == role,
                LdsSignalTrace.board_code == board_code,
            )
            .first()
        )
        payload = dict(
            name=r.get("name"),
            status=str(r.get("status") or "hit")[:20] or None,
            board_name=str(r.get("board_name") or "")[:200] or None,
            identity_score=r.get("identity_score"),
            drive_score=r.get("drive_score"),
            watch_ready=bool(r.get("watch_ready")),
            is_lonely=bool(r.get("is_lonely")),
            is_primary=bool(r.get("is_primary", True)),
            same_as_height=bool(r.get("same_as_height")),
            board_count=r.get("board_count"),
            identity_reasons=r.get("identity_reasons") or [],
            watch_reasons=r.get("watch_reasons") or [],
            detail=r.get("detail") or {},
            updated_at=datetime.now(),
        )
        if existing:
            for k, v in payload.items():
                setattr(existing, k, v)
        else:
            db.add(
                LdsSignalTrace(
                    code=code,
                    trade_date=d,
                    config_id=int(config_id),
                    role=role,
                    board_code=board_code,
                    created_at=datetime.now(),
                    **payload,
                )
            )
        n += 1
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("LDS upsert_signal_traces failed: %s", e)
        raise
    return n


def _row_to_item(r, trade_date: str) -> Dict[str, Any]:
    return {
        "code": r.code,
        "name": r.name,
        "date": r.trade_date.isoformat() if r.trade_date else trade_date,
        "trade_date": r.trade_date.isoformat() if r.trade_date else trade_date,
        "config_id": r.config_id,
        "status": r.status,
        "role": r.role,
        "board_code": r.board_code or "",
        "board_name": r.board_name,
        "identity_score": r.identity_score,
        "drive_score": r.drive_score,
        "watch_ready": bool(r.watch_ready),
        "is_lonely": bool(r.is_lonely),
        "is_primary": bool(r.is_primary),
        "same_as_height": bool(r.same_as_height),
        "board_count": r.board_count,
        "identity_reasons": r.identity_reasons or [],
        "watch_reasons": r.watch_reasons or [],
        "detail": r.detail or {},
        "_from_cache": True,
    }


def load_traces(
    db,
    *,
    trade_date: str,
    config_id: Optional[int] = None,
    code: Optional[str] = None,
    role: Optional[str] = None,
    watch_ready: Optional[bool] = None,
    limit: int = 500,
    offset: int = 0,
) -> Dict[str, Any]:
    from sqlalchemy import desc, nulls_last

    from backend_api.models import LdsSignalTrace

    d = datetime.strptime(trade_date[:10], "%Y-%m-%d").date()
    q = db.query(LdsSignalTrace).filter(LdsSignalTrace.trade_date == d)
    if config_id is not None:
        q = q.filter(LdsSignalTrace.config_id == int(config_id))
    if code:
        q = q.filter(LdsSignalTrace.code == str(code).strip().zfill(6))
    if role:
        q = q.filter(LdsSignalTrace.role == str(role))
    if watch_ready is not None:
        q = q.filter(LdsSignalTrace.watch_ready.is_(bool(watch_ready)))
    total = q.count()
    rows = (
        q.order_by(
            nulls_last(desc(LdsSignalTrace.identity_score)),
            LdsSignalTrace.code.asc(),
        )
        .offset(max(0, int(offset)))
        .limit(max(1, int(limit)))
        .all()
    )
    return {"total": total, "items": [_row_to_item(r, trade_date[:10]) for r in rows]}


def delete_traces_for_date(
    db,
    *,
    trade_date: str,
    config_id: int,
) -> int:
    from backend_api.models import LdsSignalTrace

    d = datetime.strptime(trade_date[:10], "%Y-%m-%d").date()
    deleted = (
        db.query(LdsSignalTrace)
        .filter(
            LdsSignalTrace.trade_date == d,
            LdsSignalTrace.config_id == int(config_id),
        )
        .delete(synchronize_session=False)
    )
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("LDS delete_traces_for_date failed: %s", e)
        raise
    return int(deleted or 0)
