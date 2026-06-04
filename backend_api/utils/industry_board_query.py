"""行业板块成分股查询工具。"""
from __future__ import annotations

from typing import Dict, List, Optional, Set

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend_api.models import IndustryBoardConstituent


def _normalize_code(code: str) -> str:
    s = str(code).strip()
    if s.isdigit() and len(s) < 6:
        return s.zfill(6)
    return s


def get_stock_codes_by_board_codes(
    db: Session, board_codes: List[str]
) -> Set[str]:
    """按板块代码列表取成分股代码并集。"""
    if not board_codes:
        return set()
    codes = [_normalize_code(c) for c in board_codes if c and str(c).strip()]
    if not codes:
        return set()
    rows = (
        db.query(IndustryBoardConstituent.stock_code)
        .filter(IndustryBoardConstituent.board_code.in_(codes))
        .distinct()
        .all()
    )
    return {str(r[0]).strip() for r in rows if r[0]}


def get_boards_by_stock_code(db: Session, stock_code: str) -> List[Dict]:
    """反查股票所属行业板块（含板块名称）。"""
    code = _normalize_code(stock_code)
    sql = text(
        """
        SELECT c.board_code, COALESCE(b.board_name, c.board_code) AS board_name, c.updated_at
        FROM industry_board_constituents c
        LEFT JOIN industry_board_basic_info b ON b.board_code = c.board_code
        WHERE c.stock_code = :stock_code
        ORDER BY b.board_name NULLS LAST, c.board_code
        """
    )
    rows = db.execute(sql, {"stock_code": code}).fetchall()
    return [
        {
            "board_code": str(r[0]),
            "board_name": str(r[1]) if r[1] else str(r[0]),
            "updated_at": r[2].isoformat() if hasattr(r[2], "isoformat") else str(r[2]) if r[2] else None,
        }
        for r in rows
    ]


def get_board_names_by_stock_code(db: Session, stock_code: str) -> List[str]:
    boards = get_boards_by_stock_code(db, stock_code)
    return [b["board_name"] for b in boards if b.get("board_name")]


def stock_matches_industry_filter(
    db: Session,
    stock_code: str,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
) -> bool:
    """include/exclude 可填 board_code 或 board_name。"""
    boards = get_boards_by_stock_code(db, stock_code)
    if not boards:
        return not bool(include)
    keys = set()
    for b in boards:
        keys.add(b["board_code"])
        keys.add(b["board_name"])
    if include:
        inc = set(include)
        if not keys.intersection(inc):
            return False
    if exclude:
        exc = set(exclude)
        if keys.intersection(exc):
            return False
    return True


def lookup_leading_code_from_constituents(
    db: Session, board_code: str, leading_stock_name: str
) -> Optional[str]:
    """在成分股表中按名称匹配领涨股代码。"""
    if not leading_stock_name or not str(leading_stock_name).strip():
        return None
    name = str(leading_stock_name).strip()
    row = (
        db.query(IndustryBoardConstituent.stock_code)
        .filter(
            IndustryBoardConstituent.board_code == board_code,
            IndustryBoardConstituent.stock_name == name,
        )
        .first()
    )
    if row:
        return str(row[0]).strip()
    row = (
        db.query(IndustryBoardConstituent.stock_code)
        .filter(
            IndustryBoardConstituent.board_code == board_code,
            IndustryBoardConstituent.stock_name.like(f"%{name}%"),
        )
        .first()
    )
    return str(row[0]).strip() if row else None
