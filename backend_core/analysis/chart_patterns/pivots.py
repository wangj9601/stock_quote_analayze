# -*- coding: utf-8 -*-
"""ZigZag + 分形枢轴序列，供各类形态检测使用。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from backend_core.analysis.swing_zigzag import (
    DEFAULT_FRACTAL,
    DEFAULT_MAX_BARS,
    _depth_threshold,
    _parse_bars,
    find_fractal_pivots,
    wilder_atr,
    zigzag_from_fractals,
)


def extract_pivot_sequence(
    bars: Sequence[Dict[str, Any]],
    *,
    max_bars: int = DEFAULT_MAX_BARS,
    fractal: int = DEFAULT_FRACTAL,
) -> List[Dict[str, Any]]:
    """返回按时间升序的 ZigZag 枢轴：index/kind/price/date。"""
    parsed = _parse_bars(bars)
    if len(parsed) > max_bars:
        parsed = parsed[-max_bars:]
    if len(parsed) < 10:
        return []
    atr = wilder_atr(parsed)
    close = parsed[-1][3]
    depth = _depth_threshold(close, atr)
    fractals = find_fractal_pivots(parsed, left=fractal, right=fractal)
    zz = zigzag_from_fractals(fractals, depth=depth)
    out: List[Dict[str, Any]] = []
    for p in zz:
        out.append(
            {
                "index": int(p["index"]),
                "kind": p["kind"],
                "price": round(float(p["price"]), 4),
                "date": p.get("date"),
            }
        )
    return out


def linreg_slope(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    """简单线性回归斜率；点数不足返回 None。"""
    n = min(len(xs), len(ys))
    if n < 2:
        return None
    mx = sum(xs[:n]) / n
    my = sum(ys[:n]) / n
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    den = sum((xs[i] - mx) ** 2 for i in range(n))
    if den <= 1e-12:
        return None
    return num / den
