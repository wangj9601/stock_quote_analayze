"""板块簇成交量加权基准 I_t 与斜率。"""

from __future__ import annotations

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


def linear_slope(values: Sequence[float]) -> Optional[float]:
    """简单线性回归斜率：y ~ a + b*x，x=0..n-1。"""
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
    return num / den


def sector_slope(
    benchmark: List[Dict[str, float]],
    window: int,
    *,
    transform: str = "none",
) -> Optional[float]:
    """近 window 日 I_t 回归斜率。

    transform:
      - ``none``：对原始 I_t 回归（绝对价位斜率，RPE 历史口径）
      - ``log``：对 ln(I_t) 回归（近似日对数收益趋势，跨板更可比；GMS/板指标入库用）
    """
    if not benchmark:
        return None
    w = max(5, int(window))
    vals = [float(b["i_t"]) for b in benchmark[-w:]]
    mode = (transform or "none").strip().lower()
    if mode in ("log", "ln", "log_it"):
        import math

        log_vals: List[float] = []
        for v in vals:
            if v is None or float(v) <= 0:
                return None
            log_vals.append(math.log(float(v)))
        vals = log_vals
    return linear_slope(vals)
