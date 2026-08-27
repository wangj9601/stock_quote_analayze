# -*- coding: utf-8 -*-
"""URT 买点因子后滤：均线多头分中段硬闸、回测精选模式等。"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .backtest_factor_report import flatten_score_factors


def _f(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def ma_bull_part_score(score_detail: Any) -> Optional[float]:
    sd = score_detail if isinstance(score_detail, dict) else {}
    parts = sd.get("parts") if isinstance(sd.get("parts"), dict) else {}
    ma = parts.get("ma_bull") if isinstance(parts.get("ma_bull"), dict) else {}
    return _f(ma.get("score"))


def ma_bull_mid_range(cfg: Dict[str, Any]) -> tuple[float, float]:
    lo = _f(cfg.get("exclude_ma_bull_score_lo"))
    hi = _f(cfg.get("exclude_ma_bull_score_hi"))
    return float(lo if lo is not None else 4.0), float(hi if hi is not None else 7.0)


def evaluate_ma_bull_mid_gate(score_detail: Any, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """均线多头分处于 [lo, hi) 时否决买点（A/B 验证弱项区间）。"""
    enabled = cfg.get("exclude_ma_bull_score_mid_enabled")
    if enabled is False:
        return {"enabled": False, "blocked": False, "pass": True}
    lo, hi = ma_bull_mid_range(cfg)
    part = ma_bull_part_score(score_detail)
    if part is None:
        return {
            "enabled": True,
            "blocked": False,
            "pass": True,
            "lo": lo,
            "hi": hi,
            "score": None,
            "reason": "无均线多头分项，不否决",
        }
    blocked = lo <= part < hi
    return {
        "enabled": True,
        "blocked": blocked,
        "pass": not blocked,
        "lo": lo,
        "hi": hi,
        "score": part,
        "reason": (
            f"均线多头分 {part:g} 处于弱项区间 [{lo:g},{hi:g})"
            if blocked
            else f"均线多头分 {part:g} 不在弱项区间 [{lo:g},{hi:g})"
        ),
    }


def is_ma_bull_mid_blocked(score_detail: Any, cfg: Dict[str, Any]) -> bool:
    return bool(evaluate_ma_bull_mid_gate(score_detail, cfg).get("blocked"))


def passes_signal_factor_filter(
    sig: Dict[str, Any],
    filters: Optional[Dict[str, Any]] = None,
) -> bool:
    """回测 trace 后滤：按 score_detail 展平因子做 A/B / 精选筛选。"""
    if not filters:
        return True
    sig = sig if isinstance(sig, dict) else {}
    factors = flatten_score_factors(sig)
    score = _f(sig.get("score"))

    ex_ge = filters.get("exclude_score_ge")
    if ex_ge is not None and score is not None and score >= float(ex_ge):
        return False

    ma_range = filters.get("exclude_ma_bull_range")
    if ma_range and len(ma_range) >= 2:
        f_ma = factors.get("f_ma_bull")
        lo, hi = float(ma_range[0]), float(ma_range[1])
        if f_ma is not None and lo <= float(f_ma) < hi:
            return False

    dist_max = filters.get("require_dist_to_support_max")
    if dist_max is not None:
        dist = factors.get("dist_to_support_pct")
        if dist is None or float(dist) > float(dist_max):
            return False

    rr_ge = filters.get("exclude_structure_rr_ge")
    if rr_ge is not None:
        rr = factors.get("structure_rr")
        if rr is not None and float(rr) >= float(rr_ge):
            return False

    return True


def build_signal_filter_from_cfg(
    cfg: Dict[str, Any],
    signal_quality_mode: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """由策略包 + 回测信号质量模式生成 trace 后滤规则。"""
    mode = (signal_quality_mode or cfg.get("signal_quality_mode") or "standard").strip().lower()
    flt: Dict[str, Any] = {}

    if cfg.get("exclude_ma_bull_score_mid_enabled") is not False:
        lo, hi = ma_bull_mid_range(cfg)
        flt["exclude_ma_bull_range"] = [lo, hi]

    if mode == "premium":
        dist_max = _f(cfg.get("premium_signal_near_support_max_pct"))
        flt["require_dist_to_support_max"] = float(dist_max if dist_max is not None else 2.0)
        ex_score = _f(cfg.get("premium_signal_exclude_score_ge"))
        flt["exclude_score_ge"] = float(ex_score if ex_score is not None else 90.0)

    return flt or None


def signal_quality_mode_label(mode: Optional[str]) -> str:
    m = (mode or "standard").strip().lower()
    if m == "premium":
        return "精选（近支撑≤2% + 排除弱项）"
    return "标准（排除均线多头分中段）"
