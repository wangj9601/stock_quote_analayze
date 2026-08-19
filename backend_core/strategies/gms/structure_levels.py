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
        "kde_lookback_initial": 60,
        "kde_multi_windows": None,
        "kde_anchor": None,
        "kde_window_mode": "calendar",
        "kde_time_decay": False,
        "method": "kde_volume_weighted",
        "rr": None,
        "rr_reason": "insufficient_samples",
        "rr_downside_floored": False,
        "rr_min_downside_pct": 0.015,
        "rr_downside_raw": None,
        "rr_downside": None,
    }


def pick_nth_level(
    levels: Any,
    price: Optional[float],
    *,
    side: str,
    n: int = 2,
) -> Optional[float]:
    """
    从支撑/阻力列表取第 n 档（1=最近）。
    levels 可为 float 或 {center|price}；不足 n 档则退回最近档。
    """
    if price is None:
        return None
    try:
        px = float(price)
    except (TypeError, ValueError):
        return None
    if px <= 0:
        return None
    vals: List[float] = []
    for x in levels or []:
        raw = x.get("center") if isinstance(x, dict) else x
        if raw is None and isinstance(x, dict):
            raw = x.get("price")
        try:
            f = float(raw)
        except (TypeError, ValueError):
            continue
        if f != f:
            continue
        if side == "support" and f < px:
            vals.append(f)
        elif side == "resistance" and f > px:
            vals.append(f)
    if not vals:
        return None
    vals.sort(reverse=(side == "support"))
    idx = min(max(int(n or 1), 1), len(vals)) - 1
    return round(vals[idx], 2)


