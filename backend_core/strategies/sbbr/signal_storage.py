"""SBBR 信号落库。"""

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
    from backend_api.models import SBBRSignalTrace

    n = 0
    for r in rows:
        code = str(r.get("code") or r.get("symbol") or "").strip()
        if not code:
            continue
        date_s = str(r.get("date") or trade_date)[:10]
        try:
            d = datetime.strptime(date_s, "%Y-%m-%d").date()
        except ValueError:
            continue

        existing = (
            db.query(SBBRSignalTrace)
            .filter(
                SBBRSignalTrace.code == code,
                SBBRSignalTrace.trade_date == d,
                SBBRSignalTrace.config_id == int(config_id),
            )
            .first()
        )
        payload = dict(
            name=r.get("name"),
            market_type=r.get("market_type") or "CN",
            total_mv=r.get("total_mv"),
            circ_mv=r.get("circ_mv"),
            size_ok=r.get("size_ok"),
            bottom_mode=r.get("bottom_mode"),
            bottom_matched=bool(r.get("bottom_matched")),
            entry_signal=bool(r.get("entry_signal")),
            entry_low=r.get("entry_low"),
            defense_low=r.get("defense_low"),
            defense_high=r.get("defense_high"),
            defense_buffer_pct=r.get("defense_buffer_pct"),
            close_price=r.get("close"),
            ma20=r.get("ma20"),
            volume_ratio=r.get("volume_ratio"),
            exit_flags=r.get("exit_flags") or {},
            position_advice=r.get("position_advice") or {},
            detail={
                **(r.get("detail") or {}),
                **(
                    {"circ_shares_yi": r.get("circ_shares_yi")}
                    if r.get("circ_shares_yi") is not None
                    else {}
                ),
            },
            updated_at=datetime.now(),
        )
        if existing:
            for k, v in payload.items():
                setattr(existing, k, v)
        else:
            db.add(
                SBBRSignalTrace(
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
        logger.exception("SBBR upsert_signal_traces failed: %s", e)
        raise
    return n


def load_traces(
    db,
    *,
    trade_date: str,
    config_id: int,
    entry_only: bool = False,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    from backend_api.models import SBBRSignalTrace

    d = datetime.strptime(trade_date[:10], "%Y-%m-%d").date()
    q = db.query(SBBRSignalTrace).filter(
        SBBRSignalTrace.trade_date == d,
        SBBRSignalTrace.config_id == int(config_id),
    )
    if entry_only:
        q = q.filter(SBBRSignalTrace.entry_signal.is_(True))
    rows = q.order_by(SBBRSignalTrace.entry_signal.desc(), SBBRSignalTrace.code.asc()).limit(limit).all()
    out = []
    for r in rows:
        detail = r.detail or {}
        structure = detail.get("structure") if isinstance(detail.get("structure"), dict) else {}
        out.append(
            {
                "code": r.code,
                "symbol": r.code,
                "name": r.name,
                "date": r.trade_date.isoformat() if r.trade_date else trade_date,
                "market_type": r.market_type,
                "total_mv": r.total_mv,
                "circ_mv": r.circ_mv,
                "circ_shares_yi": detail.get("circ_shares_yi"),
                "size_ok": r.size_ok,
                "bottom_mode": r.bottom_mode,
                "bottom_matched": r.bottom_matched,
                "entry_signal": r.entry_signal,
                "entry_low": r.entry_low,
                "defense_low": r.defense_low,
                "defense_high": r.defense_high,
                "defense_buffer_pct": r.defense_buffer_pct,
                "close": r.close_price,
                "ma20": r.ma20,
                "volume_ratio": r.volume_ratio,
                "box_support": detail.get("support"),
                "box_resistance": detail.get("resistance"),
                "nearest_support": structure.get("nearest_support"),
                "nearest_resistance": structure.get("nearest_resistance"),
                "kde_ok": structure.get("kde_ok"),
                "kde_reason": structure.get("kde_reason"),
                "kde_lookback_used": structure.get("kde_lookback_used"),
                "exit_flags": r.exit_flags or {},
                "position_advice": r.position_advice or {},
                "detail": detail,
                "config_id": r.config_id,
            }
        )
    return out


def query_traces_by_code(
    db,
    *,
    code: str,
    config_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    entry_only: bool = False,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    """按股票代码查询 sbbr_signal_trace（日期倒序）。"""
    from backend_api.models import SBBRSignalTrace

    code_n = str(code or "").strip()
    if code_n.isdigit() and len(code_n) <= 6:
        code_n = code_n.zfill(6)
    q = db.query(SBBRSignalTrace).filter(SBBRSignalTrace.code == code_n)
    if config_id is not None:
        q = q.filter(SBBRSignalTrace.config_id == int(config_id))
    if start_date:
        d0 = datetime.strptime(str(start_date)[:10], "%Y-%m-%d").date()
        q = q.filter(SBBRSignalTrace.trade_date >= d0)
    if end_date:
        d1 = datetime.strptime(str(end_date)[:10], "%Y-%m-%d").date()
        q = q.filter(SBBRSignalTrace.trade_date <= d1)
    if entry_only:
        q = q.filter(SBBRSignalTrace.entry_signal.is_(True))
    rows = q.order_by(SBBRSignalTrace.trade_date.desc()).limit(int(limit)).all()
    out: List[Dict[str, Any]] = []
    for r in rows:
        detail = r.detail or {}
        structure = detail.get("structure") if isinstance(detail.get("structure"), dict) else {}
        out.append(
            {
                "code": r.code,
                "symbol": r.code,
                "name": r.name,
                "date": r.trade_date.isoformat() if r.trade_date else None,
                "market_type": r.market_type,
                "total_mv": r.total_mv,
                "circ_mv": r.circ_mv,
                "circ_shares_yi": detail.get("circ_shares_yi"),
                "size_ok": r.size_ok,
                "bottom_mode": r.bottom_mode,
                "bottom_matched": r.bottom_matched,
                "entry_signal": r.entry_signal,
                "entry_low": r.entry_low,
                "defense_low": r.defense_low,
                "defense_high": r.defense_high,
                "defense_buffer_pct": r.defense_buffer_pct,
                "close": r.close_price,
                "ma20": r.ma20,
                "volume_ratio": r.volume_ratio,
                "box_support": detail.get("support"),
                "box_resistance": detail.get("resistance"),
                "nearest_support": structure.get("nearest_support"),
                "nearest_resistance": structure.get("nearest_resistance"),
                "kde_ok": structure.get("kde_ok"),
                "kde_reason": structure.get("kde_reason"),
                "kde_lookback_used": structure.get("kde_lookback_used"),
                "exit_flags": r.exit_flags or {},
                "position_advice": r.position_advice or {},
                "detail": detail,
                "config_id": r.config_id,
                "source": "trace",
            }
        )
    return out
