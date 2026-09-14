"""场景 regime：range（蓄势）/ trend（主升）。"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from backend_core.recommend.config import (
    REGIME_TREND_SLOPE_MIN,
    strategy_priority_for_regime,
)


def classify_regime(
    *,
    market_slope_20: Optional[float],
    board_slope_20: Optional[float] = None,
) -> Dict[str, Any]:
    """用 20 日斜率划分 range / trend。"""
    slopes = []
    for s in (market_slope_20, board_slope_20):
        if s is None:
            continue
        try:
            slopes.append(float(s))
        except (TypeError, ValueError):
            continue
    ref = max(slopes) if slopes else None
    if ref is not None and ref >= float(REGIME_TREND_SLOPE_MIN):
        regime = "trend"
        note = f"20日斜率 {ref:.6f} ≥ {REGIME_TREND_SLOPE_MIN:g} → trend"
    else:
        regime = "range"
        note = (
            f"20日斜率 {ref:.6f} → range"
            if ref is not None
            else "斜率缺失 → range"
        )
    return {
        "regime": regime,
        "market_slope_20": market_slope_20,
        "board_slope_20": board_slope_20,
        "ref_slope": ref,
        "note": note,
    }


def regime_quality_weights(regime: str) -> Dict[str, float]:
    """质量加权：不删策略，仅倾斜 CSB/GMS。"""
    if regime == "trend":
        return {"gms": 1.25, "csb": 0.75, "urt": 1.0, "sbbr": 1.0, "rpe": 1.0}
    return {"csb": 1.25, "gms": 0.75, "urt": 1.0, "sbbr": 1.0, "rpe": 1.0}


def pick_primary_strategy(strategies: list, regime: str) -> Optional[str]:
    order = strategy_priority_for_regime(regime)
    for s in order:
        if s in (strategies or []):
            return s
    return (strategies or [None])[0]
