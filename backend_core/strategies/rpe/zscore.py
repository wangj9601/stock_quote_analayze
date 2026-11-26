"""个股相对板块基准的滚动 Z-Score。"""

from __future__ import annotations

import math
from collections import deque
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
    """只算对齐序列最后一窗的 Z，与 ``rolling_zscore(...)[-1]`` 相同。

    日终按概念板重复评估时，全序列滚动会把 O(样本×窗宽) 的纯 Python 循环放大成主耗时。
    """
    w = max(5, int(window))
    buf: deque = deque()
    last_date = None
    last_ratio = None
    last_price = None
    last_i = None
    n = 0
    for b in benchmark:
        d = b["date"]
        try:
            i_t = float(b["i_t"])
        except (TypeError, ValueError):
            continue
        p = stock_closes.get(d)
        if p is None or i_t <= 0:
            continue
        try:
            p = float(p)
        except (TypeError, ValueError):
            continue
        if p <= 0:
            continue
        n += 1
        ratio = p / i_t
        buf.append(ratio)
        if len(buf) > w:
            buf.popleft()
        last_date = d
        last_ratio = ratio
        last_price = p
        last_i = i_t
    if n < w or last_date is None or len(buf) < w:
        return None
    mean = sum(buf) / w
    var = sum((x - mean) ** 2 for x in buf) / w
    std = math.sqrt(var)
    z = 0.0 if std <= 1e-12 else (buf[-1] - mean) / std
    return {
        "date": last_date,
        "z_score": float(z),
        "ratio": float(last_ratio),
        "price": float(last_price),
        "i_t": float(last_i),
    }
