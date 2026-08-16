# -*- coding: utf-8 -*-
"""URT 结构盈亏比风险提示 + 混合硬闸判定（破位/贴阻力/悬空否决买点；RR 偏低仅软标签）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def resolve_structure_hang_min_upside_pct(cfg: Optional[Dict[str, Any]] = None) -> float:
    cfg = cfg or {}
    try:
        v = float(cfg.get("structure_hang_min_upside_pct") or 0.08)
    except (TypeError, ValueError):
        v = 0.08
    return max(0.0, v)


def compute_hang_distance_pct(
    price: Optional[float],
    nearest_support: Any,
) -> Optional[float]:
    """相对支撑的悬空比例：(price - support) / price。无有效支撑则返回 None。"""
    if price is None or nearest_support is None:
        return None
    try:
        px = float(price)
        sp = float(nearest_support)
    except (TypeError, ValueError):
        return None
    if px <= 0 or sp <= 0 or px <= sp:
        return None
    return (px - sp) / px


def is_structure_hanging(
    price: Optional[float],
    nearest_support: Any,
    cfg: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, Optional[float]]:
    """是否悬空离支撑。返回 (是否悬空, 距离比例)。"""
    dist = compute_hang_distance_pct(price, nearest_support)
    if dist is None:
        return False, None
    thr = resolve_structure_hang_min_upside_pct(cfg)
    return dist >= thr, dist


def evaluate_structure_hard_gate(
    structure: Optional[Dict[str, Any]],
    cfg: Optional[Dict[str, Any]] = None,
    *,
    price: Optional[float] = None,
    rr_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    混合硬闸：破位支撑 / 贴·超阻力 / 悬空 → 否决正式买点。
    RR 偏低不在此闸。KDE 无效或无支撑/无阻力（无法判定对应项）时不误杀。
    """
    cfg = cfg or {}
    enabled = cfg.get("structure_rr_hard_gate_enabled")
    if enabled is False:
        return {"blocked": False, "reasons": [], "enabled": False}

    st = structure if isinstance(structure, dict) else {}
    if not st.get("kde_ok"):
        return {"blocked": False, "reasons": [], "enabled": True, "skipped": "kde_not_ok"}

    reasons: List[str] = []
    reason = ""
    if rr_info:
        reason = str(rr_info.get("reason") or "")
    else:
        reason = str(st.get("rr_reason") or "")

    # 破位：现价不高于支撑（compute_structure_rr 仅在有支撑时给出下列 reason）
    if reason in ("below_or_no_support", "zero_downside"):
        reasons.append("破位支撑")

    # 贴/超阻力、上行空间过窄
    if reason in ("at_resistance", "thin_upside"):
        reasons.append("贴/超阻力" if reason == "at_resistance" else "上行空间不足")

    # 悬空：有支撑且距离过大
    hanging, hang_pct = is_structure_hanging(price, st.get("nearest_support"), cfg)
    if hanging:
        reasons.append("悬空离支撑")

    return {
        "blocked": bool(reasons),
        "reasons": reasons,
        "enabled": True,
        "hang_distance_pct": round(hang_pct, 4) if hang_pct is not None else None,
        "hang_threshold": resolve_structure_hang_min_upside_pct(cfg),
    }


