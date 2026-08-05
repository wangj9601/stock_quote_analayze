# -*- coding: utf-8 -*-
"""GMS 成交量加权 KDE 支撑/阻力（与 URT / RPE 同口径）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def empty_structure() -> Dict[str, Any]:
    return {
        "support_levels": [],
        "resistance_levels": [],
        "nearest_support": None,
        "nearest_resistance": None,
        "kde_ok": False,
        "kde_reason": "insufficient_samples",
        "kde_bw": None,
        "kde_lookback_used": 0,
        "kde_lookback_expanded": False,
        "method": "kde_volume_weighted",
        "rr": None,
        "rr_reason": "insufficient_samples",
    }


def compute_structure_rr(
    price: Optional[float],
    nearest_support: Optional[float],
    nearest_resistance: Optional[float],
) -> Dict[str, Any]:
    """
    结构盈亏比（与 RPE structure_filter 同口径）。

    RR = (阻力 - 价) / (价 - 支撑)

    返回:
      rr: Optional[float]
      reason: str
      should_penalize: Optional[bool]
        True=必扣分；False=不扣；None=由调用方用 min_rr 与 rr 比较
    """
    if price is None:
        return {"rr": None, "reason": "no_price", "should_penalize": False}
    try:
        px = float(price)
    except (TypeError, ValueError):
        return {"rr": None, "reason": "no_price", "should_penalize": False}
    if px <= 0:
        return {"rr": None, "reason": "no_price", "should_penalize": False}

    if nearest_support is None:
        return {"rr": None, "reason": "no_support", "should_penalize": False}
    try:
        ns = float(nearest_support)
    except (TypeError, ValueError):
        return {"rr": None, "reason": "no_support", "should_penalize": False}

    if px <= ns:
        return {"rr": None, "reason": "below_or_no_support", "should_penalize": True}
    downside = px - ns
    if downside <= 0:
        return {"rr": None, "reason": "zero_downside", "should_penalize": True}

    if nearest_resistance is None:
        return {"rr": None, "reason": "no_resistance", "should_penalize": False}
    try:
        nr = float(nearest_resistance)
    except (TypeError, ValueError):
        return {"rr": None, "reason": "no_resistance", "should_penalize": False}

    upside = nr - px
    if upside <= 0:
        return {"rr": 0.0, "reason": "at_resistance", "should_penalize": True}

    rr = round(upside / downside, 4)
    return {"rr": rr, "reason": "ok", "should_penalize": None}


def resolve_kde_config(cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """从 GMS config 根或 structure / kde 子节读取 KDE 参数（根优先）。"""
    root = dict(cfg or {})
    structure = root.get("structure") if isinstance(root.get("structure"), dict) else {}
    kde = root.get("kde") if isinstance(root.get("kde"), dict) else {}
    nested = structure.get("kde") if isinstance(structure.get("kde"), dict) else {}

    def _get(key: str, default: Any = None) -> Any:
        for src in (root, structure, kde, nested):
            if key in src and src[key] is not None:
                return src[key]
        return default

    return {
        "kde_lookback_days": _get("kde_lookback_days"),
        "kde_lookback_initial": _get("kde_lookback_initial"),
        "kde_lookback_step": _get("kde_lookback_step"),
        "kde_lookback_max": _get("kde_lookback_max"),
        "kde_base_factor": _get("kde_base_factor"),
        "kde_grid_points": _get("kde_grid_points"),
    }


def kde_bars_limit(cfg: Optional[Dict[str, Any]]) -> int:
    """load_bars 建议 limit：覆盖 kde_lookback_max。"""
    kde = resolve_kde_config(cfg)
    max_lb = int(kde.get("kde_lookback_max") or 750)
    return max(max_lb + 50, 800)


def compute_structure_levels(
    bars_desc: List[Dict[str, Any]],
    cfg: Optional[Dict[str, Any]] = None,
    *,
    price: Optional[float] = None,
) -> Dict[str, Any]:
    """
    成交量加权 KDE 支撑/阻力（与 RPE / URT / 个股关键价位同口径）。
    bars_desc 为日期 DESC（最新在前）；内部转为升序喂给 KDE。
    """
    empty = empty_structure()
    if not bars_desc or price is None:
        return empty
    try:
        px = float(price)
    except (TypeError, ValueError):
        return empty
    if px <= 0:
        return empty

    # DESC → ASC
    asc = list(reversed(bars_desc))
    closes: List[float] = []
    volumes: List[float] = []
    for b in asc:
        try:
            c = float(b.get("close") or 0)
            v = float(b.get("volume") or 0)
        except (TypeError, ValueError):
            continue
        if c > 0:
            closes.append(c)
            volumes.append(v if v > 0 else 0.0)
    if len(closes) < 20:
        return empty

    from backend_core.strategies.rpe.kde_levels import (
        extract_kde_levels_expand_support,
        nearest_levels,
    )

    kde_cfg = resolve_kde_config(cfg)
    init_lb = int(kde_cfg.get("kde_lookback_days") or kde_cfg.get("kde_lookback_initial") or 250)
    step = int(kde_cfg.get("kde_lookback_step") or 250)
    max_lb = int(kde_cfg.get("kde_lookback_max") or 750)
    base = float(kde_cfg.get("kde_base_factor") or 1.0)
    grid = int(kde_cfg.get("kde_grid_points") or 200)

    kde = extract_kde_levels_expand_support(
        closes,
        volumes,
        price=px,
        initial_lookback=init_lb,
        step=step,
        max_lookback=max_lb,
        base_factor=base,
        grid_points=grid,
    )
    supports = [round(float(x), 2) for x in (kde.get("support_levels") or [])[:8]]
    resists = [round(float(x), 2) for x in (kde.get("resistance_levels") or [])[:8]]
    near = nearest_levels(px, supports, resists)
    ns = near.get("nearest_support")
    nr = near.get("nearest_resistance")
    ns_v = round(float(ns), 2) if ns is not None else None
    nr_v = round(float(nr), 2) if nr is not None else None
    rr_info = compute_structure_rr(px, ns_v, nr_v)
    return {
        "support_levels": supports,
        "resistance_levels": resists,
        "nearest_support": ns_v,
        "nearest_resistance": nr_v,
        "kde_ok": bool(kde.get("ok")),
        "kde_reason": kde.get("reason") or ("ok" if kde.get("ok") else "no_peaks"),
        "kde_bw": kde.get("bw"),
        "kde_lookback_used": int(kde.get("lookback_used") or 0),
        "kde_lookback_expanded": bool(kde.get("lookback_expanded")),
        "method": "kde_volume_weighted",
        "rr": rr_info.get("rr"),
        "rr_reason": rr_info.get("reason"),
    }


def flatten_structure_to_result(result: Dict[str, Any], structure: Dict[str, Any]) -> None:
    """将 structure 展平到结果顶层（便于列表/导出）。"""
    st = structure or empty_structure()
    result["nearest_support"] = st.get("nearest_support")
    result["nearest_resistance"] = st.get("nearest_resistance")
    result["support_levels"] = list(st.get("support_levels") or [])
    result["resistance_levels"] = list(st.get("resistance_levels") or [])
    result["kde_ok"] = st.get("kde_ok")
    result["kde_reason"] = st.get("kde_reason")
    result["kde_lookback_used"] = st.get("kde_lookback_used")
    result["kde_lookback_expanded"] = st.get("kde_lookback_expanded")
    result["structure_rr"] = st.get("rr")
    result["structure_rr_reason"] = st.get("rr_reason")
