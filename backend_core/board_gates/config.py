# -*- coding: utf-8 -*-
"""板块入场闸门常量与默认开关。"""

from __future__ import annotations

import os
from typing import Any, Dict

GATE_ALLOC = "可配"
GATE_WATCH = "观望"
GATE_AVOID = "回避"

RAW_ALLOC = "alloc"
RAW_AVOID = "avoid"
RAW_WATCH = "watch"

SHORT_CONFIRM_DAYS = 2
MIDLONG_CONFIRM_DAYS = 3

BOARD_RS_ALLOC_MIN = 70
BOARD_RS_WATCH_MAX = 69  # 50–69 → 最高观望
BOARD_RS_AVOID_MAX = 29
BOARD_RS_EXPENSIVE_BYPASS = 80  # 极贵时 RS>=80 可不因估值封顶

VALUATION_COVERAGE_MIN = 0.50
VALUATION_EXPENSIVE_PCT = 0.90
VALUATION_CHEAP_PCT = 0.20

FUND_STAGES_BLOCK_MIDLONG = frozenset({"distribute", "decline"})

TREND_BLOCK_MIDLONG_ALLOC = frozenset({"长弱短强"})
TREND_ALLOW_MIDLONG_ALLOC = frozenset(
    {"全面走强", "中强短修", "长强短弱", "中强短加速"}
)
TREND_AVOID_MIDLONG = frozenset({"全面走弱", "下行加速", "中弱延续"})

DEFAULT_BOARD_CODE_SOURCE = "tonghuashun"

# 策略硬过滤：默认 shadow（只提示不拦截）
HARD_FILTER_ENV = "BOARD_GATE_HARD_FILTER"


def hard_filter_enabled(config: Dict[str, Any] | None = None) -> bool:
    """是否对「回避」做硬过滤。默认 False（shadow）。"""
    if config:
        br = config.get("board_gate") or config.get("board_resonance") or {}
        if isinstance(br, dict) and "hard_filter_enabled" in br:
            return bool(br.get("hard_filter_enabled"))
        if isinstance(br, dict) and "board_gate_hard_filter" in br:
            return bool(br.get("board_gate_hard_filter"))
    env = (os.environ.get(HARD_FILTER_ENV) or "").strip().lower()
    return env in ("1", "true", "yes", "on")


def v2_layers_enabled(config: Dict[str, Any] | None = None) -> bool:
    if config:
        br = config.get("board_gate") or {}
        if isinstance(br, dict) and "v2_enabled" in br:
            return bool(br.get("v2_enabled"))
    env = (os.environ.get("BOARD_GATE_V2") or "1").strip().lower()
    return env not in ("0", "false", "no", "off")


STATE_LABELS = {
    GATE_ALLOC: GATE_ALLOC,
    GATE_WATCH: GATE_WATCH,
    GATE_AVOID: GATE_AVOID,
}

RAW_TO_STATE = {
    RAW_ALLOC: GATE_ALLOC,
    RAW_AVOID: GATE_AVOID,
    RAW_WATCH: GATE_WATCH,
}
