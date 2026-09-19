# -*- coding: utf-8 -*-
"""CSB 买点：PROBE / BREAKOUT / LPS。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .config import CSB_BREAKOUT, CSB_LPS, CSB_PROBE
from .indicators import _f, avg_turnover, avg_volume, bar_body_pct, upper_shadow_ratio
from .setup_detector import bar_is_spring, detect_setup, _mean_volume, _spring_params


def _probe_pattern_ok(bar: Dict[str, Any]) -> bool:
    """高下影止跌。阳线不再自动通过。"""
    o = _f(bar.get("open"))
    h = _f(bar.get("high"))
    l = _f(bar.get("low"))
    c = _f(bar.get("close"))
    if o is None or c is None or l is None or h is None or o <= 0:
        return False
    body = abs(c - o)
    lower_shadow = min(o, c) - l
    if body > 1e-9 and lower_shadow >= body:
        return True
    if c < o and (o - c) / o <= 0.02 and lower_shadow >= body * 0.5:
        return True
    return False


def _near_lower(bar: Dict[str, Any], lower: Optional[float], touch_tol_pct: float) -> bool:
    if lower is None or lower <= 0:
        return False
    low = _f(bar.get("low"))
    close = _f(bar.get("close"))
    line = lower * (1.0 + touch_tol_pct)
    return (low is not None and low <= line) or (close is not None and close <= line)


def _today_is_spring(bars: List[Dict[str, Any]], lower: Optional[float], config: Dict[str, Any]) -> bool:
    if not bars or lower is None or lower <= 0:
        return False
    sp = _spring_params(config)
    vol_avg = _mean_volume(bars[:-1], 20)
    return bar_is_spring(
        bars[-1],
        lower=float(lower),
        pierce_min_pct=sp["pierce_min_pct"],
        pierce_max_pct=sp["pierce_max_pct"],
        vol_avg=vol_avg,
        vol_ratio_max=sp["vol_ratio_max"],
    )


def detect_probe(
    bars: List[Dict[str, Any]],
    setup: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """买点1：下轨附近的缩量高下影，或当日 Spring。"""
    ecfg = (config or {}).get("entry") or {}
    ccfg = (config or {}).get("channel") or {}
    vol_max = float(ecfg.get("vol_ratio_probe_max", 0.8))
    touch_tol = float(ccfg.get("touch_tol_pct", 0.015))

    if not setup.get("setup_ok"):
        return {"entry_signal": False, "signal_type": None, "reason": "no_setup"}

    last = bars[-1]
    channel = setup.get("channel") or {}
    lower = _f(channel.get("lower"))
    vol5 = avg_volume(bars, 5)
    vol20 = avg_volume(bars, 20)
    vol_ratio = (vol5 / vol20) if vol5 and vol20 and vol20 > 0 else None
    shrink_ok = vol_ratio is not None and vol_ratio <= vol_max
    pattern_ok = _probe_pattern_ok(last)
    near_ok = _near_lower(last, lower, touch_tol)
    spring_today = _today_is_spring(bars, lower, config)

    entry = bool(near_ok and ((shrink_ok and pattern_ok) or spring_today))
    return {
        "entry_signal": entry,
        "signal_type": CSB_PROBE if entry else None,
        "reason": "ok" if entry else "probe_rules_not_met",
        "vol_ratio_5_20": vol_ratio,
        "shrink_ok": shrink_ok,
        "pattern_ok": pattern_ok,
        "near_lower_ok": near_ok,
        "spring_today": spring_today,
        "entry_low": _f(last.get("low")),
        "probe_price": _f(last.get("close")),
    }


def detect_breakout(
    bars: List[Dict[str, Any]],
    setup: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """买点2：换手放大的实体阳线，收盘突破通道上轨。"""
    ecfg = (config or {}).get("entry") or {}
    expand_mult = float(ecfg.get("vol_expand_mult", 2.0))
    break_pct = float(ecfg.get("break_pct", 0.02))
    body_min = float(ecfg.get("body_min_pct", 0.03))
    shadow_max = float(ecfg.get("upper_shadow_max_ratio", 0.20))

    if not setup.get("setup_ok"):
        return {"entry_signal": False, "signal_type": None, "reason": "no_setup"}

    channel = setup.get("channel") or {}
    upper = _f(channel.get("upper"))
    if upper is None or upper <= 0:
        return {"entry_signal": False, "signal_type": None, "reason": "no_resistance"}

    last = bars[-1]
    close = _f(last.get("close")) or 0.0
    to_today = _f(last.get("turnover_rate"))
    to20 = avg_turnover(bars[:-1], 20) or avg_turnover(bars, 20)
    to_mult = (to_today / to20) if to_today is not None and to20 and to20 > 0 else None

    body_pct = bar_body_pct(last)
    shadow_ratio = upper_shadow_ratio(last)
    break_line = upper * (1.0 + break_pct)

    expand_ok = to_mult is not None and to_mult >= expand_mult
    body_ok = body_pct is not None and body_pct >= body_min and close > (_f(last.get("open")) or 0)
    shadow_ok = shadow_ratio is not None and shadow_ratio <= shadow_max
    price_ok = close >= break_line
    # 高换手但实体不足或长上影：派发陷阱，否决买点二。
    distribution_trap = bool(expand_ok and ((not body_ok) or (not shadow_ok)))

    entry = bool(expand_ok and body_ok and shadow_ok and price_ok)
    return {
        "entry_signal": entry,
        "signal_type": CSB_BREAKOUT if entry else None,
        "reason": "distribution_trap" if distribution_trap and not entry else ("ok" if entry else "breakout_rules_not_met"),
        "vol_expand_mult": to_mult,
        "expand_basis": "turnover",
        "expand_ok": expand_ok,
        "body_pct": body_pct,
        "body_ok": body_ok,
        "upper_shadow_ratio": shadow_ratio,
        "shadow_ok": shadow_ok,
        "break_line": break_line,
        "resistance": upper,
        "distribution_trap": distribution_trap,
        "entry_low": _f(last.get("low")),
        "breakout_price": close,
    }


def confirm_lps(
    today: Dict[str, Any],
    breakout_bar: Dict[str, Any],
    *,
    channel_upper: float,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """突破后缩量回踩上轨或阳线实体中位，收盘不重回通道并转强。"""
    ecfg = (config or {}).get("entry") or {}
    ccfg = (config or {}).get("channel") or {}
    vol_max = float(ecfg.get("lps_vol_ratio_max", 0.80))
    tol = float(ccfg.get("touch_tol_pct", 0.015))

    upper = float(channel_upper or 0)
    if upper <= 0:
        return {"entry_signal": False, "reason": "no_upper"}

    bo_open = _f(breakout_bar.get("open"))
    bo_close = _f(breakout_bar.get("close"))
    mid = ((bo_open + bo_close) / 2.0) if bo_open and bo_close else None

    low = _f(today.get("low"))
    close = _f(today.get("close"))
    open_ = _f(today.get("open"))
    if low is None or close is None or open_ is None:
        return {"entry_signal": False, "reason": "bad_bar"}

    vol_today = _f(today.get("volume"))
    vol_bo = _f(breakout_bar.get("volume"))
    to_today = _f(today.get("turnover_rate"))
    to_bo = _f(breakout_bar.get("turnover_rate"))
    shrink_ok = False
    if vol_today is not None and vol_bo and vol_bo > 0:
        shrink_ok = vol_today <= vol_bo * vol_max
    elif to_today is not None and to_bo and to_bo > 0:
        shrink_ok = to_today <= to_bo * vol_max

    pullback_upper = low <= upper * (1.0 + tol)
    pullback_mid = mid is not None and mid > 0 and low <= mid * (1.0 + tol)
    pullback_ok = pullback_upper or pullback_mid
    hold_ok = close >= upper
    turn_ok = close > open_

    entry = bool(shrink_ok and pullback_ok and hold_ok and turn_ok)
    return {
        "entry_signal": entry,
        "reason": "ok" if entry else "lps_rules_not_met",
        "shrink_ok": shrink_ok,
        "pullback_ok": pullback_ok,
        "hold_ok": hold_ok,
        "turn_ok": turn_ok,
        "lps_support_upper": upper,
        "lps_body_mid": mid,
        "lps_price": close,
        "entry_low": _f(breakout_bar.get("low")),
    }


def detect_lps(bars: List[Dict[str, Any]], config: Dict[str, Any]) -> Dict[str, Any]:
    """买点3：最近 lps_window 日内出现过 BREAKOUT，当日满足 LPS。"""
    ecfg = (config or {}).get("entry") or {}
    window = int(ecfg.get("lps_window", 3))
    if len(bars) < 80 or window <= 0:
        return {"entry_signal": False, "signal_type": None, "reason": "short_history"}

    today = bars[-1]
    for offset in range(1, window + 1):
        idx = len(bars) - 1 - offset
        if idx < 60:
            break
        hist = bars[: idx + 1]
        setup_then = detect_setup(hist, config)
        bo = detect_breakout(hist, setup_then, config)
        if not bo.get("entry_signal"):
            continue
        upper = _f((setup_then.get("channel") or {}).get("upper"))
        if upper is None:
            continue
        confirmed = confirm_lps(today, hist[-1], channel_upper=upper, config=config)
        if not confirmed.get("entry_signal"):
            return {
                "entry_signal": False,
                "signal_type": None,
                "reason": confirmed.get("reason"),
                "lps_breakout_date": str(hist[-1].get("date") or "")[:10],
                **{k: confirmed.get(k) for k in ("shrink_ok", "pullback_ok", "hold_ok", "turn_ok")},
            }
        return {
            "entry_signal": True,
            "signal_type": CSB_LPS,
            "entry_kind": "lps",
            "reason": "ok",
            "channel": setup_then.get("channel"),
            "lps_breakout_date": str(hist[-1].get("date") or "")[:10],
            **confirmed,
        }
    return {"entry_signal": False, "signal_type": None, "reason": "no_recent_breakout"}


def detect_entry(bars: List[Dict[str, Any]], config: Dict[str, Any]) -> Dict[str, Any]:
    """综合入口：BREAKOUT 优先，其次 LPS，再次 PROBE。"""
    setup = detect_setup(bars, config)
    breakout = detect_breakout(bars, setup, config)
    if breakout.get("entry_signal"):
        return {**setup, **breakout, "entry_kind": "breakout"}
    lps = detect_lps(bars, config)
    if lps.get("entry_signal"):
        return {**setup, **lps, "entry_kind": "lps"}
    probe = detect_probe(bars, setup, config)
    if probe.get("entry_signal"):
        return {**setup, **probe, "entry_kind": "probe"}
    merged = {**setup, **probe}
    if lps.get("lps_breakout_date"):
        merged["lps_breakout_date"] = lps.get("lps_breakout_date")
    return {**merged, "entry_signal": False, "signal_type": setup.get("signal_type") if setup.get("setup_ok") else None, "entry_kind": None}
