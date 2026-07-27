"""A 股上市板别解析（RPE 流动性分层用）。"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

# 与 VSB / cn_listed_board_filter 前缀分组对齐，避免循环依赖而本地维护一份。
_BOARD_PREFIX_GROUPS: Dict[str, Tuple[str, ...]] = {
    "KCB": ("688",),
    "CYB": ("300",),
    "SZ_SME": ("002",),
    "BJ": ("43", "83", "87", "88", "92"),
    "MAIN": ("600", "601", "602", "603", "605", "000", "001"),
}

_BOARD_LABELS: Dict[str, str] = {
    "MAIN": "主板",
    "SZ_SME": "中小板",
    "CYB": "创业板",
    "KCB": "科创板",
    "BJ": "北证",
    "DEFAULT": "默认",
}

_MATCH_ORDER = ("KCB", "CYB", "SZ_SME", "BJ", "MAIN")


def normalize_cn_code(code: object) -> str:
    s = str(code or "").strip()
    if len(s) == 5 and s.isdigit():
        s = s.zfill(6)
    return s


def resolve_listed_board_segment(code: object) -> str:
    """
    解析上市分档键：KCB / CYB / SZ_SME / BJ / MAIN / DEFAULT。
    匹配顺序：科创 → 创业 → 中小 → 北证 → 主板 → 兜底。
    """
    c = normalize_cn_code(code)
    if len(c) != 6 or not c.isdigit():
        return "DEFAULT"
    for key in _MATCH_ORDER:
        for p in _BOARD_PREFIX_GROUPS.get(key, ()):
            if c.startswith(p):
                return key
    return "DEFAULT"


def board_segment_label(segment: str) -> str:
    return _BOARD_LABELS.get(str(segment or "").upper(), str(segment or "默认"))


def resolve_min_avg_amount(
    code: object,
    liq_cfg: Optional[Dict[str, Any]] = None,
) -> Tuple[str, float]:
    """
    按板别取均额门槛（元）。
    无 by_board 配置时回退 min_avg_amount；再无则 500 万。
    """
    cfg = liq_cfg or {}
    segment = resolve_listed_board_segment(code)
    fallback = float(cfg.get("min_avg_amount", 5_000_000) or 5_000_000)
    by_board = cfg.get("min_avg_amount_by_board")
    if not isinstance(by_board, dict) or not by_board:
        return segment, fallback
    raw = by_board.get(segment)
    if raw is None:
        raw = by_board.get("DEFAULT")
    if raw is None:
        return segment, fallback
    try:
        return segment, float(raw)
    except (TypeError, ValueError):
        return segment, fallback