def enrich_structure_with_rr(
    structure: Optional[Dict[str, Any]],
    *,
    price: Optional[float],
    cfg: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """为 structure 补写 rr / rr_reason / 分母下限字段，并生成 risk_tags + 硬闸结果。"""
    cfg = cfg or {}
    st = dict(structure or {})
    from backend_core.strategies.gms.structure_levels import (
        compute_structure_rr,
        resolve_structure_rr_min_downside_pct,
        resolve_structure_rr_min_upside_pct,
    )

    floor_pct = resolve_structure_rr_min_downside_pct(cfg)
    up_pct = resolve_structure_rr_min_upside_pct(cfg)
    info = compute_structure_rr(
        price,
        st.get("nearest_support"),
        st.get("nearest_resistance"),
        min_downside_pct=floor_pct,
        min_upside_pct=up_pct,
    )
    st["rr"] = info.get("rr")
    st["rr_reason"] = info.get("reason")
    st["rr_downside_floored"] = bool(info.get("downside_floored"))
    st["rr_min_downside_pct"] = info.get("min_downside_pct")
    st["rr_downside_raw"] = info.get("downside_raw")
    st["rr_downside"] = info.get("downside")
    st["rr_upside"] = info.get("upside")
    st["rr_upside_pct"] = info.get("upside_pct")
    st["rr_min_upside_pct"] = info.get("min_upside_pct")

    hanging, hang_pct = is_structure_hanging(price, st.get("nearest_support"), cfg)
    st["hanging"] = hanging
    st["hang_distance_pct"] = round(hang_pct, 4) if hang_pct is not None else None

    tags = build_structure_rr_risk_tags(st, cfg, price=price, rr_info=info)
    hard_gate = evaluate_structure_hard_gate(st, cfg, price=price, rr_info=info)
    return {"structure": st, "risk_tags": tags, "structure_hard_gate": hard_gate}


def _floor_hint(rr_info: Optional[Dict[str, Any]]) -> str:
    if rr_info and rr_info.get("downside_floored"):
        return "；已用分母下限"
    return ""


def build_structure_rr_risk_tags(
    structure: Optional[Dict[str, Any]],
    cfg: Optional[Dict[str, Any]] = None,
    *,
    price: Optional[float] = None,
    rr_info: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """
    基于 KDE 最近支撑/阻力生成 risk_tags。
    复用 GMS compute_structure_rr 口径；无阻力 / 无支撑 / KDE 失败不提示。
    另：悬空离支撑打独立标签。
    """
    cfg = cfg or {}
    if cfg.get("structure_rr_warn_enabled") is False:
        return []

    st = structure if isinstance(structure, dict) else {}
    if rr_info is None:
        from backend_core.strategies.gms.structure_levels import (
            compute_structure_rr,
            resolve_structure_rr_min_downside_pct,
            resolve_structure_rr_min_upside_pct,
        )

        px = price
        floor_pct = resolve_structure_rr_min_downside_pct(cfg)
        up_pct = resolve_structure_rr_min_upside_pct(cfg)
        rr_info = compute_structure_rr(
            px,
            st.get("nearest_support"),
            st.get("nearest_resistance"),
            min_downside_pct=floor_pct,
            min_upside_pct=up_pct,
        )

    rr = rr_info.get("rr") if rr_info else st.get("rr")
    reason = (rr_info.get("reason") if rr_info else None) or st.get("rr_reason") or ""
    should = rr_info.get("should_penalize") if rr_info else None
    hint = _floor_hint(rr_info)

    try:
        min_rr = float(cfg.get("structure_rr_min_rr") or 2.0)
    except (TypeError, ValueError):
        min_rr = 2.0

    tags: List[Dict[str, str]] = []
    if should is True:
        if reason in ("below_or_no_support", "zero_downside"):
            tags.append(
                {
                    "id": "poor_structure_rr",
                    "label": "破位支撑",
                    "level": "danger",
                    "reason": f"现价不高于最近支撑（结构盈亏比要求 ≥{min_rr:g}）{hint}",
                }
            )
        elif reason == "at_resistance":
            tags.append(
                {
                    "id": "poor_structure_rr",
                    "label": "贴/超阻力",
                    "level": "danger",
                    "reason": f"上行空间不足 RR={rr if rr is not None else 0}（要求 ≥{min_rr:g}）{hint}",
                }
            )
        elif reason == "thin_upside":
            up = rr_info.get("upside") if rr_info else None
            up_pct = rr_info.get("upside_pct") if rr_info else None
            need = rr_info.get("min_upside_pct") if rr_info else None
            up_txt = f"{up:.2f}元" if isinstance(up, (int, float)) else "—"
            pct_txt = f"{up_pct * 100:.2f}%" if isinstance(up_pct, (int, float)) else "—"
            need_txt = f"{float(need) * 100:.1f}%" if isinstance(need, (int, float)) else "3%"
            tags.append(
                {
                    "id": "poor_structure_rr",
                    "label": "上行空间不足",
                    "level": "danger",
                    "reason": (
                        f"距最近阻力仅约 {up_txt}（{pct_txt}），低于最小上行要求 {need_txt}"
                        f"；RR={rr if rr is not None else '—'}{hint}"
                    ),
                }
            )
        else:
            tags.append(
                {
                    "id": "poor_structure_rr",
                    "label": "结构盈亏比偏低",
                    "level": "warn",
                    "reason": f"结构盈亏比异常（{reason}）{hint}",
                }
            )
    elif should is not False and rr is not None:
        try:
            rr_f = float(rr)
        except (TypeError, ValueError):
            rr_f = None
        if rr_f is not None and rr_f < min_rr:
            tags.append(
                {
                    "id": "poor_structure_rr",
                    "label": "结构盈亏比偏低",
                    "level": "warn",
                    "reason": f"结构盈亏比 RR={rr_f:.2f} < {min_rr:g}{hint}",
                }
            )

    hanging, hang_pct = is_structure_hanging(price, st.get("nearest_support"), cfg)
    if hanging:
        thr = resolve_structure_hang_min_upside_pct(cfg)
        pct_txt = f"{hang_pct * 100:.1f}%" if hang_pct is not None else "—"
        tags.append(
            {
                "id": "structure_hanging",
                "label": "悬空离支撑",
                "level": "danger",
                "reason": f"现价相对最近支撑距离 {pct_txt} ≥ 阈值 {thr * 100:.1f}%",
            }
        )

    return tags


def build_trend_risk_tags(ind: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
    """空头趋势 / 跌破中期均线风险提示（不硬筛）。"""
    ind = ind or {}
    tags: List[Dict[str, str]] = []
    if ind.get("ma_bear_ok"):
        periods = ind.get("ma_bull_periods") or [5, 10, 20]
        label = "<".join(f"MA{p}" for p in periods)
        tags.append(
            {
                "id": "bearish_ma_trend",
                "label": "空头趋势",
                "level": "danger",
                "reason": f"均线空头排列（{label}）",
            }
        )
    elif ind.get("above_ma20") is False:
        tags.append(
            {
                "id": "below_ma20",
                "label": "跌破中期均线",
                "level": "warn",
                "reason": "收盘价低于 MA20",
            }
        )
    return tags


def _cfg_float(cfg: Dict[str, Any], key: str, default: float) -> float:
    try:
        return float(cfg.get(key) if cfg.get(key) is not None else default)
    except (TypeError, ValueError):
        return default


def evaluate_overheat_hard_gate(
    ind: Optional[Dict[str, Any]],
    cfg: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    近期涨幅过大硬闸：
    - 近 N 日相对最低价涨幅 ≥ overheat_hard_pct（默认 25%）
    - 或相对 MA20 乖离 ≥ overheat_bias_hard_pct（默认 20%）
    """
    cfg = cfg or {}
    ind = ind or {}
    if cfg.get("overheat_hard_gate_enabled") is False:
        return {"blocked": False, "reasons": [], "enabled": False}

    soft_pct = _cfg_float(cfg, "overheat_soft_pct", 0.15)
    hard_pct = _cfg_float(cfg, "overheat_hard_pct", 0.25)
    bias_soft = _cfg_float(cfg, "overheat_bias_soft_pct", 0.15)
    bias_hard = _cfg_float(cfg, "overheat_bias_hard_pct", 0.20)
    if hard_pct < soft_pct:
        hard_pct = soft_pct
    if bias_hard < bias_soft:
        bias_hard = bias_soft

    reasons: List[str] = []
    ret = ind.get("ret_from_low_n")
    bias = ind.get("ma20_bias")
    try:
        ret_f = float(ret) if ret is not None else None
    except (TypeError, ValueError):
        ret_f = None
    try:
        bias_f = float(bias) if bias is not None else None
    except (TypeError, ValueError):
        bias_f = None

    if ret_f is not None and ret_f >= hard_pct:
        reasons.append("近期涨幅过大")
    if bias_f is not None and bias_f >= bias_hard:
        reasons.append("均线乖离过大")

    return {
        "blocked": bool(reasons),
        "reasons": reasons,
        "enabled": True,
        "ret_from_low_n": ret_f,
        "ma20_bias": bias_f,
        "overheat_hard_pct": hard_pct,
        "overheat_bias_hard_pct": bias_hard,
        "overheat_lookback_days": ind.get("overheat_lookback_days")
        or cfg.get("overheat_lookback_days")
        or 10,
    }


def build_overheat_risk_tags(
    ind: Optional[Dict[str, Any]],
    cfg: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """近期涨幅 / 乖离：软提示 + 硬闸对应 danger 标签。"""
    cfg = cfg or {}
    ind = ind or {}
    if cfg.get("overheat_warn_enabled") is False:
        return []

    soft_pct = _cfg_float(cfg, "overheat_soft_pct", 0.15)
    hard_pct = _cfg_float(cfg, "overheat_hard_pct", 0.25)
    bias_soft = _cfg_float(cfg, "overheat_bias_soft_pct", 0.15)
    bias_hard = _cfg_float(cfg, "overheat_bias_hard_pct", 0.20)
    if hard_pct < soft_pct:
        hard_pct = soft_pct
    if bias_hard < bias_soft:
        bias_hard = bias_soft
    lookback = ind.get("overheat_lookback_days") or cfg.get("overheat_lookback_days") or 10

    tags: List[Dict[str, str]] = []
    try:
        ret_f = float(ind["ret_from_low_n"]) if ind.get("ret_from_low_n") is not None else None
    except (TypeError, ValueError):
        ret_f = None
    try:
        bias_f = float(ind["ma20_bias"]) if ind.get("ma20_bias") is not None else None
    except (TypeError, ValueError):
        bias_f = None

    if ret_f is not None:
        if ret_f >= hard_pct:
            tags.append(
                {
                    "id": "recent_overheat",
                    "label": "近期涨幅过大",
                    "level": "danger",
                    "reason": (
                        f"近{lookback}日相对最低价涨幅 {ret_f * 100:.1f}%"
                        f" ≥ 硬闸 {hard_pct * 100:.0f}%"
                    ),
                }
            )
        elif ret_f >= soft_pct:
            tags.append(
                {
                    "id": "recent_overheat",
                    "label": "近期涨幅偏大",
                    "level": "warn",
                    "reason": (
                        f"近{lookback}日相对最低价涨幅 {ret_f * 100:.1f}%"
                        f" ≥ 提示阈值 {soft_pct * 100:.0f}%"
                    ),
                }
            )

    if bias_f is not None:
        if bias_f >= bias_hard:
            tags.append(
                {
                    "id": "ma20_overheat",
                    "label": "均线乖离过大",
                    "level": "danger",
                    "reason": (
                        f"收盘相对 MA20 乖离 {bias_f * 100:.1f}%"
                        f" ≥ 硬闸 {bias_hard * 100:.0f}%"
                    ),
                }
            )
        elif bias_f >= bias_soft:
            tags.append(
                {
                    "id": "ma20_overheat",
                    "label": "均线乖离偏大",
                    "level": "warn",
                    "reason": (
                        f"收盘相对 MA20 乖离 {bias_f * 100:.1f}%"
                        f" ≥ 提示阈值 {bias_soft * 100:.0f}%"
                    ),
                }
            )

    return tags


def build_turnover_risk_tags(
    ind: Optional[Dict[str, Any]] = None,
    cfg: Optional[Dict[str, Any]] = None,
    *,
    turnover_part: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """换手过高软标签（减分时提示；默认不否决买点）。"""
    cfg = cfg or {}
    ind = ind or {}
    part = turnover_part if isinstance(turnover_part, dict) else {}
    if part.get("enabled") is False:
        return []
    tags: List[Dict[str, str]] = []
    try:
        score = float(part.get("score") or 0)
    except (TypeError, ValueError):
        score = 0.0
    t = ind.get("turnover_rate")
    if t is None:
        t = part.get("turnover_rate")
    try:
        t_f = float(t) if t is not None else None
    except (TypeError, ValueError):
        t_f = None
    med = ind.get("turnover_median_n")
    if med is None:
        med = part.get("median")
    rel = part.get("relative")
    abs_pen = bool(part.get("abs_penalty"))
    reason_code = str(part.get("reason") or "")

    if score >= 0 and not abs_pen and reason_code not in ("abs_penalty", "abs_penalty_full"):
        return tags

    if t_f is None and score >= 0:
        return tags

    abs_full = _cfg_float(cfg, "turnover_abs_penalty_full", 40.0)
    abs_above = _cfg_float(cfg, "turnover_abs_penalty_above", 25.0)
    level = (
        "danger"
        if (t_f is not None and t_f >= abs_full)
        or reason_code == "abs_penalty_full"
        or score <= -6
        else "warn"
    )
    bits = []
    if t_f is not None:
        bits.append(f"当日换手 {t_f:.1f}%")
    if med is not None:
        try:
            bits.append(f"近窗中位 {float(med):.1f}%")
        except (TypeError, ValueError):
            pass
    if rel is not None:
        try:
            bits.append(f"相对约 {float(rel):.1f}×")
        except (TypeError, ValueError):
            pass
    bits.append(f"换手分项 {score:+.1f}")
    if abs_pen or (t_f is not None and t_f >= abs_above):
        bits.append(f"触发绝对熔断（≥{abs_above:.0f}%）")
    tags.append(
        {
            "id": "turnover_extreme",
            "label": "换手过高",
            "level": level,
            "reason": "；".join(bits) if bits else "换手分项为负",
        }
    )
    return tags
