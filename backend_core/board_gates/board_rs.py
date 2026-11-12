# -*- coding: utf-8 -*-
"""v2.2 板级相对强度（IBD 公式，板指数截面）。

指数日 K 不足时 rs_raw 为空（中长线不得升可配）；等权回退留待数据面统一后再接。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Set

from backend_core.board_metrics.sector_slope_store import (
    DEFAULT_LOOKBACK,
    SLOPE_SOURCE_THS_INDEX,
    load_board_index_closes,
)
from backend_core.indicators.rs_rating.calculator import (
    compute_rs_raw,
    rank_cross_section,
)

logger = logging.getLogger(__name__)

BOARD_RS_LOOKBACK = max(DEFAULT_LOOKBACK, 280)


def _closes_from_index(rows: Sequence[Dict[str, Any]]) -> List[float]:
    out: List[float] = []
    for r in rows:
        try:
            c = float(r.get("close"))
        except (TypeError, ValueError):
            continue
        if c > 0:
            out.append(c)
    return out


def compute_board_rs_raw_for_code(
    db,
    board_code: str,
    *,
    board_kind: str = "industry",
    trade_date: Optional[str] = None,
) -> Dict[str, Any]:
    code = str(board_code or "").strip()
    raw_idx = load_board_index_closes(
        db,
        code,
        board_kind=board_kind,
        end_date=trade_date,
        lookback=BOARD_RS_LOOKBACK,
    )
    closes = _closes_from_index(raw_idx)
    detail = compute_rs_raw(closes) if closes else None
    if not detail:
        return {
            "board_code": code,
            "board_kind": board_kind,
            "rs_raw": None,
            "rs_source": SLOPE_SOURCE_THS_INDEX,
        }
    return {
        "board_code": code,
        "board_kind": board_kind,
        "rs_raw": float(detail["rs_raw"]),
        "rs_source": SLOPE_SOURCE_THS_INDEX,
        **{k: v for k, v in detail.items() if k != "rs_raw"},
    }


def compute_and_rank_board_rs(
    db,
    board_metas: Sequence[Dict[str, Any]],
    *,
    trade_date: str,
    board_kind: str = "industry",
) -> List[Dict[str, Any]]:
    """board_metas: [{board_code, trade_observe_flag?, ...}]"""
    raw_rows: List[Dict[str, Any]] = []
    observe_codes: Set[str] = set()
    for m in board_metas:
        code = str(m.get("board_code") or "").strip()
        if not code:
            continue
        if m.get("trade_observe_flag"):
            observe_codes.add(code)
        item = compute_board_rs_raw_for_code(
            db, code, board_kind=board_kind, trade_date=trade_date
        )
        raw_rows.append(item)

    valid = [r for r in raw_rows if r.get("rs_raw") is not None]
    ranked = rank_cross_section(valid, publish_ratings=True)
    by_code = {str(r["board_code"]): r for r in ranked}

    obs = [r for r in ranked if str(r["board_code"]) in observe_codes]
    if obs:
        obs_ranked = rank_cross_section(
            [{"board_code": r["board_code"], "rs_raw": r["rs_raw"]} for r in obs],
            publish_ratings=True,
        )
        obs_map = {str(r["board_code"]): r.get("rs_rating") for r in obs_ranked}
    else:
        obs_map = {}

    out: List[Dict[str, Any]] = []
    for m in board_metas:
        code = str(m.get("board_code") or "").strip()
        if not code:
            continue
        base = by_code.get(code) or next(
            (r for r in raw_rows if r.get("board_code") == code), {}
        )
        out.append(
            {
                "board_kind": board_kind,
                "board_code": code,
                "trade_date": trade_date[:10],
                "rs_raw": base.get("rs_raw"),
                "rs_rating": base.get("rs_rating"),
                "rs_observe": obs_map.get(code),
                "rs_source": base.get("rs_source") or SLOPE_SOURCE_THS_INDEX,
                "universe": "industry_all",
                "member_rs_median": None,
            }
        )
    return out
