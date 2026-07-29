"""成交量加权 KDE 支撑/阻力提取。

优先使用 scipy.stats.gaussian_kde；生产最小依赖若未装 scipy，
则回退到成交量加权直方图 + 平滑，避免支撑/阻力整列为空。
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


def _safe_peaks(y: Sequence[float], x: Sequence[float], *, prominence_ratio: float = 0.05) -> List[float]:
    try:
        from scipy.signal import find_peaks
    except Exception:
        return _local_maxima_peaks(y, x)
    if not y:
        return []
    prom = max(float(max(y)) * float(prominence_ratio), 1e-12)
    idxs, _ = find_peaks(y, prominence=prom)
    peaks = [float(x[i]) for i in idxs]
    if peaks:
        return peaks
    # 过平滑时 prominence 可能一个峰都找不到，退回局部极大
    return _local_maxima_peaks(y, x)


def _local_maxima_peaks(y: Sequence[float], x: Sequence[float]) -> List[float]:
    peaks = []
    for i in range(1, len(y) - 1):
        if y[i] >= y[i - 1] and y[i] >= y[i + 1] and y[i] > 0:
            peaks.append(float(x[i]))
    return peaks


def _weighted_histogram_density(
    prices: Sequence[float],
    weights: Sequence[float],
    *,
    bw: float,
    grid_points: int,
) -> Tuple[List[float], List[float]]:
    """无 scipy 时的密度近似：成交量加权直方图 + 三点平滑。"""
    lo = min(prices) * 0.98
    hi = max(prices) * 1.02
    if hi <= lo:
        hi = lo + max(abs(lo) * 0.01, 1e-6)
    n = int(max(50, grid_points))
    # 分箱宽度与带宽同量级，至少覆盖价格区间的 1/n
    span = hi - lo
    bin_w = max(bw * (sum(prices) / len(prices)), span / n, 1e-6)
    bins = max(20, int(math.ceil(span / bin_w)))
    edges = [lo + span * i / bins for i in range(bins + 1)]
    hist = [0.0] * bins
    wsum = sum(weights) or 1.0
    for p, w in zip(prices, weights):
        if p <= lo:
            idx = 0
        elif p >= hi:
            idx = bins - 1
        else:
            idx = min(bins - 1, int((p - lo) / span * bins))
        hist[idx] += float(w) / wsum

    # 三点平滑
    smooth = hist[:]
    for i in range(bins):
        left = hist[i - 1] if i > 0 else hist[i]
        right = hist[i + 1] if i + 1 < bins else hist[i]
        smooth[i] = 0.25 * left + 0.5 * hist[i] + 0.25 * right

    xs = [(edges[i] + edges[i + 1]) / 2.0 for i in range(bins)]
    # 插值到目标网格，便于峰检测
    grid = [lo + (hi - lo) * i / (n - 1) for i in range(n)]
    ys: List[float] = []
    j = 0
    for gx in grid:
        while j + 1 < len(xs) and xs[j + 1] < gx:
            j += 1
        if j + 1 >= len(xs):
            ys.append(smooth[-1])
        else:
            x0, x1 = xs[j], xs[j + 1]
            y0, y1 = smooth[j], smooth[j + 1]
            t = 0.0 if x1 == x0 else (gx - x0) / (x1 - x0)
            ys.append(y0 + (y1 - y0) * t)
    return grid, ys


def extract_kde_levels(
    closes: Sequence[float],
    volumes: Sequence[float],
    *,
    base_factor: float = 1.0,
    grid_points: int = 200,
) -> Dict[str, Any]:
    """
    以成交量为权重对价格做 gaussian_kde，提取密度峰作为结构坐标。
    返回 support_levels（低于现价）、resistance_levels（高于现价）。
    """
    pairs: List[Tuple[float, float]] = []
    for c, v in zip(closes, volumes):
        try:
            pc = float(c)
            vv = float(v)
        except (TypeError, ValueError):
            continue
        if pc <= 0 or vv <= 0:
            continue
        pairs.append((pc, vv))
    if len(pairs) < 20:
        return {
            "support_levels": [],
            "resistance_levels": [],
            "all_peaks": [],
            "bw": None,
            "ok": False,
            "reason": "insufficient_samples",
        }

    prices = [p for p, _ in pairs]
    weights = [w for _, w in pairs]
    last_price = prices[-1]
    mu = sum(prices) / len(prices)
    var = sum((p - mu) ** 2 for p in prices) / len(prices)
    sigma = var ** 0.5
    if mu <= 0 or sigma <= 0:
        return {
            "support_levels": [],
            "resistance_levels": [],
            "all_peaks": [],
            "bw": None,
            "ok": False,
            "reason": "bad_stats",
        }

    bw = float(base_factor) * (sigma / mu)
    bw = max(bw, 0.01)
    method = "scipy"
    peaks: List[float] = []

    try:
        from scipy.stats import gaussian_kde
        import numpy as np

        arr = np.asarray(prices, dtype=float)
        warr = np.asarray(weights, dtype=float)
        warr = warr / warr.sum()
        try:
            kde = gaussian_kde(arr, bw_method=bw, weights=warr)
        except TypeError:
            expanded = []
            for p, w in zip(prices, warr):
                n = max(1, int(round(w * 200)))
                expanded.extend([p] * n)
            kde = gaussian_kde(np.asarray(expanded, dtype=float), bw_method=bw)

        lo = min(prices) * 0.98
        hi = max(prices) * 1.02
        xs = np.linspace(lo, hi, int(max(50, grid_points)))
        ys = kde(xs)
        peaks = _safe_peaks(ys.tolist(), xs.tolist())
    except Exception as e:
        logger.warning("scipy KDE unavailable, fallback to histogram: %s", e)
        method = "histogram_fallback"
        try:
            xs, ys = _weighted_histogram_density(
                prices, weights, bw=bw, grid_points=int(max(50, grid_points))
            )
            peaks = _safe_peaks(ys, xs, prominence_ratio=0.03)
        except Exception as e2:
            logger.warning("KDE histogram fallback failed: %s", e2)
            return {
                "support_levels": [],
                "resistance_levels": [],
                "all_peaks": [],
                "bw": bw,
                "ok": False,
                "reason": f"kde_error:{e2}",
            }

    supports = sorted([p for p in peaks if p < last_price], reverse=True)
    resistances = sorted([p for p in peaks if p >= last_price])
    reason = "ok" if method == "scipy" else "ok_histogram_fallback"
    return {
        "support_levels": supports[:8],
        "resistance_levels": resistances[:8],
        "all_peaks": peaks,
        "bw": bw,
        "ok": True,
        "reason": reason,
        "last_price": last_price,
        "method": method,
    }


def nearest_levels(
    price: float,
    support_levels: Sequence[float],
    resistance_levels: Sequence[float],
) -> Dict[str, Optional[float]]:
    nearest_support = None
    for s in support_levels:
        if s < price:
            nearest_support = float(s)
            break
    nearest_resistance = None
    for r in resistance_levels:
        if r >= price:
            nearest_resistance = float(r)
            break
    return {"nearest_support": nearest_support, "nearest_resistance": nearest_resistance}


# 支撑缺失时回看递推：250 → 500 → 750（约 3 年交易日）
KDE_LOOKBACK_STEP = 250
KDE_LOOKBACK_MAX = 750


def _split_peaks_by_price(
    peaks: Sequence[float], price: float
) -> Tuple[List[float], List[float]]:
    supports = sorted([float(p) for p in peaks if 0 < float(p) < price], reverse=True)
    resistances = sorted([float(p) for p in peaks if float(p) >= price])
    return supports, resistances


def extract_kde_levels_expand_support(
    closes: Sequence[float],
    volumes: Sequence[float],
    *,
    price: Optional[float] = None,
    initial_lookback: int = KDE_LOOKBACK_STEP,
    step: int = KDE_LOOKBACK_STEP,
    max_lookback: int = KDE_LOOKBACK_MAX,
    base_factor: float = 1.0,
    grid_points: int = 200,
) -> Dict[str, Any]:
    """
    用近端窗口做成交量加权 KDE；若现价下方无支撑峰，则按 step 扩大回看，
    直至找到支撑或达到 max_lookback（默认 750≈3 年）。

    closes/volumes 须按时间升序；函数内部只取末尾窗口，不会超过传入长度。
    """
    n = len(closes)
    empty = {
        "support_levels": [],
        "resistance_levels": [],
        "all_peaks": [],
        "bw": None,
        "ok": False,
        "reason": "insufficient_samples",
        "lookback_used": 0,
        "lookback_expanded": False,
        "method": None,
    }
    if n < 20:
        return empty

    try:
        ref_price = float(price) if price is not None else float(closes[-1])
    except (TypeError, ValueError):
        return empty
    if ref_price <= 0:
        return empty

    init_lb = max(20, int(initial_lookback))
    max_lb = max(init_lb, int(max_lookback))
    step_n = max(1, int(step))

    last: Dict[str, Any] = empty
    used = init_lb
    while True:
        take = min(used, n)
        kde = extract_kde_levels(
            list(closes[-take:]),
            list(volumes[-take:]),
            base_factor=base_factor,
            grid_points=grid_points,
        )
        peaks = [float(p) for p in (kde.get("all_peaks") or []) if p is not None]
        supports, resistances = _split_peaks_by_price(peaks, ref_price)
        out = dict(kde)
        out["support_levels"] = supports[:8]
        out["resistance_levels"] = resistances[:8]
        out["all_peaks"] = peaks
        out["lookback_used"] = take
        out["lookback_expanded"] = take > min(init_lb, n)
        out["last_price"] = ref_price
        last = out

        if supports:
            if out["lookback_expanded"] and out.get("reason") in ("ok", "ok_histogram_fallback", None):
                out["reason"] = (
                    f"{out.get('reason') or 'ok'}_expanded_{take}"
                )
            return out

        if take >= n or used >= max_lb:
            break
        used = min(used + step_n, max_lb)

    if last is empty:
        return empty
    if not last.get("support_levels"):
        # 已扩到上限仍无支撑
        reason = last.get("reason") or "ok"
        last["reason"] = f"{reason}_no_support_after_expand"
    return last

