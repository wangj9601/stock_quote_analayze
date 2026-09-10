# -*- coding: utf-8 -*-
"""CSB SETUP：换手、年线、回踩、地量。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .channel import compute_channel_state
from .config import CSB_SETUP
from .indicators import _f, avg_turnover, avg_volume, slope_norm, sma_series


def _count_lower_touches(
    bars: Sequence[Dict[str, Any]],
    *,
    lower: float,
    touch_tol_pct: float,
    lookback: int = 60,
) -> int:
    """统计近 lookback 内触及通道下轨次数。"""
    if lower <= 0:
        return 0
    window = list(bars[-lookback:])
    touches = 0
    tol = lower * touch_tol_pct
    for b in window:
        low = _f(b.get("low"))
        close = _f(b.get("close"))
        if low is not None and low <= lower + tol:
            touches += 1
        elif close is not None and close <= lower + tol:
            touches += 1
    return touches


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


def check_ma250_defense(bars: Sequence[Dict[str, Any]], config: Dict[str, Any]) -> Dict[str, Any]:
    mcfg = (config or {}).get("ma250") or {}
    slope_min = float(mcfg.get("slope_min", -0.0005))
    closes = [_f(b.get("close")) or 0.0 for b in bars]
    ma250_series = sma_series(closes, 250)
    ma250 = ma250_series[-1] if ma250_series else None
    close = closes[-1] if closes else None
    slope = slope_norm(ma250_series, 20)

    above = bool(ma250 is not None and close is not None and close >= ma250)
    slope_ok = slope is None or slope >= slope_min
    ok = above or slope_ok

    return {
        "ma250_ok": ok,
        "ma250": ma250,
        "ma250_slope_norm": slope,
        "close_above_ma250": above,
    }


def detect_setup(bars: List[Dict[str, Any]], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    SETUP 判定：通道粘合 + 年线 + 回踩次数 + 地量 + 换手初筛。
    bars 正序。
    """
    tcfg = (config or {}).get("turnover") or {}
    ccfg = (config or {}).get("channel") or {}
    min_to = float(tcfg.get("min_avg_20", 1.0))
    min_touches = int(ccfg.get("min_touches", 2))
    touch_tol = float(ccfg.get("touch_tol_pct", 0.015))

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
    touches = _count_lower_touches(
        bars,
        lower=lower or 0.0,
        touch_tol_pct=touch_tol,
    ) if lower else 0
    touch_ok = touches >= min_touches

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
        "ma250": ma250,
        "dry_vol": dry,
    }
