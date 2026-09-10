# -*- coding: utf-8 -*-
"""CSB 买点：PROBE / BREAKOUT。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .config import CSB_BREAKOUT, CSB_PROBE
from .indicators import _f, avg_volume
from .setup_detector import detect_setup


def _bar_body_pct(bar: Dict[str, Any]) -> Optional[float]:
    o = _f(bar.get("open"))
    c = _f(bar.get("close"))
    if o is None or c is None or o <= 0:
        return None
    return (c - o) / o


def _upper_shadow_ratio(bar: Dict[str, Any]) -> Optional[float]:
    o = _f(bar.get("open"))
    h = _f(bar.get("high"))
    c = _f(bar.get("close"))
    if o is None or h is None or c is None:
        return None
    body = abs(c - o)
    upper = h - max(o, c)
    if body <= 1e-9:
        return 0.0 if upper <= 0 else 999.0
    return upper / body


def _probe_pattern_ok(bar: Dict[str, Any]) -> bool:
    """缩量止跌：收阴幅度≤2% 或下影≥实体；或阳包阴简化。"""
    o = _f(bar.get("open"))
    h = _f(bar.get("high"))
    l = _f(bar.get("low"))
    c = _f(bar.get("close"))
    if o is None or c is None or l is None or h is None or o <= 0:
        return False
    body = abs(c - o)
    lower_shadow = min(o, c) - l
    if c < o and (o - c) / o <= 0.02:
        return True
    if body > 1e-9 and lower_shadow >= body:
        return True
    if c > o:
        return True
    return False


def detect_probe(
    bars: List[Dict[str, Any]],
    setup: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """买点1：SETUP 成立 + 缩量止跌。"""
    ecfg = (config or {}).get("entry") or {}
    vol_max = float(ecfg.get("vol_ratio_probe_max", 0.8))

    if not setup.get("setup_ok"):
        return {"entry_signal": False, "signal_type": None, "reason": "no_setup"}

    last = bars[-1]
    vol5 = avg_volume(bars, 5)
    vol20 = avg_volume(bars, 20)
    vol_ratio = (vol5 / vol20) if vol5 and vol20 and vol20 > 0 else None
    shrink_ok = vol_ratio is not None and vol_ratio <= vol_max
    pattern_ok = _probe_pattern_ok(last)

    entry = bool(shrink_ok and pattern_ok)
    return {
        "entry_signal": entry,
        "signal_type": CSB_PROBE if entry else None,
        "reason": "ok" if entry else "probe_rules_not_met",
        "vol_ratio_5_20": vol_ratio,
        "shrink_ok": shrink_ok,
        "pattern_ok": pattern_ok,
        "entry_low": _f(last.get("low")),
        "probe_price": _f(last.get("close")),
    }


def detect_breakout(
    bars: List[Dict[str, Any]],
    setup: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """买点2：SETUP + 放量实体突破。"""
    ecfg = (config or {}).get("entry") or {}
    expand_mult = float(ecfg.get("vol_expand_mult", 2.0))
    break_pct = float(ecfg.get("break_pct", 0.02))
    body_min = float(ecfg.get("body_min_pct", 0.03))
    shadow_max = float(ecfg.get("upper_shadow_max_ratio", 0.30))

    if not setup.get("setup_ok"):
        return {"entry_signal": False, "signal_type": None, "reason": "no_setup"}

    channel = setup.get("channel") or {}
    upper = _f(channel.get("upper"))
    hh20 = _f(channel.get("hh20"))
    resistance = max(upper or 0.0, hh20 or 0.0)
    if resistance <= 0:
        return {"entry_signal": False, "signal_type": None, "reason": "no_resistance"}

    last = bars[-1]
    close = _f(last.get("close")) or 0.0
    vol_today = _f(last.get("volume")) or 0.0
    vol20 = avg_volume(bars[:-1], 20) or avg_volume(bars, 20)
    vol_mult = (vol_today / vol20) if vol20 and vol20 > 0 else None

    body_pct = _bar_body_pct(last)
    shadow_ratio = _upper_shadow_ratio(last)
    break_line = resistance * (1.0 + break_pct)

    expand_ok = vol_mult is not None and vol_mult >= expand_mult
    body_ok = body_pct is not None and body_pct >= body_min and close > (_f(last.get("open")) or 0)
    shadow_ok = shadow_ratio is not None and shadow_ratio <= shadow_max
    price_ok = close >= break_line

    entry = bool(expand_ok and body_ok and shadow_ok and price_ok)
    return {
        "entry_signal": entry,
        "signal_type": CSB_BREAKOUT if entry else None,
        "reason": "ok" if entry else "breakout_rules_not_met",
        "vol_expand_mult": vol_mult,
        "expand_ok": expand_ok,
        "body_pct": body_pct,
        "body_ok": body_ok,
        "upper_shadow_ratio": shadow_ratio,
        "shadow_ok": shadow_ok,
        "break_line": break_line,
        "resistance": resistance,
        "entry_low": _f(last.get("low")),
        "breakout_price": close,
    }


def detect_entry(bars: List[Dict[str, Any]], config: Dict[str, Any]) -> Dict[str, Any]:
    """综合入口：SETUP + PROBE/BREAKOUT（BREAKOUT 优先）。"""
    setup = detect_setup(bars, config)
    breakout = detect_breakout(bars, setup, config)
    if breakout.get("entry_signal"):
        return {**setup, **breakout, "entry_kind": "breakout"}
    probe = detect_probe(bars, setup, config)
    if probe.get("entry_signal"):
        return {**setup, **probe, "entry_kind": "probe"}
    return {**setup, **probe, "entry_signal": False, "signal_type": None, "entry_kind": None}
