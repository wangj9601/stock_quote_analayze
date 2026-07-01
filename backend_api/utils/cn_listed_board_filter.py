"""A 股代码段过滤，与 VSB 选股 boards（data_loader.VSB_BOARD_PREFIX_GROUPS）一致。"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, TypeVar

from sqlalchemy import Column, or_
from sqlalchemy.orm import Query

from backend_core.strategies.volume_shrink_breakout.data_loader import (
    VSB_BOARD_PREFIX_GROUPS,
    code_matches_vsb_boards,
)

_T = TypeVar("_T")


def normalize_list_board_segment(raw: Optional[str]) -> List[str]:
    """
    将单个查询参数转为板块键列表。
    MAIN = 沪深主板（SH_MAIN + SZ_MAIN），与前端「主板」对应。
  BJ / BSE = 北交所/北证。
    """
    if raw is None:
        return []
    k = str(raw).strip().upper()
    if not k:
        return []
    if k == "MAIN":
        return ["SH_MAIN", "SZ_MAIN"]
    if k in ("BSE", "北证"):
        return ["BJ"]
    if k in VSB_BOARD_PREFIX_GROUPS:
        return [k]
    return []


def is_cn_listed_equity_code(code: str) -> bool:
    """沪深京 A 股代码（含北交所），用于 GMS 等市场类型判定。"""
    c = str(code or "").strip()
    if len(c) == 5 and c.isdigit():
        return False
    if len(c) < 6 and c.isdigit():
        c = c.zfill(6)
    if len(c) != 6 or not c.isdigit():
        return False
    if c[0] in "6039":
        return True
    return code_matches_vsb_boards(c, ["BJ"])


def board_keys_to_code_prefix_or(code_column: Column, board_keys: List[str]):
    """SQLAlchemy OR：代码以任一所选板块前缀开头。"""
    conds = []
    for key in board_keys:
        for p in VSB_BOARD_PREFIX_GROUPS.get(key, ()):
            conds.append(code_column.startswith(p))
    return or_(*conds) if conds else None


def apply_cn_board_segment_filter(query: Query[_T], code_column: Column, board_segment: Optional[str]) -> Query[_T]:
    """按板块过滤 A 股代码；board_segment 无效时原样返回。"""
    keys = normalize_list_board_segment(board_segment)
    if not keys:
        return query
    crit = board_keys_to_code_prefix_or(code_column, keys)
    if crit is None:
        return query
    return query.filter(crit)


# 3倍量每日爆量推送 Excel：按板块分 sheet（顺序与表头展示名）
TVO_PUSH_EXCEL_BOARD_SHEETS: List[Tuple[str, str]] = [
    ("MAIN", "沪深主板"),
    ("SZ_SME", "中小板"),
    ("CYB", "创业板"),
    ("KCB", "科创板"),
]

TVO_PUSH_EXCEL_HK_SHEET = "港股"


def classify_tvo_excel_board_segment(code: str, market: str) -> str:
    """
    将观察股行归入推送 Excel 的板块键：MAIN / SZ_SME / CYB / KCB / HK / OTHER。
    A 股按 VSB 代码段前缀；港股单独 HK。
    """
    m = (market or "").strip().upper()
    if m == "HK":
        return "HK"
    c = str(code or "").strip()
    if len(c) == 5 and c.isdigit():
        c = c.zfill(6)
    if len(c) != 6 or not c.isdigit():
        return "OTHER"
    for seg in ("KCB", "CYB", "SZ_SME"):
        if code_matches_vsb_boards(c, [seg]):
            return seg
    if code_matches_vsb_boards(c, ["SH_MAIN", "SZ_MAIN"]):
        return "MAIN"
    return "OTHER"


def group_tvo_rows_by_excel_board(
    rows: List[Dict],
    *,
    code_key: str = "代码",
    market_key: str = "市场",
) -> Dict[str, List[Dict]]:
    """按 classify_tvo_excel_board_segment 将行字典分桶。"""
    buckets: Dict[str, List[Dict]] = {seg: [] for seg, _ in TVO_PUSH_EXCEL_BOARD_SHEETS}
    buckets["HK"] = []
    buckets["OTHER"] = []
    for row in rows:
        seg = classify_tvo_excel_board_segment(
            str(row.get(code_key, "")),
            str(row.get(market_key, "")),
        )
        if seg not in buckets:
            seg = "OTHER"
        buckets[seg].append(row)
    return buckets


def filter_query_by_market_and_board(
    query: Query[_T],
    market_column: Column,
    code_column: Column,
    market: Optional[str],
    board_segment: Optional[str],
) -> Query[_T]:
    """市场 + 可选 A 股代码段；港股忽略 board_segment。"""
    m = (market or "").strip().upper() or None
    m = m[:10] if m else None
    bs = (board_segment or "").strip() or None
    keys = normalize_list_board_segment(bs) if bs else []

    if m == "HK":
        return query.filter(market_column == "HK")
    if keys:
        q2 = query.filter(market_column == "CN")
        return apply_cn_board_segment_filter(q2, code_column, bs)
    if m:
        return query.filter(market_column == m)
    return query
