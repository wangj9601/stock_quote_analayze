# -*- coding: utf-8 -*-
"""KGT 信号落库 / 查询。"""

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
    from backend_api.models import KgtSignalTrace

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
            db.query(KgtSignalTrace)
            .filter(
                KgtSignalTrace.code == code,
                KgtSignalTrace.trade_date == d,
                KgtSignalTrace.config_id == int(config_id),
            )
            .first()
        )
        payload = dict(
            name=r.get("name"),
            direction=str(r.get("direction") or "")[:16] or None,
            status=str(r.get("status") or "hit")[:20] or None,
            score=r.get("score"),
            signal_date=str(r.get("signal_date") or "")[:10] or None,
            open_price=r.get("open"),
            high_price=r.get("high"),
            low_price=r.get("low"),
            close_price=r.get("close"),
            last_close=r.get("last_close"),
            range_pct=r.get("range_pct"),
            body_ratio=r.get("body_ratio"),
            shadow_ratio=r.get("shadow_ratio"),
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
                KgtSignalTrace(
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
        logger.exception("KGT upsert_signal_traces failed: %s", e)
        raise
    return n


def _row_to_item(r, trade_date: str) -> Dict[str, Any]:
    return {
        "code": r.code,
        "name": r.name,
        "date": r.trade_date.isoformat() if r.trade_date else trade_date,
        "config_id": r.config_id,
        "direction": r.direction,
        "status": r.status,
        "score": r.score,
        "signal_date": r.signal_date,
        "open": r.open_price,
        "high": r.high_price,
        "low": r.low_price,
        "close": r.close_price,
        "last_close": r.last_close,
        "range_pct": r.range_pct,
        "body_ratio": r.body_ratio,
        "shadow_ratio": r.shadow_ratio,
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
    direction_filter: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    from backend_api.models import KgtSignalTrace

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
    q = db.query(KgtSignalTrace).filter(
        KgtSignalTrace.trade_date == d,
        KgtSignalTrace.config_id == int(config_id),
        KgtSignalTrace.code.in_(norm),
    )
    df = (direction_filter or "").strip().lower()
    if df in ("bullish", "bearish"):
        q = q.filter(KgtSignalTrace.direction == df)
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
    from backend_api.models import KgtSignalTrace

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
        db.query(KgtSignalTrace)
        .filter(
            KgtSignalTrace.trade_date == d,
            KgtSignalTrace.config_id == int(config_id),
            KgtSignalTrace.code.in_(stale),
        )
        .delete(synchronize_session=False)
    )
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("KGT delete_traces_not_in_codes failed: %s", e)
        raise
    return int(deleted or 0)


def load_traces(
    db,
    *,
    trade_date: str,
    config_id: Optional[int] = None,
    direction: Optional[str] = None,
    code: Optional[str] = None,
    limit: int = 500,
    offset: int = 0,
) -> Dict[str, Any]:
    from sqlalchemy import desc, nulls_last

    from backend_api.models import KgtSignalTrace

    d = datetime.strptime(trade_date[:10], "%Y-%m-%d").date()
    q = db.query(KgtSignalTrace).filter(KgtSignalTrace.trade_date == d)
    if config_id is not None:
        q = q.filter(KgtSignalTrace.config_id == int(config_id))
    if direction and direction.strip().lower() in ("bullish", "bearish"):
        q = q.filter(KgtSignalTrace.direction == direction.strip().lower())
    if code:
        q = q.filter(KgtSignalTrace.code == str(code).strip().zfill(6))
    total = q.count()
    rows = (
        q.order_by(
            nulls_last(desc(KgtSignalTrace.score)),
            KgtSignalTrace.code.asc(),
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