def compute_structure_rr(
    price: Optional[float],
    nearest_support: Optional[float],
    nearest_resistance: Optional[float],
    *,
    min_downside_pct: float = 0.015,
    min_upside_pct: float = 0.0,
    atr: Optional[float] = None,
    atr_k: float = 0.0,
) -> Dict[str, Any]:
    """
    结构盈亏比（无量纲）。

    RR = upside / max(价−支撑, 现价×min_downside_pct, k×ATR)

    贴支撑时原始 downside 极小会导致 RR 虚高；默认至少按现价 1.5% 作为风险分母
    （覆盖滑点/假破缓冲）。atr_k>0 且 ATR 有效时再与 k×ATR 取 max。
    min_downside_pct<=0 时关闭价格比例下限；atr 缺失或 atr_k<=0 时关闭波动下限。

    min_upside_pct>0 时：若 (阻力−价)/价 低于该比例，视为上行空间不足（贴阻力类），
    should_penalize=True，reason=thin_upside（避免「支撑贴身、阻力仅几毛」仍算可交易）。

    返回:
      rr / reason / should_penalize
      downside_raw / downside / downside_floored / min_downside_pct / downside_pct
      upside / upside_pct / min_upside_pct
      floor_source / atr / atr_k / atr_floor
    """
    empty_extra = {
        "downside_raw": None,
        "downside": None,
        "downside_floored": False,
        "downside_pct": None,
        "min_downside_pct": float(min_downside_pct or 0),
        "upside": None,
        "upside_pct": None,
        "min_upside_pct": float(min_upside_pct or 0),
        "floor_source": "raw",
        "atr": None,
        "atr_k": float(atr_k or 0),
        "atr_floor": None,
    }
    if price is None:
        return {"rr": None, "reason": "no_price", "should_penalize": False, **empty_extra}
    try:
        px = float(price)
    except (TypeError, ValueError):
        return {"rr": None, "reason": "no_price", "should_penalize": False, **empty_extra}
    if px <= 0:
        return {"rr": None, "reason": "no_price", "should_penalize": False, **empty_extra}

    if nearest_support is None:
        return {"rr": None, "reason": "no_support", "should_penalize": False, **empty_extra}
    try:
        ns = float(nearest_support)
    except (TypeError, ValueError):
        return {"rr": None, "reason": "no_support", "should_penalize": False, **empty_extra}

    if px <= ns:
        return {"rr": None, "reason": "below_or_no_support", "should_penalize": True, **empty_extra}
    downside_raw = px - ns
    if downside_raw <= 0:
        return {"rr": None, "reason": "zero_downside", "should_penalize": True, **empty_extra}

    try:
        floor_pct = float(min_downside_pct or 0)
    except (TypeError, ValueError):
        floor_pct = 0.015
    if floor_pct < 0:
        floor_pct = 0.0
    pct_floor = px * floor_pct if floor_pct > 0 else 0.0
    try:
        atr_v = float(atr) if atr is not None else None
    except (TypeError, ValueError):
        atr_v = None
    if atr_v is not None and (atr_v <= 0 or atr_v != atr_v):
        atr_v = None
    try:
        k = float(atr_k or 0)
    except (TypeError, ValueError):
        k = 0.0
    if k < 0:
        k = 0.0
    atr_floor = (atr_v * k) if (atr_v is not None and k > 0) else 0.0
    downside = max(downside_raw, pct_floor, atr_floor)
    if downside <= downside_raw + 1e-15:
        floor_source = "raw"
        floored = False
    elif atr_floor >= pct_floor and atr_floor > downside_raw:
        floor_source = "atr"
        floored = True
    else:
        floor_source = "pct"
        floored = True

    try:
        up_floor_pct = float(min_upside_pct or 0)
    except (TypeError, ValueError):
        up_floor_pct = 0.0
    if up_floor_pct < 0:
        up_floor_pct = 0.0

    base_extra = {
        "downside_raw": round(downside_raw, 6),
        "downside": round(downside, 6),
        "downside_floored": floored,
        "downside_pct": round(downside_raw / px, 6) if px > 0 else None,
        "min_downside_pct": floor_pct,
        "min_upside_pct": up_floor_pct,
        "floor_source": floor_source,
        "atr": round(atr_v, 6) if atr_v is not None else None,
        "atr_k": k,
        "atr_floor": round(atr_floor, 6) if atr_floor > 0 else None,
    }

    if nearest_resistance is None:
        return {
            "rr": None,
            "reason": "no_resistance",
            "should_penalize": False,
            "upside": None,
            "upside_pct": None,
            **base_extra,
        }
    try:
        nr = float(nearest_resistance)
    except (TypeError, ValueError):
        return {
            "rr": None,
            "reason": "no_resistance",
            "should_penalize": False,
            "upside": None,
            "upside_pct": None,
            **base_extra,
        }

    upside = nr - px
    upside_pct = upside / px if px > 0 else None
    if upside <= 0:
        return {
            "rr": 0.0,
            "reason": "at_resistance",
            "should_penalize": True,
            "upside": round(upside, 6),
            "upside_pct": round(upside_pct, 6) if upside_pct is not None else 0.0,
            **base_extra,
        }

    rr = round(upside / downside, 4)
    # 上行空间相对现价过窄：按贴阻力处理（硬闸/减分），避免「涨几毛就到阻力」虚买点
    if up_floor_pct > 0 and upside_pct is not None and upside_pct < up_floor_pct:
        return {
            "rr": rr,
            "reason": "thin_upside",
            "should_penalize": True,
            "upside": round(upside, 6),
            "upside_pct": round(upside_pct, 6),
            **base_extra,
        }

    return {
        "rr": rr,
        "reason": "ok",
        "should_penalize": None,
        "upside": round(upside, 6),
        "upside_pct": round(upside_pct, 6) if upside_pct is not None else None,
        **base_extra,
    }


def resolve_structure_rr_min_downside_pct(cfg: Optional[Dict[str, Any]] = None) -> float:
    """配置键 structure_rr_min_downside_pct，默认 0.015（现价 1.5%）。"""
    root = cfg if isinstance(cfg, dict) else {}
    raw = root.get("structure_rr_min_downside_pct")
    if raw is None and isinstance(root.get("structure"), dict):
        raw = root["structure"].get("structure_rr_min_downside_pct")
    if raw is None and isinstance(root.get("scoring"), dict):
        raw = root["scoring"].get("structure_rr_min_downside_pct")
    try:
        v = float(raw) if raw is not None else 0.015
    except (TypeError, ValueError):
        v = 0.015
    return max(0.0, v)


def resolve_structure_rr_min_upside_pct(cfg: Optional[Dict[str, Any]] = None) -> float:
    """配置键 structure_rr_min_upside_pct；默认 0（关闭）。URT 建议默认 0.03。"""
    root = cfg if isinstance(cfg, dict) else {}
    raw = root.get("structure_rr_min_upside_pct")
    if raw is None and isinstance(root.get("structure"), dict):
        raw = root["structure"].get("structure_rr_min_upside_pct")
    if raw is None and isinstance(root.get("scoring"), dict):
        raw = root["scoring"].get("structure_rr_min_upside_pct")
    try:
        v = float(raw) if raw is not None else 0.0
    except (TypeError, ValueError):
        v = 0.0
    return max(0.0, v)


