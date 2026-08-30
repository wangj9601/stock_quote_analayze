"""多周期加权 RS_Raw 与截面百分位评级。"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .config import RS_WEIGHTS, RS_WINDOWS


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def roc(closes_asc: Sequence[float], window: int) -> Optional[float]:
    """
    ROC(n) = P_t / P_{t-n} - 1。
    closes_asc：按交易日升序的收盘价；需要至少 window+1 根。
    """
    n = int(window)
    if n < 1 or len(closes_asc) < n + 1:
        return None
    p_t = _safe_float(closes_asc[-1])
    p_prev = _safe_float(closes_asc[-(n + 1)])
    if p_t is None or p_prev is None or p_prev <= 0:
        return None
    return p_t / p_prev - 1.0


def compute_rs_raw(
    closes_asc: Sequence[float],
    *,
    windows: Sequence[int] = RS_WINDOWS,
    weights: Sequence[float] = RS_WEIGHTS,
) -> Optional[Dict[str, Any]]:
    """计算单票 RS_Raw 与各窗口 ROC；任一窗口缺失则返回 None。"""
    wins = list(windows)
    wts = list(weights)
    if len(wins) != len(wts) or not wins:
        return None
    rocs: List[float] = []
    detail: Dict[str, float] = {}
    for w in wins:
        r = roc(closes_asc, w)
        if r is None:
            return None
        rocs.append(r)
        detail[f"roc_{w}"] = float(r)
    raw = sum(float(wt) * float(r) for wt, r in zip(wts, rocs))
    return {
        "rs_raw": float(raw),
        **detail,
    }


def percentile_ranks_0_1(values: Sequence[Optional[float]]) -> List[Optional[float]]:
    """截面百分位 [0, 1]；并列取平均秩。None 保持 None。"""
    indexed = [(i, _safe_float(v)) for i, v in enumerate(values)]
    valid = [(i, v) for i, v in indexed if v is not None]
    out: List[Optional[float]] = [None] * len(values)
    n = len(valid)
    if n == 0:
        return out
    if n == 1:
        out[valid[0][0]] = 1.0
        return out
    valid.sort(key=lambda x: x[1])
    i = 0
    while i < n:
        j = i
        while j + 1 < n and valid[j + 1][1] == valid[i][1]:
            j += 1
        avg_rank = (i + j) / 2.0  # 0-based
        pct = avg_rank / (n - 1)
        for k in range(i, j + 1):
            out[valid[k][0]] = pct
        i = j + 1
    return out


def percentile_to_rating(percentile_0_1: Optional[float]) -> Optional[int]:
    """percentile ∈ [0,1] → 整数 1–99。"""
    if percentile_0_1 is None:
        return None
    p = float(percentile_0_1)
    if math.isnan(p) or math.isinf(p):
        return None
    p = max(0.0, min(1.0, p))
    rating = int(round(p * 98.0 + 1.0))
    return max(1, min(99, rating))


def rank_cross_section(
    rows: Sequence[Dict[str, Any]],
    *,
    publish_ratings: bool,
) -> List[Dict[str, Any]]:
    """
    对含 rs_raw 的行做截面排名，写入 rs_rating / percentile。
    publish_ratings=False 时 rs_rating 一律为 None（仍写 percentile 便于排查）。
    """
    raws = [_safe_float(r.get("rs_raw")) for r in rows]
    pcts = percentile_ranks_0_1(raws)
    out: List[Dict[str, Any]] = []
    for r, pct in zip(rows, pcts):
        item = dict(r)
        item["percentile"] = pct
        item["rs_rating"] = percentile_to_rating(pct) if publish_ratings else None
        out.append(item)
    return out
