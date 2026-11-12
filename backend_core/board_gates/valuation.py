# -*- coding: utf-8 -*-
"""v2.3 板级估值聚合（成分 PE/PB/ROE 中位数 + 观察池分位）。"""

from __future__ import annotations

import logging
import statistics
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import bindparam, text

from backend_core.board_gates.config import VALUATION_COVERAGE_MIN
from backend_core.indicators.rs_rating.calculator import percentile_ranks_0_1

logger = logging.getLogger(__name__)


def _f(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        x = float(v)
        if x != x:  # NaN
            return None
        return x
    except (TypeError, ValueError):
        return None


def _median(vals: Sequence[float]) -> Optional[float]:
    if not vals:
        return None
    return float(statistics.median(vals))


def _trim_extremes(vals: Sequence[float], *, lo_pct: float = 0.05, hi_pct: float = 0.95) -> List[float]:
    xs = sorted(float(v) for v in vals)
    if len(xs) < 5:
        return xs
    lo_i = int(len(xs) * lo_pct)
    hi_i = max(lo_i + 1, int(len(xs) * hi_pct))
    return xs[lo_i:hi_i]


def load_industry_constituents(
    db, board_codes: Sequence[str]
) -> Dict[str, List[str]]:
    codes = [str(c).strip() for c in board_codes if c]
    out: Dict[str, List[str]] = {c: [] for c in codes}
    if not codes:
        return out
    try:
        rows = db.execute(
            text(
                """
                SELECT board_code, stock_code
                FROM industry_board_constituents
                WHERE board_code IN :codes
                """
            ).bindparams(bindparam("codes", expanding=True)),
            {"codes": codes},
        ).fetchall()
        for bc, sc in rows:
            b = str(bc or "").strip()
            s = str(sc or "").strip()
            if b in out and s:
                out[b].append(s)
    except Exception as e:
        logger.warning("load_industry_constituents failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
    return out


def load_stock_pe_pb(db, stock_codes: Sequence[str]) -> Dict[str, Dict[str, Optional[float]]]:
    """优先实时表最新 pe_dynamic / pb_ratio。"""
    codes = [str(c).strip() for c in stock_codes if c]
    out: Dict[str, Dict[str, Optional[float]]] = {}
    if not codes:
        return out
    # 分批
    chunk = 500
    try:
        for i in range(0, len(codes), chunk):
            part = codes[i : i + chunk]
            rows = db.execute(
                text(
                    """
                    SELECT DISTINCT ON (code)
                           code, pe_dynamic, pb_ratio
                    FROM stock_realtime_quote
                    WHERE code IN :codes
                    ORDER BY code, trade_date DESC NULLS LAST, update_time DESC NULLS LAST
                    """
                ).bindparams(bindparam("codes", expanding=True)),
                {"codes": part},
            ).fetchall()
            for code, pe, pb in rows:
                out[str(code).strip()] = {"pe": _f(pe), "pb": _f(pb)}
    except Exception as e:
        logger.warning("load_stock_pe_pb failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
    return out


def load_stock_roe(db, stock_codes: Sequence[str]) -> Dict[str, Optional[float]]:
    """可选：财务 ROE；表结构差异时静默跳过。"""
    codes = [str(c).strip() for c in stock_codes if c]
    out: Dict[str, Optional[float]] = {}
    if not codes:
        return out
    chunk = 400
    try:
        for i in range(0, len(codes), chunk):
            part = codes[i : i + chunk]
            rows = db.execute(
                text(
                    """
                    SELECT DISTINCT ON (code6)
                           RIGHT(REGEXP_REPLACE(ts_code, '[^0-9]', '', 'g'), 6) AS code6,
                           roe
                    FROM stock_fina_indicator
                    WHERE RIGHT(REGEXP_REPLACE(ts_code, '[^0-9]', '', 'g'), 6) IN :codes
                    ORDER BY code6, end_date DESC NULLS LAST
                    """
                ).bindparams(bindparam("codes", expanding=True)),
                {"codes": part},
            ).fetchall()
            for code6, roe in rows:
                c = str(code6 or "").strip()
                if c:
                    out[c] = _f(roe)
    except Exception as e:
        logger.debug("load_stock_roe failed (optional): %s", e)
        try:
            db.rollback()
        except Exception:
            pass
    return out


def aggregate_board_valuation(
    db,
    board_metas: Sequence[Dict[str, Any]],
    *,
    trade_date: str,
    board_kind: str = "industry",
) -> List[Dict[str, Any]]:
    """仅行业板；观察池内算 pe_pct/pb_pct。"""
    codes = [str(m.get("board_code") or "").strip() for m in board_metas]
    codes = [c for c in codes if c]
    cons = load_industry_constituents(db, codes)
    all_stocks: List[str] = []
    for lst in cons.values():
        all_stocks.extend(lst)
    all_stocks = sorted(set(all_stocks))
    pe_pb = load_stock_pe_pb(db, all_stocks)
    roe_map = load_stock_roe(db, all_stocks)

    board_rows: List[Dict[str, Any]] = []
    for m in board_metas:
        code = str(m.get("board_code") or "").strip()
        if not code:
            continue
        members = cons.get(code) or []
        pe_vals: List[float] = []
        pb_vals: List[float] = []
        roe_vals: List[float] = []
        for sc in members:
            q = pe_pb.get(sc) or {}
            pe = q.get("pe")
            pb = q.get("pb")
            if pe is not None and pe > 0:
                pe_vals.append(pe)
            if pb is not None and pb > 0:
                pb_vals.append(pb)
            rv = roe_map.get(sc)
            if rv is not None:
                roe_vals.append(rv)

        n_mem = len(members)
        valid_pe = len(pe_vals)
        coverage = (valid_pe / n_mem) if n_mem else 0.0
        unknown = coverage < VALUATION_COVERAGE_MIN
        pe_med = _median(_trim_extremes(pe_vals)) if pe_vals else None
        pb_med = _median(_trim_extremes(pb_vals)) if pb_vals else None
        roe_med = _median(roe_vals) if roe_vals else None
        board_rows.append(
            {
                "board_kind": board_kind,
                "board_code": code,
                "trade_date": trade_date[:10],
                "board_pe_median": pe_med,
                "board_pb_median": pb_med,
                "board_roe_median": roe_med,
                "pe_pct": None,
                "pb_pct": None,
                "coverage_ratio": float(coverage),
                "valuation_unknown": bool(unknown),
                "member_count": n_mem,
                "valid_pe_count": valid_pe,
                "trade_observe_flag": bool(m.get("trade_observe_flag")),
            }
        )

    # 观察池横截面分位
    obs = [r for r in board_rows if r.get("trade_observe_flag") and not r.get("valuation_unknown")]
    pe_list = [r.get("board_pe_median") for r in obs]
    pb_list = [r.get("board_pb_median") for r in obs]
    pe_pcts = percentile_ranks_0_1(pe_list)
    pb_pcts = percentile_ranks_0_1(pb_list)
    for r, pp, bp in zip(obs, pe_pcts, pb_pcts):
        r["pe_pct"] = pp
        r["pb_pct"] = bp

    for r in board_rows:
        r.pop("trade_observe_flag", None)
    return board_rows
