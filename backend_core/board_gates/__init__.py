# -*- coding: utf-8 -*-
"""板块中长线/短线入场闸门（v1+v2）。"""

from backend_core.board_gates.compute_daily import (
    compute_board_gates_for_date,
    run_board_gates_daily,
)
from backend_core.board_gates.config import (
    GATE_ALLOC,
    GATE_AVOID,
    GATE_WATCH,
    hard_filter_enabled,
)
from backend_core.board_gates.strategy_filter import enrich_items_with_board_gate

__all__ = [
    "GATE_ALLOC",
    "GATE_AVOID",
    "GATE_WATCH",
    "compute_board_gates_for_date",
    "run_board_gates_daily",
    "enrich_items_with_board_gate",
    "hard_filter_enabled",
]
