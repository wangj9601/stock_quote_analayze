# -*- coding: utf-8 -*-
"""CSB 信号 trace 读写（csb_signal_trace）。"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from .config import CSB_TRACE_SCANNED_MARKER
from .json_safe import sanitize_for_pg_json

logger = logging.getLogger(__name__)


def _row_to_dict(r) -> Dict[str, Any]:
    return {
        "code": r.code,
        "name": r.name,
        "trade_date": r.trade_date.isoformat() if r.trade_date else None,
        "signal_date": r.trade_date.isoformat() if r.trade_date else None,
        "date": r.trade_date.isoformat() if r.trade_date else None,
        "config_id": r.config_id,
        "signal_type": r.signal_type,
        "setup_ok": r.setup_ok,
        "entry_signal": r.entry_signal,
        "buy_signal": bool(r.entry_signal),
        "score": r.score,
        "close": r.close_price,
        "channel_lower": r.channel_lower,
        "channel_upper": r.channel_upper,
        "squeeze_days": r.squeeze_days,
        "entry_low": r.entry_low,
        "detail": r.detail or {},
        "from_cache": True,
    }


def _normalize_code(code: str) -> str:
    s = str(code or "").strip()
    if s.isdigit() and len(s) <= 6:
        return s.zfill(6)
    return s


def upsert_trace_rows(db: Session, *, config_id: int, rows: List[Dict[str, Any]]) -> int:
    from backend_api.models import CSBSignalTrace

    n = 0
    now = datetime.now()
    for r in rows:
        code = str(r.get("code") or "").strip()
        date_s = str(r.get("signal_date") or r.get("trade_date") or r.get("date") or "")[:10]
        sig_type = str(r.get("signal_type") or "")
        if not code or not date_s:
            continue
        try:
            d = datetime.strptime(date_s, "%Y-%m-%d").date()
        except ValueError:
            continue
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
        fields = dict(
            name=r.get("name"),
            setup_ok=bool(r.get("setup_ok")),
            entry_signal=bool(r.get("entry_signal")),
            score=r.get("score"),
            close_price=r.get("close"),
            channel_lower=r.get("channel_lower"),
            channel_upper=r.get("channel_upper"),
            squeeze_days=r.get("squeeze_days"),
            entry_low=r.get("entry_low"),
            detail=sanitize_for_pg_json(r.get("detail")),
            updated_at=now,
        )
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
        else:
            db.add(
                CSBSignalTrace(
                    code=code,
                    trade_date=d,
                    config_id=int(config_id),
                    signal_type=sig_type,
                    created_at=now,
                    **fields,
                )
            )
        n += 1
        if n % 200 == 0:
            db.commit()
    db.commit()
    return n


def delete_trace_for_config(db: Session, *, config_id: int) -> int:
    from backend_api.models import CSBSignalTrace

    n = (
        db.query(CSBSignalTrace)
        .filter(CSBSignalTrace.config_id == int(config_id))
        .delete(synchronize_session=False)
    )
    db.commit()
    return int(n or 0)


def mark_date_scanned(
    db: Session,
    *,
    config_id: int,
    trade_date: str,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    detail = {"marker": "universe_scanned"}
    if extra:
        detail.update(extra)
    upsert_trace_rows(
        db,
        config_id=int(config_id),
        rows=[
            {
                "code": CSB_TRACE_SCANNED_MARKER,
                "name": "",
                "signal_date": str(trade_date)[:10],
                "signal_type": "SCANNED",
                "setup_ok": False,
                "entry_signal": False,
                "score": 0,
                "detail": detail,
            }
        ],
    )


def marker_covers_universe_request(
    extra: Optional[Dict[str, Any]],
    *,
    want_pool: bool,
    pool_need: int = 1,
    min_full_market_codes: int = 500,
) -> bool:
    extra = extra if isinstance(extra, dict) else {}
    scope = str(extra.get("scope") or "").strip().lower()
    try:
        cand_n = int(extra.get("candidates")) if extra.get("candidates") is not None else None
    except (TypeError, ValueError):
        cand_n = None
    threshold = max(1, int(min_full_market_codes))
    if not want_pool:
        if scope == "pool":
            return False
        if cand_n is not None and cand_n < threshold:
            return False
        return scope == "full_market" or (cand_n is not None and cand_n >= threshold)
    if scope == "full_market":
        return True
    if scope == "pool":
        return cand_n is not None and cand_n >= max(1, int(pool_need))
    return False


def dates_ready_for_universe_backtest(
    db: Session,
    *,
    config_id: int,
    dates: List[str],
    stock_pool: Optional[List[str]] = None,
    min_full_market_codes: Optional[int] = None,
) -> Set[str]:
    from sqlalchemy import func

    from backend_api.models import CSBSignalTrace

    if not dates:
        return set()
    date_list = [str(d)[:10] for d in dates]
    cid = int(config_id)
    if min_full_market_codes is None:
        env_raw = (os.getenv("CSB_FULL_MARKET_TRACE_MIN_CODES") or "").strip()
        min_full_market_codes = int(env_raw) if env_raw.isdigit() else 500
    threshold = max(1, int(min_full_market_codes))
    want_pool = bool(stock_pool)
    pool_need = 1
    if want_pool:
        pool_n = len({_normalize_code(c) for c in stock_pool if str(c).strip()})
        pool_need = max(1, int((pool_n * 4 + 4) // 5))

    marker_rows = (
        db.query(CSBSignalTrace.trade_date, CSBSignalTrace.detail)
        .filter(
            CSBSignalTrace.config_id == cid,
            CSBSignalTrace.code == CSB_TRACE_SCANNED_MARKER,
        )
        .all()
    )
    ready: Set[str] = set()
    marker_dates = {str(r[0])[:10] if r[0] else "" for r in marker_rows}
    for r in marker_rows:
        d = str(r[0])[:10] if r[0] else ""
        if d not in date_list:
            continue
        if marker_covers_universe_request(
            r[1] if isinstance(r[1], dict) else {},
            want_pool=want_pool,
            pool_need=pool_need,
            min_full_market_codes=threshold,
        ):
            ready.add(d)

    pending = [d for d in date_list if d not in ready]
    if not pending:
        return ready

    cnt_rows = (
        db.query(CSBSignalTrace.trade_date, func.count(func.distinct(CSBSignalTrace.code)))
        .filter(
            CSBSignalTrace.config_id == cid,
            CSBSignalTrace.trade_date.in_(pending),
            CSBSignalTrace.code != CSB_TRACE_SCANNED_MARKER,
        )
        .group_by(CSBSignalTrace.trade_date)
        .all()
    )
    if stock_pool:
        pool_set = {_normalize_code(c) for c in stock_pool if str(c).strip()}
        need = max(1, int((len(pool_set) * 4 + 4) // 5))
        if len(pool_set) <= 2000:
            pool_cnt = (
                db.query(CSBSignalTrace.trade_date, func.count(func.distinct(CSBSignalTrace.code)))
                .filter(
                    CSBSignalTrace.config_id == cid,
                    CSBSignalTrace.trade_date.in_(pending),
                    CSBSignalTrace.code.in_(list(pool_set)),
                )
                .group_by(CSBSignalTrace.trade_date)
                .all()
            )
            for r in pool_cnt:
                d = str(r[0])[:10]
                if int(r[1] or 0) >= need:
                    ready.add(d)
    else:
        for r in cnt_rows:
            d = str(r[0])[:10]
            if int(r[1] or 0) >= threshold:
                ready.add(d)
    return ready


def query_buy_signals_for_date(
    db: Session,
    *,
    trade_date: str,
    config_id: int,
    min_score: Optional[float] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    from backend_api.models import CSBSignalTrace

    q = (
        db.query(CSBSignalTrace)
        .filter(
            CSBSignalTrace.trade_date == str(trade_date)[:10],
            CSBSignalTrace.config_id == int(config_id),
            CSBSignalTrace.entry_signal.is_(True),
            CSBSignalTrace.code != CSB_TRACE_SCANNED_MARKER,
        )
        .order_by(CSBSignalTrace.score.desc())
    )
    if min_score is not None:
        q = q.filter(CSBSignalTrace.score >= float(min_score))
    if limit:
        q = q.limit(int(limit))
    return [_row_to_dict(r) for r in q.all()]


def query_trace_by_code(
    db: Session,
    *,
    code: str,
    config_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    from backend_api.models import CSBSignalTrace

    code_n = _normalize_code(code)
    q = db.query(CSBSignalTrace).filter(CSBSignalTrace.code == code_n)
    if config_id is not None:
        q = q.filter(CSBSignalTrace.config_id == int(config_id))
    if start_date:
        q = q.filter(CSBSignalTrace.trade_date >= datetime.strptime(start_date[:10], "%Y-%m-%d").date())
    if end_date:
        q = q.filter(CSBSignalTrace.trade_date <= datetime.strptime(end_date[:10], "%Y-%m-%d").date())
    rows = q.order_by(CSBSignalTrace.trade_date.desc()).limit(int(limit)).all()
    return [_row_to_dict(r) for r in rows]
