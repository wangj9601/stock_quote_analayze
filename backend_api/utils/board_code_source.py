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
# 管理端新增/导入默认：同花顺；东财同步用 SYNC；存量空值展示用 LEGACY
DEFAULT_BOARD_CODE_SOURCE = "tonghuashun"
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


def merge_board_code_source_on_sync(
    existing: Any,
    incoming: Any = SYNC_BOARD_CODE_SOURCE,
) -> str:
    """东财同步写入用：已有非空来源则保留，禁止把 tonghuashun 等静默改成 eastmoney。

    仅当库中无记录或来源为空时，才写入同步侧来源（默认 eastmoney）。
    """
    kept = normalize_board_code_source(existing)
    if kept:
        return kept
    return resolve_board_code_source(incoming, fallback=SYNC_BOARD_CODE_SOURCE)


def sql_board_code_source_preserve_on_conflict(table_name: str) -> str:
    """ON CONFLICT DO UPDATE 片段：保留已有非空 board_code_source。"""
    return (
        f"board_code_source = COALESCE("
        f"NULLIF(TRIM({table_name}.board_code_source), ''), "
        f"EXCLUDED.board_code_source)"
    )
