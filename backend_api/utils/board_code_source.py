"""板块代码来源枚举与校验。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

BOARD_CODE_SOURCE_OPTIONS: List[Dict[str, str]] = [
    {"value": "eastmoney", "label": "东方财富"},
    {"value": "tonghuashun", "label": "同花顺"},
    {"value": "huatai", "label": "华泰"},
    {"value": "manual", "label": "手动维护"},
    {"value": "other", "label": "其他"},
]

BOARD_CODE_SOURCE_VALUES = {o["value"] for o in BOARD_CODE_SOURCE_OPTIONS}
DEFAULT_BOARD_CODE_SOURCE = "manual"
SYNC_BOARD_CODE_SOURCE = "eastmoney"
LEGACY_DEFAULT_BOARD_CODE_SOURCE = "eastmoney"


def normalize_board_code_source(raw: Any) -> Optional[str]:
    s = str(raw or "").strip().lower()
    if not s:
        return None
    if s in BOARD_CODE_SOURCE_VALUES:
        return s
    alias = {
        "东财": "eastmoney",
        "东方财富": "eastmoney",
        "同花顺": "tonghuashun",
        "ths": "tonghuashun",
        "华泰": "huatai",
        "手动": "manual",
    }
    return alias.get(s)


def board_code_source_label(value: Optional[str]) -> str:
    v = normalize_board_code_source(value) or LEGACY_DEFAULT_BOARD_CODE_SOURCE
    for opt in BOARD_CODE_SOURCE_OPTIONS:
        if opt["value"] == v:
            return opt["label"]
    return v


def resolve_board_code_source(raw: Any, *, fallback: str = LEGACY_DEFAULT_BOARD_CODE_SOURCE) -> str:
    return normalize_board_code_source(raw) or fallback
