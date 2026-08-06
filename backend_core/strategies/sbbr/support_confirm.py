"""上方支撑确认：试探仓加仓门闩。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _f(v) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _ma(closes: List[float], period: int) -> Optional[float]:
    if period <= 0 or len(closes) < period:
        return None
    window = closes[-period:]
    if any(c <= 0 for c in window):
        return None
    return sum(window) / float(period)


def evaluate_support_confirm(
    *,
    close: float,
    defense_low: float,
    defense_breached: bool,
    nearest_support: Optional[float],
    kde_ok: bool,
    box_resistance: Optional[float],
    bars: Optional[List[Dict[str, Any]]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    上方支撑确认（加仓门闩）为 True 当且仅当：
    1) 防守未破位
    2) KDE 有效且 close > nearest_support
    3) 箱体：有 box_resistance 则 close >= resistance*(1-tol)；
       无阻力（如黄金坑）则 close >= MA20
    """
    scfg = (config or {}).get("support_confirm") or {}
    tol = float(scfg.get("box_resistance_tol_pct", 0.01))
    ma_period = int(scfg.get("ma_period", 20))

    reasons: List[str] = []
    ns = _f(nearest_support)
    box_res = _f(box_resistance)

    closes: List[float] = []
    if bars:
        for b in bars:
            c = _f(b.get("close"))
            if c is not None:
                closes.append(c)
    ma20 = _ma(closes, ma_period)

    if defense_breached or close < float(defense_low or 0):
        reasons.append("defense_breached")

    kde_hold = bool(kde_ok) and ns is not None and close > ns
    if not kde_ok:
        reasons.append("kde_not_ok")
    elif ns is None:
        reasons.append("no_nearest_support")
    elif close <= ns:
        reasons.append("below_nearest_support")

    if box_res is not None and box_res > 0:
        threshold = box_res * (1.0 - tol)
        box_ok = close >= threshold
        if not box_ok:
            reasons.append("below_box_resistance")
    else:
        box_ok = ma20 is not None and close >= ma20
        if ma20 is None:
            reasons.append("no_ma20")
        elif close < ma20:
            reasons.append("below_ma20")

    confirmed = len(reasons) == 0
    return {
        "confirmed": confirmed,
        "reason": "ok" if confirmed else reasons[0],
        "reasons": reasons,
        "box_ok": box_ok,
        "kde_hold": kde_hold,
        "ma20": ma20,
        "nearest_support": ns,
        "box_resistance": box_res,
        "tol_pct": tol,
    }
