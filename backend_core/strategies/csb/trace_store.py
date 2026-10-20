# -*- coding: utf-8 -*-
"""CSB 信号 trace 读写（csb_signal_trace）。"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from .config import CSB_STOCK_DAY_SCANNED, CSB_TRACE_SCANNED_MARKER
from .json_safe import sanitize_for_pg_json

logger = logging.getLogger(__name__)


def _row_to_dict(r) -> Dict[str, Any]:
    detail = r.detail or {}
    if not isinstance(detail, dict):
        detail = {}
    score_detail = detail.get("score") if isinstance(detail.get("score"), dict) else None
    setup = detail.get("setup") if isinstance(detail.get("setup"), dict) else {}
    channel = setup.get("channel") if isinstance(setup.get("channel"), dict) else {}
    entry = detail.get("entry") if isinstance(detail.get("entry"), dict) else {}
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
        "score_detail": score_detail,
        "close": r.close_price,
        "channel_lower": r.channel_lower,
        "channel_upper": r.channel_upper,
        "squeeze_days": r.squeeze_days,
        "squeeze_pct": channel.get("squeeze_pct"),
        "hh20": channel.get("hh20"),
        "resistance": channel.get("resistance") or entry.get("resistance"),
        "touch_count": setup.get("touch_count"),
        "touch_episodes": setup.get("touch_episodes") or [],
        "entry_low": r.entry_low,
        "vol_expand_mult": entry.get("vol_expand_mult"),
        "vol_ratio_5_20": entry.get("vol_ratio_5_20"),
        "entry_kind": entry.get("entry_kind"),
        "detail": detail,
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


def delete_trace_for_config_in_range(
    db: Session,
    *,
    config_id: int,
    start_date: str,
    end_date: str,
) -> int:
    """只删除指定参数版本在 [start_date, end_date] 内的 trace（含 SCANNED 占位）。"""
    from backend_api.models import CSBSignalTrace

    start_s = str(start_date or "").strip()[:10]
    end_s = str(end_date or "").strip()[:10]
    if not start_s or not end_s:
        raise ValueError("删除区间需同时提供 start_date 与 end_date")
    if start_s > end_s:
        raise ValueError("start_date 不能晚于 end_date")
    n = (
        db.query(CSBSignalTrace)
        .filter(
            CSBSignalTrace.config_id == int(config_id),
            CSBSignalTrace.trade_date >= start_s,
            CSBSignalTrace.trade_date <= end_s,
        )
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
    # full_market 标记优先：即使 candidates 字段缺失/偏小，也视为全市场已扫完
    if scope == "full_market":
        return True
    if not want_pool:
        if scope == "pool":
            return False
        return cand_n is not None and cand_n >= threshold
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
    entry_only: bool = True,
) -> List[Dict[str, Any]]:
    from backend_api.models import CSBSignalTrace

    q = db.query(CSBSignalTrace).filter(
        CSBSignalTrace.trade_date == str(trade_date)[:10],
        CSBSignalTrace.config_id == int(config_id),
        CSBSignalTrace.code != CSB_TRACE_SCANNED_MARKER,
        CSBSignalTrace.signal_type != CSB_STOCK_DAY_SCANNED,
    )
    if entry_only:
        q = q.filter(CSBSignalTrace.entry_signal.is_(True))
    q = q.order_by(CSBSignalTrace.score.desc())
    # 仅入场时按最低分过滤；未勾选时入场行也要保留，不能被最低分丢掉
    if entry_only and min_score is not None:
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
    q = db.query(CSBSignalTrace).filter(
        CSBSignalTrace.code == code_n,
        CSBSignalTrace.signal_type != CSB_STOCK_DAY_SCANNED,
    )
    if config_id is not None:
        q = q.filter(CSBSignalTrace.config_id == int(config_id))
    if start_date:
        q = q.filter(CSBSignalTrace.trade_date >= datetime.strptime(start_date[:10], "%Y-%m-%d").date())
    if end_date:
        q = q.filter(CSBSignalTrace.trade_date <= datetime.strptime(end_date[:10], "%Y-%m-%d").date())
    rows = q.order_by(CSBSignalTrace.trade_date.desc()).limit(int(limit)).all()
    return [_row_to_dict(r) for r in rows]


def codes_present_on_date(
    db: Session,
    *,
    config_id: int,
    trade_date: str,
    codes: List[str],
) -> Set[str]:
    """该日已有任意 trace 行（含无信号占位）的代码。"""
    from backend_api.models import CSBSignalTrace

    norm = [_normalize_code(c) for c in codes if str(c).strip()]
    if not norm:
        return set()
    rows = (
        db.query(CSBSignalTrace.code)
        .filter(
            CSBSignalTrace.config_id == int(config_id),
            CSBSignalTrace.trade_date == str(trade_date)[:10],
            CSBSignalTrace.code.in_(norm),
        )
        .distinct()
        .all()
    )
    return {_normalize_code(r[0]) for r in rows if r and r[0]}


def dates_present_for_code(
    db: Session,
    *,
    config_id: int,
    code: str,
    start_date: str,
    end_date: str,
) -> Set[str]:
    """单股区间内已有任意 trace 行的交易日（含无信号占位）。"""
    from backend_api.models import CSBSignalTrace

    code_n = _normalize_code(code)
    start_d = datetime.strptime(str(start_date)[:10], "%Y-%m-%d").date()
    end_d = datetime.strptime(str(end_date)[:10], "%Y-%m-%d").date()
    rows = (
        db.query(CSBSignalTrace.trade_date)
        .filter(
            CSBSignalTrace.config_id == int(config_id),
            CSBSignalTrace.code == code_n,
            CSBSignalTrace.trade_date >= start_d,
            CSBSignalTrace.trade_date <= end_d,
        )
        .distinct()
        .all()
    )
    return {str(r[0])[:10] for r in rows if r and r[0]}
