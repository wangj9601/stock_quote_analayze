# -*- coding: utf-8 -*-
"""CSB 纯函数指标（可单测）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence


def _f(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        x = float(v)
        if x != x:
            return None
        return x
    except (TypeError, ValueError):
        return None


def sma(values: Sequence[float], period: int) -> Optional[float]:
    if len(values) < period or period <= 0:
        return None
    chunk = list(values[-period:])
    if any(x is None or x <= 0 for x in chunk):
        return None
    return sum(chunk) / period


def sma_series(closes: Sequence[float], period: int) -> List[Optional[float]]:
    out: List[Optional[float]] = []
    for i in range(len(closes)):
        if i + 1 < period:
            out.append(None)
        else:
            out.append(sma(closes[: i + 1], period))
    return out


def slope_norm(values: Sequence[Optional[float]], lookback: int = 20) -> Optional[float]:
    """近 lookback 日斜率 / 均值（归一化）。"""
    seq = [v for v in values if v is not None]
    if len(seq) < lookback:
        return None
    chunk = seq[-lookback:]
    if not chunk or chunk[0] == 0:
        return None
    return (chunk[-1] - chunk[0]) / (len(chunk) - 1) / chunk[0] if len(chunk) > 1 else 0.0


def avg_turnover(bars: Sequence[Dict[str, Any]], lookback: int) -> Optional[float]:
    if len(bars) < lookback:
        return None
    vals = [_f(b.get("turnover_rate")) for b in bars[-lookback:]]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def avg_volume(bars: Sequence[Dict[str, Any]], lookback: int) -> Optional[float]:
    if len(bars) < lookback:
        return None
    vals = [_f(b.get("volume")) or 0.0 for b in bars[-lookback:]]
    if not vals or all(v <= 0 for v in vals):
        return None
    return sum(vals) / len(vals)
