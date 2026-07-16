"""共振弱转强入场检测。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _f(v) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _sma(values: List[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    chunk = values[-period:]
    if any(x <= 0 for x in chunk):
        return None
    return sum(chunk) / period


def detect_entry(
    bars: List[Dict[str, Any]],
    market_returns: List[float],
    *,
    bottom_matched: bool,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    入场：筑底成立 + 大盘近期调整 + 底部缩量后收盘上穿 MA20 且微放量。
    bars 时间正序。
    """
    ecfg = (config or {}).get("entry") or {}
    if not bottom_matched:
        return {"entry_signal": False, "reason": "no_bottom"}

    if len(bars) < 25:
        return {"entry_signal": False, "reason": "insufficient_bars"}

    closes = [_f(b.get("close")) or 0.0 for b in bars]
    volumes = [_f(b.get("volume")) or 0.0 for b in bars]
    lows = [_f(b.get("low")) or 0.0 for b in bars]

    ma_period = int(ecfg.get("ma_period", 20))
    ma_today = _sma(closes, ma_period)
    ma_yest = _sma(closes[:-1], ma_period)
    if ma_today is None or ma_yest is None:
        return {"entry_signal": False, "reason": "no_ma"}

    last_c = closes[-1]
    prev_c = closes[-2]
    cross_up = prev_c <= ma_yest and last_c > ma_today

    # 缩量：近 5 日前量均 vs 更早
    vol5 = volumes[-6:-1]
    vol_base = volumes[-11:-6] if len(volumes) >= 11 else volumes[:-6]
    avg_recent = sum(vol5) / len(vol5) if vol5 else 0.0
    avg_base = sum(vol_base) / len(vol_base) if vol_base else avg_recent
    shrink_max = float(ecfg.get("shrink_volume_ratio_max", 0.7))
    shrink_ok = avg_base > 0 and (avg_recent / avg_base) <= shrink_max

    # 今日微放量
    exp_min = float(ecfg.get("expand_volume_ratio_min", 1.05))
    exp_max = float(ecfg.get("expand_volume_ratio_max", 1.8))
    vol_ratio = (volumes[-1] / avg_recent) if avg_recent > 0 else 0.0
    expand_ok = exp_min <= vol_ratio <= exp_max

    market_ok = True
    if bool(ecfg.get("require_market_sync_down", True)):
        lookback = int(ecfg.get("market_lookback_days", 5))
        drop = float(ecfg.get("market_drop_pct", -0.01))
        recent_m = market_returns[-lookback:] if market_returns else []
        if not recent_m:
            market_ok = True  # 无大盘数据时不阻断
        else:
            cum = 1.0
            for r in recent_m:
                cum *= 1.0 + float(r)
            market_ok = (cum - 1.0) <= drop

    entry = bool(cross_up and shrink_ok and expand_ok and market_ok)
    return {
        "entry_signal": entry,
        "reason": "ok" if entry else "rules_not_met",
        "ma20": ma_today,
        "close": last_c,
        "volume_ratio": vol_ratio,
        "cross_up": cross_up,
        "shrink_ok": shrink_ok,
        "expand_ok": expand_ok,
        "market_ok": market_ok,
        "entry_low": lows[-1],
        "signal_date": str(bars[-1].get("date") or "")[:10],
    }
