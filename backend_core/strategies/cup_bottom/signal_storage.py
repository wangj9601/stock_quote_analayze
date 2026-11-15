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


def latest_signal_trade_date(
    db,
    *,
    config_id: Optional[int] = None,
) -> Optional[str]:
    """返回指定配置（或任意配置）下 cupb_signal_trace 最新有信号的交易日。"""
    from backend_api.models import CupbSignalTrace
    from sqlalchemy import desc

    q = db.query(CupbSignalTrace.trade_date)
    if config_id is not None:
        q = q.filter(CupbSignalTrace.config_id == int(config_id))
    row = q.order_by(desc(CupbSignalTrace.trade_date)).first()
    if not row or row[0] is None:
        return None
    d = row[0]
    return d.isoformat() if hasattr(d, "isoformat") else str(d)[:10]


def _norm_yyyy_mm_dd(raw: Optional[str], field: str) -> str:
    text = str(raw or "").strip()[:10]
    if not text:
        return ""
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(f"{field} 格式应为 YYYY-MM-DD") from e
    return text


def resolve_trace_span(
    *,
    trade_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """单日或闭区间。只给一端时按那一天查，区间长度不设上限。"""
    start = _norm_yyyy_mm_dd(start_date, "start_date")
    end = _norm_yyyy_mm_dd(end_date, "end_date")
    day = _norm_yyyy_mm_dd(trade_date, "trade_date")
    if start or end:
        if not start:
            start = end
        if not end:
            end = start
    elif day:
        start = end = day
    else:
        raise ValueError("请提供交易日或日期区间")
    d0 = datetime.strptime(start, "%Y-%m-%d").date()
    d1 = datetime.strptime(end, "%Y-%m-%d").date()
    if d0 > d1:
        raise ValueError("开始日不能晚于结束日")
    return d0, d1


def resolve_screening_trade_date(
    db,
    *,
    trade_date: Optional[str] = None,
    config_id: Optional[int] = None,
) -> str:
    """选股默认日：显式传入 > 该 config 最新有信号日 > 库内最新 A 股行情日。"""
    if trade_date and str(trade_date).strip():
        return str(trade_date).strip()[:10]
    latest = latest_signal_trade_date(db, config_id=config_id)
    if latest:
        return latest
    from sqlalchemy import text

    row = db.execute(
        text("SELECT MAX(trade_date) FROM historical_quotes")
    ).fetchone()
    if row and row[0] is not None:
        d = row[0]
        return d.isoformat() if hasattr(d, "isoformat") else str(d)[:10]
    raise ValueError("库内无 CUPB 信号且无 A 股行情日")


def load_traces(
    db,
    *,
    trade_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    config_id: Optional[int] = None,
    status: Optional[str] = None,
    code: Optional[str] = None,
    cn_board_segments: Optional[List[str]] = None,
    limit: int = 500,
    offset: int = 0,
    open_span: bool = False,
) -> Dict[str, Any]:
    from backend_api.models import CupbSignalTrace
    from backend_api.utils.cn_listed_board_filter import (
        board_keys_to_code_prefix_or,
        normalize_multi_board_segments,
    )

    code_n = normalize_ashare_code(code) if code and str(code).strip() else ""
    start_s = _norm_yyyy_mm_dd(start_date, "start_date")
    end_s = _norm_yyyy_mm_dd(end_date, "end_date")
    day_s = _norm_yyyy_mm_dd(trade_date, "trade_date")
    all_dates = not (day_s or start_s or end_s)
    if all_dates and not code_n:
        raise ValueError("请提供交易日或日期区间")
    d0 = d1 = None
    q = db.query(CupbSignalTrace)
    if open_span and not all_dates:
        if start_s and end_s:
            d0, d1 = resolve_trace_span(start_date=start_s, end_date=end_s)
        elif start_s:
            d0 = datetime.strptime(start_s, "%Y-%m-%d").date()
        elif end_s:
            d1 = datetime.strptime(end_s, "%Y-%m-%d").date()
        elif day_s:
            d0 = d1 = datetime.strptime(day_s, "%Y-%m-%d").date()
        if d0 is not None:
            q = q.filter(CupbSignalTrace.trade_date >= d0)
        if d1 is not None:
            q = q.filter(CupbSignalTrace.trade_date <= d1)
    elif not all_dates:
        d0, d1 = resolve_trace_span(
            trade_date=trade_date,
            start_date=start_date,
            end_date=end_date,
        )
        q = q.filter(
            CupbSignalTrace.trade_date >= d0,
            CupbSignalTrace.trade_date <= d1,
        )
    if config_id is not None:
        q = q.filter(CupbSignalTrace.config_id == int(config_id))
    if status and status.strip().lower() in ("forming", "confirmed"):
        q = q.filter(CupbSignalTrace.status == status.strip().lower())
    if code_n:
        from sqlalchemy import func, or_

        q = q.filter(
            or_(
                CupbSignalTrace.code == code_n,
                func.right(CupbSignalTrace.code, 6) == code_n,
            )
        )
    board_keys = normalize_multi_board_segments(list(cn_board_segments or []))
    if board_keys:
        crit = board_keys_to_code_prefix_or(CupbSignalTrace.code, board_keys)
        if crit is not None:
            q = q.filter(crit)
    total = q.count()
    from sqlalchemy import case, desc, func, nulls_last

    if all_dates or d0 is None or d1 is None:
        bounds = q.order_by(None).with_entities(
            func.min(CupbSignalTrace.trade_date),
            func.max(CupbSignalTrace.trade_date),
        ).one()
        if bounds and bounds[0] is not None:
            if d0 is None:
                d0 = bounds[0]
            if d1 is None:
                d1 = bounds[1]
    status_rank = case((CupbSignalTrace.status == "confirmed", 0), else_=1)
    order_by = []
    if all_dates or (d0 is not None and d1 is not None and d0 != d1):
        order_by.append(desc(CupbSignalTrace.trade_date))
    order_by.extend(
        [
            status_rank.asc(),
            nulls_last(desc(CupbSignalTrace.confirm_date)),
            nulls_last(desc(CupbSignalTrace.right_rim_date)),
            CupbSignalTrace.code.asc(),
        ]
    )
    rows = (
        q.order_by(*order_by)
        .offset(max(0, int(offset)))
        .limit(max(1, int(limit)))
        .all()
    )
    anchor = d1.isoformat() if d1 is not None and hasattr(d1, "isoformat") else (str(d1)[:10] if d1 else "")
    items = [_row_to_item(r, anchor) for r in rows]
    try:
        from backend_core.strategies.double_bottom.universe import enrich_items_with_ths_industry

        enrich_items_with_ths_industry(db, items, force=False)
    except Exception:
        pass
    return {
        "total": total,
        "items": items,
        "trade_date": d0.isoformat() if d0 is not None and d0 == d1 else None,
        "start_date": d0.isoformat() if d0 is not None else None,
        "end_date": d1.isoformat() if d1 is not None else None,
        "mode": "stock" if all_dates or open_span else "range",
    }


def normalize_ashare_code(raw: str) -> str:
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    if not digits:
        raise ValueError("请提供股票代码")
    if len(digits) > 6:
        digits = digits[-6:]
    return digits.zfill(6)


def stock_history_span(latest, start_date: Optional[str] = None, end_date: Optional[str] = None):
    """个股历史窗口。未给日期时不截断；只给一端时另一端不封顶。"""
    del latest
    start = _norm_yyyy_mm_dd(start_date, "start_date")
    end = _norm_yyyy_mm_dd(end_date, "end_date")
    if not start and not end:
        return None
    start_d = datetime.strptime(start, "%Y-%m-%d").date() if start else None
    end_d = datetime.strptime(end, "%Y-%m-%d").date() if end else None
    if start_d and end_d and start_d > end_d:
        raise ValueError("开始日不能晚于结束日")
    return start_d, end_d


def _latest_trace_meta(db, code: str, config_id: Optional[int]):
    from backend_api.models import CupbSignalTrace
    from sqlalchemy import desc

    q = db.query(CupbSignalTrace.trade_date, CupbSignalTrace.name).filter(
        CupbSignalTrace.code == code
    )
    if config_id is not None:
        q = q.filter(CupbSignalTrace.config_id == int(config_id))
    row = q.order_by(desc(CupbSignalTrace.trade_date)).first()
    if not row:
        return None, ""
    return row[0], str(row[1] or "")


def load_stock_signal_history(
    db,
    *,
    code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    config_id: Optional[int] = None,
    limit: int = 2000,
) -> Dict[str, Any]:
    """一只股票在日期窗口内的杯底信号，只读 cupb_signal_trace。"""
    code_n = normalize_ashare_code(code)
    latest, name = _latest_trace_meta(db, code_n, config_id)
    if not str(start_date or "").strip() and not str(end_date or "").strip():
        payload = load_traces(
            db,
            config_id=config_id,
            code=code_n,
            limit=max(1, int(limit)),
            offset=0,
        )
    else:
        span = stock_history_span(latest, start_date, end_date)
        if span is None:
            return {
                "code": code_n,
                "name": name,
                "config_id": config_id,
                "total": 0,
                "items": [],
                "trade_date": None,
                "start_date": None,
                "end_date": None,
                "mode": "stock",
            }
        d0, d1 = span
        payload = load_traces(
            db,
            start_date=d0.isoformat() if d0 else None,
            end_date=d1.isoformat() if d1 else None,
            config_id=config_id,
            code=code_n,
            limit=max(1, int(limit)),
            offset=0,
            open_span=True,
        )
    if not name:
        for item in payload.get("items") or []:
            if item.get("name"):
                name = str(item["name"])
                break
    payload["code"] = code_n
    payload["name"] = name
    payload["config_id"] = config_id
    return payload
