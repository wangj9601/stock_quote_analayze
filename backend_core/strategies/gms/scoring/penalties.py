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
        "description": "当日收盘价 d₂₀ 低于 60 日均线 ma60_d 时扣分。",
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


def _eval_rule(rule_id: str, row: Dict[str, Any]) -> bool:
    if rule_id == "close_below_ma60":
        close = _close_price(row)
        ma60 = row.get("ma60_d")
        if ma60 is None:
            return False
        ma60_f = safe_float(ma60, 0.0)
        if close <= 0 or ma60_f <= 0:
            return False
        return close < ma60_f
    return False


class PenaltyEngine:
    """根据 scoring.penalty_rules 计算总减分与明细。"""

    def __init__(self, config: Dict[str, Any]):
        scoring = config.get("scoring") or {}
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
            if not _eval_rule(rid, row):
                continue
            meta = PENALTY_RULE_TYPES.get(rid, {})
            label = rule.get("label") or meta.get("label") or rid
            total += points
            details.append(
                {
                    "id": rid,
                    "label": label,
                    "points": points,
                    "applied": True,
                }
            )
        return total, details
