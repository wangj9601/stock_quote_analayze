# -*- coding: utf-8 -*-
"""CUPB 信号落库 / 查询。"""

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
    from backend_api.models import CupbSignalTrace

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
            db.query(CupbSignalTrace)
            .filter(
                CupbSignalTrace.code == code,
                CupbSignalTrace.trade_date == d,
                CupbSignalTrace.config_id == int(config_id),
            )
            .first()
        )
        payload = dict(
            name=r.get("name"),
            status=str(r.get("status") or ""),
            left_rim_date=str(r.get("left_rim_date") or "")[:10] or None,
            cup_bottom_date=str(r.get("cup_bottom_date") or "")[:10] or None,
            right_rim_date=str(r.get("right_rim_date") or "")[:10] or None,
            handle_low_date=str(r.get("handle_low_date") or "")[:10] or None,
            left_rim_price=r.get("left_rim_price"),
            cup_bottom_price=r.get("cup_bottom_price"),
            right_rim_price=r.get("right_rim_price"),
            handle_low_price=r.get("handle_low_price"),
            rim=r.get("rim"),
            last_close=r.get("last_close"),
            confirm_date=str(r.get("confirm_date") or "")[:10] or None,
            cup_depth_pct=r.get("cup_depth_pct"),
            handle_retrace_pct=r.get("handle_retrace_pct"),
            board_labels=r.get("board_labels") or None,
            detail={
                **(r.get("detail") or {}),
                "boards": r.get("boards") or [],
                "grade": r.get("grade"),
                "volume_score": r.get("volume_score"),
                "volume_flags": (r.get("detail") or {}).get("volume_flags"),
                "quality_flags": (r.get("detail") or {}).get("quality_flags"),
                "first_confirm_date": r.get("first_confirm_date"),
                "ever_confirmed": r.get("ever_confirmed"),
                "price_adjust": r.get("price_adjust") or "none",
            },
            updated_at=datetime.now(),
        )
        if existing:
            for k, v in payload.items():
                setattr(existing, k, v)
        else:
            db.add(
                CupbSignalTrace(
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
        logger.exception("CUPB upsert_signal_traces failed: %s", e)
        raise
    return n


def _row_to_item(r, trade_date: str) -> Dict[str, Any]:
    detail = r.detail or {}
    return {
        "code": r.code,
        "name": r.name,
        "date": r.trade_date.isoformat() if r.trade_date else trade_date,
        "config_id": r.config_id,
        "status": r.status,
        "left_rim_date": r.left_rim_date,
        "cup_bottom_date": r.cup_bottom_date,
        "right_rim_date": r.right_rim_date,
        "handle_low_date": r.handle_low_date,
        "left_rim_price": r.left_rim_price,
        "cup_bottom_price": r.cup_bottom_price,
        "right_rim_price": r.right_rim_price,
        "handle_low_price": r.handle_low_price,
        "rim": r.rim,
        "last_close": r.last_close,
        "confirm_date": r.confirm_date,
        "first_confirm_date": detail.get("first_confirm_date"),
        "ever_confirmed": bool(detail.get("ever_confirmed")),
        "price_adjust": detail.get("price_adjust") or "none",
        "cup_depth_pct": r.cup_depth_pct,
        "handle_retrace_pct": r.handle_retrace_pct,
        "board_labels": r.board_labels,
        "grade": detail.get("grade"),
        "volume_score": detail.get("volume_score"),
        "detail": detail,
        "boards": detail.get("boards") or [],
        "_from_cache": True,
    }


def load_traces_by_codes(
    db,
    *,
    trade_date: str,
    config_id: int,
    codes: List[str],
    status_filter: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    from backend_api.models import CupbSignalTrace

    if not codes:
        return {}
    d = datetime.strptime(trade_date[:10], "%Y-%m-%d").date()
    norm = []
    seen = set()
    for c in codes:
        s = str(c or "").strip().zfill(6) if str(c or "").strip().isdigit() else str(c or "").strip()
        if s and s not in seen:
            seen.add(s)
            norm.append(s)
    if not norm:
        return {}
    q = db.query(CupbSignalTrace).filter(
        CupbSignalTrace.trade_date == d,
        CupbSignalTrace.config_id == int(config_id),
        CupbSignalTrace.code.in_(norm),
    )
    sf = (status_filter or "").strip().lower()
    if sf in ("forming", "confirmed"):
        q = q.filter(CupbSignalTrace.status == sf)
    out: Dict[str, Dict[str, Any]] = {}
    for r in q.all():
        item = _row_to_item(r, trade_date[:10])
        out[str(r.code)] = item
    return out


def delete_traces_not_in_codes(
    db,
    *,
    trade_date: str,
    config_id: int,
    scope_codes: List[str],
    keep_codes: List[str],
) -> int:
    from backend_api.models import CupbSignalTrace

    if not scope_codes:
        return 0
    d = datetime.strptime(trade_date[:10], "%Y-%m-%d").date()
    scope = {str(c).strip().zfill(6) if str(c).strip().isdigit() else str(c).strip() for c in scope_codes if c}
    keep = {str(c).strip().zfill(6) if str(c).strip().isdigit() else str(c).strip() for c in keep_codes if c}
    stale = [c for c in scope if c and c not in keep]
    if not stale:
        return 0
    deleted = (
        db.query(CupbSignalTrace)
        .filter(
            CupbSignalTrace.trade_date == d,
            CupbSignalTrace.config_id == int(config_id),
            CupbSignalTrace.code.in_(stale),
        )
        .delete(synchronize_session=False)
    )
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("CUPB delete_traces_not_in_codes failed: %s", e)
        raise
    return int(deleted or 0)


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
    from backend_api.models import CupbSignalTrace

    d = datetime.strptime(trade_date[:10], "%Y-%m-%d").date()
    q = db.query(CupbSignalTrace).filter(CupbSignalTrace.trade_date == d)
    if config_id is not None:
        q = q.filter(CupbSignalTrace.config_id == int(config_id))
    if status and status.strip().lower() in ("forming", "confirmed"):
        q = q.filter(CupbSignalTrace.status == status.strip().lower())
    if code:
        q = q.filter(CupbSignalTrace.code == str(code).strip().zfill(6))
    total = q.count()
    from sqlalchemy import case, desc, nulls_last

    status_rank = case((CupbSignalTrace.status == "confirmed", 0), else_=1)
    rows = (
        q.order_by(
            status_rank.asc(),
            nulls_last(desc(CupbSignalTrace.confirm_date)),
            nulls_last(desc(CupbSignalTrace.right_rim_date)),
            CupbSignalTrace.code.asc(),
        )
        .offset(max(0, int(offset)))
        .limit(max(1, int(limit)))
        .all()
    )
    items = [_row_to_item(r, trade_date[:10]) for r in rows]
    try:
        from backend_core.strategies.double_bottom.universe import enrich_items_with_ths_industry

        enrich_items_with_ths_industry(db, items, force=False)
    except Exception:
        pass
    return {"total": total, "items": items}
