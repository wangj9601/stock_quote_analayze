# -*- coding: utf-8 -*-
"""统一形态识别入口。"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from .double_extremes import detect_double_extremes
from .head_shoulders import detect_head_shoulders
from .pivots import extract_pivot_sequence
from .triangles import detect_triangles
from .wedges_flags import detect_wedges_flags

PATTERN_FAMILIES = (
    "double_extremes",
    "head_shoulders",
    "triangle",
    "wedge_flag",
)

FAMILY_ALIASES = {
    "double": "double_extremes",
    "double_extremes": "double_extremes",
    "double_top": "double_extremes",
    "double_bottom": "double_extremes",
    "hs": "head_shoulders",
    "head_shoulders": "head_shoulders",
    "triangle": "triangle",
    "triangles": "triangle",
    "wedge": "wedge_flag",
    "flag": "wedge_flag",
    "wedge_flag": "wedge_flag",
}


def normalize_families(types: Optional[Iterable[str]]) -> Set[str]:
    if not types:
        return set(PATTERN_FAMILIES)
    out: Set[str] = set()
    for t in types:
        key = str(t or "").strip().lower()
        if not key or key in ("all", "*"):
            return set(PATTERN_FAMILIES)
        fam = FAMILY_ALIASES.get(key, key)
        if fam in PATTERN_FAMILIES:
            out.add(fam)
    return out or set(PATTERN_FAMILIES)


def detect_all(
    bars: Sequence[Dict[str, Any]],
    *,
    types: Optional[Iterable[str]] = None,
    pattern_cfg: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """对升序日线 bars 跑所选形态族，返回标准化 hit 列表。"""
    seq = [b for b in (bars or []) if isinstance(b, dict)]
    if len(seq) < 30:
        return []
    families = normalize_families(types)
    pivots = extract_pivot_sequence(seq)
    hits: List[Dict[str, Any]] = []
    if "double_extremes" in families:
        hits.extend(detect_double_extremes(seq, pattern_cfg=pattern_cfg))
    if "head_shoulders" in families:
        hits.extend(detect_head_shoulders(seq, pivots))
    if "triangle" in families:
        hits.extend(detect_triangles(seq, pivots))
    if "wedge_flag" in families:
        hits.extend(detect_wedges_flags(seq, pivots))
    hits.sort(key=lambda h: (-float(h.get("confidence") or 0), str(h.get("pattern_type") or "")))
    return hits
