# -*- coding: utf-8 -*-
"""CSB 防守出场：假突破、基准止损、MA 跟踪。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .config import CSB_DISTRIBUTE, CSB_FALSE_BREAK, CSB_STOP, CSB_TRAIL
from .indicators import _f, bar_body_pct, sma, upper_shadow_ratio


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
        # 回测 bars 常从信号次日开始，窗口直接覆盖前 N 根。
        start = 0
    else:
        start = idx + 1
    end = min(len(bars), start + int(false_break_days))
    for j in range(start, end):
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


def baseline_stop_price(entry_low: Optional[float], buffer_pct: float = 0.0) -> Optional[float]:
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


def _mean_positive(values: Sequence[float], n: int = 20) -> Optional[float]:
    chunk = [v for v in list(values)[-n:] if v is not None and v > 0]
    if not chunk:
        return None
    return sum(chunk) / len(chunk)


def latest_swing_low(bars: Sequence[Dict[str, Any]], window: int = 2) -> Optional[float]:
    """最近一个已确认的波段低点（左右各 window 根更高）。"""
    n = len(bars)
    w = max(1, int(window))
    if n < w * 2 + 1:
        return None
    for i in range(n - 1 - w, w - 1, -1):
        low_i = _f(bars[i].get("low"))
        if low_i is None:
            continue
        ok = True
        for k in range(1, w + 1):
            left = _f(bars[i - k].get("low"))
            right = _f(bars[i + k].get("low"))
            if left is None or right is None or low_i > left or low_i > right:
                ok = False
                break
        if ok:
            return low_i
    return None


def evaluate_distribution_exit(
    bar: Dict[str, Any],
    *,
    entry_price: float,
    closes_before: Sequence[float],
    vols_before: Sequence[float],
    turnovers_before: Sequence[float],
    config: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """主升后的天量滞涨，或放量跌破 MA10。"""
    dcfg = (config or {}).get("defense") or {}
    cl = _f(bar.get("close"))
    if cl is None or entry_price <= 0:
        return None
    gain = cl / entry_price - 1.0
    min_gain = float(dcfg.get("distribution_min_gain", 0.08))
    if gain < min_gain:
        return None

    mult = float(dcfg.get("distribution_turnover_mult", 2.0))
    to = _f(bar.get("turnover_rate"))
    vol = _f(bar.get("volume"))
    to_avg = _mean_positive(turnovers_before, 20)
    vol_avg = _mean_positive(vols_before, 20)
    effort = False
    if to is not None and to_avg and to >= to_avg * mult:
        effort = True
    elif vol is not None and vol_avg and vol >= vol_avg * mult:
        effort = True

    body = bar_body_pct(bar)
    shadow = upper_shadow_ratio(bar)
    body_max = float(dcfg.get("distribution_body_max", 0.03))
    shadow_max = float(dcfg.get("distribution_shadow_max", 0.20))
    low_result = body is None or body < body_max or (shadow is not None and shadow > shadow_max)
    exit_date = str(bar.get("date") or "")[:10]
    if effort and low_result:
        return {
            "exit_reason": "distribution",
            "signal_type": CSB_DISTRIBUTE,
            "exit_date": exit_date,
            "exit_price": cl,
            "distribution_kind": "stall",
        }

    ma_fast = int(dcfg.get("trail_ma_fast", 10))
    ma10 = sma(list(closes_before) + [cl], ma_fast)
    if ma10 is not None and cl < ma10 and effort:
        return {
            "exit_reason": "distribution",
            "signal_type": CSB_DISTRIBUTE,
            "exit_date": exit_date,
            "exit_price": cl,
            "distribution_kind": "ma10_break",
            "trail_ma": ma10,
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
    prior_bars: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    结构出场：假突破 → 基准止损（无缓冲）→ 派发 → 阶梯跟踪 → 到期。
    跟踪线取波段低点与 MA10/MA20 中仍在收盘价之下的较高者，只上移。
    """
    dcfg = (config or {}).get("defense") or {}
    false_days = int(dcfg.get("false_break_days", 3))
    trail_ma = int(dcfg.get("trail_ma", 20))
    trail_fast = int(dcfg.get("trail_ma_fast", 10))
    buffer = float(dcfg.get("stop_buffer_pct", 0.0))
    arm_gain = float(dcfg.get("trail_arm_gain", 0.03))
    swing_w = int(dcfg.get("swing_window", 2))

    if channel_upper and signal_date:
        fb = check_false_break(
            bars_after_entry,
            breakout_date=signal_date,
            channel_upper=float(channel_upper),
            false_break_days=false_days,
        )
        if fb.get("false_break"):
            return fb

    stop_px = baseline_stop_price(entry_low, buffer)
    closes: List[float] = []
    vols: List[float] = []
    tos: List[float] = []
    for b in prior_bars or []:
        c = _f(b.get("close"))
        if c:
            closes.append(c)
        v = _f(b.get("volume"))
        if v:
            vols.append(v)
        t = _f(b.get("turnover_rate"))
        if t:
            tos.append(t)

    path: List[Dict[str, Any]] = []
    ratchet: Optional[float] = None
    running_high = float(entry_price)
    anchor = str(signal_date or "")[:10]

    for bar in bars_after_entry:
        cl = _f(bar.get("close")) or entry_price
        hi = _f(bar.get("high")) or cl
        bar_date = str(bar.get("date") or "")[:10]
        if anchor and bar_date == anchor:
            path.append(bar)
            closes.append(cl)
            v0 = _f(bar.get("volume"))
            t0 = _f(bar.get("turnover_rate"))
            if v0:
                vols.append(v0)
            if t0:
                tos.append(t0)
            running_high = max(running_high, hi)
            continue

        if stop_px is not None:
            hit = evaluate_baseline_stop(bar, stop_price=stop_px)
            if hit:
                return hit

        dist = evaluate_distribution_exit(
            bar,
            entry_price=entry_price,
            closes_before=closes,
            vols_before=vols,
            turnovers_before=tos,
            config=config,
        )
        if dist:
            return dist

        running_high = max(running_high, hi)
        if running_high >= entry_price * (1.0 + arm_gain):
            swing = latest_swing_low(path, swing_w)
            ma_fast = sma(closes + [cl], trail_fast)
            ma_slow = sma(closes + [cl], trail_ma)
            cands = [lvl for lvl in (swing, ma_fast, ma_slow) if lvl is not None and lvl < cl]
            if cands:
                proposed = max(cands)
                if ratchet is None or proposed > ratchet:
                    ratchet = proposed
            if ratchet is not None and cl < ratchet:
                return {
                    "exit_reason": "ma_trail",
                    "signal_type": CSB_TRAIL,
                    "exit_date": bar_date,
                    "exit_price": cl,
                    "trail_level": ratchet,
                }

        path.append(bar)
        closes.append(cl)
        v1 = _f(bar.get("volume"))
        t1 = _f(bar.get("turnover_rate"))
        if v1:
            vols.append(v1)
        if t1:
            tos.append(t1)

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
    signal_date: Optional[str] = None,
) -> Dict[str, Any]:
    """risk_exit：基准止损（无额外缓冲）+ 固定百分比止损。"""
    buffer = float(((config or {}).get("defense") or {}).get("stop_buffer_pct", 0.0))
    stop_px = baseline_stop_price(entry_low, buffer)
    pct_stop = entry_price * (1.0 - stop_loss_pct / 100.0)
    anchor = str(signal_date or "")[:10]

    for bi, bar in enumerate(bars_after_entry):
        bar_date = str(bar.get("date") or "")[:10]
        if anchor:
            if bar_date == anchor:
                continue
        elif bi == 0:
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
