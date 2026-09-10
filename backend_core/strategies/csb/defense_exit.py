# -*- coding: utf-8 -*-
"""CSB 防守出场：假突破、基准止损、MA 跟踪。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .config import CSB_FALSE_BREAK, CSB_STOP, CSB_TRAIL
from .indicators import _f, sma


def check_false_break(
    bars: Sequence[Dict[str, Any]],
    *,
    breakout_date: str,
    channel_upper: float,
    false_break_days: int = 3,
) -> Dict[str, Any]:
    """
    突破后 T+1～T+N 任一日收盘 < 通道上轨 → 假突破。
    bars 正序且含突破日。
    """
    if channel_upper <= 0 or not bars:
        return {"false_break": False}
    bd = str(breakout_date)[:10]
    idx = None
    for i, b in enumerate(bars):
        if str(b.get("date") or "")[:10] == bd:
            idx = i
            break
    if idx is None:
        return {"false_break": False}

    for j in range(idx + 1, min(len(bars), idx + 1 + int(false_break_days))):
        cl = _f(bars[j].get("close"))
        if cl is not None and cl < channel_upper:
            return {
                "false_break": True,
                "signal_type": CSB_FALSE_BREAK,
                "exit_reason": "false_break",
                "exit_date": str(bars[j].get("date") or "")[:10],
                "exit_price": cl,
            }
    return {"false_break": False}


def baseline_stop_price(entry_low: Optional[float], buffer_pct: float = 0.02) -> Optional[float]:
    if entry_low is None or entry_low <= 0:
        return None
    return float(entry_low) * (1.0 - buffer_pct)


def evaluate_baseline_stop(
    bar: Dict[str, Any],
    *,
    stop_price: float,
) -> Optional[Dict[str, Any]]:
    cl = _f(bar.get("close"))
    if cl is not None and cl <= stop_price:
        return {
            "exit_reason": "baseline_stop",
            "signal_type": CSB_STOP,
            "exit_date": str(bar.get("date") or "")[:10],
            "exit_price": cl,
        }
    return None


def evaluate_ma_trail_exit(
    bar: Dict[str, Any],
    *,
    ma_period: int,
    closes_before: Sequence[float],
) -> Optional[Dict[str, Any]]:
    """收盘跌破 MA 跟踪线。"""
    ma = sma(list(closes_before) + [_f(bar.get("close")) or 0.0], ma_period)
    cl = _f(bar.get("close"))
    if ma is not None and cl is not None and cl < ma:
        return {
            "exit_reason": "ma_trail",
            "signal_type": CSB_TRAIL,
            "exit_date": str(bar.get("date") or "")[:10],
            "exit_price": cl,
            "trail_ma": ma,
        }
    return None


def evaluate_structure_exit_rules(
    *,
    entry_price: float,
    entry_low: Optional[float],
    channel_upper: Optional[float],
    bars_after_entry: Sequence[Dict[str, Any]],
    signal_date: str,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    CSB structure_exit：假突破 → 基准止损 → MA 跟踪 → 到期。
    bars_after_entry 含入场日（正序）。
    """
    dcfg = (config or {}).get("defense") or {}
    false_days = int(dcfg.get("false_break_days", 3))
    trail_ma = int(dcfg.get("trail_ma", 20))

    if channel_upper and signal_date:
        fb = check_false_break(
            bars_after_entry,
            breakout_date=signal_date,
            channel_upper=float(channel_upper),
            false_break_days=false_days,
        )
        if fb.get("false_break"):
            return fb

    stop_px = baseline_stop_price(entry_low)
    closes: List[float] = []
    for bi, bar in enumerate(bars_after_entry):
        if bi == 0:
            closes.append(_f(bar.get("close")) or entry_price)
            continue
        if stop_px is not None:
            hit = evaluate_baseline_stop(bar, stop_price=stop_px)
            if hit:
                return hit
        trail = evaluate_ma_trail_exit(
            bar,
            ma_period=trail_ma,
            closes_before=closes,
        )
        if trail:
            return trail
        closes.append(_f(bar.get("close")) or entry_price)

    last = bars_after_entry[-1] if bars_after_entry else {}
    exit_px = _f(last.get("close")) or entry_price
    return {
        "exit_reason": "horizon_end",
        "exit_date": str(last.get("date") or "")[:10],
        "exit_price": exit_px,
    }


def evaluate_risk_exit_rules(
    *,
    entry_price: float,
    entry_low: Optional[float],
    bars_after_entry: Sequence[Dict[str, Any]],
    config: Dict[str, Any],
    stop_loss_pct: float = 8.0,
) -> Dict[str, Any]:
    """risk_exit：基准止损 + 固定百分比止损。"""
    stop_px = baseline_stop_price(entry_low)
    pct_stop = entry_price * (1.0 - stop_loss_pct / 100.0)

    for bi, bar in enumerate(bars_after_entry):
        if bi == 0:
            continue
        cl = _f(bar.get("close")) or entry_price
        if stop_px is not None and cl <= stop_px:
            return {
                "exit_reason": "baseline_stop",
                "signal_type": CSB_STOP,
                "exit_date": str(bar.get("date") or "")[:10],
                "exit_price": cl,
            }
        if cl <= pct_stop:
            return {
                "exit_reason": "price_stop",
                "signal_type": CSB_STOP,
                "exit_date": str(bar.get("date") or "")[:10],
                "exit_price": cl,
            }

    last = bars_after_entry[-1] if bars_after_entry else {}
    exit_px = _f(last.get("close")) or entry_price
    return {
        "exit_reason": "horizon_end",
        "exit_date": str(last.get("date") or "")[:10],
        "exit_price": exit_px,
    }
