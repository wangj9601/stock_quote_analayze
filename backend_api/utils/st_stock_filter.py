"""A 股 ST 类股票过滤（名称含 ST，含 ST、*ST、S*ST 等）。"""

from __future__ import annotations

from typing import List, Optional, Set

from sqlalchemy.orm import Session

from backend_api.models import StockBasicInfo


def is_st_stock_name(name: Optional[str]) -> bool:
    """名称是否属于 ST 类（与项目内其它选股策略一致：name LIKE '%ST%'）。"""
    return bool(name) and "ST" in str(name).upper()


def filter_codes_exclude_st(db: Session, codes: List[str]) -> List[str]:
    """从代码列表中剔除 A 股 ST 类股票（按 stock_basic_info.name）。"""
    if not codes:
        return codes
    cn_codes = [
        str(c).strip()
        for c in codes
        if len(str(c).strip()) == 6 and str(c).strip().isdigit()
    ]
    if not cn_codes:
        return codes
    st_codes: Set[str] = set()
    chunk = 500
    for i in range(0, len(cn_codes), chunk):
        batch = cn_codes[i : i + chunk]
        rows = (
            db.query(StockBasicInfo.code)
            .filter(StockBasicInfo.code.in_(batch), StockBasicInfo.name.like("%ST%"))
            .all()
        )
        st_codes.update(str(r.code).strip() for r in rows if r.code)
    if not st_codes:
        return codes
    return [c for c in codes if str(c).strip() not in st_codes]
