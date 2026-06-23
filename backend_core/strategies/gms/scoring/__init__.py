"""GMS 打分机制注册表。"""

from .registry import (
    DEFAULT_MECHANISM,
    get_mechanism,
    get_mechanism_meta,
    list_mechanisms,
    list_penalty_rule_types,
    normalize_scoring_defaults,
    validate_scoring_config,
)

__all__ = [
    "DEFAULT_MECHANISM",
    "get_mechanism",
    "get_mechanism_meta",
    "list_mechanisms",
    "list_penalty_rule_types",
    "normalize_scoring_defaults",
    "validate_scoring_config",
]
