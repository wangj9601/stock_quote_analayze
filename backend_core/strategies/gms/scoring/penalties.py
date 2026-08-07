"""
减分规则引擎：在标准分基础上按配置扣分。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ._helpers import safe_float

PENALTY_RULE_TYPES = {
    "close_below_ma60": {
        "id": "close_below_ma60",
        "label": "收盘低于60日均线",
        "description": "当日收盘价 d₂₀ 低于 60 日均线 ma60_d 时扣分；若 MA60 走平（默认回看「观察周期」内的交易日数，通常 20 天，与下方 MA60 走平判定中的回看周期一致；变化率 < 1.5%）则扣分减半。",
        "default_points": 10,
    },
    "volume_shrink_after_breakout": {
        "id": "volume_shrink_after_breakout",
        "label": "突破后缩量回落",
        "description": "放量突破后量比回落至 1.0 以下且 Δ/d₁ 转弱时扣分。",
        "default_points": 8,
    },
    "momentum_fade": {
        "id": "momentum_fade",
        "label": "动量衰减",
        "description": "动量模块分偏低且 F/Z 比值走弱时扣分。",
        "default_points": 6,
    },
    "excessive_deviation": {
        "id": "excessive_deviation",
        "label": "乖离过大",
        "description": "Δ/d₂₀ 超过「乖离过大阈值」时扣分（默认 15%，对应配置项 overbought_ratio / 退出·乖离过大阈值）。",
        "default_points": 12,
    },
    "observation_range_amplitude": {
        "id": "observation_range_amplitude",
        "label": "观察周期振幅过大",
        "description": "策略观察周期（observation_period，默认 20 个交易日）内，最高价与最低价区间振幅 (高−低)/高 超过阈值时扣分；默认阈值 30%，扣 10 分。",
        "default_points": 10,
        "default_amplitude_threshold_pct": 0.30,
    },
    "poor_structure_rr": {
        "id": "poor_structure_rr",
        "label": "结构盈亏比偏低",
        "description": (
            "基于 KDE 最近支撑/阻力：盈亏比 RR=(阻力−现价)/max(现价−支撑, 现价×分母下限)。"
            "默认分母下限为现价 1.5%（可配置 structure_rr_min_downside_pct / 规则 min_downside_pct；设 0 关闭），"
            "避免贴支撑时 RR 虚高。现价破位支撑、贴阻力或 RR 低于阈值（默认 1.5）时扣分；"
            "无阻力或缺少支撑/KDE 失败时不扣分。与 RPE 结构盈亏比同口径，本项为软减分非硬筛。"
        ),
        "default_points": 10,
        "default_min_rr": 1.5,
        "default_min_downside_pct": 0.015,
    },
    "board_weak": {
        "id": "board_weak",
        "label": "主行业板走弱",
        "description": (
            "个股所属同花顺主行业板环境偏弱时软减分（非硬过滤）。"
            "默认用成分量权基准近 N 日斜率 < 0 判定；斜率不可用时回退当日板块涨跌幅 < 0。"
            "板级资金流尚未采集，本项不依赖资金流；二期可与净流入组合。"
        ),
        "default_points": 10,
    },
}


def list_penalty_rule_type_meta() -> List[Dict[str, Any]]:
    return list(PENALTY_RULE_TYPES.values())


def _close_price(row: Dict[str, Any]) -> float:
    d20 = row.get("d20")
    if d20 is not None:
        return safe_float(d20, 0.0)
    ma20 = safe_float(row.get("ma20_d"), 0.0)
    inst = safe_float(row.get("instant_deviation"), 0.0)
    if ma20 > 0:
        return ma20 + inst
    return 0.0


def _eval_rule(
    rule_id: str,
    row: Dict[str, Any],
    config: Dict[str, Any],
    rule: Optional[Dict[str, Any]] = None,
) -> bool:
    if rule_id == "close_below_ma60":
        close = _close_price(row)
        ma60 = row.get("ma60_d")
        if ma60 is None:
            return False
        ma60_f = safe_float(ma60, 0.0)
        if close <= 0 or ma60_f <= 0:
            return False
        return close < ma60_f

    if rule_id == "volume_shrink_after_breakout":
        vol = safe_float(row.get("volume_ratio"), 0.0)
        ratio_d1 = safe_float(row.get("ratio_d1"), 0.0)
        # 曾放量（量比>1.2）后缩量且短期乖离转负
        peak_hint = safe_float(row.get("_peak_volume_ratio_hint"), vol)
        if peak_hint >= 1.2 and vol < 1.0 and ratio_d1 < 0:
            return True
        return vol > 0 and vol < 0.7 and ratio_d1 < -0.01

    if rule_id == "momentum_fade":
        mom = safe_float(row.get("score_momentum"), 0.0)
        fz = safe_float(row.get("fz_ratio"), 0.0)
        mom_th = safe_float((config.get("scoring") or {}).get("momentum_batch_threshold"), 50.0)
        return mom > 0 and mom < mom_th and fz < 0.5

    if rule_id == "excessive_deviation":
        scoring = config.get("scoring") or {}
        th = safe_float(scoring.get("overbought_ratio") or config.get("overbought_ratio"), 0.15)
        ratio_d20 = safe_float(row.get("ratio_d20"), 0.0)
        return ratio_d20 > th

    if rule_id == "observation_range_amplitude":
        amp = row.get("observation_range_amplitude_pct")
        if amp is None:
            return False
        from ..observation_range import resolve_amplitude_threshold_pct

        threshold = resolve_amplitude_threshold_pct(rule=rule or {}, config=config)
        return safe_float(amp, -1.0) > threshold

    if rule_id == "poor_structure_rr":
        from ..structure_levels import (
            compute_structure_rr,
            resolve_structure_rr_min_downside_pct,
        )

        floor_pct = safe_float(
            (rule or {}).get("min_downside_pct"),
            resolve_structure_rr_min_downside_pct(config),
        )
        info = compute_structure_rr(
            _close_price(row),
            row.get("nearest_support"),
            row.get("nearest_resistance"),
            min_downside_pct=floor_pct,
        )
        if info.get("should_penalize") is True:
            return True
        if info.get("should_penalize") is False:
            return False
        rr = info.get("rr")
        if rr is None:
            return False
        meta = PENALTY_RULE_TYPES["poor_structure_rr"]
        min_rr = safe_float(
            (rule or {}).get("min_rr"),
            safe_float(meta.get("default_min_rr"), 1.5),
        )
        return float(rr) < min_rr

    if rule_id == "board_weak":
        # 选股后处理会写入 board_weak；引擎内若无字段则不扣
        if row.get("board_weak") is True:
            return True
        slope = row.get("sector_slope")
        if slope is not None:
            try:
                th = safe_float((rule or {}).get("slope_threshold"), 0.0)
                return float(slope) < th
            except (TypeError, ValueError):
                return False
        return False

    return False


def _ma60_is_flat(row: Dict[str, Any], config: Dict[str, Any]) -> bool:
    if row.get("ma60_flat") is not None:
        return bool(row.get("ma60_flat"))
    from ..ma60_source import DEFAULT_MA60_FLAT_TOL, is_ma60_flat

    scoring = config.get("scoring") or {}
    tol = safe_float(scoring.get("ma60_flat_tol"), DEFAULT_MA60_FLAT_TOL)
    return is_ma60_flat(row.get("ma60_d"), row.get("ma60_d_lag"), tol)


def _effective_penalty_points(
    rule_id: str,
    rule: Dict[str, Any],
    row: Dict[str, Any],
    config: Dict[str, Any],
    base_points: float,
) -> Tuple[float, Dict[str, Any]]:
    extra: Dict[str, Any] = {"base_points": base_points}
    if rule_id == "observation_range_amplitude":
        from ..observation_range import resolve_amplitude_threshold_pct

        extra["observation_range_amplitude_pct"] = row.get("observation_range_amplitude_pct")
        extra["amplitude_threshold_pct"] = resolve_amplitude_threshold_pct(rule=rule, config=config)
        extra["observation_period_high"] = row.get("observation_period_high")
        extra["observation_period_low"] = row.get("observation_period_low")
        if row.get("observation_range_period_days") is not None:
            extra["observation_range_period_days"] = row.get("observation_range_period_days")
        return base_points, extra
    if rule_id == "poor_structure_rr":
        from ..structure_levels import (
            compute_structure_rr,
            resolve_structure_rr_min_downside_pct,
        )

        meta = PENALTY_RULE_TYPES["poor_structure_rr"]
        min_rr = safe_float(rule.get("min_rr"), safe_float(meta.get("default_min_rr"), 1.5))
        floor_pct = safe_float(
            rule.get("min_downside_pct"),
            resolve_structure_rr_min_downside_pct(config),
        )
        info = compute_structure_rr(
            _close_price(row),
            row.get("nearest_support"),
            row.get("nearest_resistance"),
            min_downside_pct=floor_pct,
        )
        extra["min_rr"] = min_rr
        extra["rr"] = info.get("rr")
        extra["rr_reason"] = info.get("reason")
        extra["nearest_support"] = row.get("nearest_support")
        extra["nearest_resistance"] = row.get("nearest_resistance")
        extra["downside_floored"] = bool(info.get("downside_floored"))
        extra["min_downside_pct"] = info.get("min_downside_pct")
        extra["downside_raw"] = info.get("downside_raw")
        extra["downside"] = info.get("downside")
        return base_points, extra
    if rule_id == "board_weak":
        extra["sector_slope"] = row.get("sector_slope")
        extra["board_change_percent"] = row.get("board_change_percent")
        extra["board_weak_reason"] = row.get("board_weak_reason")
        extra["primary_board_code"] = row.get("primary_board_code")
        extra["primary_board_name"] = row.get("primary_board_name")
        return base_points, extra
    if rule_id != "close_below_ma60":
        return base_points, extra
    half_when_flat = rule.get("half_when_ma60_flat", True)
    ma60_flat = _ma60_is_flat(row, config)
    extra["ma60_flat"] = ma60_flat
    extra["half_when_ma60_flat"] = bool(half_when_flat)
    if row.get("ma60_d_lag") is not None:
        extra["ma60_d_lag"] = row.get("ma60_d_lag")
    if row.get("ma60_flat_change_pct") is not None:
        extra["ma60_flat_change_pct"] = row.get("ma60_flat_change_pct")
    effective = base_points
    if half_when_flat and ma60_flat:
        effective = base_points * 0.5
    return effective, extra


class PenaltyEngine:
    """根据 scoring.penalty_rules 计算总减分与明细。"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config or {}
        scoring = self.config.get("scoring") or {}
        raw_rules = scoring.get("penalty_rules") or []
        self.rules: List[Dict[str, Any]] = []
        if isinstance(raw_rules, list):
            for r in raw_rules:
                if isinstance(r, dict) and r.get("enabled", True):
                    self.rules.append(r)

    def apply(self, row: Dict[str, Any]) -> Tuple[float, List[Dict[str, Any]]]:
        total = 0.0
        details: List[Dict[str, Any]] = []
        for rule in self.rules:
            rid = (rule.get("id") or "").strip()
            if not rid:
                continue
            points = safe_float(rule.get("points"), 0.0)
            if points <= 0:
                continue
            if not _eval_rule(rid, row, self.config, rule=rule):
                continue
            meta = PENALTY_RULE_TYPES.get(rid, {})
            label = rule.get("label") or meta.get("label") or rid
            effective_points, extra = _effective_penalty_points(
                rid, rule, row, self.config, points
            )
            total += effective_points
            detail = {
                "id": rid,
                "label": label,
                "points": effective_points,
                "applied": True,
            }
            detail.update(extra)
            details.append(detail)
        return total, details
