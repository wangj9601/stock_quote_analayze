"""stock_recommend_brief 读写。"""

from __future__ import annotations

import logging
import math
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def sanitize_brief_json(obj: Any) -> Any:
    """递归清洗 JSON 载荷：date/datetime/Decimal/NaN → 可序列化值。

    板斜率 asof、资金流 trade_date 等常以 date 对象渗入 payload，
    SQLAlchemy JSON 列默认 json.dumps 无法编码。
    """
    if obj is None or isinstance(obj, (bool, str)):
        return obj
    if isinstance(obj, datetime):
        return obj.isoformat(sep=" ", timespec="seconds")
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        try:
            f = float(obj)
        except (TypeError, ValueError, OverflowError):
            return None
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    if isinstance(obj, int) and not isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    item = getattr(obj, "item", None)  # numpy 标量
    if callable(item):
        try:
            return sanitize_brief_json(item())
        except (ValueError, AttributeError, TypeError):
            return None
    if isinstance(obj, dict):
        return {str(k): sanitize_brief_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [sanitize_brief_json(v) for v in obj]
    # 兜底：不可序列化对象转字符串，避免整单失败
    try:
        import json

        json.dumps(obj)
        return obj
    except (TypeError, ValueError, OverflowError):
        return str(obj)


def _ensure_model():
    from backend_api.models import StockRecommendBrief

    return StockRecommendBrief


def upsert_brief(
    db: Session,
    *,
    horizon: str,
    asof_date: str,
    items: List[Dict[str, Any]],
    summary: Optional[Dict[str, Any]] = None,
    risk_observe: Optional[List[Dict[str, Any]]] = None,
    kpi: Optional[Dict[str, Any]] = None,
    market_stance: Optional[str] = None,
    plan_for: Optional[str] = None,
    late_run: bool = False,
) -> Dict[str, Any]:
    StockRecommendBrief = _ensure_model()
    asof = date.fromisoformat(str(asof_date)[:10])
    hz = str(horizon).strip().lower()
    safe_summary = sanitize_brief_json(summary or {})
    safe_items = sanitize_brief_json(items or [])
    safe_risk = sanitize_brief_json(risk_observe or [])
    safe_kpi = sanitize_brief_json(kpi or {})
    safe_plan = sanitize_brief_json(plan_for) if plan_for is not None else None
    row = (
        db.query(StockRecommendBrief)
        .filter(
            StockRecommendBrief.horizon == hz,
            StockRecommendBrief.asof_date == asof,
        )
        .first()
    )
    now = datetime.now()
    if row is None:
        row = StockRecommendBrief(
            horizon=hz,
            asof_date=asof,
            plan_for=safe_plan,
            late_run=bool(late_run),
            market_stance=market_stance,
            summary_json=safe_summary if isinstance(safe_summary, dict) else {},
            items_json=safe_items if isinstance(safe_items, list) else [],
            risk_observe_json=safe_risk if isinstance(safe_risk, list) else [],
            kpi_json=safe_kpi if isinstance(safe_kpi, dict) else {},
            generated_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        row.plan_for = safe_plan
        row.late_run = bool(late_run)
        row.market_stance = market_stance
        row.summary_json = safe_summary if isinstance(safe_summary, dict) else {}
        row.items_json = safe_items if isinstance(safe_items, list) else []
        row.risk_observe_json = safe_risk if isinstance(safe_risk, list) else []
        row.kpi_json = safe_kpi if isinstance(safe_kpi, dict) else {}
        row.generated_at = now
        row.updated_at = now
    db.commit()
    db.refresh(row)
    return brief_to_dict(row)


def get_brief(
    db: Session, *, horizon: str, asof_date: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    StockRecommendBrief = _ensure_model()
    hz = str(horizon).strip().lower()
    q = db.query(StockRecommendBrief).filter(StockRecommendBrief.horizon == hz)
    if asof_date:
        asof = date.fromisoformat(str(asof_date)[:10])
        row = q.filter(StockRecommendBrief.asof_date == asof).first()
    else:
        row = q.order_by(StockRecommendBrief.asof_date.desc()).first()
    return brief_to_dict(row) if row else None


def list_asof_dates(
    db: Session, *, horizon: str, limit: int = 60
) -> List[str]:
    StockRecommendBrief = _ensure_model()
    hz = str(horizon).strip().lower()
    rows = (
        db.query(StockRecommendBrief.asof_date)
        .filter(StockRecommendBrief.horizon == hz)
        .order_by(StockRecommendBrief.asof_date.desc())
        .limit(limit)
        .all()
    )
    out = []
    for r in rows:
        v = r[0]
        out.append(v.isoformat() if hasattr(v, "isoformat") else str(v)[:10])
    return out


def brief_to_dict(row: Any) -> Dict[str, Any]:
    if row is None:
        return {}
    asof = row.asof_date
    return {
        "id": int(row.id) if row.id is not None else None,
        "horizon": row.horizon,
        "asof_date": asof.isoformat() if hasattr(asof, "isoformat") else str(asof)[:10],
        "plan_for": row.plan_for,
        "late_run": bool(row.late_run),
        "market_stance": row.market_stance,
        "summary": row.summary_json if isinstance(row.summary_json, dict) else {},
        "items": row.items_json if isinstance(row.items_json, list) else [],
        "risk_observe": row.risk_observe_json
        if isinstance(row.risk_observe_json, list)
        else [],
        "kpi": row.kpi_json if isinstance(row.kpi_json, dict) else {},
        "generated_at": row.generated_at.isoformat()
        if getattr(row, "generated_at", None)
        else None,
        "updated_at": row.updated_at.isoformat()
        if getattr(row, "updated_at", None)
        else None,
    }
