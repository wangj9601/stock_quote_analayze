# -*- coding: utf-8 -*-
"""CSB SETUP：换手、年线、独立回踩、Spring、地量。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .channel import compute_channel_state
from .config import CSB_SETUP
from .indicators import _f, avg_turnover, avg_volume, slope_norm, sma_series


def _mean_volume(bars: Sequence[Dict[str, Any]], lookback: int = 20) -> Optional[float]:
    if not bars:
        return None
    chunk = list(bars[-lookback:])
    vals = [_f(b.get("volume")) or 0.0 for b in chunk]
    vals = [v for v in vals if v > 0]
    if len(vals) < 5:
        return None
    return sum(vals) / len(vals)


def bar_is_spring(
    bar: Dict[str, Any],
    *,
    lower: float,
    pierce_min_pct: float,
    pierce_max_pct: float,
    vol_avg: Optional[float],
    vol_ratio_max: float,
) -> bool:
    """盘中假跌破下轨后收回，且量能极小。"""
    if lower <= 0:
        return False
    low = _f(bar.get("low"))
    close = _f(bar.get("close"))
    vol = _f(bar.get("volume"))
    if low is None or close is None or vol is None:
        return False
    pierce = (lower - low) / lower
    if pierce < pierce_min_pct or pierce > pierce_max_pct:
        return False
    if close < lower:
        return False
    if vol_avg is None or vol_avg <= 0:
        return False
    return vol <= vol_avg * vol_ratio_max


def _spring_params(config: Dict[str, Any]) -> Dict[str, float]:
    scfg = (config or {}).get("spring") or {}
    return {
        "pierce_min_pct": float(scfg.get("pierce_min_pct", 0.01)),
        "pierce_max_pct": float(scfg.get("pierce_max_pct", 0.02)),
        "vol_ratio_max": float(scfg.get("vol_ratio_max", 0.55)),
    }


def count_support_tests(
    bars: Sequence[Dict[str, Any]],
    *,
    lower: float,
    touch_tol_pct: float,
    leave_pct: float = 0.03,
    lookback: int = 60,
    config: Optional[Dict[str, Any]] = None,
) -> int:
    """独立回踩次数：连续贴轨只计 1 次，离开下轨后再回来才计下一次。

    收盘有效跌破（深于 Spring 上限）的触碰不计入支撑测试。
    """
    if lower <= 0 or not bars:
        return 0
    sp = _spring_params(config or {})
    start = max(0, len(bars) - int(lookback))
    tests = 0
    armed = True
    touch_line = lower * (1.0 + touch_tol_pct)
    leave_line = lower * (1.0 + leave_pct)
    reclaim_line = lower * (1.0 - 0.002)
    for i in range(start, len(bars)):
        b = bars[i]
        low = _f(b.get("low"))
        close = _f(b.get("close"))
        touching = (low is not None and low <= touch_line) or (close is not None and close <= touch_line)
        left = close is not None and close >= leave_line and not touching
        if touching and armed:
            vol_avg = _mean_volume(bars[max(0, i - 20) : i], 20)
            spring = bar_is_spring(
                b,
                lower=lower,
                pierce_min_pct=sp["pierce_min_pct"],
                pierce_max_pct=sp["pierce_max_pct"],
                vol_avg=vol_avg,
                vol_ratio_max=sp["vol_ratio_max"],
            )
            reclaimed = close is not None and close >= reclaim_line
            if reclaimed or spring:
                tests += 1
            armed = False
        if left:
            armed = True
    return tests


def find_springs(
    bars: Sequence[Dict[str, Any]],
    *,
    lower: float,
    lookback: int = 60,
    config: Optional[Dict[str, Any]] = None,
) -> List[int]:
    """返回 lookback 内 Spring K 线的下标（相对 bars）。"""
    if lower <= 0 or not bars:
        return []
    sp = _spring_params(config or {})
    start = max(0, len(bars) - int(lookback))
    hits: List[int] = []
    for i in range(start, len(bars)):
        vol_avg = _mean_volume(bars[max(0, i - 20) : i], 20)
        if bar_is_spring(
            bars[i],
            lower=lower,
            pierce_min_pct=sp["pierce_min_pct"],
            pierce_max_pct=sp["pierce_max_pct"],
            vol_avg=vol_avg,
            vol_ratio_max=sp["vol_ratio_max"],
        ):
            hits.append(i)
    return hits


def check_ma250_defense(bars: Sequence[Dict[str, Any]], config: Dict[str, Any]) -> Dict[str, Any]:
    mcfg = (config or {}).get("ma250") or {}
    slope_min = float(mcfg.get("slope_min", -0.0005))
    closes = [_f(b.get("close")) or 0.0 for b in bars]
    ma250_series = sma_series(closes, 250)
    ma250 = ma250_series[-1] if ma250_series else None
    close = closes[-1] if closes else None
    slope = slope_norm(ma250_series, 20)

    above = bool(ma250 is not None and close is not None and close >= ma250)
    # 年线本身走平或向上；收盘在年线之上不能替代斜率条件。
    slope_ok = slope is not None and slope >= slope_min

    return {
        "ma250_ok": slope_ok,
        "ma250": ma250,
        "ma250_slope_norm": slope,
        "close_above_ma250": above,
        "slope_ok": slope_ok,
    }


def check_dry_volume(bars: Sequence[Dict[str, Any]], config: Dict[str, Any]) -> Dict[str, Any]:
    dcfg = (config or {}).get("dry_vol") or {}
    short_n = int(dcfg.get("lookback_short", 5))
    long_n = int(dcfg.get("lookback_long", 60))
    ratio_max = float(dcfg.get("dry_vol_ratio", 0.55))

    vol_short = avg_volume(bars, short_n)
    vol_long = avg_volume(bars, long_n)
    to_short = avg_turnover(bars, short_n)
    to_long = avg_turnover(bars, long_n)

    vol_ratio = (vol_short / vol_long) if vol_short and vol_long and vol_long > 0 else None
    to_ratio = (to_short / to_long) if to_short and to_long and to_long > 0 else None

    vol_ok = vol_ratio is not None and vol_ratio <= ratio_max
    to_ok = to_ratio is None or to_ratio <= ratio_max  # 缺换手时不阻断
    dry_ok = vol_ok and to_ok

    return {
        "dry_ok": dry_ok,
        "vol_ratio_short_long": vol_ratio,
        "turnover_ratio_short_long": to_ratio,
    }


def detect_setup(bars: List[Dict[str, Any]], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    SETUP 判定：通道粘合 + 年线走平/向上 + 独立回踩 + 地量 + 换手初筛。
    bars 正序。
    """
    tcfg = (config or {}).get("turnover") or {}
    ccfg = (config or {}).get("channel") or {}
    min_to = float(tcfg.get("min_avg_20", 1.0))
    min_touches = int(ccfg.get("min_touches", 2))
    touch_tol = float(ccfg.get("touch_tol_pct", 0.015))
    leave_pct = float(ccfg.get("touch_leave_pct", 0.03))
    lookback = int(ccfg.get("touch_lookback", 60))

    channel = compute_channel_state(bars, config)
    if not channel.get("ok"):
        return {
            "signal_type": None,
            "setup_ok": False,
            "reason": channel.get("reason", "channel_fail"),
            "channel": channel,
        }

    avg_to = avg_turnover(bars, 20)
    turnover_ok = avg_to is not None and avg_to >= min_to

    ma250 = check_ma250_defense(bars, config)
    lower = _f(channel.get("lower"))
    touches = (
        count_support_tests(
            bars,
            lower=lower or 0.0,
            touch_tol_pct=touch_tol,
            leave_pct=leave_pct,
            lookback=lookback,
            config=config,
        )
        if lower
        else 0
    )
    touch_ok = touches >= min_touches
    springs = find_springs(bars, lower=lower or 0.0, lookback=lookback, config=config) if lower else []
    spring_low = None
    if springs:
        lows = [_f(bars[i].get("low")) for i in springs]
        lows = [x for x in lows if x is not None]
        spring_low = min(lows) if lows else None

    dry = check_dry_volume(bars, config)

    setup_ok = bool(
        channel.get("squeeze_ok")
        and turnover_ok
        and ma250.get("ma250_ok")
        and touch_ok
        and dry.get("dry_ok")
    )

    return {
        "signal_type": CSB_SETUP if setup_ok else None,
        "setup_ok": setup_ok,
        "reason": "ok" if setup_ok else "rules_not_met",
        "channel": channel,
        "turnover_avg_20": avg_to,
        "turnover_ok": turnover_ok,
        "touch_count": touches,
        "touch_ok": touch_ok,
        "spring_ok": bool(springs),
        "spring_count": len(springs),
        "spring_low": spring_low,
        "ma250": ma250,
        "dry_vol": dry,
    }
