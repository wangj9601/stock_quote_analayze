# -*- coding: utf-8 -*-
"""BVF 信号落库 / 查询。"""

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
    from backend_api.models import BvfSignalTrace

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
            db.query(BvfSignalTrace)
            .filter(
                BvfSignalTrace.code == code,
                BvfSignalTrace.trade_date == d,
                BvfSignalTrace.config_id == int(config_id),
            )
            .first()
        )
        payload = dict(
            name=r.get("name"),
            status=str(r.get("status") or "hit")[:20] or None,
            left_date=str(r.get("left_date") or "")[:10] or None,
            mid_date=str(r.get("mid_date") or "")[:10] or None,
            right_date=str(r.get("right_date") or "")[:10] or None,
            mid_low=r.get("mid_low"),
            min_low=r.get("min_low"),
            bottom_dev_pct=r.get("bottom_dev_pct"),
            vol_ratio_actual=r.get("vol_ratio_actual"),
            mid_volume=r.get("mid_volume"),
            last_close=r.get("last_close"),
            limit_flag=str(r.get("limit_flag") or "")[:20] or None,
            price_adjust=str(r.get("price_adjust") or "")[:16] or None,
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
                BvfSignalTrace(
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
        logger.exception("BVF upsert_signal_traces failed: %s", e)
        raise
    return n


def _row_to_item(r, trade_date: str) -> Dict[str, Any]:
    return {
        "code": r.code,
        "name": r.name,
        "date": r.trade_date.isoformat() if r.trade_date else trade_date,
        "config_id": r.config_id,
        "status": r.status,
        "left_date": r.left_date,
        "mid_date": r.mid_date,
        "right_date": r.right_date,
        "mid_low": r.mid_low,
        "min_low": r.min_low,
        "bottom_dev_pct": r.bottom_dev_pct,
        "vol_ratio_actual": r.vol_ratio_actual,
        "mid_volume": r.mid_volume,
        "last_close": r.last_close,
        "limit_flag": r.limit_flag,
        "price_adjust": r.price_adjust,
        "board_labels": r.board_labels,
        "detail": r.detail or {},
        "boards": (r.detail or {}).get("boards") or [],
        "_from_cache": True,
    }


def load_traces_by_codes(
    db,
    *,
    trade_date: str,
    config_id: int,
    codes: List[str],
) -> Dict[str, Dict[str, Any]]:
    from backend_api.models import BvfSignalTrace

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
    q = db.query(BvfSignalTrace).filter(
        BvfSignalTrace.trade_date == d,
        BvfSignalTrace.config_id == int(config_id),
        BvfSignalTrace.code.in_(norm),
    )
    out: Dict[str, Dict[str, Any]] = {}
    for r in q.all():
        out[str(r.code)] = _row_to_item(r, trade_date[:10])
    return out


def delete_traces_not_in_codes(
    db,
    *,
    trade_date: str,
    config_id: int,
    scope_codes: List[str],
    keep_codes: List[str],
) -> int:
    from backend_api.models import BvfSignalTrace

    if not scope_codes:
        return 0
    d = datetime.strptime(trade_date[:10], "%Y-%m-%d").date()
    scope = {
        str(c).strip().zfill(6) if str(c).strip().isdigit() else str(c).strip()
        for c in scope_codes
        if c
    }
    keep = {
        str(c).strip().zfill(6) if str(c).strip().isdigit() else str(c).strip()
        for c in keep_codes
        if c
    }
    stale = [c for c in scope if c and c not in keep]
    if not stale:
        return 0
    deleted = (
        db.query(BvfSignalTrace)
        .filter(
            BvfSignalTrace.trade_date == d,
            BvfSignalTrace.config_id == int(config_id),
            BvfSignalTrace.code.in_(stale),
        )
        .delete(synchronize_session=False)
    )
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("BVF delete_traces_not_in_codes failed: %s", e)
        raise
    return int(deleted or 0)


def load_traces(
    db,
    *,
    trade_date: str,
    config_id: Optional[int] = None,
    code: Optional[str] = None,
    limit: int = 500,
    offset: int = 0,
) -> Dict[str, Any]:
    from sqlalchemy import desc, nulls_last

    from backend_api.models import BvfSignalTrace

    d = datetime.strptime(trade_date[:10], "%Y-%m-%d").date()
    q = db.query(BvfSignalTrace).filter(BvfSignalTrace.trade_date == d)
    if config_id is not None:
        q = q.filter(BvfSignalTrace.config_id == int(config_id))
    if code:
        q = q.filter(BvfSignalTrace.code == str(code).strip().zfill(6))
    total = q.count()
    rows = (
        q.order_by(
            nulls_last(desc(BvfSignalTrace.vol_ratio_actual)),
            BvfSignalTrace.code.asc(),
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
