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


def _bar_turnover_pct(
    bar: Dict[str, Any],
    *,
    free_float_shares: Optional[float],
) -> Optional[float]:
    """日换手率（百分比口径，如 5.0 表示 5%）。优先 turnover_rate，否则用成交额/流通市值估算。"""
    tr = _f(bar.get("turnover_rate"))
    if tr is not None:
        return tr
    amount = _f(bar.get("amount"))
    close = _f(bar.get("close"))
    ff = _f(free_float_shares)
    if amount is None or close is None or close <= 0 or ff is None or ff <= 0:
        return None
    circ_mv = ff * close
    if circ_mv <= 0:
        return None
    # amount 与 circ_mv 同为元；换手率用百分比以对齐 turnover_rate 常见口径
    return (amount / circ_mv) * 100.0


def evaluate_exit_factors(
    bars: List[Dict[str, Any]],
    *,
    entry_price: float,
    entry_idx: Optional[int] = None,
    free_float_shares: Optional[float] = None,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    三要素：
    1) 空间充足（涨幅达阈值）
    2) 高位盘整时间足够（自入场日起算高点，无入场索引则退回全序列）
    3) 近 N 日累计换手 >= 100%（缺 turnover_rate 时用成交额/流通股本估算）
    """
    ecfg = (config or {}).get("exit") or {}
    empty = {
        "space_ok": False,
        "consolidate_ok": False,
        "turnover_ok": False,
        "any_ok": False,
        "all_ok": False,
        "gain_pct": 0.0,
        "flags": [],
        "turnover_sum": 0.0,
        "turnover_reason": None,
        "suggest_full_exit": False,
        "suggest_partial_exit": False,
    }
    if not bars or entry_price <= 0:
        return empty

    if entry_idx is not None and 0 <= int(entry_idx) < len(bars):
        post = bars[int(entry_idx) :]
    else:
        post = bars

    closes = [_f(b.get("close")) or 0.0 for b in post]
    if not closes:
        return empty
    last = closes[-1]
    gain = (last - entry_price) / entry_price if entry_price > 0 else 0.0
    space_pcts = list(ecfg.get("space_pcts") or [0.50, 0.70, 1.00])
    space_ok = any(gain >= float(p) for p in space_pcts)

    # 高位盘整：相对入场后最高点，近 N 日窄幅
    hi = max(closes) if closes else last
    cons_days = int(ecfg.get("high_consolidate_days", 15))
    cons_range = float(ecfg.get("high_consolidate_range_pct", 0.15))
    window = post[-cons_days:] if len(post) >= cons_days else post
    w_closes = [_f(b.get("close")) or 0.0 for b in window]
    w_hi = max(w_closes) if w_closes else 0.0
    w_lo = min(w_closes) if w_closes else 0.0
    near_high = hi > 0 and last >= hi * 0.85
    range_pct = ((w_hi - w_lo) / w_hi) if w_hi > 0 else 1.0
    consolidate_ok = near_high and len(window) >= cons_days and range_pct <= cons_range

    t_days = int(ecfg.get("turnover_sum_days", 5))
    t_need = float(ecfg.get("turnover_sum_pct", 100.0))
    turnovers: List[float] = []
    missing = 0
    for b in bars[-t_days:]:
        tr = _bar_turnover_pct(b, free_float_shares=free_float_shares)
        if tr is None:
            missing += 1
        else:
            turnovers.append(tr)
    turnover_sum = sum(turnovers) if turnovers else 0.0
    if not turnovers:
        turnover_ok = False
        turnover_reason = "missing_data"
    else:
        turnover_ok = turnover_sum >= t_need
        turnover_reason = "ok" if turnover_ok else ("partial_data" if missing else "below_threshold")

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
        "turnover_reason": turnover_reason,
        "flags": flags,
        "suggest_full_exit": len(flags) >= 3,
        "suggest_partial_exit": 1 <= len(flags) < 3,
    }
