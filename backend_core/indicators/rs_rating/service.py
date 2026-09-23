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


def list_rs_ratings_page(
    db: Session,
    *,
    market: str = "CN",
    keyword: str = "",
    date: Optional[str] = None,
    min_rating: Optional[int] = None,
    cn_board_segments: Optional[List[str]] = None,
    page: int = 1,
    page_size: int = 50,
) -> Dict[str, Any]:
    """
    分页列出预计算 RS 排行（按 rs_rating 降序）。
    market=CN → rs_ratings + stock_basic_info；
    market=HK → rs_ratings_hk + stock_basic_info_hk。
    """
    from sqlalchemy import text

    from backend_api.utils.cn_listed_board_filter import normalize_multi_board_segments
    from backend_core.strategies.volume_shrink_breakout.data_loader import (
        VSB_BOARD_PREFIX_GROUPS,
    )

    mkt = (market or "CN").strip().upper()
    if mkt not in ("CN", "HK"):
        mkt = "CN"
    page = max(1, int(page or 1))
    page_size = max(1, min(200, int(page_size or 50)))

    if mkt == "HK":
        rating_table = "rs_ratings_hk"
        basic_table = "stock_basic_info_hk"
        market_filter_sql = ""
        market_params: Dict[str, Any] = {}
    else:
        rating_table = "rs_ratings"
        basic_table = "stock_basic_info"
        market_filter_sql = " AND r.market_type = 'CN'"
        market_params = {}

    asof = (date or "").strip()[:10] or None
    if not asof:
        max_sql = f"SELECT MAX(date) FROM {rating_table}"
        if mkt == "CN":
            max_sql += " WHERE market_type = 'CN' AND rs_rating IS NOT NULL"
        else:
            max_sql += " WHERE rs_rating IS NOT NULL"
        row = db.execute(text(max_sql)).fetchone()
        asof = str(row[0]).strip()[:10] if row and row[0] else None
        if not asof:
            max_sql2 = f"SELECT MAX(date) FROM {rating_table}"
            if mkt == "CN":
                max_sql2 += " WHERE market_type = 'CN'"
            row2 = db.execute(text(max_sql2)).fetchone()
            asof = str(row2[0]).strip()[:10] if row2 and row2[0] else None
    if not asof:
        return {
            "success": True,
            "data": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "asof": None,
            "market": mkt,
            "cn_board_segments": [],
            "message": "尚无 RS 预计算数据",
        }

    where_parts = [f"r.date = :asof"]
    params: Dict[str, Any] = {"asof": asof, **market_params}
    if market_filter_sql:
        # already AND-prefixed fragment without leading AND for first join — inject as clause
        where_parts.insert(0, "r.market_type = 'CN'")

    kw = (keyword or "").strip()
    if kw:
        where_parts.append("(r.code ILIKE :kw OR COALESCE(b.name, '') ILIKE :kw)")
        params["kw"] = f"%{kw}%"
    if min_rating is not None:
        where_parts.append("r.rs_rating >= :min_rating")
        params["min_rating"] = int(min_rating)

    board_keys: List[str] = []
    board_out: List[str] = []
    if mkt == "CN":
        board_keys = normalize_multi_board_segments(cn_board_segments)
        if board_keys:
            prefix_conds: List[str] = []
            pi = 0
            for key in board_keys:
                for pref in VSB_BOARD_PREFIX_GROUPS.get(key, ()):
                    pname = f"bp{pi}"
                    pi += 1
                    prefix_conds.append(f"r.code LIKE :{pname}")
                    params[pname] = f"{pref}%"
            if prefix_conds:
                where_parts.append("(" + " OR ".join(prefix_conds) + ")")
            seen_b = set()
            for k in board_keys:
                label_key = "MAIN" if k in ("SH_MAIN", "SZ_MAIN") else k
                if label_key not in seen_b:
                    seen_b.add(label_key)
                    board_out.append(label_key)

    where_sql = " AND ".join(where_parts)
    total = (
        db.execute(
            text(
                f"""
                SELECT COUNT(1)
                FROM {rating_table} r
                LEFT JOIN {basic_table} b ON b.code = r.code
                WHERE {where_sql}
                """
            ),
            params,
        ).scalar()
        or 0
    )
    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset
    rows = (
        db.execute(
            text(
                f"""
                SELECT
                    r.code,
                    b.name,
                    r.date,
                    r.rs_rating,
                    r.rs_raw,
                    r.roc_63,
                    r.roc_126,
                    r.roc_189,
                    r.roc_252,
                    r.universe_size,
                    r.coverage_ratio
                FROM {rating_table} r
                LEFT JOIN {basic_table} b ON b.code = r.code
                WHERE {where_sql}
                ORDER BY r.rs_rating DESC NULLS LAST, r.rs_raw DESC NULLS LAST, r.code ASC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )
        .mappings()
        .all()
    )

    data: List[Dict[str, Any]] = []
    for r in rows:
        rating = r.get("rs_rating")
        data.append(
            {
                "code": r.get("code"),
                "name": r.get("name"),
                "date": str(r.get("date") or "")[:10],
                "market": mkt,
                "rs_rating": int(rating) if rating is not None else None,
                "rs_raw": r.get("rs_raw"),
                "roc_63": r.get("roc_63"),
                "roc_126": r.get("roc_126"),
                "roc_189": r.get("roc_189"),
                "roc_252": r.get("roc_252"),
                "universe_size": r.get("universe_size"),
                "coverage_ratio": r.get("coverage_ratio"),
                "strength_label": strength_label(
                    int(rating) if rating is not None else None
                ),
            }
        )
    return {
        "success": True,
        "data": data,
        "total": int(total),
        "page": page,
        "page_size": page_size,
        "asof": asof,
        "market": mkt,
        "cn_board_segments": board_out,
        "message": "ok" if data else "当前条件下无数据",
    }
