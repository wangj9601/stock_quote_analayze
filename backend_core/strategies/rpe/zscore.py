"""个股相对板块基准的滚动 Z-Score。"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence


def relative_ratio_series(
    stock_closes: Dict[str, float],
    benchmark: List[Dict[str, float]],
) -> List[Dict[str, float]]:
    """对齐日期，计算 P/I 比价序列。"""
    out = []
    for b in benchmark:
        d = b["date"]
        i_t = float(b["i_t"])
        p = stock_closes.get(d)
        if p is None or i_t <= 0 or p <= 0:
            continue
        out.append({"date": d, "ratio": float(p) / i_t, "price": float(p), "i_t": i_t})
    return out


def rolling_zscore(values: Sequence[float], window: int) -> List[Optional[float]]:
    w = max(5, int(window))
    out: List[Optional[float]] = []
    for i in range(len(values)):
        if i + 1 < w:
            out.append(None)
            continue
        chunk = list(values[i + 1 - w : i + 1])
        mean = sum(chunk) / len(chunk)
        var = sum((x - mean) ** 2 for x in chunk) / len(chunk)
        std = math.sqrt(var)
        if std <= 1e-12:
            out.append(0.0)
        else:
            out.append((chunk[-1] - mean) / std)
    return out


def latest_zscore(
    stock_closes: Dict[str, float],
    benchmark: List[Dict[str, float]],
    window: int,
) -> Optional[Dict]:
    series = relative_ratio_series(stock_closes, benchmark)
    if len(series) < max(5, window):
        return None
    ratios = [s["ratio"] for s in series]
    zs = rolling_zscore(ratios, window)
    z = zs[-1]
    if z is None:
        return None
    last = series[-1]
    return {
        "date": last["date"],
        "z_score": float(z),
        "ratio": last["ratio"],
        "price": last["price"],
        "i_t": last["i_t"],
    }
