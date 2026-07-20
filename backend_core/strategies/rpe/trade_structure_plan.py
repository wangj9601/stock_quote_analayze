"""观察/正式交易用的结构价位计划（禁止固定百分比止损）。"""

from __future__ import annotations

from typing import Any, Dict, Optional


def build_structure_plan(
    *,
    entry_price: float,
    nearest_support: Optional[float],
    nearest_resistance: Optional[float],
) -> Dict[str, Any]:
    return {
        "entry_price": float(entry_price),
        "structure_support": nearest_support,
        "structure_resistance": nearest_resistance,
        "exit_rule": "structure_break",
        "note": "离场仅依据收盘跌破结构支撑，不使用固定百分比止损",
    }
