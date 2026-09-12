"""板块基准 I_t 与斜率。

- ``compute_vwap_benchmark``：价位型量权均价，供 RPE 比价 Z 使用。
- ``compute_equal_weight_return_benchmark``：前复权等权收益链，供斜率回退。
- 斜率默认对 ln(I_t) 做 OLS，可同时返回 R²。
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple


def compute_vwap_benchmark(
    date_to_members: Dict[str, List[Tuple[float, float]]],
) -> List[Dict[str, float]]:
    """
    date_to_members: {date: [(close, volume), ...]}
    返回按日期升序的 [{"date", "i_t", "volume_sum"}, ...]
    """
    out = []
    for d in sorted(date_to_members.keys()):
        members = date_to_members[d]
        num = 0.0
        den = 0.0
        for close, vol in members:
            c = float(close or 0)
            v = float(vol or 0)
            if c <= 0 or v <= 0:
                continue
            num += c * v
            den += v
        if den <= 0:
            continue
        out.append({"date": d, "i_t": num / den, "volume_sum": den})
    return out


def compute_equal_weight_return_benchmark(
    panel: Dict[str, List[Dict]],
    *,
    min_members: int = 5,
    start_level: float = 1000.0,
) -> List[Dict[str, float]]:
    """前复权成分日收益等权平均，累加成指数链。

    panel: {code: [{"date", "close", ...}, ...]}，close 须已前复权。
    当日有效家数 < min_members 则跳过该日（不递推）。
    返回 [{"date", "i_t", "member_count"}, ...]，i_t 从 start_level 起累乘 (1+R_t)。
    """
    # code -> sorted date -> close
    by_code: Dict[str, Dict[str, float]] = {}
    all_dates: set = set()
    for code, bars in (panel or {}).items():
        if not bars:
            continue
        m: Dict[str, float] = {}
        for b in bars:
            d = str(b.get("date") or "")[:10]
            try:
                c = float(b.get("close") or 0)
            except (TypeError, ValueError):
                continue
            if not d or c <= 0:
                continue
            m[d] = c
            all_dates.add(d)
        if m:
            by_code[str(code)] = m
    if not by_code or not all_dates:
        return []

    dates = sorted(all_dates)
    out: List[Dict[str, float]] = []
    level = float(start_level)
    for i, d in enumerate(dates):
        if i == 0:
            continue
        prev = dates[i - 1]
        rets: List[float] = []
        for closes in by_code.values():
            p0 = closes.get(prev)
            p1 = closes.get(d)
            if p0 is None or p1 is None or p0 <= 0 or p1 <= 0:
                continue
            rets.append(p1 / p0 - 1.0)
        if len(rets) < int(min_members):
            continue
        r_t = sum(rets) / len(rets)
        level = level * (1.0 + r_t)
        if level <= 0:
            return out
        out.append(
            {
                "date": d,
                "i_t": float(level),
                "member_count": float(len(rets)),
                "r_t": float(r_t),
            }
        )
    return out


def linear_slope_fit(
    values: Sequence[float],
) -> Optional[Tuple[float, float, int]]:
    """OLS：y ~ a + b*x，x=0..n-1。返回 (slope_b, r_squared, n)；样本不足返回 None。"""
    n = len(values)
    if n < 5:
        return None
    xs = list(range(n))
    mean_x = (n - 1) / 2.0
    mean_y = sum(values) / n
    num = 0.0
    den = 0.0
    for x, y in zip(xs, values):
        dx = x - mean_x
        num += dx * (y - mean_y)
        den += dx * dx
    if den <= 0:
        return None
    b = num / den
    a = mean_y - b * mean_x
    ss_tot = 0.0
    ss_res = 0.0
    for x, y in zip(xs, values):
        y_hat = a + b * x
        ss_tot += (y - mean_y) ** 2
        ss_res += (y - y_hat) ** 2
    if ss_tot <= 1e-18:
        r2 = 1.0 if ss_res <= 1e-18 else 0.0
    else:
        r2 = max(0.0, min(1.0, 1.0 - ss_res / ss_tot))
    return float(b), float(r2), int(n)


def linear_slope(values: Sequence[float]) -> Optional[float]:
    """简单线性回归斜率：y ~ a + b*x，x=0..n-1。兼容旧调用。"""
    fit = linear_slope_fit(values)
    return None if fit is None else fit[0]


def _prepare_slope_values(
    benchmark: List[Dict[str, float]],
    window: int,
    *,
    transform: str = "log",
) -> Optional[List[float]]:
    if not benchmark:
        return None
    w = max(5, int(window))
    vals = [float(b["i_t"]) for b in benchmark[-w:]]
    mode = (transform or "log").strip().lower()
    if mode in ("log", "ln", "log_it"):
        log_vals: List[float] = []
        for v in vals:
            if v is None or float(v) <= 0:
                return None
            log_vals.append(math.log(float(v)))
        return log_vals
    return vals


def sector_slope_fit(
    benchmark: List[Dict[str, float]],
    window: int,
    *,
    transform: str = "log",
) -> Optional[Dict[str, float]]:
    """近 window 日板块基准回归，返回 {sector_slope, slope_r2, slope_n}。"""
    vals = _prepare_slope_values(benchmark, window, transform=transform)
    if vals is None:
        return None
    fit = linear_slope_fit(vals)
    if fit is None:
        return None
    b, r2, n = fit
    return {
        "sector_slope": float(b),
        "slope_r2": float(r2),
        "slope_n": float(n),
    }


def sector_slope(
    benchmark: List[Dict[str, float]],
    window: int,
    *,
    transform: str = "log",
) -> Optional[float]:
    """近 window 日板块基准回归斜率。

    transform:
      - ``log`` / ``ln``：对 ln(I_t) 回归（近似日对数收益趋势，跨板可比；
        行情板块详情、GMS 入库、RPE 默认口径）
      - ``none``：对原始 I_t 回归（绝对价位斜率，历史兼容）
    """
    info = sector_slope_fit(benchmark, window, transform=transform)
    return None if info is None else float(info["sector_slope"])


def index_closes_to_benchmark(
    rows: Sequence[Dict],
) -> List[Dict[str, float]]:
    """将指数日 K（含 date/close）转为斜率用的 benchmark 序列。"""
    out: List[Dict[str, float]] = []
    for r in rows or []:
        d = str(r.get("date") or r.get("trade_date") or "")[:10]
        try:
            c = float(r.get("close") or 0)
        except (TypeError, ValueError):
            continue
        if not d or c <= 0:
            continue
        out.append({"date": d, "i_t": c})
    out.sort(key=lambda x: x["date"])
    return out
