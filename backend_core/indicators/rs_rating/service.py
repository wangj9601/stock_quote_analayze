"""个股 RS Rating as-of 查询。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from .config import MARKET_TYPE, strength_label, window_weight_pairs


def _date_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, date):
        return v.isoformat()
    s = str(v).strip()
    return s[:10] if s else None


def get_rs_rating_for_stock(
    db: Session,
    code: str,
    *,
    asof: Optional[str] = None,
    market_type: str = MARKET_TYPE,
) -> Dict[str, Any]:
    """
    读取预计算表；指定 asof 时取 <= asof 的最近一条，否则取最新一条。
    """
    from backend_api.models import RSRatings

    code_n = str(code or "").strip()
    if len(code_n) == 6 and code_n.isdigit():
        pass
    else:
        code_n = code_n.zfill(6) if code_n.isdigit() else code_n

    q = db.query(RSRatings).filter(
        RSRatings.code == code_n,
        RSRatings.market_type == market_type,
    )
    if asof:
        asof_s = asof[:10]
        q = q.filter(RSRatings.date <= asof_s)
    row = q.order_by(RSRatings.date.desc()).first()
    if not row:
        return {
            "success": False,
            "code": code_n,
            "message": "尚未预计算或历史不足",
            "reason": "not_found",
            "data": None,
        }

    rating = row.rs_rating
    data = {
        "code": row.code,
        "trade_date": _date_str(row.date),
        "market_type": row.market_type,
        "rs_rating": int(rating) if rating is not None else None,
        "rs_raw": row.rs_raw,
        "roc_63": row.roc_63,
        "roc_126": row.roc_126,
        "roc_189": row.roc_189,
        "roc_252": row.roc_252,
        "universe_size": row.universe_size,
        "coverage_ratio": row.coverage_ratio,
        "strength_label": strength_label(int(rating) if rating is not None else None),
        "windows": window_weight_pairs(),
        "asof": asof[:10] if asof else _date_str(row.date),
    }
    if rating is None:
        return {
            "success": True,
            "code": code_n,
            "message": "已有加权得分，但当日覆盖率不足未发布评级",
            "reason": "rating_unpublished",
            "data": data,
        }
    return {
        "success": True,
        "code": code_n,
        "message": "ok",
        "reason": None,
        "data": data,
    }
