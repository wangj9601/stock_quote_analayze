# -*- coding: utf-8 -*-
"""K 线行数据标准化：把 List[Dict] 转成 numpy 序列，供趋势与形态模块共用。

行的键兼容项目现有写法：trade_date/date、high/low/close/open、volume/vol、amount。
只做算术，不依赖 pandas，全市场扫描时比 DataFrame 快一个量级。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np


def _f(v: Any) -> Optional[float]:
    if isinstance(v, float):
        return v if v == v else None
    if v is None or v == "":
        return None
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def _as_date(v: Any) -> Optional[date]:
    """日期解析快路径：库内日期是 'YYYY-MM-DD' 文本，切片构造比 strptime 快一个量级。

    全市场扫描时每只票要解析数百个日期，这里是最热的循环之一
    （改前 340 根 K 线 parse 一次约 5.9ms，改后 0.6ms）。
    """
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = v if isinstance(v, str) else str(v)
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        try:
            return date(int(s[0:4]), int(s[5:7]), int(s[8:10]))
        except ValueError:
            return None
    s = s.strip()[:10]
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_bars(bars: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """返回 dates / open / high / low / close / volume 数组，以及 swing_zigzag 需要的元组序列。"""
    rows: List[Tuple[date, float, float, float, float, float]] = []
    for b in bars or []:
        if not isinstance(b, dict):
            continue
        d = _as_date(b.get("trade_date") or b.get("date"))
        h = _f(b.get("high"))
        lo = _f(b.get("low"))
        c = _f(b.get("close"))
        if d is None or h is None or lo is None or c is None:
            continue
        if h < lo:
            h, lo = lo, h
        o = _f(b.get("open"))
        v = _f(b.get("volume"))
        if v is None:
            v = _f(b.get("vol"))
        rows.append((d, o if o is not None else c, h, lo, c, v if v is not None else 0.0))

    rows.sort(key=lambda r: r[0])
    if not rows:
        return {
            "dates": [],
            "open": np.array([], dtype=float),
            "high": np.array([], dtype=float),
            "low": np.array([], dtype=float),
            "close": np.array([], dtype=float),
            "volume": np.array([], dtype=float),
            "parsed": [],
        }

    dates = [r[0] for r in rows]
    return {
        "dates": dates,
        "open": np.array([r[1] for r in rows], dtype=float),
        "high": np.array([r[2] for r in rows], dtype=float),
        "low": np.array([r[3] for r in rows], dtype=float),
        "close": np.array([r[4] for r in rows], dtype=float),
        "volume": np.array([r[5] for r in rows], dtype=float),
        # swing_zigzag.find_fractal_pivots 需要 (date, high, low, close)
        "parsed": [(r[0], r[2], r[3], r[4]) for r in rows],
    }


def sma(arr: np.ndarray, window: int) -> np.ndarray:
    """简单移动平均；不足窗口的前段为 nan。"""
    n = int(window)
    out = np.full(len(arr), np.nan, dtype=float)
    if n <= 0 or len(arr) < n:
        return out
    cs = np.cumsum(np.insert(arr.astype(float), 0, 0.0))
    out[n - 1:] = (cs[n:] - cs[:-n]) / n
    return out


def weighted_momentum(close: np.ndarray) -> float:
    """O'Neil 加权动量：3 月 40%、6 月 20%、9 月 20%、12 月 20%。"""
    arr = np.asarray(close, dtype=float)
    if arr.size < 2:
        return float("nan")

    def ret(n: int) -> float:
        k = min(n, arr.size - 1)
        if k <= 0 or arr[-1 - k] <= 0:
            return 0.0
        return arr[-1] / arr[-1 - k] - 1.0

    return 0.4 * ret(63) + 0.2 * ret(126) + 0.2 * ret(189) + 0.2 * ret(252)


def rs_rank(values: Sequence[float]) -> List[float]:
    """横截面百分位（0~100，越大越强）；nan 按最弱处理。"""
    arr = np.asarray(list(values), dtype=float)
    n = arr.size
    if n == 0:
        return []
    order = np.argsort(np.where(np.isnan(arr), -np.inf, arr), kind="mergesort")
    ranks = np.empty(n, dtype=float)
    ranks[order] = np.arange(1, n + 1, dtype=float)
    return list(ranks / n * 100.0)
