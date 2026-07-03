"""
减分规则引擎：在标准分基础上按配置扣分。
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ._helpers import safe_float

PENALTY_RULE_TYPES = {
    "close_below_ma60": {
        "id": "close_below_ma60",
        "label": "收盘低于60日均线",
        "description": "当日收盘价 d₂₀ 低于 60 日均线 ma60_d 时扣分；若 MA60 走平（默认回看 observation_period 个交易日，变化率 < 1.5%）则扣分减半。",
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
        "description": "Δ/d₂₀ 超过配置的 overbought_ratio 阈值时扣分。",
        "default_points": 12,
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


def _eval_rule(rule_id: str, row: Dict[str, Any], config: Dict[str, Any]) -> bool:
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
            if not _eval_rule(rid, row, self.config):
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
