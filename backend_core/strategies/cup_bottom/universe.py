# -*- coding: utf-8 -*-
"""CUPB 杯底形态股票池：市场范围 / A 股板块多选 / 无效代码过滤。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import func, not_, or_

from backend_api.utils.cn_listed_board_filter import (
    filter_stock_codes_by_board_segments,
    is_cn_listed_equity_code,
    normalize_multi_board_segments,
)
from backend_core.strategies.double_bottom.universe import (
    enrich_items_with_ths_industry,
    normalize_a_code,
    normalize_code_list,
    resolve_concept_pool,
    resolve_industry_pool,
)

# 与 VSB / URT 一致的板块键
CN_BOARD_SEGMENT_OPTIONS = ("MAIN", "CYB", "SZ_SME", "KCB", "BJ")


def normalize_market_scopes(raw: Optional[Sequence[Any]]) -> List[str]:
    """归一市场范围：CN / HK；默认 CN。"""
    if not raw:
        return ["CN"]
    out: List[str] = []
    seen = set()
    for item in raw:
        for piece in str(item or "").replace(",", " ").split():
            k = piece.strip().upper()
            if k in ("CN", "A", "A股", "ASHARE"):
                k = "CN"
            elif k in ("HK", "H", "港股"):
                k = "HK"
            else:
                continue
            if k not in seen:
                seen.add(k)
                out.append(k)
    return out or ["CN"]


def normalize_cn_board_segments(raw: Optional[Sequence[Any]]) -> List[str]:
    """多选 A 股板块；空=不限（默认仍排除北证及 4/8 杂码）。"""
    if not raw:
        return []
    flat: List[str] = []
    for item in raw:
        for piece in str(item or "").replace(",", " ").split():
            k = piece.strip().upper()
            if k in ("BSE", "北证"):
                k = "BJ"
            if k in CN_BOARD_SEGMENT_OPTIONS:
                flat.append(k)
    keys = normalize_multi_board_segments(flat)
    rev = {
        "SH_MAIN": "MAIN",
        "SZ_MAIN": "MAIN",
        "CYB": "CYB",
        "SZ_SME": "SZ_SME",
        "KCB": "KCB",
        "BJ": "BJ",
    }
    out: List[str] = []
    seen = set()
    for k in keys:
        seg = rev.get(k, k)
        if seg not in seen:
            seen.add(seg)
            out.append(seg)
    return out


def is_valid_cupb_cn_code(code: str, *, board_segments: Optional[List[str]] = None) -> bool:
    """
    有效 A 股代码：
    - 须为沪深京合法代码段（排除 4/8 打头的无效杂码）
    - 未选板块时默认不含北证（仅 0/3/6 段）
    - 选了板块则按板块并集过滤
    """
    c = normalize_a_code(code)
    if len(c) != 6 or not c.isdigit():
        return False
    if not is_cn_listed_equity_code(c):
        return False
    segs = normalize_cn_board_segments(board_segments) if board_segments else []
    if segs:
        return c in set(filter_stock_codes_by_board_segments([c], segs))
    # 默认全 A（不含北证）：过滤 4/8 打头及北证代码
    if c[0] in "48":
        return False
    return c[0] in "036"


def filter_cupb_cn_codes(
    codes: Sequence[str],
    *,
    board_segments: Optional[Sequence[str]] = None,
) -> List[str]:
    segs = normalize_cn_board_segments(board_segments) if board_segments else []
    out: List[str] = []
    for raw in codes:
        c = normalize_a_code(raw)
        if not c:
            continue
        if not is_valid_cupb_cn_code(c, board_segments=segs or None):
            continue
        if segs:
            filtered = filter_stock_codes_by_board_segments([c], segs)
            if not filtered:
                continue
        out.append(c)
    return out


def resolve_cn_market_pool(
    db,
    *,
    board_segments: Optional[Sequence[str]] = None,
    limit: Optional[int] = None,
) -> List[str]:
    from backend_api.models import StockBasicInfo

    qry = (
        db.query(StockBasicInfo.code)
        .filter(func.length(StockBasicInfo.code) == 6)
        .filter(not_(StockBasicInfo.name.like("%ST%")))
        .filter(
            or_(
                StockBasicInfo.collect_enabled.is_(True),
                StockBasicInfo.collect_enabled.is_(None),
            )
        )
        .order_by(StockBasicInfo.code)
    )
    if limit is not None and int(limit) > 0:
        qry = qry.limit(int(limit))
    raw = [normalize_a_code(r[0]) for r in qry.all() if r[0]]
    return filter_cupb_cn_codes(raw, board_segments=board_segments)


def resolve_hk_market_pool(db, *, limit: Optional[int] = None) -> List[str]:
    from backend_api.models import StockBasicInfoHK

    qry = (
        db.query(StockBasicInfoHK.code)
        .filter(not_(StockBasicInfoHK.name.like("%ST%")))
        .filter(
            or_(
                StockBasicInfoHK.collect_enabled.is_(True),
                StockBasicInfoHK.collect_enabled.is_(None),
            )
        )
        .order_by(StockBasicInfoHK.code)
    )
    if limit is not None and int(limit) > 0:
        qry = qry.limit(int(limit))
    out: List[str] = []
    for r in qry.all():
        s = str(r[0] or "").strip()
        if s.isdigit() and len(s) <= 5:
            out.append(s.zfill(5))
    return out


def resolve_stock_pool(
    db,
    *,
    stock_pool_mode: str,
    industry_board_codes: Optional[Sequence[Any]] = None,
    concept_board_codes: Optional[Sequence[Any]] = None,
    stock_codes: Optional[Sequence[Any]] = None,
    universe_limit: Optional[int] = None,
    market_scopes: Optional[Sequence[Any]] = None,
    cn_board_segments: Optional[Sequence[Any]] = None,
) -> Dict[str, Any]:
    """解析 CUPB 股票池。"""
    mode = (stock_pool_mode or "stocks").strip().lower()
    boards_by: Dict[str, List[Dict[str, str]]] = {}
    board_codes: List[str] = []
    scopes = normalize_market_scopes(market_scopes)
    cn_segs = normalize_cn_board_segments(cn_board_segments)

    if mode == "industry_board":
        board_codes, codes, boards_by = resolve_industry_pool(db, industry_board_codes or [])
        codes = filter_cupb_cn_codes(codes, board_segments=cn_segs or None)
    elif mode == "concept_board":
        board_codes, codes, boards_by = resolve_concept_pool(db, concept_board_codes or [])
        codes = filter_cupb_cn_codes(codes, board_segments=cn_segs or None)
    elif mode == "market":
        codes = []
        if "CN" in scopes:
            codes.extend(resolve_cn_market_pool(db, board_segments=cn_segs or None, limit=universe_limit))
        if "HK" in scopes:
            hk_codes = resolve_hk_market_pool(db, limit=universe_limit)
            codes.extend(hk_codes)
        codes = list(dict.fromkeys(codes))
    elif mode == "stocks":
        raw = normalize_code_list(stock_codes)
        cn_part = [c for c in raw if len(c) == 6]
        hk_part = [c for c in raw if len(c) == 5 and c.isdigit()]
        other = [c for c in raw if c not in cn_part and c not in hk_part]
        codes = filter_cupb_cn_codes(cn_part, board_segments=cn_segs or None) + hk_part + other
    else:
        raise ValueError(f"不支持的 stock_pool_mode: {mode}")

    scope_meta = {
        "stock_pool_mode": mode,
        "board_codes": list(board_codes),
        "stock_count": len(codes),
        "universe_limit": universe_limit,
        "market_scopes": scopes,
        "cn_board_segments": cn_segs,
    }
    return {
        "codes": codes,
        "board_codes": board_codes,
        "boards_by_code": boards_by,
        "mode": mode,
        "scope_meta": scope_meta,
    }


__all__ = [
    "CN_BOARD_SEGMENT_OPTIONS",
    "enrich_items_with_ths_industry",
    "filter_cupb_cn_codes",
    "is_valid_cupb_cn_code",
    "normalize_cn_board_segments",
    "normalize_market_scopes",
    "resolve_stock_pool",
]