def resolve_structure_rr_atr_k(cfg: Optional[Dict[str, Any]] = None) -> float:
    """配置键 structure_rr_atr_k；默认 0.75。0 表示关闭 ATR 分母。"""
    root = cfg if isinstance(cfg, dict) else {}
    raw = root.get("structure_rr_atr_k")
    if raw is None and isinstance(root.get("structure"), dict):
        raw = root["structure"].get("structure_rr_atr_k")
    if raw is None and isinstance(root.get("scoring"), dict):
        raw = root["scoring"].get("structure_rr_atr_k")
    try:
        v = float(raw) if raw is not None else 0.75
    except (TypeError, ValueError):
        v = 0.75
    return max(0.0, min(3.0, v))


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
        KDE_MULTI_WINDOW_ENABLED,
        KDE_STRUCTURAL_WINDOW_ENABLED,
        compute_kde_bundle,
        nearest_levels,
    )

    kde_cfg = resolve_kde_config(cfg)
    init_lb_cfg = kde_cfg.get("kde_lookback_days") or kde_cfg.get("kde_lookback_initial")
    # 配置显式写了初始回看 → 日历；否则结构锚窗
    forced_lb = int(init_lb_cfg) if init_lb_cfg is not None else None
    # 若配置仍是默认 60 且未关结构窗，允许结构锚覆盖（与个股关键价位一致）
    use_structural = bool(KDE_STRUCTURAL_WINDOW_ENABLED) and (
        forced_lb is None or int(forced_lb) == 60
    )
    # 策略配置若给了非 60 的值，视为强制日历
    if forced_lb is not None and int(forced_lb) != 60:
        use_structural = False
    step = int(kde_cfg.get("kde_lookback_step") or 250)
    max_lb = int(kde_cfg.get("kde_lookback_max") or 750)
    base = float(kde_cfg.get("kde_base_factor") or 1.0)
    grid = int(kde_cfg.get("kde_grid_points") or 200)
    use_multi = bool(KDE_MULTI_WINDOW_ENABLED)

    # asc bars as dicts for zigzag
    bar_dicts = list(asc)
    bundle = compute_kde_bundle(
        closes,
        volumes,
        price=px,
        bars=bar_dicts if use_structural else None,
        initial_lookback=None if use_structural else (forced_lb or 60),
        max_lookback=max_lb,
        step=step,
        base_factor=base,
        grid_points=grid,
        structural=use_structural,
        multi_window=use_multi,
        calendar_fallback=int(forced_lb or 60),
    )
    kde = bundle.get("main") or {}
    supports = [round(float(x), 2) for x in (kde.get("support_levels") or [])[:8]]
    resists = [round(float(x), 2) for x in (kde.get("resistance_levels") or [])[:8]]
    near = nearest_levels(px, supports, resists)
    ns = near.get("nearest_support")
    nr = near.get("nearest_resistance")
    ns_v = round(float(ns), 2) if ns is not None else None
    nr_v = round(float(nr), 2) if nr is not None else None
    floor_pct = resolve_structure_rr_min_downside_pct(cfg)
    rr_info = compute_structure_rr(px, ns_v, nr_v, min_downside_pct=floor_pct)
    anchor = bundle.get("anchor") or {}
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
        "kde_lookback_initial": int(bundle.get("initial_lookback") or forced_lb or 60),
        "kde_multi_windows": bundle.get("multi_windows"),
        "kde_anchor": anchor,
        "kde_window_mode": (
            "structural" if use_structural and anchor.get("ok") else "calendar"
        ),
        "kde_time_decay": bool(kde.get("time_decay")),
        "method": "kde_volume_weighted",
        "rr": rr_info.get("rr"),
        "rr_reason": rr_info.get("reason"),
        "rr_downside_floored": bool(rr_info.get("downside_floored")),
        "rr_min_downside_pct": rr_info.get("min_downside_pct"),
        "rr_downside_raw": rr_info.get("downside_raw"),
        "rr_downside": rr_info.get("downside"),
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
    result["structure_rr_downside_floored"] = st.get("rr_downside_floored")
    result["structure_rr_min_downside_pct"] = st.get("rr_min_downside_pct")
    result["structure_rr_downside_raw"] = st.get("rr_downside_raw")
    result["structure_rr_downside"] = st.get("rr_downside")
