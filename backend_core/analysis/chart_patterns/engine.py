# -*- coding: utf-8 -*-
"""统一形态识别入口。"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .double_extremes import detect_double_extremes
from .head_shoulders import detect_head_shoulders
from .pivots import extract_pivot_sequence
from .rules import NMS_BOUND_REL_TOL
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

# 楔/旗重叠对：同向巩固形态易同界误报
_NMS_PAIRS = (
    frozenset({"falling_wedge", "bear_flag"}),
    frozenset({"rising_wedge", "bull_flag"}),
)


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


def _bound_rel_diff(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    try:
        fa, fb = float(a), float(b)
    except (TypeError, ValueError):
        return None
    mid = (abs(fa) + abs(fb)) / 2.0
    if mid <= 1e-12:
        return None
    return abs(fa - fb) / mid


def _pivot_date_span(hit: Dict[str, Any]) -> Tuple[str, str]:
    dates = []
    for p in hit.get("pivots") or []:
        if not isinstance(p, dict):
            continue
        d = str(p.get("date") or "")[:10]
        if d:
            dates.append(d)
    fa = str(hit.get("formed_at") or "")[:10]
    if fa:
        dates.append(fa)
    if not dates:
        return ("", "")
    return (min(dates), max(dates))


def _spans_overlap(a: Tuple[str, str], b: Tuple[str, str]) -> bool:
    """同时间段：日期区间相交，或任一侧缺日期则视为可重叠（仅靠边界判）。"""
    a0, a1 = a
    b0, b1 = b
    if not a0 or not a1 or not b0 or not b1:
        return True
    return not (a1 < b0 or b1 < a0)


def _hit_rank_key(h: Dict[str, Any]) -> Tuple[int, float]:
    """优先已确认，其次置信度。"""
    st = str(h.get("status") or "")
    conf = float(h.get("confidence") or 0)
    if st == "confirmed":
        return (2, conf)
    if st == "forming":
        return (1, conf)
    return (0, conf)


def nms_wedge_flag_overlaps(
    hits: List[Dict[str, Any]],
    *,
    rel_tol: float = NMS_BOUND_REL_TOL,
) -> List[Dict[str, Any]]:
    """下降楔形↔下降旗形、上升楔形↔上升旗形：同界且同时间段只留更优者。"""
    by_type: Dict[str, List[int]] = {}
    for i, h in enumerate(hits):
        if str(h.get("status") or "") == "invalidated":
            continue
        t = str(h.get("pattern_type") or "")
        by_type.setdefault(t, []).append(i)

    drop: Set[int] = set()
    for pair in _NMS_PAIRS:
        types = list(pair)
        a_idxs = by_type.get(types[0], [])
        b_idxs = by_type.get(types[1], [])
        for ia in a_idxs:
            if ia in drop:
                continue
            ha = hits[ia]
            la = (ha.get("key_levels") or {})
            span_a = _pivot_date_span(ha)
            for ib in b_idxs:
                if ib in drop:
                    continue
                hb = hits[ib]
                lb = (hb.get("key_levels") or {})
                if not _spans_overlap(span_a, _pivot_date_span(hb)):
                    continue
                du = _bound_rel_diff(la.get("upper"), lb.get("upper"))
                dl = _bound_rel_diff(la.get("lower"), lb.get("lower"))
                if du is None or dl is None:
                    continue
                if du > rel_tol or dl > rel_tol:
                    continue
                # 同界：保留 rank 更高者
                if _hit_rank_key(ha) >= _hit_rank_key(hb):
                    drop.add(ib)
                else:
                    drop.add(ia)
                    break
    return [h for i, h in enumerate(hits) if i not in drop]


def detect_all(
    bars: Sequence[Dict[str, Any]],
    *,
    types: Optional[Iterable[str]] = None,
    pattern_cfg: Optional[Dict[str, Any]] = None,
    include_invalidated: bool = False,
) -> List[Dict[str, Any]]:
    """对升序日线 bars 跑所选形态族，返回标准化 hit 列表。

    默认不返回 status=invalidated（失效）项；传 include_invalidated=True 可保留。
    后处理：楔/旗同界 NMS。
    """
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

    hits = nms_wedge_flag_overlaps(hits)
    if not include_invalidated:
        hits = [h for h in hits if str(h.get("status") or "") != "invalidated"]
    hits.sort(key=lambda h: (-float(h.get("confidence") or 0), str(h.get("pattern_type") or "")))
    return hits
