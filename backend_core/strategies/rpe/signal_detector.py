"""信号组装：catch_up / lead。"""

from __future__ import annotations

from typing import Any, Dict, Optional


def detect_signal(
    *,
    z_score: Optional[float],
    sector_slope: Optional[float],
    structure_valid: bool,
    liquidity_ok: bool,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    z_lead = float(config.get("z_lead", 2.0))
    z_catch = float(config.get("z_catch_up", -1.5))
    enable_veto = bool(config.get("enable_trend_veto", True))
    enable_lead_trade = bool(config.get("enable_lead_trade", False))

    veto = False
    if enable_veto and sector_slope is not None and float(sector_slope) < 0:
        veto = True

    signal_type = None
    entry_signal = False
    watch_only = False

    if z_score is None:
        return {
            "signal_type": None,
            "entry_signal": False,
            "watch_only": False,
            "trend_veto": veto,
            "reason": "no_z",
        }

    z = float(z_score)
    if z <= z_catch:
        signal_type = "catch_up"
        if not veto and structure_valid and liquidity_ok:
            entry_signal = True
            reason = "catch_up_ok"
        else:
            reason = "catch_up_filtered"
            watch_only = True
    elif z >= z_lead:
        signal_type = "lead"
        if enable_lead_trade and not veto and structure_valid and liquidity_ok:
            entry_signal = True
            reason = "lead_trade_ok"
        else:
            watch_only = True
            reason = "lead_watch"
    else:
        reason = "in_band"

    return {
        "signal_type": signal_type,
        "entry_signal": entry_signal,
        "watch_only": watch_only,
        "trend_veto": veto,
        "reason": reason,
    }
