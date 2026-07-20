"""RPE 信号落库。"""

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
    from backend_api.models import RPESignalTrace

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
            db.query(RPESignalTrace)
            .filter(
                RPESignalTrace.code == code,
                RPESignalTrace.trade_date == d,
                RPESignalTrace.config_id == int(config_id),
                RPESignalTrace.market_type == (r.get("market_type") or "CN"),
            )
            .first()
        )
        payload = dict(
            name=r.get("name"),
            sector_id=r.get("sector_id"),
            sector_name=r.get("sector_name"),
            z_score=r.get("z_score"),
            ratio=r.get("ratio"),
            signal_type=r.get("signal_type"),
            entry_signal=bool(r.get("entry_signal")),
            watch_only=bool(r.get("watch_only")),
            trend_veto=bool(r.get("trend_veto")),
            sector_slope=r.get("sector_slope"),
            support_levels=r.get("support_levels") or [],
            resistance_levels=r.get("resistance_levels") or [],
            nearest_support=r.get("nearest_support"),
            nearest_resistance=r.get("nearest_resistance"),
            structure_valid=bool(r.get("structure_valid")),
            liquidity_ok=bool(r.get("liquidity_ok")),
            close_price=r.get("close"),
            detail=r.get("detail") or {},
            updated_at=datetime.now(),
        )
        if existing:
            for k, v in payload.items():
                setattr(existing, k, v)
        else:
            db.add(
                RPESignalTrace(
                    code=code,
                    trade_date=d,
                    market_type=r.get("market_type") or "CN",
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
        logger.exception("RPE upsert_signal_traces failed: %s", e)
        raise
    return n


def load_traces(
    db,
    *,
    trade_date: str,
    config_id: int,
    entry_only: bool = False,
    signal_type: str = None,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    from backend_api.models import RPESignalTrace

    d = datetime.strptime(trade_date[:10], "%Y-%m-%d").date()
    q = db.query(RPESignalTrace).filter(
        RPESignalTrace.trade_date == d,
        RPESignalTrace.config_id == int(config_id),
    )
    if entry_only:
        q = q.filter(RPESignalTrace.entry_signal.is_(True))
    if signal_type:
        q = q.filter(RPESignalTrace.signal_type == signal_type)
    rows = (
        q.order_by(RPESignalTrace.entry_signal.desc(), RPESignalTrace.z_score.asc())
        .limit(limit)
        .all()
    )
    out = []
    for r in rows:
        out.append(
            {
                "code": r.code,
                "symbol": r.code,
                "name": r.name,
                "date": r.trade_date.isoformat() if r.trade_date else trade_date,
                "market_type": r.market_type,
                "sector_id": r.sector_id,
                "sector_name": r.sector_name,
                "z_score": r.z_score,
                "ratio": r.ratio,
                "signal_type": r.signal_type,
                "entry_signal": r.entry_signal,
                "watch_only": r.watch_only,
                "trend_veto": r.trend_veto,
                "sector_slope": r.sector_slope,
                "support_levels": r.support_levels or [],
                "resistance_levels": r.resistance_levels or [],
                "nearest_support": r.nearest_support,
                "nearest_resistance": r.nearest_resistance,
                "structure_valid": r.structure_valid,
                "liquidity_ok": r.liquidity_ok,
                "close": r.close_price,
                "detail": r.detail or {},
                "config_id": r.config_id,
            }
        )
    return out
