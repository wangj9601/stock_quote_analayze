"""五·三·二仓位建议。"""

from __future__ import annotations

from typing import Any, Dict, Optional


def advise_position(
    *,
    current_stage: Optional[str],
    allocated_pct: float,
    open_positions: int,
    total_capital: Optional[float],
    has_new_support: bool,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    pcfg = (config or {}).get("position") or {}
    probe = float(pcfg.get("probe_pct", 50))
    add = float(pcfg.get("add_pct", 30))
    reserve = float(pcfg.get("reserve_cash_pct", 20))
    max_pos = int(pcfg.get("max_open_positions", 3))
    small_max = int(pcfg.get("small_capital_max_positions", 2))
    small_th = float(pcfg.get("small_capital_threshold", 1_000_000))

    if total_capital is not None and total_capital < small_th:
        max_pos = min(max_pos, small_max)

    can_open = open_positions < max_pos
    stage = (current_stage or "").strip().lower() or None
    next_action = "hold"
    next_pct = 0.0
    message = ""

    if stage is None:
        if can_open:
            next_action = "probe"
            next_pct = probe
            message = f"确认弱转强后试探配置 {probe:.0f}%"
        else:
            next_action = "blocked"
            message = f"已达最大同时持仓数 {max_pos}"
    elif stage in ("probe", "trial"):
        if has_new_support and allocated_pct + add <= (100.0 - reserve + 1e-6):
            next_action = "add"
            next_pct = add
            message = f"上方新支撑确认后可追加 {add:.0f}%"
        else:
            next_action = "hold_probe"
            message = "等待上方稳固支撑后再追加"
    elif stage == "add":
        next_action = "hold_reserve"
        message = f"已完成加仓，保留现金 {reserve:.0f}% 不作满仓"
    else:
        next_action = "hold"
        message = "维持现有仓位"

    max_alloc = 100.0 - reserve
    return {
        "probe_pct": probe,
        "add_pct": add,
        "reserve_cash_pct": reserve,
        "max_open_positions": max_pos,
        "max_allocated_pct": max_alloc,
        "can_open": can_open,
        "next_action": next_action,
        "next_pct": next_pct,
        "message": message,
        "allocated_pct": float(allocated_pct or 0),
        "stage": stage,
    }
