"""趋势否决、结构过滤、流动性过滤。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence


def trend_veto(sector_slope: Optional[float], enabled: bool = True) -> bool:
    """返回 True 表示应否决（禁止入选）。"""
    if not enabled:
        return False
    if sector_slope is None:
        return False
    return float(sector_slope) < 0


def structure_filter(
    price: float,
    nearest_support: Optional[float],
    nearest_resistance: Optional[float],
    *,
    min_rr: float = 1.5,
) -> Dict[str, Any]:
    """
    现价须在支撑之上；距阻力的上行空间 / 距支撑的下行空间 >= min_rr。
    """
    if nearest_support is None or price <= float(nearest_support):
        return {"structure_valid": False, "rr": None, "reason": "below_or_no_support"}
    downside = price - float(nearest_support)
    if downside <= 0:
        return {"structure_valid": False, "rr": None, "reason": "zero_downside"}
    if nearest_resistance is None:
        # 无上方阻力时认为空间充足
        return {"structure_valid": True, "rr": None, "reason": "no_resistance"}
    upside = float(nearest_resistance) - price
    if upside <= 0:
        return {"structure_valid": False, "rr": 0.0, "reason": "at_resistance"}
    rr = upside / downside
    ok = rr >= float(min_rr)
    return {
        "structure_valid": ok,
        "rr": rr,
        "reason": "ok" if ok else "rr_too_small",
    }


def liquidity_ok(
    bars: List[Dict[str, Any]],
    *,
    lookback: int = 20,
    min_avg_amount: float = 5_000_000.0,
    min_avg_turnover_rate: float = 0.5,
) -> Dict[str, Any]:
    if not bars:
        return {"liquidity_ok": False, "reason": "no_bars"}
    window = bars[-max(5, int(lookback)) :]
    amounts = []
    turnovers = []
    for b in window:
        a = b.get("amount")
        if a is not None:
            try:
                amounts.append(float(a))
            except (TypeError, ValueError):
                pass
        tr = b.get("turnover_rate")
        if tr is not None:
            try:
                turnovers.append(float(tr))
            except (TypeError, ValueError):
                pass
    avg_amt = sum(amounts) / len(amounts) if amounts else 0.0
    avg_tr = sum(turnovers) / len(turnovers) if turnovers else 0.0
    ok = avg_amt >= float(min_avg_amount)
    if turnovers:
        ok = ok and avg_tr >= float(min_avg_turnover_rate)
    return {
        "liquidity_ok": ok,
        "avg_amount": avg_amt,
        "avg_turnover_rate": avg_tr,
        "reason": "ok" if ok else "thin_liquidity",
    }


def structure_break(close: float, structure_support: Optional[float]) -> bool:
    """收盘跌破结构支撑 = 破位。"""
    if structure_support is None:
        return False
    return float(close) < float(structure_support)
