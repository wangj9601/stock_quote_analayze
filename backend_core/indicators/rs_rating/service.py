"""个股 RS Rating as-of 查询（A 股 rs_ratings / 港股 rs_ratings_hk）。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .config import MARKET_TYPE, MARKET_TYPE_HK, PRICE_ADJUST, strength_label, window_weight_pairs


def _date_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, date):
        return v.isoformat()
    s = str(v).strip()
    return s[:10] if s else None


def _normalize_cn_code(code: str) -> str:
    code_n = str(code or "").strip()
    if code_n.isdigit():
        return code_n.zfill(6) if len(code_n) <= 6 else code_n
    return code_n


def _normalize_hk_code(code: str) -> str:
    code_n = str(code or "").strip().upper()
    if code_n.startswith("HK") and len(code_n) > 2:
        code_n = code_n[2:]
    if code_n.isdigit():
        return code_n.zfill(5) if len(code_n) <= 5 else code_n
    return code_n


def _is_hk_market(market_type: str, code: str) -> bool:
    mt = (market_type or "").strip().upper()
    if mt == MARKET_TYPE_HK:
        return True
    code_n = str(code or "").strip()
    return len(code_n) == 5 and code_n.isdigit()


def get_rs_rating_for_stock(
    db: Session,
    code: str,
    *,
    asof: Optional[str] = None,
    market_type: str = MARKET_TYPE,
) -> Dict[str, Any]:
    """
    读取预计算表；指定 asof 时取 <= asof 的最近一条，否则取最新一条。
    港股读 ``rs_ratings_hk``，A 股读 ``rs_ratings``。
    """
    if _is_hk_market(market_type, code):
        return _get_rs_rating_hk(db, code, asof=asof)
    return _get_rs_rating_cn(db, code, asof=asof, market_type=market_type or MARKET_TYPE)


def _get_rs_rating_cn(
    db: Session,
    code: str,
    *,
    asof: Optional[str] = None,
    market_type: str = MARKET_TYPE,
) -> Dict[str, Any]:
    from backend_api.models import RSRatings

    code_n = _normalize_cn_code(code)
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
        "market_type": row.market_type or MARKET_TYPE,
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
        "price_adjust": PRICE_ADJUST,
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


def _get_rs_rating_hk(
    db: Session,
    code: str,
    *,
    asof: Optional[str] = None,
) -> Dict[str, Any]:
    from backend_api.models import RSRatingsHK

    code_n = _normalize_hk_code(code)
    q = db.query(RSRatingsHK).filter(RSRatingsHK.code == code_n)
    if asof:
        asof_s = asof[:10]
        q = q.filter(RSRatingsHK.date <= asof_s)
    row = q.order_by(RSRatingsHK.date.desc()).first()
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
        "market_type": MARKET_TYPE_HK,
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
        "price_adjust": PRICE_ADJUST,
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


def list_rs_rating_history(
    db: Session,
    code: str,
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 120,
    market_type: str = MARKET_TYPE,
) -> Dict[str, Any]:
    """按股票拉取 RS 历史序列（日期降序）。"""
    if _is_hk_market(market_type, code):
        return _list_rs_rating_history_hk(
            db, code, start_date=start_date, end_date=end_date, limit=limit
        )
    return _list_rs_rating_history_cn(
        db,
        code,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        market_type=market_type or MARKET_TYPE,
    )


def _list_rs_rating_history_cn(
    db: Session,
    code: str,
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 120,
    market_type: str = MARKET_TYPE,
) -> Dict[str, Any]:
    from backend_api.models import RSRatings, StockBasicInfo

    code_n = _normalize_cn_code(code)
    lim = max(1, min(int(limit or 120), 500))
    q = db.query(RSRatings).filter(
        RSRatings.code == code_n,
        RSRatings.market_type == market_type,
    )
    if start_date:
        q = q.filter(RSRatings.date >= start_date[:10])
    if end_date:
        q = q.filter(RSRatings.date <= end_date[:10])
    rows = q.order_by(RSRatings.date.desc()).limit(lim).all()
    name = None
    try:
        basic = db.query(StockBasicInfo).filter(StockBasicInfo.code == code_n).first()
        if basic:
            name = basic.name
    except Exception:
        name = None

    items: List[Dict[str, Any]] = []
    for row in rows:
        rating = row.rs_rating
        items.append(
            {
                "code": row.code,
                "date": _date_str(row.date),
                "market_type": MARKET_TYPE,
                "rs_rating": int(rating) if rating is not None else None,
                "rs_raw": row.rs_raw,
                "roc_63": row.roc_63,
                "roc_126": row.roc_126,
                "roc_189": row.roc_189,
                "roc_252": row.roc_252,
                "universe_size": row.universe_size,
                "coverage_ratio": row.coverage_ratio,
                "strength_label": strength_label(
                    int(rating) if rating is not None else None
                ),
                "price_adjust": PRICE_ADJUST,
            }
        )
    return {
        "success": True,
        "code": code_n,
        "name": name,
        "market_type": MARKET_TYPE,
        "count": len(items),
        "limit": lim,
        "start_date": start_date[:10] if start_date else None,
        "end_date": end_date[:10] if end_date else None,
        "price_adjust": PRICE_ADJUST,
        "data": items,
        "message": "ok" if items else "暂无历史预计算记录",
    }


def _list_rs_rating_history_hk(
    db: Session,
    code: str,
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 120,
) -> Dict[str, Any]:
    from backend_api.models import RSRatingsHK, StockBasicInfoHK

    code_n = _normalize_hk_code(code)
    lim = max(1, min(int(limit or 120), 500))
    q = db.query(RSRatingsHK).filter(RSRatingsHK.code == code_n)
    if start_date:
        q = q.filter(RSRatingsHK.date >= start_date[:10])
    if end_date:
        q = q.filter(RSRatingsHK.date <= end_date[:10])
    rows = q.order_by(RSRatingsHK.date.desc()).limit(lim).all()
    name = None
    try:
        basic = (
            db.query(StockBasicInfoHK).filter(StockBasicInfoHK.code == code_n).first()
        )
        if basic:
            name = basic.name
    except Exception:
        name = None

    items: List[Dict[str, Any]] = []
    for row in rows:
        rating = row.rs_rating
        items.append(
            {
                "code": row.code,
                "date": _date_str(row.date),
                "market_type": MARKET_TYPE_HK,
                "rs_rating": int(rating) if rating is not None else None,
                "rs_raw": row.rs_raw,
                "roc_63": row.roc_63,
                "roc_126": row.roc_126,
                "roc_189": row.roc_189,
                "roc_252": row.roc_252,
                "universe_size": row.universe_size,
                "coverage_ratio": row.coverage_ratio,
                "strength_label": strength_label(
                    int(rating) if rating is not None else None
                ),
                "price_adjust": PRICE_ADJUST,
            }
        )
    return {
        "success": True,
        "code": code_n,
        "name": name,
        "market_type": MARKET_TYPE_HK,
        "count": len(items),
        "limit": lim,
        "start_date": start_date[:10] if start_date else None,
        "end_date": end_date[:10] if end_date else None,
        "price_adjust": PRICE_ADJUST,
        "data": items,
        "message": "ok" if items else "暂无历史预计算记录",
    }
