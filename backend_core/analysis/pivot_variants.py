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


def extreme_role_flip_note(
    *,
    side: str,
    level_key: str,
    price: float,
    label: str = "Camarilla",
    decimals: int = PRICE_DECIMALS,
) -> str:
    """极端档破位 → 角色反转标准文案。

    side:
      - below_support：跌破最低支撑档（如 S4）→ 转为阻力
      - above_resistance：突破最高阻力档（如 R4）→ 转为支撑
    """
    d = int(decimals)
    px = float(price)
    key = str(level_key)
    if side == "below_support":
        return f"已跌破{label}最低档{key}({px:.{d}f})并转为阻力"
    if side == "above_resistance":
        return f"已突破{label}最高档{key}({px:.{d}f})并转为支撑"
    raise ValueError(f"unsupported role-flip side: {side}")


def attach_nearest(
    levels: Dict[str, Any],
    last_close: Optional[float],
    keys: Sequence[str],
    *,
    label: str = "同窗",
    role_flip_extremes: Optional[tuple] = None,
) -> Dict[str, Any]:
    """标注最近支撑/阻力；可选对极端档启用「破位→角色反转」文案。

    role_flip_extremes: (最低支撑键, 最高阻力键)，如 Camarilla 的 ("S4", "R4")。
    未指定或破的不是该极端档时，仍用「暂无同窗支撑/压力」真空口径。
    """
    out = dict(levels)
    out["support_note"] = None
    out["resistance_note"] = None
    out["extreme_role_flip"] = None
    if last_close is None:
        out["nearest_support"] = None
        out["nearest_resistance"] = None
        return out
    vals: List[float] = []
    keyed: List[tuple] = []
    for k in keys:
        try:
            v = out.get(k)
            if v is not None:
                fv = float(v)
                vals.append(fv)
                keyed.append((k, fv))
        except (TypeError, ValueError):
            continue
    ns = _nearest_below(vals, float(last_close))
    nr = _nearest_above(vals, float(last_close))
    out["nearest_support"] = round(ns, PRICE_DECIMALS) if ns is not None else None
    out["nearest_resistance"] = round(nr, PRICE_DECIMALS) if nr is not None else None
    d = PRICE_DECIMALS
    px = float(last_close)
    flip_lo = flip_hi = None
    if isinstance(role_flip_extremes, (tuple, list)) and len(role_flip_extremes) >= 2:
        flip_lo, flip_hi = str(role_flip_extremes[0]), str(role_flip_extremes[1])
    if nr is None and keyed:
        top_k, top_v = max(keyed, key=lambda x: x[1])
        if px > top_v:
            if flip_hi and top_k == flip_hi:
                out["resistance_note"] = extreme_role_flip_note(
                    side="above_resistance",
                    level_key=top_k,
                    price=top_v,
                    label=label,
                    decimals=d,
                )
                out["extreme_role_flip"] = {
                    "level": top_k,
                    "price": round(top_v, d),
                    "from_role": "resistance",
                    "to_role": "support",
                    "side": "above_resistance",
                }
            else:
                out["resistance_note"] = (
                    f"已突破{label}最高档{top_k}({top_v:.{d}f})，上方暂无同窗压力"
                )
    if ns is None and keyed:
        bot_k, bot_v = min(keyed, key=lambda x: x[1])
        if px < bot_v:
            if flip_lo and bot_k == flip_lo:
                out["support_note"] = extreme_role_flip_note(
                    side="below_support",
                    level_key=bot_k,
                    price=bot_v,
                    label=label,
                    decimals=d,
                )
                out["extreme_role_flip"] = {
                    "level": bot_k,
                    "price": round(bot_v, d),
                    "from_role": "support",
                    "to_role": "resistance",
                    "side": "below_support",
                }
            else:
                out["support_note"] = (
                    f"已跌破{label}最低档{bot_k}({bot_v:.{d}f})，下方暂无同窗支撑"
                )
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
        label="Camarilla",
        role_flip_extremes=("S4", "R4"),
    )

    atr = wilder_atr(parsed)
    atr_piv = None
    if atr is not None and atr > 0:
        p = float(classic_p) if classic_p is not None else (h + l + c) / 3.0
        atr_piv = atr_pivot_bands(p, atr)
        atr_piv["trade_date"] = cam["trade_date"]
        atr_piv = attach_nearest(
            atr_piv, last_close, ("S2", "S1", "P", "R1", "R2"), label="ATR-Pivot"
        )

    return {
        "camarilla": cam,
        "atr_pivot": atr_piv,
        "atr": round(float(atr), PRICE_DECIMALS) if atr is not None else None,
    }
