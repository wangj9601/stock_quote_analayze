"""A 股代码段过滤，与 VSB 选股 boards（data_loader.VSB_BOARD_PREFIX_GROUPS）一致。"""

from __future__ import annotations

from typing import List, Optional, TypeVar

from sqlalchemy import Column, or_
from sqlalchemy.orm import Query

from backend_core.strategies.volume_shrink_breakout.data_loader import VSB_BOARD_PREFIX_GROUPS

_T = TypeVar("_T")


def normalize_list_board_segment(raw: Optional[str]) -> List[str]:
    """
    将单个查询参数转为板块键列表。
    MAIN = 沪深主板（SH_MAIN + SZ_MAIN），与前端「主板」对应。
    """
    if raw is None:
        return []
    k = str(raw).strip().upper()
    if not k:
        return []
    if k == "MAIN":
        return ["SH_MAIN", "SZ_MAIN"]
    if k in VSB_BOARD_PREFIX_GROUPS:
        return [k]
    return []


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
