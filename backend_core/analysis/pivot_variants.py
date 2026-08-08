# -*- coding: utf-8 -*-
"""Camarilla 与 ATR-Pivot 波动率修正（参考用）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from backend_core.analysis.swing_zigzag import wilder_atr

PRICE_DECIMALS = 2


def _nearest_below(levels: Sequence[float], price: float) -> Optional[float]:
    below = [x for x in levels if x is not None and x < price]
    return max(below) if below else None


def _nearest_above(levels: Sequence[float], price: float) -> Optional[float]:
    above = [x for x in levels if x is not None and x > price]
    return min(above) if above else None


def camarilla_from_hlc(high: float, low: float, close: float) -> Dict[str, Any]:
    h, l, c = float(high), float(low), float(close)
    rng = h - l
    d = PRICE_DECIMALS
    return {
        "method": "camarilla",
        "H": round(h, d),
        "L": round(l, d),
        "C": round(c, d),
        "R4": round(c + rng * 1.1 / 2.0, d),
        "R3": round(c + rng * 1.1 / 4.0, d),
        "R2": round(c + rng * 1.1 / 6.0, d),
        "R1": round(c + rng * 1.1 / 12.0, d),
        "S1": round(c - rng * 1.1 / 12.0, d),
        "S2": round(c - rng * 1.1 / 6.0, d),
        "S3": round(c - rng * 1.1 / 4.0, d),
        "S4": round(c - rng * 1.1 / 2.0, d),
    }


def atr_pivot_bands(pivot_p: float, atr: float) -> Dict[str, Any]:
    p = float(pivot_p)
    a = float(atr)
    d = PRICE_DECIMALS
    return {
        "method": "atr_pivot",
        "P": round(p, d),
        "atr": round(a, d),
        "R1": round(p + 1.0 * a, d),
        "S1": round(p - 1.0 * a, d),
        "R2": round(p + 2.0 * a, d),
        "S2": round(p - 2.0 * a, d),
    }


def attach_nearest(
    levels: Dict[str, Any],
    last_close: Optional[float],
    keys: Sequence[str],
) -> Dict[str, Any]:
    out = dict(levels)
    if last_close is None:
        out["nearest_support"] = None
        out["nearest_resistance"] = None
        return out
    vals: List[float] = []
    for k in keys:
        try:
            v = out.get(k)
            if v is not None:
                vals.append(float(v))
        except (TypeError, ValueError):
            continue
    ns = _nearest_below(vals, float(last_close))
    nr = _nearest_above(vals, float(last_close))
    out["nearest_support"] = round(ns, PRICE_DECIMALS) if ns is not None else None
    out["nearest_resistance"] = round(nr, PRICE_DECIMALS) if nr is not None else None
    return out


def compute_vol_pivots_from_parsed(
    parsed: Sequence[tuple],
    *,
    last_close: Optional[float],
    classic_p: Optional[float] = None,
) -> Dict[str, Any]:
    """parsed: List[(date, high, low, close)] 升序。"""
    empty = {"camarilla": None, "atr_pivot": None, "atr": None}
    if len(parsed) < 2:
        return empty
    prev = parsed[-2]
    h, l, c = prev[1], prev[2], prev[3]
    cam = camarilla_from_hlc(h, l, c)
    cam["trade_date"] = prev[0].isoformat() if hasattr(prev[0], "isoformat") else str(prev[0])
    cam = attach_nearest(
        cam,
        last_close,
        ("S4", "S3", "S2", "S1", "R1", "R2", "R3", "R4"),
    )

    atr = wilder_atr(parsed)
    atr_piv = None
    if atr is not None and atr > 0:
        p = float(classic_p) if classic_p is not None else (h + l + c) / 3.0
        atr_piv = atr_pivot_bands(p, atr)
        atr_piv["trade_date"] = cam["trade_date"]
        atr_piv = attach_nearest(atr_piv, last_close, ("S2", "S1", "P", "R1", "R2"))

    return {
        "camarilla": cam,
        "atr_pivot": atr_piv,
        "atr": round(float(atr), PRICE_DECIMALS) if atr is not None else None,
    }
