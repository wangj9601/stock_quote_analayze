# -*- coding: utf-8 -*-
"""URT 打分：MA20 梯度 + 连阳天数/实体 + 量能 + 中期/多头 + 位置RR + 换手甜区 + 过热扣分 + 可选量比。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .indicators import (
    ma_bull_prefix_depth,
    normalize_ma_bull_periods,
    normalize_ma_bull_score_periods,
    normalize_yang_medium_rules,
)


def resolve_turnover_flags(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, bool]:
    """解耦换手硬筛 / 积分；未显式配置新键时回退 use_turnover。"""
    cfg = cfg or {}
    legacy = bool(cfg.get("use_turnover"))
    hard = cfg.get("turnover_hard_filter")
    score = cfg.get("turnover_score_enabled")
    return {
        "hard_filter": bool(legacy if hard is None else hard),
        "score_enabled": bool(legacy if score is None else score),
    }


def _cfg_float(cfg: Dict[str, Any], key: str, default: float) -> float:
    try:
        v = cfg.get(key)
        if v is None:
            return float(default)
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _yang_score(ya: int, yb: int) -> float:
    """连阳天数原始分（满分 40，再缩放到 yang_score_max）。"""
    if yb >= 5:
        return 40.0
    if yb >= 4:
        return 36.0
    if ya >= 4:
        return 34.0
    if ya >= 3:
        return 30.0
    return max(0.0, ya * 8.0)


def _volume_score(vm: float, need: float, full_multiple: float) -> float:
    """
    量能原始分（满分 40，再缩放到 volume_score_max）。
    - vm < need：按比例给基础分
    - need ≤ vm < full_multiple：从 30 过渡到 40
    - vm ≥ full_multiple：满分 40
    """
    need = max(need, 0.1)
    full = max(float(full_multiple or need), need)
    if vm >= full:
        return 40.0
    if vm >= need:
        span = max(full - need, 0.1)
        return 30.0 + min(10.0, (vm - need) / span * 10.0)
    return max(0.0, vm / need * 30.0)


def _yang_medium_score(ind: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    """中期阳线：按各窗口相对阈值完成度等权平均 × max。"""
    rules = normalize_yang_medium_rules(cfg)
    score_max = _cfg_float(cfg, "yang_medium_score_max", 5.0)
    detail = ind.get("yang_medium_detail")
    by_window: Dict[int, int] = {}
    if isinstance(detail, list):
        for d in detail:
            if isinstance(d, dict) and d.get("window") is not None:
                try:
                    by_window[int(d["window"])] = int(d.get("count") or 0)
                except (TypeError, ValueError):
                    continue
    ratios: List[float] = []
    items: List[Dict[str, Any]] = []
    for rule in rules:
        w = int(rule["window"])
        need = max(1, int(rule["min_up_days"]))
        cnt = by_window.get(w)
        if cnt is None:
            key = f"yang_count_{w}"
            try:
                cnt = int(ind.get(key) or 0)
            except (TypeError, ValueError):
                cnt = 0
        ratio = min(1.0, float(cnt) / float(need))
        ratios.append(ratio)
        items.append({"window": w, "count": cnt, "min_up_days": need, "ratio": round(ratio, 4)})
    if not ratios:
        return 0.0, {"score": 0.0, "max": score_max, "items": []}
    part = round(sum(ratios) / len(ratios) * score_max, 2)
    return part, {
        "score": part,
        "max": score_max,
        "ok": bool(ind.get("yang_medium_ok")),
        "items": items,
    }


def _ma20_trend_score(ind: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    """站上 MA20 后的斜率/发散梯度分；未站上得 0。"""
    score_max = _cfg_float(cfg, "ma20_score_max", 10.0)
    mode = str(cfg.get("ma20_score_mode") or "slope_bias").strip().lower()
    above = bool(ind.get("above_ma20"))
    meta: Dict[str, Any] = {
        "ok": above,
        "mode": mode,
        "score": 0.0,
        "max": score_max,
        "bias20": ind.get("ma20_bias"),
        "slope20": ind.get("ma20_slope"),
        "slope_days": ind.get("ma20_slope_days") or cfg.get("ma20_slope_days") or 5,
    }
    if not above:
        return 0.0, meta

    if mode in ("binary", "static", "pass"):
        meta["score"] = score_max
        return score_max, meta

    bias = ind.get("ma20_bias")
    slope = ind.get("ma20_slope")
    try:
        bias_f = float(bias) if bias is not None else 0.0
    except (TypeError, ValueError):
        bias_f = 0.0
    try:
        slope_f = float(slope) if slope is not None else 0.0
    except (TypeError, ValueError):
        slope_f = 0.0

    # 温和发散偏好：bias 约 1%～8%、slope 约 0.3%～2% 给高分；贴线与过热区降分
    bias_abs = abs(bias_f)
    if bias_abs <= 0.005:
        bias_term = 0.25
    elif bias_abs <= 0.02:
        bias_term = _lerp(bias_abs, 0.005, 0.02, 0.45, 1.0)
    elif bias_abs <= 0.08:
        bias_term = 1.0
    elif bias_abs <= 0.15:
        bias_term = _lerp(bias_abs, 0.08, 0.15, 1.0, 0.55)
    else:
        bias_term = 0.45

    if slope_f <= 0:
        slope_term = 0.35
    elif slope_f <= 0.003:
        slope_term = _lerp(slope_f, 0.0, 0.003, 0.35, 0.7)
    elif slope_f <= 0.02:
        slope_term = _lerp(slope_f, 0.003, 0.02, 0.7, 1.0)
    else:
        slope_term = 0.85

    raw = 0.55 * bias_term + 0.45 * slope_term
    part = round(max(0.0, min(score_max, raw * score_max)), 2)
    # 至少给过线基础分，避免贴线过低（硬筛已过）
    floor = score_max * 0.35
    part = max(floor, part)
    meta["score"] = part
    meta["bias_term"] = round(bias_term, 4)
    meta["slope_term"] = round(slope_term, 4)
    return part, meta


def _yang_quality_score(ind: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    score_max = _cfg_float(cfg, "yang_quality_score_max", 10.0)
    q = ind.get("yang_quality") if isinstance(ind.get("yang_quality"), dict) else {}
    raw = q.get("quality_raw")
    try:
        raw_f = float(raw) if raw is not None else 0.0
    except (TypeError, ValueError):
        raw_f = 0.0
    part = round(max(0.0, min(score_max, raw_f * score_max)), 2)
    meta = {
        "score": part,
        "max": score_max,
        "quality_raw": q.get("quality_raw"),
        "avg_body_ratio": q.get("avg_body_ratio"),
        "breakout_body_ratio": q.get("breakout_body_ratio"),
        "breakout_amplitude": q.get("breakout_amplitude"),
        "window": q.get("window"),
    }
    return part, meta


def _structure_position_score(ind: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    """贴近支撑（0～prox_max）+ RR（0～rr_max）；KDE/RR 缺失给中性偏低分。"""
    prox_max = _cfg_float(cfg, "structure_proximity_score_max", 8.0)
    rr_max = _cfg_float(cfg, "structure_rr_score_max", 7.0)
    total_max = prox_max + rr_max
    near_pct = _cfg_float(cfg, "structure_proximity_full_pct", 0.02)
    far_pct = _cfg_float(cfg, "structure_proximity_zero_pct", 0.08)
    rr_full = _cfg_float(cfg, "structure_rr_score_full", 3.0)
    rr_mid = _cfg_float(cfg, "structure_rr_score_mid", 2.0)
    rr_low = _cfg_float(cfg, "structure_rr_score_low", 1.5)
    neutral_rr = _cfg_float(cfg, "structure_rr_score_missing", 2.0)

    close = ind.get("close")
    support = ind.get("nearest_support")
    rr = ind.get("structure_rr")
    kde_ok = ind.get("kde_ok")

    prox = 0.0
    prox_reason = "no_support"
    try:
        c = float(close) if close is not None else None
        s = float(support) if support is not None else None
    except (TypeError, ValueError):
        c, s = None, None
    if c is not None and c > 0 and s is not None:
        if c < s:
            prox = 0.0
            prox_reason = "below_support"
        else:
            dist = (c - s) / c
            if dist <= near_pct:
                prox = prox_max
                prox_reason = "near_support"
            elif dist >= far_pct:
                prox = 0.0
                prox_reason = "hanging"
            else:
                prox = _lerp(dist, near_pct, far_pct, prox_max, 0.0)
                prox_reason = "mid_distance"
    elif kde_ok is False:
        prox = prox_max * 0.25
        prox_reason = "kde_missing_neutral"

    rr_score = neutral_rr
    rr_reason = "rr_missing"
    try:
        rr_f = float(rr) if rr is not None else None
    except (TypeError, ValueError):
        rr_f = None
    if rr_f is not None:
        if rr_f >= rr_full:
            rr_score = rr_max
            rr_reason = "rr_strong"
        elif rr_f >= rr_mid:
            rr_score = _lerp(rr_f, rr_mid, rr_full, rr_max * 0.55, rr_max)
            rr_reason = "rr_good"
        elif rr_f >= rr_low:
            rr_score = _lerp(rr_f, rr_low, rr_mid, rr_max * 0.2, rr_max * 0.55)
            rr_reason = "rr_weak"
        else:
            rr_score = 0.0
            rr_reason = "rr_poor"

    part = round(max(0.0, min(total_max, prox + rr_score)), 2)
    meta = {
        "score": part,
        "max": total_max,
        "proximity_score": round(prox, 2),
        "proximity_max": prox_max,
        "proximity_reason": prox_reason,
        "rr_score": round(rr_score, 2),
        "rr_max": rr_max,
        "rr_reason": rr_reason,
        "nearest_support": support,
        "structure_rr": rr,
        "kde_ok": kde_ok,
        "close": close,
    }
    return part, meta


def _overheat_penalty_score(ind: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    """过热阶梯扣分：软阈值起扣，硬阈值附近扣满（负分）。"""
    pen_max = abs(_cfg_float(cfg, "overheat_penalty_max", 10.0))
    soft_pct = _cfg_float(cfg, "overheat_soft_pct", 0.15)
    hard_pct = _cfg_float(cfg, "overheat_hard_pct", 0.25)
    bias_soft = _cfg_float(cfg, "overheat_bias_soft_pct", 0.15)
    bias_hard = _cfg_float(cfg, "overheat_bias_hard_pct", 0.20)

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

    def _tier(v: Optional[float], soft: float, hard: float) -> float:
        if v is None or v < soft:
            return 0.0
        if v >= hard:
            return 1.0
        return _lerp(v, soft, hard, 0.0, 1.0)

    t_ret = _tier(ret_f, soft_pct, hard_pct)
    t_bias = _tier(bias_f, bias_soft, bias_hard)
    intensity = max(t_ret, t_bias)
    part = round(-pen_max * intensity, 2)
    meta = {
        "score": part,
        "max": 0.0,
        "min": -pen_max,
        "intensity": round(intensity, 4),
        "ret_from_low_n": ret_f,
        "ma20_bias": bias_f,
        "soft_pct": soft_pct,
        "hard_pct": hard_pct,
        "bias_soft_pct": bias_soft,
        "bias_hard_pct": bias_hard,
    }
    return part, meta


def _lerp(x: float, x0: float, x1: float, y0: float, y1: float) -> float:
    if x1 <= x0:
        return y1
    t = (x - x0) / (x1 - x0)
    t = max(0.0, min(1.0, t))
    return y0 + (y1 - y0) * t


def _turnover_score_from_relative(
    r: float,
    *,
    score_max: float,
    score_min: float,
    sweet_low: float,
    sweet_high: float,
    soft_cap: float,
    penalty_full: float,
) -> float:
    """相对倍数甜区：爬坡 → 满分平台 → 衰减至 0 → 减分至 score_min。"""
    lo = float(sweet_low)
    hi = max(float(sweet_high), lo)
    soft = max(float(soft_cap), hi)
    full_pen = max(float(penalty_full), soft)
    smax = float(score_max)
    smin = float(score_min)

    if r < lo:
        # 0 → max 爬坡（r=0 得 0，r=lo 得 max）
        return _lerp(r, 0.0, lo, 0.0, smax) if lo > 0 else 0.0
    if r <= hi:
        return smax
    if r <= soft:
        return _lerp(r, hi, soft, smax, 0.0)
    if r <= full_pen:
        return _lerp(r, soft, full_pen, 0.0, smin)
    return smin


def _turnover_score_absolute_fallback(
    t: float,
    *,
    score_max: float,
    score_min: float,
    sweet_low: float,
    sweet_high: float,
    abs_pen_above: float,
    abs_pen_full: float,
) -> float:
    """中位不足时：绝对 3%~7% 甜区，≥25% 减分。"""
    lo = float(sweet_low)
    hi = max(float(sweet_high), lo)
    pen0 = float(abs_pen_above)
    pen1 = max(float(abs_pen_full), pen0)
    smax = float(score_max)
    smin = float(score_min)

    if t >= pen1:
        return smin
    if t >= pen0:
        return _lerp(t, pen0, pen1, 0.0, smin)
    if t < lo:
        return _lerp(t, 0.0, lo, 0.0, smax) if lo > 0 else 0.0
    if t <= hi:
        return smax
    # hi → pen0：满分衰减到 0
    if t < pen0:
        return _lerp(t, hi, pen0, smax, 0.0)
    return 0.0


def _turnover_absolute_penalty_overlay(
    t: float,
    rel_score: float,
    *,
    score_min: float,
    abs_pen_above: float,
    abs_pen_full: float,
) -> Tuple[float, bool]:
    """绝对熔断覆盖：取相对分与绝对负分的更严（更小）者。"""
    pen0 = float(abs_pen_above)
    pen1 = max(float(abs_pen_full), pen0)
    smin = float(score_min)
    if t < pen0:
        return rel_score, False
    if t >= pen1:
        return min(rel_score, smin), True
    abs_neg = _lerp(t, pen0, pen1, 0.0, smin)
    return min(rel_score, abs_neg), True


def compute_turnover_score_part(
    turnover_rate: Optional[float],
    turnover_median: Optional[float],
    cfg: Dict[str, Any],
) -> Dict[str, Any]:
    """换手分项：相对自身中位甜区 + 绝对熔断减分。"""
    flags = resolve_turnover_flags(cfg)
    score_max = _cfg_float(cfg, "turnover_score_max", 8.0)
    score_min = _cfg_float(cfg, "turnover_score_min", -8.0)
    lookback = int(_cfg_float(cfg, "turnover_lookback", 20))
    base: Dict[str, Any] = {
        "enabled": flags["score_enabled"],
        "hard_filter": flags["hard_filter"],
        "turnover_rate": turnover_rate,
        "median": turnover_median,
        "relative": None,
        "score": 0.0,
        "max": score_max if flags["score_enabled"] else 0.0,
        "min": score_min if flags["score_enabled"] else 0.0,
        "mode": None,
        "abs_penalty": False,
        "reason": None,
        "lookback": lookback,
    }
    if not flags["score_enabled"]:
        base["reason"] = "score_disabled"
        return base
    if turnover_rate is None:
        base["reason"] = "missing_turnover"
        return base

    t = float(turnover_rate)
    abs_pen_above = _cfg_float(cfg, "turnover_abs_penalty_above", 25.0)
    abs_pen_full = _cfg_float(cfg, "turnover_abs_penalty_full", 40.0)
    rel_sweet_lo = _cfg_float(cfg, "turnover_rel_sweet_low", 1.0)
    rel_sweet_hi = _cfg_float(cfg, "turnover_rel_sweet_high", 2.0)
    rel_soft = _cfg_float(cfg, "turnover_rel_soft_cap", 3.5)
    rel_pen_full = _cfg_float(cfg, "turnover_rel_penalty_full", 5.0)
    abs_sweet_lo = _cfg_float(cfg, "turnover_abs_sweet_low", 3.0)
    abs_sweet_hi = _cfg_float(cfg, "turnover_abs_sweet_high", 7.0)

    med = None
    try:
        if turnover_median is not None:
            med = float(turnover_median)
    except (TypeError, ValueError):
        med = None

    if med is not None and med > 0:
        r = t / max(med, 0.5)
        rel_s = _turnover_score_from_relative(
            r,
            score_max=score_max,
            score_min=score_min,
            sweet_low=rel_sweet_lo,
            sweet_high=rel_sweet_hi,
            soft_cap=rel_soft,
            penalty_full=rel_pen_full,
        )
        final, abs_hit = _turnover_absolute_penalty_overlay(
            t,
            rel_s,
            score_min=score_min,
            abs_pen_above=abs_pen_above,
            abs_pen_full=abs_pen_full,
        )
        base.update(
            {
                "relative": round(r, 4),
                "score": round(final, 2),
                "mode": "relative",
                "abs_penalty": abs_hit,
                "reason": (
                    "abs_penalty_full"
                    if t >= abs_pen_full
                    else ("abs_penalty" if abs_hit else "relative_curve")
                ),
            }
        )
        return base

    # 中位不足：绝对回退
    fb = _turnover_score_absolute_fallback(
        t,
        score_max=score_max,
        score_min=score_min,
        sweet_low=abs_sweet_lo,
        sweet_high=abs_sweet_hi,
        abs_pen_above=abs_pen_above,
        abs_pen_full=abs_pen_full,
    )
    base.update(
        {
            "score": round(fb, 2),
            "mode": "absolute_fallback",
            "abs_penalty": t >= abs_pen_above,
            "reason": (
                "abs_penalty_full"
                if t >= abs_pen_full
                else ("abs_penalty" if t >= abs_pen_above else "absolute_sweet")
            ),
        }
    )
    return base


_DEFAULT_MA_BULL_SCORE_TABLE = [0.0, 1.5, 3.0, 4.5, 6.0, 7.0, 8.0]


def _normalize_ma_bull_score_table(cfg: Dict[str, Any]) -> List[float]:
    raw = cfg.get("ma_bull_score_table")
    if not isinstance(raw, (list, tuple)) or not raw:
        return list(_DEFAULT_MA_BULL_SCORE_TABLE)
    out: List[float] = []
    for x in raw:
        try:
            out.append(float(x))
        except (TypeError, ValueError):
            continue
    return out if out else list(_DEFAULT_MA_BULL_SCORE_TABLE)


def _ma_bull_pairs_ok(periods: List[int], depth: int) -> List[str]:
    bits: List[str] = []
    for i in range(len(periods) - 1):
        mark = "✓" if i < depth else "✗"
        bits.append(f"{periods[i]}>{periods[i + 1]}{mark}")
    return bits


def _ma_bull_tier_score(
    ind: Dict[str, Any],
    cfg: Dict[str, Any],
) -> Tuple[float, Dict[str, Any]]:
    """前缀链深度分档：硬筛链空头 −8；否则按 depth 查表（默认满分 8）。"""
    bull_ok = bool(ind.get("ma_bull_ok"))
    bear_ok = bool(ind.get("ma_bear_ok"))
    hard_periods = ind.get("ma_bull_periods") or normalize_ma_bull_periods(cfg)
    score_periods = ind.get("ma_bull_score_periods") or normalize_ma_bull_score_periods(cfg)
    if not isinstance(score_periods, list) or len(score_periods) < 2:
        score_periods = normalize_ma_bull_score_periods(cfg)
    score_periods = [int(p) for p in score_periods]

    score_values = ind.get("ma_bull_score_values")
    if not isinstance(score_values, list) or len(score_values) != len(score_periods):
        hard_vals = ind.get("ma_bull_values")
        hard_map: Dict[int, Any] = {}
        if isinstance(hard_periods, list) and isinstance(hard_vals, list):
            for p, v in zip(hard_periods, hard_vals):
                try:
                    hard_map[int(p)] = v
                except (TypeError, ValueError):
                    continue
        score_values = [hard_map.get(int(p)) for p in score_periods]

    depth = ind.get("ma_bull_depth")
    try:
        depth_i = int(depth) if depth is not None else ma_bull_prefix_depth(score_values)
    except (TypeError, ValueError):
        depth_i = ma_bull_prefix_depth(score_values)

    table = _normalize_ma_bull_score_table(cfg)
    score_max = _cfg_float(cfg, "ma_bull_score_max", 8.0)

    if bear_ok:
        bull_part = -8.0
    else:
        idx = max(0, min(depth_i, len(table) - 1))
        bull_part = max(0.0, min(score_max, float(table[idx])))

    max_depth = max(0, len(score_periods) - 1)
    tip_period = None
    if depth_i > 0 and depth_i < len(score_periods):
        tip_period = int(score_periods[depth_i])
    elif depth_i >= max_depth and score_periods:
        tip_period = int(score_periods[-1])

    meta = {
        "ok": bull_ok,
        "bear_ok": bear_ok,
        "score": float(bull_part),
        "max": score_max,
        "min": -8.0,
        "periods": hard_periods,
        "values": ind.get("ma_bull_values"),
        "score_periods": score_periods,
        "score_values": score_values,
        "depth": depth_i,
        "max_depth": max_depth,
        "tip_period": tip_period,
        "pairs_ok": _ma_bull_pairs_ok(score_periods, depth_i),
        "ma5": ind.get("ma5"),
        "ma10": ind.get("ma10"),
        "ma20_stack": ind.get("ma20_stack"),
        "hard_filter": bool(cfg.get("require_ma_bull")),
    }
    return float(bull_part), meta


def compute_score_breakdown(ind: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    """返回 (总分, 分项明细)。"""
    parts: Dict[str, Any] = {}
    score = 0.0

    ma_part, ma_meta = _ma20_trend_score(ind, cfg)
    parts["above_ma20"] = ma_meta
    score += ma_part

    ya = int(ind.get("yang_count_4") or 0)
    yb = int(ind.get("yang_count_5") or 0)
    yang_max = _cfg_float(cfg, "yang_score_max", 20.0)
    yang_raw = _yang_score(ya, yb)
    yang_part = round(yang_raw * yang_max / 40.0, 2)
    parts["yang"] = {
        "yang_count_4": ya,
        "yang_count_5": yb,
        "score": yang_part,
        "max": yang_max,
        "raw_40": yang_raw,
    }
    score += yang_part

    yq_part, yq_meta = _yang_quality_score(ind, cfg)
    parts["yang_quality"] = yq_meta
    score += yq_part

    # 量能主分上限 volume_score_max（默认 25）
    vm = float(ind.get("volume_multiple") or 0)
    need = float(cfg.get("volume_multiple") or 3.0)
    try:
        full_mult = float(cfg.get("volume_score_full_multiple") or 4.0)
    except (TypeError, ValueError):
        full_mult = 4.0
    vol_max = _cfg_float(cfg, "volume_score_max", 25.0)
    vol_raw = _volume_score(vm, need, full_mult)
    vol_part = round(vol_raw * vol_max / 40.0, 2)
    parts["volume"] = {
        "volume_multiple": vm,
        "threshold": need,
        "full_multiple": full_mult,
        "score": vol_part,
        "max": vol_max,
    }
    score += vol_part

    mid_part, mid_meta = _yang_medium_score(ind, cfg)
    parts["yang_medium"] = mid_meta
    score += mid_part

    bull_part, bull_meta = _ma_bull_tier_score(ind, cfg)
    parts["ma_bull"] = bull_meta
    score += bull_part
    bear_ok = bool(bull_meta.get("bear_ok"))
    bull_ok = bool(bull_meta.get("ok"))
    parts["ma_bear"] = {
        "ok": bear_ok,
        "score": -8.0 if bear_ok and not bull_ok else 0.0,
        "max": 0,
        "min": -8,
    }

    to_meta = compute_turnover_score_part(
        ind.get("turnover_rate"),
        ind.get("turnover_median_n"),
        cfg,
    )
    parts["turnover"] = to_meta
    score += float(to_meta.get("score") or 0.0)

    use_vr = bool(cfg.get("use_volume_ratio"))
    vr_part = 0.0
    if use_vr:
        vr = ind.get("volume_ratio")
        if vr is not None:
            vr_part = min(5.0, max(0.0, float(vr) / 3.0 * 5.0))
    parts["volume_ratio"] = {
        "enabled": use_vr,
        "volume_ratio": ind.get("volume_ratio"),
        "score": round(vr_part, 2),
        "max": 5 if use_vr else 0,
    }
    score += vr_part

    st_part, st_meta = _structure_position_score(ind, cfg)
    parts["structure_position"] = st_meta
    score += st_part

    oh_part, oh_meta = _overheat_penalty_score(ind, cfg)
    parts["overheat_penalty"] = oh_meta
    score += oh_part

    total = round(max(0.0, min(100.0, score)), 2)
    detail = {
        "total": total,
        "min_score": float(cfg.get("min_score") or 70),
        "parts": parts,
        "inputs": {
            "close": ind.get("close"),
            "open": ind.get("open"),
            "ma20": ind.get("ma20"),
            "ma5": ind.get("ma5"),
            "ma10": ind.get("ma10"),
            "ma20_bias": ind.get("ma20_bias"),
            "ma20_slope": ind.get("ma20_slope"),
            "yang_count_10": ind.get("yang_count_10"),
            "yang_count_15": ind.get("yang_count_15"),
            "yang_count_20": ind.get("yang_count_20"),
            "volume": ind.get("volume"),
            "avg_volume_20": ind.get("avg_volume_20"),
            "date": ind.get("date"),
            "ma_bear_ok": bear_ok,
            "turnover_rate": ind.get("turnover_rate"),
            "turnover_median_n": ind.get("turnover_median_n"),
            "nearest_support": ind.get("nearest_support"),
            "structure_rr": ind.get("structure_rr"),
            "ret_from_low_n": ind.get("ret_from_low_n"),
        },
    }
    return total, detail


def compute_score(ind: Dict[str, Any], cfg: Dict[str, Any]) -> float:
    total, _ = compute_score_breakdown(ind, cfg)
    return total
