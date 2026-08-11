# -*- coding: utf-8 -*-
"""形态扫描：股票池解析 + 限量检测。"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from .engine import detect_all, normalize_families

logger = logging.getLogger(__name__)

DEFAULT_SCAN_LIMIT = 100
HARD_SCAN_CAP = 200
DEFAULT_LOOKBACK = 160
DEFAULT_TIMEOUT_SEC = 45.0


def resolve_scan_codes(
    db: Session,
    *,
    scope: str = "market",
    board_codes: Optional[Sequence[str]] = None,
    board_kind: str = "industry",
    board_code_source: str = "tonghuashun",
    limit: int = DEFAULT_SCAN_LIMIT,
) -> List[str]:
    """解析扫描代码池。scope=market|industry|concept。"""
    from backend_api.utils.board_code_source import LEGACY_EMPTY_AS_EASTMONEY
    from backend_core.strategies.double_bottom.universe import (
        normalize_a_code,
        resolve_concept_pool,
        resolve_industry_pool,
    )

    lim = max(1, min(int(limit or DEFAULT_SCAN_LIMIT), HARD_SCAN_CAP))
    scope_l = (scope or "market").strip().lower()
    boards = [str(c).strip() for c in (board_codes or []) if str(c).strip()]
    codes: List[str] = []

    if scope_l in ("industry", "concept") and boards:
        if scope_l == "concept" or (board_kind or "").lower() == "concept":
            _, codes, _ = resolve_concept_pool(db, boards)
        else:
            _, codes, _ = resolve_industry_pool(db, boards)
        # 再按同花顺来源收紧（若成分表有 source 关联）
        if board_code_source and codes:
            try:
                from backend_api.utils.board_code_source import resolve_board_code_source

                src = resolve_board_code_source(board_code_source)
                table_b = (
                    "concept_board_basic_info"
                    if scope_l == "concept"
                    else "industry_board_basic_info"
                )
                table_c = (
                    "concept_board_constituents"
                    if scope_l == "concept"
                    else "industry_board_constituents"
                )
                sql = text(
                    f"""
                    SELECT DISTINCT c.stock_code
                    FROM {table_c} c
                    JOIN {table_b} b ON b.board_code = c.board_code
                    WHERE c.board_code IN :boards
                      AND COALESCE(NULLIF(TRIM(b.board_code_source), ''), :legacy) = :src
                    """
                ).bindparams(bindparam("boards", expanding=True))
                rows = db.execute(
                    sql,
                    {
                        "boards": boards,
                        "legacy": LEGACY_EMPTY_AS_EASTMONEY,
                        "src": src,
                    },
                ).fetchall()
                filtered = [normalize_a_code(r[0]) for r in rows if normalize_a_code(r[0])]
                if filtered:
                    codes = filtered
            except Exception as e:
                logger.debug("board source filter skip: %s", e)
    else:
        from backend_core.strategies.double_bottom.universe import resolve_market_pool

        codes = resolve_market_pool(db, limit=lim * 2)

    seen = set()
    out: List[str] = []
    for c in codes:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
        if len(out) >= lim:
            break
    return out


def normalize_price_adjust(adjust: Optional[str]) -> str:
    """价格口径：none | qfq（与 /api/analysis/levels 一致）。"""
    adjust_n = str(adjust or "none").strip().lower() or "none"
    if adjust_n not in ("none", "qfq"):
        raise ValueError("adjust 仅支持 none 或 qfq")
    return adjust_n


def apply_qfq_to_code_bars(
    db: Session,
    code: str,
    bars: List[Dict[str, Any]],
    *,
    refresh_factor: bool = False,
    factor_source: str = "auto",
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """对单票日 K 现算前复权；返回 (bars_qfq, adj_meta)。失败抛 AdjQuotesError。"""
    try:
        from backend_api.utils.adj_quotes import AdjQuotesError, apply_qfq_to_bars, ensure_adj_factors
    except ImportError:
        from utils.adj_quotes import AdjQuotesError, apply_qfq_to_bars, ensure_adj_factors  # type: ignore

    # A 股 / 港股均走 ensure_adj_factors（港股 source=akshare_sina_hk_qfq）
    ensured = ensure_adj_factors(
        db,
        code,
        force_refresh=bool(refresh_factor),
        factor_source=factor_source or "auto",
        prefer_db=True,
    )
    raw_sorted = sorted(
        list(bars or []),
        key=lambda b: str((b or {}).get("date") or ""),
    )
    qfq_bars = apply_qfq_to_bars(raw_sorted, ensured["factors"])
    adj_meta = {
        "source": ensured.get("source"),
        "adj_factor_asof": ensured.get("adj_factor_asof"),
        "factor_fetched": ensured.get("factor_fetched"),
        "factor_source": ensured.get("factor_source"),
    }
    return qfq_bars, adj_meta


def scan_patterns(
    db: Session,
    *,
    scope: str = "market",
    board_codes: Optional[Sequence[str]] = None,
    board_kind: str = "industry",
    types: Optional[Iterable[str]] = None,
    asof: Optional[str] = None,
    lookback: int = DEFAULT_LOOKBACK,
    limit: int = DEFAULT_SCAN_LIMIT,
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
    adjust: str = "none",
    refresh_factor: bool = False,
    factor_source: str = "auto",
) -> Dict[str, Any]:
    """扫描股票池，返回命中列表（含 code/name）。"""
    from backend_core.strategies.double_bottom.data_loader import (
        batch_load_ohlc_asc,
        load_names,
        resolve_effective_trade_date,
    )

    try:
        from backend_api.utils.adj_quotes import AdjQuotesError
    except ImportError:
        from utils.adj_quotes import AdjQuotesError  # type: ignore

    t0 = time.monotonic()
    lim = max(1, min(int(limit or DEFAULT_SCAN_LIMIT), HARD_SCAN_CAP))
    asof_s = resolve_effective_trade_date(db, asof)
    families = sorted(normalize_families(types))
    adjust_n = normalize_price_adjust(adjust)
    codes = resolve_scan_codes(
        db,
        scope=scope,
        board_codes=board_codes,
        board_kind=board_kind,
        limit=lim,
    )
    if not codes:
        return {
            "asof": asof_s,
            "scope": scope,
            "price_adjust": adjust_n,
            "scanned": 0,
            "pool_size": 0,
            "hit_count": 0,
            "truncated": False,
            "timed_out": False,
            "families": families,
            "items": [],
        }

    bars_map = batch_load_ohlc_asc(db, codes, lookback=lookback, asof=asof_s)
    names = load_names(db, codes)
    items: List[Dict[str, Any]] = []
    scanned = 0
    timed_out = False
    for code in codes:
        if time.monotonic() - t0 > float(timeout_sec):
            timed_out = True
            break
        bars = bars_map.get(code) or []
        scanned += 1
        if len(bars) < 30:
            continue
        if adjust_n == "qfq":
            try:
                bars, _meta = apply_qfq_to_code_bars(
                    db,
                    code,
                    bars,
                    refresh_factor=refresh_factor,
                    factor_source=factor_source,
                )
            except AdjQuotesError as e:
                logger.debug("pattern scan qfq skip %s: %s", code, e)
                continue
            except Exception as e:
                logger.debug("pattern scan qfq fail %s: %s", code, e)
                continue
        try:
            hits = detect_all(bars, types=families)
        except Exception as e:
            logger.debug("pattern detect fail %s: %s", code, e)
            continue
        for h in hits:
            row = dict(h)
            row["code"] = code
            row["name"] = names.get(code) or ""
            items.append(row)

    items.sort(
        key=lambda r: (
            -float(r.get("confidence") or 0),
            str(r.get("code") or ""),
            str(r.get("pattern_type") or ""),
        )
    )
    return {
        "asof": asof_s,
        "scope": scope,
        "price_adjust": adjust_n,
        "scanned": scanned,
        "pool_size": len(codes),
        "hit_count": len(items),
        "truncated": len(codes) >= lim,
        "timed_out": timed_out,
        "families": families,
        "items": items,
    }
