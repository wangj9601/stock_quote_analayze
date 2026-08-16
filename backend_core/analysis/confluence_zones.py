# -*- coding: utf-8 -*-
"""多源价位 1D 聚类 → 少而精共振支撑/压力带（参考用，不作策略硬门槛）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

PRICE_DECIMALS = 2
MAX_ZONES_EACH = 3
ALIGN_TOL_PCT = 0.015
# 近端密集簇兜底：现价±near_pct 内，点数≥near_min_points 或 来源数≥near_min_sources
# 时强制纳入 nearest_* 候选（避免远端高强度带截断 TopN 后近端消失）
NEAR_PCT = 0.025  # 2.5%
NEAR_MIN_SOURCES = 2
NEAR_MIN_POINTS = 3
# 单带最大相对带宽（相对中心）；超出则按簇内最大 gap 拆成近端/远端带（不改全局 eps）
MAX_ZONE_WIDTH_PCT = 0.025  # 2.5%
_MAX_ZONE_SPLIT_DEPTH = 4
# 支撑位于 VP VAL 下方（筹码真空侧）时：保留原始 strength，另输出折减强度与警示
CHIPS_VOID_STRENGTH_FACTOR = 0.85
CHIPS_VOID_ATR_PCT_HIGH = 0.04  # ATR/close ≥4% 时 void_note 强调高 ATR 击穿
# 阻力与 VP 关键水平（POC/VAH/VAL）重叠时：保留原始 strength，另输出增益强度（与真空折减对称、分边）
CHIPS_HVZ_GAIN = 1.25
CHIPS_HVZ_OVERLAP_PCT = 0.01  # 落入带内，或相对距离 ≤1%
# 展示分档：与战术贴压强度门槛对齐（≥10 或来源≥3 → 强共振）
STRONG_TIER_STRENGTH = 10.0
STRONG_TIER_MIN_SOURCES = 3
# 多源等距时的来源优先级（数值越小优先）
_HVZ_SOURCE_PRIORITY = {"poc": 0, "vah": 1, "val": 2}


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
    kde_multi_windows: Optional[Dict[str, Any]] = None,
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

    # Phase1：多窗同源峰（默认进共振；source=kde_60/120/250）
    mw_root = kde_multi_windows or {}
    mw_map = mw_root.get("windows") if isinstance(mw_root.get("windows"), dict) else mw_root
    if isinstance(mw_map, dict):
        for key, entry in mw_map.items():
            if not isinstance(entry, dict) or not entry.get("ok"):
                continue
            try:
                win = int(key)
            except (TypeError, ValueError):
                continue
            wgt = _f(entry.get("weight"))
            if wgt is None:
                wgt = {60: 0.55, 120: 0.65, 250: 0.75}.get(win, 0.6)
            src = f"kde_{win}"
            for i, v in enumerate(list(entry.get("support_levels") or [])[:3]):
                _add(pts, v, source=src, weight=float(wgt), label=f"{src}_s{i+1}")
            for i, v in enumerate(list(entry.get("resistance_levels") or [])[:3]):
                _add(pts, v, source=src, weight=float(wgt), label=f"{src}_r{i+1}")

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


def _members_center(members: Sequence[Dict[str, Any]]) -> float:
    wsum = sum(float(m["weight"]) for m in members) or 1.0
    return sum(float(m["price"]) * float(m["weight"]) for m in members) / wsum


def _members_width_pct(members: Sequence[Dict[str, Any]]) -> float:
    if len(members) < 2:
        return 0.0
    lo = min(float(m["price"]) for m in members)
    hi = max(float(m["price"]) for m in members)
    center = abs(_members_center(members))
    if center <= 0:
        mid = abs((lo + hi) / 2.0)
        if mid <= 0:
            return 0.0
        return (hi - lo) / mid
    return (hi - lo) / center


def _zone_dict_from_members(members: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    wsum = sum(float(m["weight"]) for m in members) or 1.0
    center = sum(float(m["price"]) * float(m["weight"]) for m in members) / wsum
    lo = min(float(m["price"]) for m in members)
    hi = max(float(m["price"]) for m in members)
    sources = sorted({str(m["source"]) for m in members})
    labels_u = sorted({str(m.get("label") or m["source"]) for m in members})
    strength = wsum * len(sources)
    return {
        "center": round(center, PRICE_DECIMALS),
        "low": round(lo, PRICE_DECIMALS),
        "high": round(hi, PRICE_DECIMALS),
        "strength": round(strength, 3),
        "sources": sources,
        "labels": labels_u,
        "n_points": len(members),
    }


def annotate_zone_tier(
    zone: Optional[Dict[str, Any]],
    *,
    side: str,
    strong_strength: float = STRONG_TIER_STRENGTH,
    strong_min_sources: int = STRONG_TIER_MIN_SOURCES,
) -> Optional[Dict[str, Any]]:
    """为共振带补充展示字段 tier / label_zh（不改 strength 公式）。"""
    if not isinstance(zone, dict):
        return zone
    z = dict(zone)
    strength = _f(z.get("strength"))
    if strength is None:
        strength = _f(z.get("strength_adjusted"))
    n_src = len(z.get("sources") or [])
    is_strong = (strength is not None and float(strength) >= float(strong_strength)) or (
        n_src >= int(strong_min_sources)
    )
    side_n = str(side or "").strip().lower()
    is_support = side_n in ("support", "s", "支撑")
    z["tier"] = "strong" if is_strong else "normal"
    if is_support:
        z["label_zh"] = "强共振支撑" if is_strong else "共振支撑"
    else:
        z["label_zh"] = "强共振压力" if is_strong else "共振压力"
    return z


def _annotate_zones_tier(
    zones: Sequence[Dict[str, Any]],
    *,
    side: str,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for z in zones or []:
        az = annotate_zone_tier(z if isinstance(z, dict) else None, side=side)
        if az is not None:
            out.append(az)
    return out


def _split_members_by_max_gap(
    members: Sequence[Dict[str, Any]],
) -> Optional[Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]]:
    """按相邻最大价差二分；两侧均须 ≥2 点，否则不可拆。"""
    if len(members) < 4:
        return None
    ordered = sorted(members, key=lambda m: float(m["price"]))
    best_i: Optional[int] = None
    best_gap = -1.0
    for i in range(len(ordered) - 1):
        left_n = i + 1
        right_n = len(ordered) - left_n
        if left_n < 2 or right_n < 2:
            continue
        gap = float(ordered[i + 1]["price"]) - float(ordered[i]["price"])
        if gap > best_gap:
            best_gap = gap
            best_i = i
    if best_i is None:
        return None
    left = list(ordered[: best_i + 1])
    right = list(ordered[best_i + 1 :])
    return left, right


def _split_wide_members(
    members: Sequence[Dict[str, Any]],
    *,
    max_zone_width_pct: float,
    depth: int = 0,
    max_depth: int = _MAX_ZONE_SPLIT_DEPTH,
) -> List[List[Dict[str, Any]]]:
    """带宽超限则按最大 gap 递归拆成近端/远端子簇。"""
    mem = list(members)
    if len(mem) < 2:
        return []
    max_w = float(max_zone_width_pct)
    if max_w <= 0 or _members_width_pct(mem) <= max_w or depth >= int(max_depth):
        return [mem]
    parts = _split_members_by_max_gap(mem)
    if parts is None:
        return [mem]
    left, right = parts
    # 支撑语义：价高一侧更近现价；压力相反——此处仅拆簇，侧向分类仍走后续 center vs px
    out: List[List[Dict[str, Any]]] = []
    out.extend(
        _split_wide_members(
            left, max_zone_width_pct=max_w, depth=depth + 1, max_depth=max_depth
        )
    )
    out.extend(
        _split_wide_members(
            right, max_zone_width_pct=max_w, depth=depth + 1, max_depth=max_depth
        )
    )
    return out if out else [mem]


def _clip_zone_to_price_side(
    zone: Dict[str, Any],
    *,
    px: float,
    side: str,
) -> Optional[Dict[str, Any]]:
    """按现价裁剪带区间，避免「支撑带上沿 > 现价」等语义越界。

    - support：high 裁到 ≤ px，必要时重算 center
    - resistance：low 裁到 ≥ px
    裁剪后若 low >= high（相对容差）则丢弃该带。
    """
    z = dict(zone)
    try:
        lo = float(z["low"])
        hi = float(z["high"])
        center = float(z.get("center") or ((lo + hi) / 2.0))
    except (KeyError, TypeError, ValueError):
        return None
    clipped = False
    if side == "support":
        if lo >= px:
            return None
        if hi > px:
            hi = px
            clipped = True
    else:
        if hi <= px:
            return None
        if lo < px:
            lo = px
            clipped = True
    if hi - lo <= max(abs(px) * 1e-6, 1e-9):
        return None
    if center < lo or center > hi:
        center = (lo + hi) / 2.0
        clipped = True
    z["low"] = round(lo, PRICE_DECIMALS)
    z["high"] = round(hi, PRICE_DECIMALS)
    z["center"] = round(center, PRICE_DECIMALS)
    if clipped:
        z["clipped_to_price"] = True
    return z


def _zone_id(z: Dict[str, Any]) -> Tuple[float, float, float]:
    return (float(z["center"]), float(z["low"]), float(z["high"]))


def _zone_void_ref_price(z: Dict[str, Any]) -> Optional[float]:
    """真空判定参考价：优先 center，否则 high。"""
    c = _f(z.get("center"))
    if c is not None:
        return c
    return _f(z.get("high"))


def _chips_void_note(
    *,
    val: float,
    lookback: Optional[int] = None,
    atr: Optional[float] = None,
    last_close: Optional[float] = None,
) -> str:
    lb = int(lookback) if lookback and int(lookback) > 0 else 60
    base = f"位于{lb}日筹码真空区（VAL={round(float(val), PRICE_DECIMALS)}）"
    a, c = _f(atr), _f(last_close)
    if a is not None and c is not None and c > 0 and (a / c) >= float(CHIPS_VOID_ATR_PCT_HIGH):
        atr_pct = a / c * 100.0
        return f"{base}，ATR≈{atr_pct:.1f}%，需防范高ATR击穿效应"
    return f"{base}，需防范高ATR击穿效应"


def annotate_support_chips_void(
    zone: Dict[str, Any],
    *,
    vp_val: Optional[float],
    vp_lookback: Optional[int] = None,
    atr: Optional[float] = None,
    last_close: Optional[float] = None,
    factor: float = CHIPS_VOID_STRENGTH_FACTOR,
) -> Dict[str, Any]:
    """若支撑带参考价 < VAL，保留 strength，写入 strength_adjusted / chips_void / void_note。

    无 VAL 或带不在真空侧时原样返回（不破坏无 VP 路径）。
    仅作用于支撑侧；不与阻力 HVZ 增益混用。
    """
    z = dict(zone)
    val = _f(vp_val)
    if val is None or val <= 0:
        return z
    ref = _zone_void_ref_price(z)
    if ref is None or ref >= val:
        return z
    strength = _f(z.get("strength"))
    fac = float(factor) if factor and float(factor) > 0 else float(CHIPS_VOID_STRENGTH_FACTOR)
    z["chips_void"] = True
    z["void_val"] = round(val, PRICE_DECIMALS)
    if vp_lookback is not None and int(vp_lookback) > 0:
        z["void_lookback"] = int(vp_lookback)
    z["void_note"] = _chips_void_note(
        val=val, lookback=vp_lookback, atr=atr, last_close=last_close
    )
    if strength is not None:
        z["strength_adjusted"] = round(strength * fac, 3)
    return z


def _annotate_supports_chips_void(
    supports: List[Dict[str, Any]],
    nearest: Optional[Dict[str, Any]],
    *,
    vp_val: Optional[float],
    vp_lookback: Optional[int] = None,
    atr: Optional[float] = None,
    last_close: Optional[float] = None,
    factor: float = CHIPS_VOID_STRENGTH_FACTOR,
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    kwargs = dict(
        vp_val=vp_val,
        vp_lookback=vp_lookback,
        atr=atr,
        last_close=last_close,
        factor=factor,
    )
    out = [annotate_support_chips_void(z, **kwargs) for z in supports]
    nearest_out = (
        annotate_support_chips_void(nearest, **kwargs)
        if isinstance(nearest, dict)
        else None
    )
    return out, nearest_out


def _zone_hvz_ref_prices(z: Dict[str, Any]) -> List[float]:
    """HVZ 距离参考：center / low / high（去空）。"""
    out: List[float] = []
    for key in ("center", "low", "high"):
        v = _f(z.get(key))
        if v is not None and v > 0:
            out.append(float(v))
    return out


def _zone_overlaps_vp_level(
    zone: Dict[str, Any],
    level: float,
    *,
    tol_pct: float = CHIPS_HVZ_OVERLAP_PCT,
) -> Tuple[bool, float]:
    """阻力带与 VP 水平是否重叠。

    规则：level 落入 [low, high]，或相对最近带边/中心的距离 ≤ tol_pct。
    返回 (是否重叠, 绝对距离)；不重叠时距离为 +inf。
    """
    lv = float(level)
    if lv <= 0:
        return False, float("inf")
    lo, hi = _f(zone.get("low")), _f(zone.get("high"))
    if lo is not None and hi is not None:
        a, b = (lo, hi) if lo <= hi else (hi, lo)
        if a <= lv <= b:
            return True, 0.0
    refs = _zone_hvz_ref_prices(zone)
    if not refs:
        return False, float("inf")
    dist = min(abs(r - lv) for r in refs)
    denom = max(abs(lv), abs(refs[0]), 1e-9)
    if dist / denom <= float(tol_pct):
        return True, dist
    return False, dist


def _pick_hvz_source(
    zone: Dict[str, Any],
    *,
    vp_poc: Optional[float] = None,
    vp_vah: Optional[float] = None,
    vp_val: Optional[float] = None,
    tol_pct: float = CHIPS_HVZ_OVERLAP_PCT,
) -> Optional[Tuple[str, float, float]]:
    """在 POC/VAH/VAL 中选最近重叠源。返回 (source, level, dist) 或 None。"""
    candidates: List[Tuple[str, float]] = []
    for src, raw in (("poc", vp_poc), ("vah", vp_vah), ("val", vp_val)):
        lv = _f(raw)
        if lv is not None and lv > 0:
            candidates.append((src, float(lv)))
    if not candidates:
        return None
    best: Optional[Tuple[str, float, float]] = None
    for src, lv in candidates:
        ok, dist = _zone_overlaps_vp_level(zone, lv, tol_pct=tol_pct)
        if not ok:
            continue
        if best is None:
            best = (src, lv, dist)
            continue
        _, _, best_dist = best
        if dist < best_dist - 1e-12:
            best = (src, lv, dist)
        elif abs(dist - best_dist) <= 1e-12:
            # 等距：POC > VAH > VAL
            if _HVZ_SOURCE_PRIORITY.get(src, 99) < _HVZ_SOURCE_PRIORITY.get(best[0], 99):
                best = (src, lv, dist)
    return best


def _chips_hvz_note(
    *,
    source: str,
    level: float,
    strength: float,
    adjusted: float,
    lookback: Optional[int] = None,
) -> str:
    lb = int(lookback) if lookback and int(lookback) > 0 else 60
    src = str(source or "").lower()
    if src == "poc":
        tag = "POC/筹码密集峰"
    elif src == "vah":
        tag = "VAH/价值区上沿"
    else:
        tag = "VAL/密集抛压区"
    return (
        f"重叠{lb}日VP {tag}（{round(float(level), PRICE_DECIMALS)}），"
        f"压制因子放大至{round(float(adjusted), 3)}"
        f"（原始强度{round(float(strength), 3)}）"
    )


def annotate_resistance_chips_hvz(
    zone: Dict[str, Any],
    *,
    vp_poc: Optional[float] = None,
    vp_vah: Optional[float] = None,
    vp_val: Optional[float] = None,
    vp_lookback: Optional[int] = None,
    gain: float = CHIPS_HVZ_GAIN,
    overlap_pct: float = CHIPS_HVZ_OVERLAP_PCT,
) -> Dict[str, Any]:
    """若阻力带与 POC/VAH/VAL 重叠，保留 strength，写入 strength_adjusted / chips_hvz 等。

    专家规则（与支撑 chips_void 对称、分边）：
    - 仅阻力侧；不改写支撑、不与 void 折减叠乘。
    - 重叠：水平落入 [low,high]，或相对带中心/边距 ≤ overlap_pct（默认 1%）。
    - 含 VAL：现价常在 VAL 下方时，VAL 为价值区下沿/密集抛压起点（601698: 27.59≈VAL 27.81）。
    """
    z = dict(zone)
    picked = _pick_hvz_source(
        z,
        vp_poc=vp_poc,
        vp_vah=vp_vah,
        vp_val=vp_val,
        tol_pct=overlap_pct,
    )
    if picked is None:
        return z
    src, level, _dist = picked
    strength = _f(z.get("strength"))
    g = float(gain) if gain and float(gain) > 0 else float(CHIPS_HVZ_GAIN)
    z["chips_hvz"] = True
    z["hvz_source"] = src
    z["hvz_level"] = round(level, PRICE_DECIMALS)
    if vp_lookback is not None and int(vp_lookback) > 0:
        z["hvz_lookback"] = int(vp_lookback)
    if strength is not None:
        adj = round(strength * g, 3)
        z["strength_adjusted"] = adj
        z["hvz_note"] = _chips_hvz_note(
            source=src,
            level=level,
            strength=strength,
            adjusted=adj,
            lookback=vp_lookback,
        )
    else:
        z["hvz_note"] = _chips_hvz_note(
            source=src,
            level=level,
            strength=0.0,
            adjusted=0.0,
            lookback=vp_lookback,
        )
    return z


def _annotate_resistances_chips_hvz(
    resistances: List[Dict[str, Any]],
    nearest: Optional[Dict[str, Any]],
    *,
    vp_poc: Optional[float] = None,
    vp_vah: Optional[float] = None,
    vp_val: Optional[float] = None,
    vp_lookback: Optional[int] = None,
    gain: float = CHIPS_HVZ_GAIN,
    overlap_pct: float = CHIPS_HVZ_OVERLAP_PCT,
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    kwargs = dict(
        vp_poc=vp_poc,
        vp_vah=vp_vah,
        vp_val=vp_val,
        vp_lookback=vp_lookback,
        gain=gain,
        overlap_pct=overlap_pct,
    )
    out = [annotate_resistance_chips_hvz(z, **kwargs) for z in resistances]
    nearest_out = (
        annotate_resistance_chips_hvz(nearest, **kwargs)
        if isinstance(nearest, dict)
        else None
    )
    return out, nearest_out


def _is_near_dense_zone(
    z: Dict[str, Any],
    *,
    px: float,
    side: str,
    near_pct: float,
    near_min_sources: int,
    near_min_points: int,
) -> bool:
    """现价同侧近距离内的多源/多点密集簇。"""
    try:
        center = float(z["center"])
    except (TypeError, ValueError, KeyError):
        return False
    if px <= 0:
        return False
    if side == "support" and center >= px:
        return False
    if side == "resistance" and center <= px:
        return False
    if abs(center - px) / abs(px) > float(near_pct):
        return False
    n_src = len(z.get("sources") or [])
    n_pts = int(z.get("n_points") or 0)
    return n_pts >= int(near_min_points) or n_src >= int(near_min_sources)


def _select_zones_with_near_fallback(
    zones: List[Dict[str, Any]],
    *,
    px: Optional[float],
    side: str,
    max_each: int,
    near_pct: float,
    near_min_sources: int,
    near_min_points: int,
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """列表 TopN；nearest 在 TopN ∪ 近端密集兜底 集合上计算。"""
    if not zones:
        return [], None
    top_n = max(1, int(max_each))
    top = list(zones[:top_n])
    near: List[Dict[str, Any]] = []
    if px is not None and px > 0 and float(near_pct) > 0:
        near = [
            z
            for z in zones
            if _is_near_dense_zone(
                z,
                px=px,
                side=side,
                near_pct=near_pct,
                near_min_sources=near_min_sources,
                near_min_points=near_min_points,
            )
        ]
    seen = {_zone_id(z) for z in top}
    display = list(top)
    for z in near:
        zid = _zone_id(z)
        if zid not in seen:
            seen.add(zid)
            display.append(z)
    # nearest 候选 = TopN ∪ 近端兜底（保证近端多源簇可成为 nearest）
    pool = display
    if side == "support":
        nearest = max(pool, key=lambda z: z["center"]) if pool else None
        # 展示序：按 center 降序（近现价=支撑1）；TopN 仍按强度选取
        display.sort(key=lambda z: (-float(z["center"]), -float(z.get("strength") or 0)))
    else:
        nearest = min(pool, key=lambda z: z["center"]) if pool else None
        # 展示序：按 center 升序（近现价=压力1）
        display.sort(key=lambda z: (float(z["center"]), -float(z.get("strength") or 0)))
    return display, nearest


def build_confluence_zones(
    points: Sequence[Dict[str, Any]],
    *,
    last_close: Optional[float],
    atr: Optional[float] = None,
    max_each: int = MAX_ZONES_EACH,
    near_pct: float = NEAR_PCT,
    near_min_sources: int = NEAR_MIN_SOURCES,
    near_min_points: int = NEAR_MIN_POINTS,
    max_zone_width_pct: float = MAX_ZONE_WIDTH_PCT,
    vp_val: Optional[float] = None,
    vp_poc: Optional[float] = None,
    vp_vah: Optional[float] = None,
    vp_lookback: Optional[int] = None,
    chips_void_factor: float = CHIPS_VOID_STRENGTH_FACTOR,
    chips_hvz_gain: float = CHIPS_HVZ_GAIN,
    chips_hvz_overlap_pct: float = CHIPS_HVZ_OVERLAP_PCT,
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
        "params": {
            "max_each": int(max_each),
            "near_pct": float(near_pct),
            "near_min_sources": int(near_min_sources),
            "near_min_points": int(near_min_points),
            "max_zone_width_pct": float(max_zone_width_pct),
            "chips_void_factor": float(chips_void_factor),
            "chips_hvz_gain": float(chips_hvz_gain),
            "chips_hvz_overlap_pct": float(chips_hvz_overlap_pct),
        },
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
    for _lab, members in clusters.items():
        if len(members) < 2:
            continue
        was_wide = (
            float(max_zone_width_pct) > 0
            and _members_width_pct(members) > float(max_zone_width_pct)
        )
        parts = _split_wide_members(
            members, max_zone_width_pct=float(max_zone_width_pct)
        )
        for part in parts:
            if len(part) < 2:
                continue
            z = _zone_dict_from_members(part)
            if was_wide and len(parts) > 1:
                z["split_from_wide_cluster"] = True
            zones.append(z)

    params = {
        "max_each": int(max_each),
        "near_pct": float(near_pct),
        "near_min_sources": int(near_min_sources),
        "near_min_points": int(near_min_points),
        "max_zone_width_pct": float(max_zone_width_pct),
        "chips_void_factor": float(chips_void_factor),
        "chips_hvz_gain": float(chips_hvz_gain),
        "chips_hvz_overlap_pct": float(chips_hvz_overlap_pct),
    }

    if not zones:
        return {
            **empty,
            "reason": "no_clusters",
            "eps": round(eps, PRICE_DECIMALS),
            "method": method,
            "params": params,
        }

    if px is None:
        # 无现价时按中位价二分，避免同一带同时进支撑/压力
        mid = sorted(z["center"] for z in zones)[len(zones) // 2]
        supports = [z for z in zones if z["center"] <= mid]
        resistances = [z for z in zones if z["center"] > mid]
    else:
        supports = [z for z in zones if z["center"] < px]
        resistances = [z for z in zones if z["center"] > px]
        supports = [_clip_zone_to_price_side(z, px=px, side="support") for z in supports]
        resistances = [
            _clip_zone_to_price_side(z, px=px, side="resistance") for z in resistances
        ]
        supports = [z for z in supports if z is not None]
        resistances = [z for z in resistances if z is not None]
    supports.sort(key=lambda z: (-z["strength"], -z["center"]))
    resistances.sort(key=lambda z: (-z["strength"], z["center"]))

    supports, nearest_s = _select_zones_with_near_fallback(
        supports,
        px=px,
        side="support",
        max_each=max_each,
        near_pct=near_pct,
        near_min_sources=near_min_sources,
        near_min_points=near_min_points,
    )
    resistances, nearest_r = _select_zones_with_near_fallback(
        resistances,
        px=px,
        side="resistance",
        max_each=max_each,
        near_pct=near_pct,
        near_min_sources=near_min_sources,
        near_min_points=near_min_points,
    )

    # VAL 下方支撑：筹码真空折减（TopN/nearest 已按原始 strength 选定）
    supports, nearest_s = _annotate_supports_chips_void(
        supports,
        nearest_s,
        vp_val=vp_val,
        vp_lookback=vp_lookback,
        atr=atr_v,
        last_close=px,
        factor=float(chips_void_factor),
    )
    # 阻力与 POC/VAH/VAL 重叠：筹码密集压制增益（与 void 分边，不叠乘）
    resistances, nearest_r = _annotate_resistances_chips_hvz(
        resistances,
        nearest_r,
        vp_poc=vp_poc,
        vp_vah=vp_vah,
        vp_val=vp_val,
        vp_lookback=vp_lookback,
        gain=float(chips_hvz_gain),
        overlap_pct=float(chips_hvz_overlap_pct),
    )

    supports = _annotate_zones_tier(supports, side="support")
    resistances = _annotate_zones_tier(resistances, side="resistance")
    nearest_s = annotate_zone_tier(nearest_s, side="support")
    nearest_r = annotate_zone_tier(nearest_r, side="resistance")
    params = {
        **params,
        "strong_tier_strength": float(STRONG_TIER_STRENGTH),
        "strong_tier_min_sources": int(STRONG_TIER_MIN_SOURCES),
    }

    return {
        "ok": True,
        "reason": "ok",
        "method": method,
        "eps": round(eps, PRICE_DECIMALS),
        "params": params,
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
    kde_multi_windows: Optional[Dict[str, Any]] = None,
    last_close: Optional[float] = None,
    atr: Optional[float] = None,
    max_each: int = MAX_ZONES_EACH,
    near_pct: float = NEAR_PCT,
    near_min_sources: int = NEAR_MIN_SOURCES,
    near_min_points: int = NEAR_MIN_POINTS,
    max_zone_width_pct: float = MAX_ZONE_WIDTH_PCT,
    chips_void_factor: float = CHIPS_VOID_STRENGTH_FACTOR,
    chips_hvz_gain: float = CHIPS_HVZ_GAIN,
    chips_hvz_overlap_pct: float = CHIPS_HVZ_OVERLAP_PCT,
) -> Dict[str, Any]:
    pts = collect_candidate_points(
        kde_support=kde_support,
        kde_resistance=kde_resistance,
        kde_supports=kde_supports,
        kde_resistances=kde_resistances,
        kde_multi_windows=kde_multi_windows,
        volume_profile=ref.get("volume_profile"),
        fibonacci=ref.get("fibonacci"),
        pivot=ref.get("pivot"),
        camarilla=ref.get("camarilla"),
        atr_pivot=ref.get("atr_pivot"),
    )
    atr_v = atr if atr is not None else (ref.get("atr") or (ref.get("atr_pivot") or {}).get("atr"))
    lc = last_close if last_close is not None else ref.get("last_close")
    vp = ref.get("volume_profile") if isinstance(ref.get("volume_profile"), dict) else {}
    vp_ok = bool(vp.get("ok"))
    vp_val = _f(vp.get("val")) if vp_ok else None
    vp_poc = _f(vp.get("poc")) if vp_ok else None
    vp_vah = _f(vp.get("vah")) if vp_ok else None
    vp_lb = vp.get("lookback")
    try:
        vp_lookback = int(vp_lb) if vp_lb is not None else None
    except (TypeError, ValueError):
        vp_lookback = None
    return build_confluence_zones(
        pts,
        last_close=lc,
        atr=atr_v,
        max_each=max_each,
        near_pct=near_pct,
        near_min_sources=near_min_sources,
        near_min_points=near_min_points,
        max_zone_width_pct=max_zone_width_pct,
        vp_val=vp_val,
        vp_poc=vp_poc,
        vp_vah=vp_vah,
        vp_lookback=vp_lookback,
        chips_void_factor=chips_void_factor,
        chips_hvz_gain=chips_hvz_gain,
        chips_hvz_overlap_pct=chips_hvz_overlap_pct,
    )
