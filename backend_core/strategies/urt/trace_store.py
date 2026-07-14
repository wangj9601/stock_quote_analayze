# -*- coding: utf-8 -*-
"""URT 信号写入 urt_signal_trace。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session


def upsert_trace_rows(
    db: Session,
    *,
    config_id: int,
    rows: List[Dict[str, Any]],
) -> int:
    """批量 upsert；每行需含 code、signal_date（或 date）。返回写入条数。"""
    from backend_api.models import URTSignalTrace

    n = 0
    now = datetime.now()
    for r in rows:
        code = str(r.get("code") or "").strip()
        date_s = str(r.get("signal_date") or r.get("date") or "")[:10]
        if not code or not date_s:
            continue
        existing = (
            db.query(URTSignalTrace)
            .filter(
                URTSignalTrace.code == code,
                URTSignalTrace.date == date_s,
                URTSignalTrace.config_id == int(config_id),
            )
            .first()
        )
        fields = dict(
            name=r.get("name"),
            buy_signal=bool(r.get("buy_signal")),
            score=r.get("score"),
            signal_strength=r.get("signal_strength", r.get("score")),
            close=r.get("close"),
            open=r.get("open"),
            ma20=r.get("ma20"),
            above_ma20=r.get("above_ma20"),
            yang_count_4=r.get("yang_count_4"),
            yang_count_5=r.get("yang_count_5"),
            yang_rule=r.get("yang_rule"),
            volume=r.get("volume"),
            avg_volume_20=r.get("avg_volume_20"),
            volume_multiple=r.get("volume_multiple"),
            volume_ratio=r.get("volume_ratio"),
            turnover_rate=r.get("turnover_rate"),
            score_detail=r.get("score_detail"),
            created_at=now,
        )
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
        else:
            db.add(
                URTSignalTrace(
                    code=code,
                    date=date_s,
                    config_id=int(config_id),
                    **fields,
                )
            )
        n += 1
        if n % 200 == 0:
            db.commit()
    db.commit()
    return n


def query_buy_signals_for_date(
    db: Session,
    *,
    trade_date: str,
    config_id: int,
    min_score: Optional[float] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    from backend_api.models import URTSignalTrace

    q = (
        db.query(URTSignalTrace)
        .filter(
            URTSignalTrace.date == str(trade_date)[:10],
            URTSignalTrace.config_id == int(config_id),
            URTSignalTrace.buy_signal.is_(True),
        )
        .order_by(URTSignalTrace.score.desc())
    )
    if min_score is not None:
        q = q.filter(URTSignalTrace.score >= float(min_score))
    if limit:
        q = q.limit(int(limit))
    out: List[Dict[str, Any]] = []
    for row in q.all():
        out.append(
            {
                "code": row.code,
                "name": row.name or "",
                "signal_date": row.date,
                "close": row.close,
                "open": row.open,
                "ma20": row.ma20,
                "above_ma20": row.above_ma20,
                "yang_count_4": row.yang_count_4,
                "yang_count_5": row.yang_count_5,
                "yang_rule": row.yang_rule,
                "avg_volume_20": row.avg_volume_20,
                "volume": row.volume,
                "volume_multiple": row.volume_multiple,
                "volume_ratio": row.volume_ratio,
                "turnover_rate": row.turnover_rate,
                "score": row.score,
                "signal_strength": row.signal_strength,
                "score_detail": row.score_detail,
                "buy_signal": True,
                "from_cache": True,
            }
        )
    return out


def query_trace_by_code(
    db: Session,
    *,
    code: str,
    config_id: Optional[int] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    from backend_api.models import URTSignalTrace

    q = db.query(URTSignalTrace).filter(URTSignalTrace.code == str(code).strip())
    if config_id is not None:
        q = q.filter(URTSignalTrace.config_id == int(config_id))
    rows = q.order_by(URTSignalTrace.date.desc()).limit(int(limit)).all()
    return [
        {
            "code": r.code,
            "name": r.name,
            "date": r.date,
            "config_id": r.config_id,
            "buy_signal": r.buy_signal,
            "score": r.score,
            "close": r.close,
            "open": r.open,
            "ma20": r.ma20,
            "above_ma20": r.above_ma20,
            "yang_count_4": r.yang_count_4,
            "yang_count_5": r.yang_count_5,
            "yang_rule": r.yang_rule,
            "volume": r.volume,
            "avg_volume_20": r.avg_volume_20,
            "volume_multiple": r.volume_multiple,
            "volume_ratio": r.volume_ratio,
            "turnover_rate": r.turnover_rate,
            "score_detail": r.score_detail,
        }
        for r in rows
    ]
