# -*- coding: utf-8 -*-
"""策略侧闸门接入：shadow 标注 / 可选硬过滤。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from backend_core.board_gates.config import (
    DEFAULT_BOARD_CODE_SOURCE,
    GATE_AVOID,
    GATE_WATCH,
    hard_filter_enabled,
)
from backend_core.board_gates.storage import load_board_gates_for_date, resolve_asof_trade_date

logger = logging.getLogger(__name__)


def enrich_items_with_board_gate(
    db,
    items: Sequence[Dict[str, Any]],
    *,
    trade_date: Optional[str] = None,
    board_code_key: str = "board_code",
    board_kind: str = "industry",
    config: Optional[Dict[str, Any]] = None,
    drop_avoid_on_hard_filter: bool = True,
) -> List[Dict[str, Any]]:
    """
    为策略结果附加 board_gate_* 字段。
    hard_filter 开启且 short/midlong 为回避时：标记 blocked，并可剔除。
    """
    asof = resolve_asof_trade_date(db, trade_date)
    codes = []
    for it in items:
        c = str(it.get(board_code_key) or it.get("industry_board_code") or "").strip()
        if c:
            codes.append(c)
    if not items:
        return []
    gates = (
        load_board_gates_for_date(
            db, asof, board_kind=board_kind, board_codes=codes
        )
        if codes
        else {}
    )
    hard = hard_filter_enabled(config)
    out: List[Dict[str, Any]] = []
    for it in items:
        row = dict(it)
        code = str(
            row.get(board_code_key) or row.get("industry_board_code") or ""
        ).strip()
        g = gates.get(code) or {}
        short_s = g.get("short_state")
        mid_s = g.get("midlong_state")
        row["board_gate_trade_date"] = asof
        row["board_gate_short"] = short_s
        row["board_gate_midlong"] = mid_s
        row["board_gate_conflict"] = g.get("conflict_action")
        row["board_gate_shadow_hint"] = g.get("shadow_hard_filter_hint")
        row["board_gate_hard_filter"] = hard

        blocked = False
        downweight = False
        if short_s == GATE_AVOID or mid_s == GATE_AVOID:
            if hard:
                blocked = True
            row["board_gate_would_block"] = True
        if short_s == GATE_WATCH or mid_s == GATE_WATCH:
            downweight = True
            row["board_gate_downweight"] = True

        row["board_gate_blocked"] = blocked
        if blocked and drop_avoid_on_hard_filter:
            continue
        if downweight and not blocked:
            # soft：附加风险标签，不改分（shadow/硬开前一致展示）
            tags = list(row.get("risk_tags") or [])
            tags.append(
                {
                    "id": "board_gate_watch",
                    "label": "板块闸门观望",
                    "points": 0 if not hard else 5,
                }
            )
            row["risk_tags"] = tags
        out.append(row)
    return out
