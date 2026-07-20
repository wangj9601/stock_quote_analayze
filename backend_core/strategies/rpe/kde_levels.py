"""成交量加权 KDE 支撑/阻力提取。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


def _safe_peaks(y: Sequence[float], x: Sequence[float]) -> List[float]:
    try:
        from scipy.signal import find_peaks
    except Exception:
        # fallback: local maxima
        peaks = []
        for i in range(1, len(y) - 1):
            if y[i] >= y[i - 1] and y[i] >= y[i + 1] and y[i] > 0:
                peaks.append(float(x[i]))
        return peaks
    idxs, _ = find_peaks(y, prominence=max(float(max(y)) * 0.05, 1e-12) if y else 1e-12)
    return [float(x[i]) for i in idxs]


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

    try:
        from scipy.stats import gaussian_kde
        import numpy as np

        # gaussian_kde 权重通过 resample 近似：重复采样按权重比例太重；
        # 使用 dataset=price，weights 在较新 scipy 支持；若不支持则按权重重复轻量扩展。
        arr = np.asarray(prices, dtype=float)
        warr = np.asarray(weights, dtype=float)
        warr = warr / warr.sum()
        try:
            kde = gaussian_kde(arr, bw_method=bw, weights=warr)
        except TypeError:
            # 旧版无 weights：按归一化权重离散复制（上限控制）
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
        logger.warning("KDE failed: %s", e)
        return {
            "support_levels": [],
            "resistance_levels": [],
            "all_peaks": [],
            "bw": bw,
            "ok": False,
            "reason": f"kde_error:{e}",
        }

    supports = sorted([p for p in peaks if p < last_price], reverse=True)
    resistances = sorted([p for p in peaks if p >= last_price])
    return {
        "support_levels": supports[:8],
        "resistance_levels": resistances[:8],
        "all_peaks": peaks,
        "bw": bw,
        "ok": True,
        "reason": "ok",
        "last_price": last_price,
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
