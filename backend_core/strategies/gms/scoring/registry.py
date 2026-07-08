"""
GMS 打分机制注册表与配置校验。
"""

from __future__ import annotations

from typing import Any, Dict, List, Type

from .penalties import list_penalty_rule_type_meta
from .tiered_dual_max import TieredDualMaxScorer
from .tiered_dual_penalty import TieredDualPenaltyScorer

DEFAULT_MECHANISM = "tiered_dual_max"

MECHANISM_META: Dict[str, Dict[str, Any]] = {
    "tiered_dual_max": {
        "id": "tiered_dual_max",
        "label": "标准版·双模块阶梯",
        "description": "均值收敛态与动量溢出态独立阶梯评分，综合分取两者较高者。与现网默认行为一致。",
        "version": "1.0",
        "supports_penalties": False,
    },
    "tiered_dual_penalty": {
        "id": "tiered_dual_penalty",
        "label": "增强版·阶梯+减分",
        "description": "在标准版基础分上，按配置规则扣分（如收盘低于 MA60 减分），最终分限制在 0~100。",
        "version": "1.0",
        "supports_penalties": True,
    },
}

_MECHANISM_CLASSES: Dict[str, Type] = {
    "tiered_dual_max": TieredDualMaxScorer,
    "tiered_dual_penalty": TieredDualPenaltyScorer,
}


def list_mechanisms() -> List[Dict[str, Any]]:
    return list(MECHANISM_META.values())


def get_mechanism_meta(mechanism_id: str) -> Dict[str, Any]:
    mid = (mechanism_id or DEFAULT_MECHANISM).strip()
    if mid not in MECHANISM_META:
        raise ValueError(f"未知打分机制: {mechanism_id}")
    return MECHANISM_META[mid]


def list_penalty_rule_types() -> List[Dict[str, Any]]:
    return list_penalty_rule_type_meta()


def get_mechanism(mechanism_id: str):
    mid = (mechanism_id or DEFAULT_MECHANISM).strip()
    cls = _MECHANISM_CLASSES.get(mid)
    if cls is None:
        raise ValueError(f"未知打分机制: {mechanism_id}")
    return cls


def validate_scoring_config(scoring: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not isinstance(scoring, dict):
        return ["scoring 必须为对象"]
    mechanism = (scoring.get("mechanism") or DEFAULT_MECHANISM).strip()
    if mechanism not in MECHANISM_META:
        errors.append(f"不支持的 scoring.mechanism: {mechanism}")
        return errors
    rules = scoring.get("penalty_rules") or []
    if mechanism == "tiered_dual_max":
        if isinstance(rules, list) and len(rules) > 0:
            enabled = [r for r in rules if isinstance(r, dict) and r.get("enabled", True)]
            if enabled:
                errors.append("标准版 tiered_dual_max 不允许配置启用的减分规则")
    elif mechanism == "tiered_dual_penalty":
        if not isinstance(rules, list):
            errors.append("增强版 penalty_rules 必须为数组")
        else:
            enabled = [r for r in rules if isinstance(r, dict) and r.get("enabled", True)]
            if not enabled:
                errors.append("增强版至少需一条启用的减分规则")
            for r in enabled:
                rid = (r.get("id") or "").strip()
                from .penalties import PENALTY_RULE_TYPES

                if rid not in PENALTY_RULE_TYPES:
                    errors.append(f"未知减分规则 id: {rid}")
                    continue
                pts = r.get("points")
                try:
                    p = float(pts)
                    if p <= 0 or p > 100:
                        errors.append(f"减分规则 {rid} 的 points 须在 (0, 100]")
                except (TypeError, ValueError):
                    errors.append(f"减分规则 {rid} 的 points 无效")
                if rid == "observation_range_amplitude":
                    th = r.get("amplitude_threshold_pct")
                    if th is not None:
                        try:
                            t = float(th)
                            if t <= 0 or t > 2.0:
                                errors.append(
                                    f"减分规则 {rid} 的 amplitude_threshold_pct 须在 (0, 2.0] 范围内"
                                )
                        except (TypeError, ValueError):
                            errors.append(f"减分规则 {rid} 的 amplitude_threshold_pct 无效")
        lookback = scoring.get("ma60_flat_lookback_days")
        if lookback is not None:
            try:
                lb = int(lookback)
                if lb < 1:
                    errors.append("ma60_flat_lookback_days 须 >= 1")
            except (TypeError, ValueError):
                errors.append("ma60_flat_lookback_days 无效")
        tol = scoring.get("ma60_flat_tol")
        if tol is not None:
            try:
                t = float(tol)
                if t <= 0 or t > 0.1:
                    errors.append("ma60_flat_tol 须在 (0, 0.1] 范围内")
            except (TypeError, ValueError):
                errors.append("ma60_flat_tol 无效")
    return errors


def normalize_scoring_defaults(scoring: Dict[str, Any]) -> Dict[str, Any]:
    """补全 mechanism / penalty_rules 默认值。"""
    out = dict(scoring or {})
    if not out.get("mechanism"):
        out["mechanism"] = DEFAULT_MECHANISM
    if out.get("penalty_rules") is None:
        out["penalty_rules"] = []
    if out.get("ma60_flat_tol") is None:
        out["ma60_flat_tol"] = 0.015
    return out
