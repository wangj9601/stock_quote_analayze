"""弹性防守与三要素退出。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _f(v) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def calc_defense_band(anchor_low: float, config: Dict[str, Any]) -> Dict[str, float]:
    dcfg = (config or {}).get("defense") or {}
    buf = float(dcfg.get("default_buffer_pct", 0.03))
    buf = max(float(dcfg.get("buffer_min_pct", 0.02)), min(float(dcfg.get("buffer_max_pct", 0.05)), buf))
    low = float(anchor_low) * (1.0 - buf)
    high = float(anchor_low)
    return {"defense_low": low, "defense_high": high, "buffer_pct": buf}


def check_defense_breach(
    bars: List[Dict[str, Any]],
    defense_low: float,
) -> Dict[str, Any]:
    """尾盘确认：收盘跌破防守下沿。bars 正序。"""
    if not bars:
        return {"breached": False}
    last = bars[-1]
    close = _f(last.get("close")) or 0.0
    breached = close < float(defense_low)
    return {
        "breached": breached,
        "close": close,
        "defense_low": float(defense_low),
        "date": str(last.get("date") or "")[:10],
    }


def evaluate_exit_factors(
    bars: List[Dict[str, Any]],
    *,
    entry_price: float,
    entry_idx: Optional[int] = None,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    三要素：
    1) 空间充足（涨幅达阈值）
    2) 高位盘整时间足够
    3) 近 N 日累计换手 >= 100%
    """
    ecfg = (config or {}).get("exit") or {}
    if not bars or entry_price <= 0:
        return {
            "space_ok": False,
            "consolidate_ok": False,
            "turnover_ok": False,
            "any_ok": False,
            "all_ok": False,
            "gain_pct": 0.0,
            "flags": [],
        }

    closes = [_f(b.get("close")) or 0.0 for b in bars]
    last = closes[-1]
    gain = (last - entry_price) / entry_price if entry_price > 0 else 0.0
    space_pcts = list(ecfg.get("space_pcts") or [0.50, 0.70, 1.00])
    space_ok = any(gain >= float(p) for p in space_pcts)

    # 高位盘整：从最高点回落后在窄幅震荡
    hi = max(closes) if closes else last
    cons_days = int(ecfg.get("high_consolidate_days", 15))
    cons_range = float(ecfg.get("high_consolidate_range_pct", 0.15))
    window = bars[-cons_days:] if len(bars) >= cons_days else bars
    w_closes = [_f(b.get("close")) or 0.0 for b in window]
    w_hi = max(w_closes) if w_closes else 0.0
    w_lo = min(w_closes) if w_closes else 0.0
    near_high = hi > 0 and last >= hi * 0.85
    range_pct = ((w_hi - w_lo) / w_hi) if w_hi > 0 else 1.0
    consolidate_ok = near_high and len(window) >= cons_days and range_pct <= cons_range

    t_days = int(ecfg.get("turnover_sum_days", 5))
    t_need = float(ecfg.get("turnover_sum_pct", 100.0))
    turnovers = []
    for b in bars[-t_days:]:
        tr = _f(b.get("turnover_rate"))
        if tr is not None:
            turnovers.append(tr)
    turnover_sum = sum(turnovers) if turnovers else 0.0
    turnover_ok = turnover_sum >= t_need

    flags = []
    if space_ok:
        flags.append("space")
    if consolidate_ok:
        flags.append("consolidate")
    if turnover_ok:
        flags.append("turnover")

    return {
        "space_ok": space_ok,
        "consolidate_ok": consolidate_ok,
        "turnover_ok": turnover_ok,
        "any_ok": bool(flags),
        "all_ok": len(flags) >= 3,
        "gain_pct": gain,
        "turnover_sum": turnover_sum,
        "flags": flags,
        "suggest_full_exit": len(flags) >= 3,
        "suggest_partial_exit": 1 <= len(flags) < 3,
    }
