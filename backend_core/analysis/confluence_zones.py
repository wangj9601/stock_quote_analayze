# -*- coding: utf-8 -*-
"""多源价位 1D 聚类 → 少而精共振支撑/压力带（参考用，不作策略硬门槛）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

PRICE_DECIMALS = 2
MAX_ZONES_EACH = 3
ALIGN_TOL_PCT = 0.015


def _f(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def _add(
    points: List[Dict[str, Any]],
    price: Any,
    *,
    source: str,
    weight: float,
    label: Optional[str] = None,
) -> None:
    p = _f(price)
    if p is None or p <= 0:
        return
    points.append(
        {
            "price": float(p),
            "source": source,
            "weight": float(weight),
            "label": label or source,
        }
    )


def collect_candidate_points(
    *,
    kde_support: Optional[float] = None,
    kde_resistance: Optional[float] = None,
    kde_supports: Optional[Sequence[float]] = None,
    kde_resistances: Optional[Sequence[float]] = None,
    volume_profile: Optional[Dict[str, Any]] = None,
    fibonacci: Optional[Dict[str, Any]] = None,
    pivot: Optional[Dict[str, Any]] = None,
    camarilla: Optional[Dict[str, Any]] = None,
    atr_pivot: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    pts: List[Dict[str, Any]] = []
    _add(pts, kde_support, source="kde", weight=1.0, label="kde_nearest_s")
    _add(pts, kde_resistance, source="kde", weight=1.0, label="kde_nearest_r")
    for i, v in enumerate(list(kde_supports or [])[:3]):
        _add(pts, v, source="kde", weight=1.0, label=f"kde_s{i+1}")
    for i, v in enumerate(list(kde_resistances or [])[:3]):
        _add(pts, v, source="kde", weight=1.0, label=f"kde_r{i+1}")

    vp = volume_profile or {}
    if vp.get("ok"):
        for key, lab in (
            ("poc", "vp_poc"),
            ("val", "vp_val"),
            ("vah", "vp_vah"),
            ("nearest_support", "vp_ns"),
            ("nearest_resistance", "vp_nr"),
        ):
            _add(pts, vp.get(key), source="vp", weight=0.85, label=lab)

    fib = fibonacci or {}
    for x in fib.get("retracements") or []:
        if isinstance(x, dict):
            _add(
                pts,
                x.get("price"),
                source="fib",
                weight=0.7,
                label=f"fib_{x.get('ratio')}",
            )
    ne = fib.get("nearest_extension")
    if isinstance(ne, dict):
        _add(pts, ne.get("price"), source="fib", weight=0.65, label="fib_ext")

    piv = pivot or {}
    for k in ("P", "S1", "S2", "R1", "R2"):
        _add(pts, piv.get(k), source="pivot", weight=0.5, label=f"piv_{k}")

    cam = camarilla or {}
    for k in ("S1", "S2", "S3", "R1", "R2", "R3"):
        _add(pts, cam.get(k), source="camarilla", weight=0.65, label=f"cam_{k}")
    for k in ("S4", "R4"):
        _add(pts, cam.get(k), source="camarilla", weight=0.45, label=f"cam_{k}")

    ap = atr_pivot or {}
    for k in ("S2", "S1", "P", "R1", "R2"):
        _add(pts, ap.get(k), source="atr_pivot", weight=0.55, label=f"atr_{k}")

    return pts


def _cluster_dbscan(
    prices: List[float],
    *,
    eps: float,
) -> List[int]:
    try:
        from sklearn.cluster import DBSCAN
        import numpy as np

        X = np.asarray(prices, dtype=float).reshape(-1, 1)
        labels = DBSCAN(eps=float(eps), min_samples=2, metric="euclidean").fit_predict(X)
        return [int(x) for x in labels]
    except Exception:
        return _cluster_distance_merge(prices, eps=eps)


def _cluster_distance_merge(
    prices: List[float],
    *,
    eps: float,
) -> List[int]:
    """无 sklearn：按价格排序后相邻距离合并。"""
    n = len(prices)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: prices[i])
    labels = [-1] * n
    cid = 0
    cluster_members = [order[0]]
    for idx in order[1:]:
        prev = cluster_members[-1]
        mid = (prices[idx] + prices[prev]) / 2.0
        thr = float(eps)
        # eps 既可能是绝对价格距离（与 DBSCAN 一致）
        if abs(prices[idx] - prices[prev]) <= thr:
            cluster_members.append(idx)
        else:
            for m in cluster_members:
                labels[m] = cid if len(cluster_members) >= 2 else -1
            cid += 1
            cluster_members = [idx]
    for m in cluster_members:
        labels[m] = cid if len(cluster_members) >= 2 else -1
    return labels


def build_confluence_zones(
    points: Sequence[Dict[str, Any]],
    *,
    last_close: Optional[float],
    atr: Optional[float] = None,
    max_each: int = MAX_ZONES_EACH,
) -> Dict[str, Any]:
    pts = [p for p in points if _f(p.get("price")) is not None]
    empty = {
        "ok": False,
        "reason": "insufficient_points",
        "method": "dbscan_or_distance_merge",
        "supports": [],
        "resistances": [],
        "nearest_support_zone": None,
        "nearest_resistance_zone": None,
        "eps": None,
    }
    if len(pts) < 2:
        return empty

    px = _f(last_close)
    prices = [float(p["price"]) for p in pts]
    ref_px = px if px and px > 0 else (sum(prices) / len(prices))
    atr_v = _f(atr)
    eps = max(
        (atr_v * 0.35) if atr_v and atr_v > 0 else 0.0,
        abs(ref_px) * 0.012,
    )
    if eps <= 0:
        eps = abs(ref_px) * 0.012 or 0.01

    labels = _cluster_dbscan(prices, eps=eps)
    method = "dbscan"
    try:
        import sklearn  # noqa: F401
    except Exception:
        method = "distance_merge"

    clusters: Dict[int, List[Dict[str, Any]]] = {}
    for p, lab in zip(pts, labels):
        if lab < 0:
            continue
        clusters.setdefault(int(lab), []).append(p)

    zones: List[Dict[str, Any]] = []
    for lab, members in clusters.items():
        if len(members) < 2:
            continue
        wsum = sum(float(m["weight"]) for m in members) or 1.0
        center = sum(float(m["price"]) * float(m["weight"]) for m in members) / wsum
        lo = min(float(m["price"]) for m in members)
        hi = max(float(m["price"]) for m in members)
        sources = sorted({str(m["source"]) for m in members})
        labels_u = sorted({str(m.get("label") or m["source"]) for m in members})
        strength = wsum * len(sources)
        zones.append(
            {
                "center": round(center, PRICE_DECIMALS),
                "low": round(lo, PRICE_DECIMALS),
                "high": round(hi, PRICE_DECIMALS),
                "strength": round(strength, 3),
                "sources": sources,
                "labels": labels_u,
                "n_points": len(members),
            }
        )

    if not zones:
        return {
            **empty,
            "reason": "no_clusters",
            "eps": round(eps, PRICE_DECIMALS),
            "method": method,
        }

    if px is None:
        # 无现价时按中位价二分，避免同一带同时进支撑/压力
        mid = sorted(z["center"] for z in zones)[len(zones) // 2]
        supports = [z for z in zones if z["center"] <= mid]
        resistances = [z for z in zones if z["center"] > mid]
    else:
        supports = [z for z in zones if z["center"] < px]
        resistances = [z for z in zones if z["center"] > px]
    supports.sort(key=lambda z: (-z["strength"], -z["center"]))
    resistances.sort(key=lambda z: (-z["strength"], z["center"]))
    supports = supports[: max(1, int(max_each))]
    resistances = resistances[: max(1, int(max_each))]

    nearest_s = max(supports, key=lambda z: z["center"]) if supports else None
    nearest_r = min(resistances, key=lambda z: z["center"]) if resistances else None

    return {
        "ok": True,
        "reason": "ok",
        "method": method,
        "eps": round(eps, PRICE_DECIMALS),
        "supports": supports,
        "resistances": resistances,
        "nearest_support_zone": nearest_s,
        "nearest_resistance_zone": nearest_r,
    }


def compute_confluence_from_reference(
    ref: Dict[str, Any],
    *,
    kde_support: Optional[float] = None,
    kde_resistance: Optional[float] = None,
    kde_supports: Optional[Sequence[float]] = None,
    kde_resistances: Optional[Sequence[float]] = None,
    last_close: Optional[float] = None,
    atr: Optional[float] = None,
) -> Dict[str, Any]:
    pts = collect_candidate_points(
        kde_support=kde_support,
        kde_resistance=kde_resistance,
        kde_supports=kde_supports,
        kde_resistances=kde_resistances,
        volume_profile=ref.get("volume_profile"),
        fibonacci=ref.get("fibonacci"),
        pivot=ref.get("pivot"),
        camarilla=ref.get("camarilla"),
        atr_pivot=ref.get("atr_pivot"),
    )
    atr_v = atr if atr is not None else (ref.get("atr") or (ref.get("atr_pivot") or {}).get("atr"))
    lc = last_close if last_close is not None else ref.get("last_close")
    return build_confluence_zones(pts, last_close=lc, atr=atr_v)
