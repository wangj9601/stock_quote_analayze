# -*- coding: utf-8 -*-
"""闸门确认粘性：连续 N 日 raw 同向才升可配/回避。"""

from __future__ import annotations

from typing import List, Sequence, Tuple

from backend_core.board_gates.config import (
    GATE_ALLOC,
    GATE_AVOID,
    GATE_WATCH,
    RAW_ALLOC,
    RAW_AVOID,
    RAW_WATCH,
)


def apply_sticky(
    raw_today: str,
    prior_raws_asc: Sequence[str],
    *,
    confirm_days: int,
) -> Tuple[str, int]:
    """
    prior_raws_asc：不含今日、按日期升序的历史 raw。
    返回 (state, confirm_count)。
    """
    need = max(1, int(confirm_days))
    hist = [str(x) for x in prior_raws_asc if x][-(need - 1) :]
    window = hist + [str(raw_today)]
    # 对齐长度：不足时用 watch 填前（不能提前升档）
    while len(window) < need:
        window = [RAW_WATCH] + window
    window = window[-need:]

    if all(x == RAW_ALLOC for x in window):
        return GATE_ALLOC, need
    if all(x == RAW_AVOID for x in window):
        return GATE_AVOID, need

    # 确认进度：末尾连续与今日同向的天数
    streak = 0
    for x in reversed(window):
        if x == raw_today and raw_today in (RAW_ALLOC, RAW_AVOID):
            streak += 1
        else:
            break
    return GATE_WATCH, streak


def conflict_action(midlong_state: str | None, short_state: str | None) -> str:
    ml = midlong_state or ""
    sh = short_state or ""
    if ml == GATE_ALLOC and sh == GATE_AVOID:
        return "hold_no_new"
    if ml == GATE_AVOID and sh == GATE_ALLOC:
        return "ultrashort_only"
    if sh == GATE_AVOID or ml == GATE_AVOID:
        return "block_new_buy"
    if sh == GATE_WATCH or ml == GATE_WATCH:
        return "downweight"
    if sh == GATE_ALLOC or ml == GATE_ALLOC:
        return "full"
    return "neutral"
