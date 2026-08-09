# -*- coding: utf-8 -*-
"""双底策略股票池：行业 / 概念 / 个股 / 全市场。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple


def normalize_a_code(raw: Any) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    if s.isdigit() and len(s) <= 6:
        return s.zfill(6)
    return s


def normalize_code_list(raw: Optional[Sequence[Any]]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in raw or []:
        for part in str(item or "").replace("\n", ",").replace(" ", ",").split(","):
            code = normalize_a_code(part)
            if not code or code in seen:
                continue
            if code.isdigit() and len(code) != 6:
                continue
            seen.add(code)
            out.append(code)
    return out


def normalize_board_codes(raw: Optional[Sequence[Any]], *, upper: bool = False) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in raw or []:
        for part in str(item or "").split(","):
            code = part.strip()
            if not code:
                continue
            if upper:
                code = code.upper()
            if code in seen:
                continue
            seen.add(code)
            out.append(code)
    return out


def resolve_industry_pool(db, raw: Sequence[Any]) -> Tuple[List[str], List[str], Dict[str, List[Dict[str, str]]]]:
    """返回 (board_codes, stock_codes, boards_by_stock)。"""
    from backend_api.models import IndustryBoardConstituent
    from backend_api.utils.bk_board_code import resolve_industry_board_codes

    bcodes = resolve_industry_board_codes(db, list(raw or []))
    if not bcodes:
        return [], [], {}
    # 名称
    name_map: Dict[str, str] = {}
    try:
        from backend_api.models import IndustryBoardRealtimeQuotes

        rows_n = (
            db.query(
                IndustryBoardRealtimeQuotes.board_code,
                IndustryBoardRealtimeQuotes.board_name,
            )
            .filter(IndustryBoardRealtimeQuotes.board_code.in_(bcodes))
            .all()
        )
        for r in rows_n:
            name_map[str(r[0])] = str(r[1] or r[0])
    except Exception:
        pass

    rows = (
        db.query(IndustryBoardConstituent.stock_code, IndustryBoardConstituent.board_code)
        .filter(IndustryBoardConstituent.board_code.in_(bcodes))
        .all()
    )
    codes: List[str] = []
    seen = set()
    boards_by: Dict[str, List[Dict[str, str]]] = {}
    for stock_code, board_code in rows:
        c = normalize_a_code(stock_code)
        bc = str(board_code or "").strip()
        if not c:
            continue
        if c not in seen:
            seen.add(c)
            codes.append(c)
        blist = boards_by.setdefault(c, [])
        if bc and not any(x.get("board_code") == bc for x in blist):
            blist.append({"board_code": bc, "board_name": name_map.get(bc, bc)})
    codes.sort()
    return bcodes, codes, boards_by


def resolve_concept_pool(db, raw: Sequence[Any]) -> Tuple[List[str], List[str], Dict[str, List[Dict[str, str]]]]:
    from backend_api.models import ConceptBoardConstituent

    bcodes = normalize_board_codes(raw, upper=True)
    if not bcodes:
        return [], [], {}
    name_map: Dict[str, str] = {bc: bc for bc in bcodes}
    try:
        # 概念名优先从成分表无；若有实时行情表再覆盖
        from backend_api.models import ConceptBoardRealtimeQuotes  # type: ignore

        rows_n = (
            db.query(
                ConceptBoardRealtimeQuotes.board_code,
                ConceptBoardRealtimeQuotes.board_name,
            )
            .filter(ConceptBoardRealtimeQuotes.board_code.in_(bcodes))
            .all()
        )
        for r in rows_n:
            name_map[str(r[0])] = str(r[1] or r[0])
    except Exception:
        pass

    rows = (
        db.query(ConceptBoardConstituent.stock_code, ConceptBoardConstituent.board_code)
        .filter(ConceptBoardConstituent.board_code.in_(bcodes))
        .all()
    )
    codes: List[str] = []
    seen = set()
    boards_by: Dict[str, List[Dict[str, str]]] = {}
    for stock_code, board_code in rows:
        c = normalize_a_code(stock_code)
        bc = str(board_code or "").strip().upper()
        if not c:
            continue
        if c not in seen:
            seen.add(c)
            codes.append(c)
        blist = boards_by.setdefault(c, [])
        if bc and not any(x.get("board_code") == bc for x in blist):
            blist.append({"board_code": bc, "board_name": name_map.get(bc, bc)})
    codes.sort()
    return bcodes, codes, boards_by


def resolve_market_pool(db, *, limit: Optional[int] = None) -> List[str]:
    from sqlalchemy import func, not_, or_

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
    return [normalize_a_code(r[0]) for r in qry.all() if r[0]]


def batch_ths_industry_labels(
    db, stock_codes: Sequence[Any]
) -> Dict[str, str]:
    """批量取同花顺行业板块归属：code -> 顿号拼接的板块名。"""
    codes = normalize_code_list(stock_codes)
    if not codes:
        return {}
    try:
        from backend_api.utils.industry_board_query import (
            batch_industry_board_names_by_stock_codes,
        )

        raw = batch_industry_board_names_by_stock_codes(
            db, codes, board_code_source="tonghuashun"
        ) or {}
    except Exception:
        return {}
    out: Dict[str, str] = {}
    for code, names in raw.items():
        c = normalize_a_code(code)
        label = str(names or "").replace(",", "、").strip()
        if c and label:
            out[c] = label
    return out


def enrich_items_with_ths_industry(
    db,
    items: List[Dict[str, Any]],
    *,
    force: bool = False,
) -> None:
    """为结果行填充同花顺行业「所属板块」；force=True 时覆盖已有标签。"""
    if not items:
        return
    need = [
        r.get("code")
        for r in items
        if r.get("code") and (force or not str(r.get("board_labels") or "").strip())
    ]
    if not need:
        return
    labels = batch_ths_industry_labels(db, need)
    if not labels:
        return
    for r in items:
        code = normalize_a_code(r.get("code"))
        label = labels.get(code)
        if not label:
            continue
        if force or not str(r.get("board_labels") or "").strip():
            r["board_labels"] = label


def resolve_stock_pool(
    db,
    *,
    stock_pool_mode: str,
    industry_board_codes: Optional[Sequence[Any]] = None,
    concept_board_codes: Optional[Sequence[Any]] = None,
    stock_codes: Optional[Sequence[Any]] = None,
    universe_limit: Optional[int] = None,
) -> Dict[str, Any]:
    """解析股票池。

    返回:
      codes, board_codes, boards_by_code, mode, scope_meta
    """
    mode = (stock_pool_mode or "stocks").strip().lower()
    boards_by: Dict[str, List[Dict[str, str]]] = {}
    board_codes: List[str] = []

    if mode == "industry_board":
        board_codes, codes, boards_by = resolve_industry_pool(db, industry_board_codes or [])
    elif mode == "concept_board":
        board_codes, codes, boards_by = resolve_concept_pool(db, concept_board_codes or [])
    elif mode == "market":
        codes = resolve_market_pool(db, limit=universe_limit)
    elif mode == "stocks":
        codes = normalize_code_list(stock_codes)
    else:
        raise ValueError(f"不支持的 stock_pool_mode: {mode}")

    scope_meta = {
        "stock_pool_mode": mode,
        "board_codes": list(board_codes),
        "stock_count": len(codes),
        "universe_limit": universe_limit,
    }
    return {
        "codes": codes,
        "board_codes": board_codes,
        "boards_by_code": boards_by,
        "mode": mode,
        "scope_meta": scope_meta,
    }
