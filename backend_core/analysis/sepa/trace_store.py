# -*- coding: utf-8 -*-
"""SEPA 信号 trace 读写（sepa_signal_scan / sepa_signal_trace）。"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _parse_date(value: str) -> date:
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()[:10]
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return item()
        except Exception:
            pass
    return str(value)


def json_safe(value: Any) -> Any:
    """把评估结果收成可写入 JSON/JSONB 的结构。"""
    return json.loads(json.dumps(value, ensure_ascii=False, default=_json_default))


def cache_covers_request(
    pool: Optional[Dict[str, Any]],
    *,
    limit_codes: int,
    min_avg_amount: float,
) -> bool:
    """预计算按全市场流动性池落库。缩小股票池或改成交额门槛时不能复用。"""
    if int(limit_codes or 0) > 0:
        return False
    stored = (pool or {}).get("min_avg_amount")
    if stored is None:
        return False
    try:
        return abs(float(stored) - float(min_avg_amount)) < 1.0
    except (TypeError, ValueError):
        return False


def replace_trace(
    db: Session,
    *,
    trade_date: str,
    rows: List[Dict[str, Any]],
    universe: int,
    funnel: Dict[str, Any],
    pool: Dict[str, Any],
) -> int:
    """按交易日整批替换。同一日重跑先删后写，避免旧形态残留。"""
    from backend_api.models import SEPASignalScan, SEPASignalTrace

    d = _parse_date(trade_date)
    now = datetime.now()
    db.query(SEPASignalTrace).filter(SEPASignalTrace.trade_date == d).delete(
        synchronize_session=False
    )
    objects = []
    for row in rows:
        code = str(row.get("code") or "").strip()
        status = str(row.get("vcp_status") or "").strip()
        if not code or not status:
            continue
        payload = json_safe(row)
        objects.append(
            SEPASignalTrace(
                code=code,
                trade_date=d,
                name=str(row.get("name") or "")[:200] or None,
                tier=(str(row.get("tier") or "")[:8] or None),
                vcp_status=status[:32],
                score=row.get("score"),
                row_data=payload,
                created_at=now,
                updated_at=now,
            )
        )
    if objects:
        db.add_all(objects)

    scan = db.query(SEPASignalScan).filter(SEPASignalScan.trade_date == d).one_or_none()
    if scan is None:
        scan = SEPASignalScan(trade_date=d, created_at=now)
        db.add(scan)
    scan.universe = int(universe or 0)
    scan.hit_count = len(objects)
    scan.funnel = json_safe(funnel or {})
    scan.pool = json_safe(pool or {})
    scan.updated_at = now
    db.commit()
    return len(objects)


def load_precompute(db: Session, trade_date: str) -> Optional[Dict[str, Any]]:
    """读某日预计算。没有 scan 记录时返回 None，调用方再决定是否现算。"""
    from backend_api.models import SEPASignalScan, SEPASignalTrace

    d = _parse_date(trade_date)
    scan = db.query(SEPASignalScan).filter(SEPASignalScan.trade_date == d).one_or_none()
    if scan is None:
        return None
    traces = (
        db.query(SEPASignalTrace)
        .filter(SEPASignalTrace.trade_date == d)
        .all()
    )
    rows: List[Dict[str, Any]] = []
    for item in traces:
        payload = item.row_data if isinstance(item.row_data, dict) else None
        if payload:
            rows.append(payload)
    return {
        "trade_date": d.isoformat(),
        "universe": int(scan.universe or 0),
        "hit_count": int(scan.hit_count or 0),
        "funnel": scan.funnel if isinstance(scan.funnel, dict) else {},
        "pool": scan.pool if isinstance(scan.pool, dict) else {},
        "rows": rows,
    }
