# -*- coding: utf-8 -*-
"""统一形态识别入口。"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .cup_handle import detect_cup_with_handle
from .double_extremes import detect_double_extremes
from .head_shoulders import detect_head_shoulders
from .lifecycle import apply_pattern_lifecycle
from .pivots import extract_pivot_sequence
from .rules import NMS_BOUND_REL_TOL
from .triangles import detect_triangles
from .wedges_flags import detect_wedges_flags

PATTERN_FAMILIES = (
    "double_extremes",
    "head_shoulders",
    "triangle",
    "wedge_flag",
    "cup_handle",
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
    "cup": "cup_handle",
    "cup_handle": "cup_handle",
    "cup_with_handle": "cup_handle",
}

# 同源重叠对：同向巩固形态易同界/同枢轴误报双出
_NMS_PAIRS = (
    frozenset({"falling_wedge", "bear_flag"}),
    frozenset({"rising_wedge", "bull_flag"}),
    # 几何互斥：收敛楔形 vs 反向旗形（同界时不应并存）
    frozenset({"falling_wedge", "bull_flag"}),
    frozenset({"rising_wedge", "bear_flag"}),
    frozenset({"descending_triangle", "falling_wedge"}),
    frozenset({"ascending_triangle", "rising_wedge"}),
)

# 三角↔楔形：用斜率几何定主分类（而非纯置信度）
_TRIANGLE_WEDGE_PAIRS = frozenset(
    {
        frozenset({"descending_triangle", "falling_wedge"}),
        frozenset({"ascending_triangle", "rising_wedge"}),
    }
)

# 楔形↔反向旗形：同源时优先保留楔形（旗形为简化启发式）
_WEDGE_OPPOSITE_FLAG_PAIRS = frozenset(
    {
        frozenset({"falling_wedge", "bull_flag"}),
        frozenset({"rising_wedge", "bear_flag"}),
    }
)

_PATTERN_LABEL_ZH = {
    "descending_triangle": "下降三角",
    "ascending_triangle": "上升三角",
    "symmetrical_triangle": "对称三角",
    "falling_wedge": "下降楔形",
    "rising_wedge": "上升楔形",
    "bear_flag": "下降旗形",
    "bull_flag": "上升旗形",
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


_MIX_INACTIVE = frozenset({"invalidated", "archived"})
_DOUBLE_MIX_NOTE = "与反向双顶/双底同窗交织，置信已降权"
_DOUBLE_MIX_CONF_CAP = 0.45
_SHARED_PIVOT_REL = 0.005  # 共用枢轴相对差 <0.5%


def _mix_f(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x != x:
        return None
    return x


def _mix_neck(hit: Dict[str, Any]) -> Optional[float]:
    lv = hit.get("key_levels") if isinstance(hit.get("key_levels"), dict) else {}
    return _mix_f(lv.get("neckline"))


def _shared_pivot_reuse(top: Dict[str, Any], bottom: Dict[str, Any]) -> bool:
    """双底颈≈双顶 H1/H2，或双顶颈≈双底 L1/L2（相对差 <0.5%）。"""
    lv_t = top.get("key_levels") if isinstance(top.get("key_levels"), dict) else {}
    lv_b = bottom.get("key_levels") if isinstance(bottom.get("key_levels"), dict) else {}
    n_b = _mix_f(lv_b.get("neckline"))
    for k in ("h1", "h2"):
        hx = _mix_f(lv_t.get(k))
        if n_b is not None and hx is not None and hx > 0:
            if abs(n_b - hx) / hx < _SHARED_PIVOT_REL:
                return True
    n_t = _mix_f(lv_t.get("neckline"))
    for k in ("l1", "l2"):
        lx = _mix_f(lv_b.get(k))
        if n_t is not None and lx is not None and max(abs(n_t), abs(lx)) > 0:
            ref = max(abs(n_t), abs(lx))
            if abs(n_t - lx) / ref < _SHARED_PIVOT_REL:
                return True
    return False


def _compute_range_box(
    top: Dict[str, Any], bottom: Dict[str, Any]
) -> Tuple[Optional[float], Optional[float]]:
    """箱体：min/max(两颈线)；缺颈线则用 key_levels 合理兜底。"""
    n_t = _mix_neck(top)
    n_b = _mix_neck(bottom)
    if n_t is not None and n_b is not None:
        return min(n_t, n_b), max(n_t, n_b)
    lows: List[float] = []
    highs: List[float] = []
    for h, side in ((top, "top"), (bottom, "bottom")):
        lv = h.get("key_levels") if isinstance(h.get("key_levels"), dict) else {}
        neck = _mix_f(lv.get("neckline"))
        if side == "top":
            for k in ("h1", "h2", "upper", "neckline"):
                v = _mix_f(lv.get(k))
                if v is not None:
                    highs.append(v)
            if neck is not None:
                lows.append(neck)
        else:
            for k in ("l1", "l2", "lower", "neckline"):
                v = _mix_f(lv.get(k))
                if v is not None:
                    lows.append(v)
            if neck is not None:
                highs.append(neck)
    if not lows or not highs:
        # 最后兜底：两边全部价位
        all_px: List[float] = []
        for h in (top, bottom):
            lv = h.get("key_levels") if isinstance(h.get("key_levels"), dict) else {}
            for v in lv.values():
                fv = _mix_f(v)
                if fv is not None and fv > 0:
                    all_px.append(fv)
        if len(all_px) < 2:
            return None, None
        return min(all_px), max(all_px)
    return min(lows), max(highs)


def _mark_double_mix(
    hit: Dict[str, Any],
    *,
    box_low: Optional[float] = None,
    box_high: Optional[float] = None,
    shared_pivot: bool = False,
) -> None:
    """同窗双顶+双底交织：降权、bias_mix，并写入箱体震荡上下沿。"""
    conf = float(hit.get("confidence") or 0.0)
    hit["confidence"] = round(min(conf, _DOUBLE_MIX_CONF_CAP), 3)
    reason = str(hit.get("reason") or "").strip()
    bits: List[str] = []
    if _DOUBLE_MIX_NOTE not in reason:
        bits.append(_DOUBLE_MIX_NOTE)
    if box_low is not None and box_high is not None:
        box_note = (
            f"同窗多空互斥，合并观察为箱体震荡[{box_low:.2f}–{box_high:.2f}]"
        )
        if box_note not in reason:
            bits.append(box_note)
        if shared_pivot and "同枢轴复用" not in reason:
            bits.append("同枢轴复用")
    if bits:
        hit["reason"] = f"{reason}；{'；'.join(bits)}" if reason else "；".join(bits)
    lv = hit.get("key_levels") if isinstance(hit.get("key_levels"), dict) else {}
    lv = dict(lv)
    lv["bias_mix"] = True
    if box_low is not None and box_high is not None:
        lv["box_low"] = round(float(box_low), 4)
        lv["box_high"] = round(float(box_high), 4)
        lv["range_label"] = "箱体震荡"
        lv["range_box"] = True
        hit["range_box"] = True
        hit["box_low"] = lv["box_low"]
        hit["box_high"] = lv["box_high"]
    hit["key_levels"] = lv
    extra = hit.get("extra") if isinstance(hit.get("extra"), dict) else {}
    # make_hit 常把 extra 摊到顶层；同时写顶层与 extra 便于下游读取
    hit["bias_mix"] = True
    if extra:
        extra = dict(extra)
        extra["bias_mix"] = True
        if box_low is not None and box_high is not None:
            extra["range_box"] = True
            extra["box_low"] = lv.get("box_low")
            extra["box_high"] = lv.get("box_high")
        hit["extra"] = extra


def annotate_double_extremes_mix(hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """同窗活跃双顶+双底：强制交织降权（cap confidence），合并箱体震荡，供 tactical bias_mix。"""
    if not hits:
        return hits
    tops: List[Dict[str, Any]] = []
    bottoms: List[Dict[str, Any]] = []
    for h in hits:
        st = str(h.get("status") or "")
        if st in _MIX_INACTIVE:
            continue
        pt = str(h.get("pattern_type") or "")
        if pt == "double_top":
            tops.append(h)
        elif pt == "double_bottom":
            bottoms.append(h)
    if not tops or not bottoms:
        return hits
    touched: Set[int] = set()
    for t in tops:
        ts = _pivot_date_span(t)
        for b in bottoms:
            if not _spans_overlap(ts, _pivot_date_span(b)):
                continue
            box_low, box_high = _compute_range_box(t, b)
            shared = _shared_pivot_reuse(t, b)
            for h in (t, b):
                hid = id(h)
                if hid in touched:
                    continue
                touched.add(hid)
                _mark_double_mix(
                    h, box_low=box_low, box_high=box_high, shared_pivot=shared
                )
    return hits


def _hit_status_tier(h: Dict[str, Any]) -> int:
    st = str(h.get("status") or "")
    if st == "confirmed":
        return 2
    if st == "forming":
        return 1
    return 0


def _hit_rank_key(h: Dict[str, Any]) -> Tuple[int, float]:
    """优先已确认，其次置信度。"""
    return (_hit_status_tier(h), float(h.get("confidence") or 0))


def _merged_slopes(
    ha: Dict[str, Any], hb: Dict[str, Any]
) -> Tuple[Optional[float], Optional[float], float]:
    """取上下沿斜率与价格参考（用于走平阈值）。"""
    la = ha.get("key_levels") or {}
    lb = hb.get("key_levels") or {}
    us = la.get("upper_slope")
    if us is None:
        us = lb.get("upper_slope")
    ls = la.get("lower_slope")
    if ls is None:
        ls = lb.get("lower_slope")
    ref = (
        la.get("upper")
        or la.get("lower")
        or lb.get("upper")
        or lb.get("lower")
        or 1.0
    )
    try:
        us_f = float(us) if us is not None else None
    except (TypeError, ValueError):
        us_f = None
    try:
        ls_f = float(ls) if ls is not None else None
    except (TypeError, ValueError):
        ls_f = None
    try:
        ref_f = abs(float(ref))
    except (TypeError, ValueError):
        ref_f = 1.0
    if ref_f <= 1e-12:
        ref_f = 1.0
    return us_f, ls_f, ref_f


def _geom_preferred_type(ha: Dict[str, Any], hb: Dict[str, Any]) -> Optional[str]:
    """三角↔楔形：按下/上沿是否近似走平定主分类；无法判断则 None。"""
    ta = str(ha.get("pattern_type") or "")
    tb = str(hb.get("pattern_type") or "")
    pair = frozenset({ta, tb})
    if pair not in _TRIANGLE_WEDGE_PAIRS:
        return None
    us, ls, ref = _merged_slopes(ha, hb)
    if us is None or ls is None:
        return None
    # 与 triangles.detect_triangles 同量级：价格 × 0.0008 作为斜率「走平」阈值
    flat_thr = max(ref * 0.0008, 1e-9)
    if pair == frozenset({"descending_triangle", "falling_wedge"}):
        # 下沿近似走平 + 上沿下行 → 下降三角；双沿明确下行 → 下降楔形
        if abs(ls) < flat_thr and us < -flat_thr:
            return "descending_triangle"
        if us < -flat_thr and ls < -flat_thr:
            return "falling_wedge"
        return None
    if pair == frozenset({"ascending_triangle", "rising_wedge"}):
        if abs(us) < flat_thr and ls > flat_thr:
            return "ascending_triangle"
        if us > flat_thr and ls > flat_thr:
            return "rising_wedge"
        return None
    return None


def _pattern_label_zh(pattern_type: str) -> str:
    t = str(pattern_type or "")
    return _PATTERN_LABEL_ZH.get(t, t or "未知形态")


def _annotate_nms_suppressed(keeper: Dict[str, Any], dropped: Dict[str, Any]) -> None:
    """在保留项 reason / nms_suppressed 中记录被抑制的同源形态。"""
    label = _pattern_label_zh(str(dropped.get("pattern_type") or ""))
    note = f"同源亦曾匹配{label}"
    reason = str(keeper.get("reason") or "").strip()
    if note not in reason:
        keeper["reason"] = f"{reason}；{note}" if reason else note
    suppressed = list(keeper.get("nms_suppressed") or [])
    suppressed.append(
        {
            "pattern_type": dropped.get("pattern_type"),
            "confidence": dropped.get("confidence"),
            "status": dropped.get("status"),
            "label": label,
        }
    )
    keeper["nms_suppressed"] = suppressed


def _pick_nms_winner(
    ha: Dict[str, Any],
    hb: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """选出保留项与丢弃项：状态优先 → 三角/楔斜率几何 → 楔优先于反向旗 → 置信度。"""
    sa, sb = _hit_status_tier(ha), _hit_status_tier(hb)
    if sa != sb:
        return (ha, hb) if sa > sb else (hb, ha)
    pref = _geom_preferred_type(ha, hb)
    if pref:
        ta = str(ha.get("pattern_type") or "")
        tb = str(hb.get("pattern_type") or "")
        if pref == ta and pref != tb:
            return ha, hb
        if pref == tb and pref != ta:
            return hb, ha
    ta = str(ha.get("pattern_type") or "")
    tb = str(hb.get("pattern_type") or "")
    pair = frozenset({ta, tb})
    if pair in _WEDGE_OPPOSITE_FLAG_PAIRS:
        if ta in ("falling_wedge", "rising_wedge") and tb not in (
            "falling_wedge",
            "rising_wedge",
        ):
            return ha, hb
        if tb in ("falling_wedge", "rising_wedge") and ta not in (
            "falling_wedge",
            "rising_wedge",
        ):
            return hb, ha
    if _hit_rank_key(ha) >= _hit_rank_key(hb):
        return ha, hb
    return hb, ha


def _role_pivot_series(
    hit: Dict[str, Any], role: str
) -> List[Tuple[str, float]]:
    out: List[Tuple[str, float]] = []
    for p in hit.get("pivots") or []:
        if not isinstance(p, dict):
            continue
        if str(p.get("role") or "") != role:
            continue
        try:
            px = float(p.get("price"))
        except (TypeError, ValueError):
            continue
        if px != px:
            continue
        out.append((str(p.get("date") or "")[:10], px))
    return out


def _pivot_series_homologous(
    a: List[Tuple[str, float]],
    b: List[Tuple[str, float]],
    *,
    rel_tol: float,
) -> bool:
    """同角色枢轴条数一致且按日期排序后价位相对差均 ≤ rel_tol（日期均有则须相同）。"""
    if len(a) < 2 or len(b) < 2 or len(a) != len(b):
        return False
    sa, sb = sorted(a), sorted(b)
    for (da, pa), (db, pb) in zip(sa, sb):
        if da and db and da != db:
            return False
        d = _bound_rel_diff(pa, pb)
        if d is None or d > rel_tol:
            return False
    return True


def _hits_homologous(
    ha: Dict[str, Any],
    hb: Dict[str, Any],
    *,
    rel_tol: float,
) -> bool:
    """同时间段且（上下沿同界 或 高/低枢轴序列同源）视为同一结构误报双出。"""
    if not _spans_overlap(_pivot_date_span(ha), _pivot_date_span(hb)):
        return False
    la = ha.get("key_levels") or {}
    lb = hb.get("key_levels") or {}
    du = _bound_rel_diff(la.get("upper"), lb.get("upper"))
    dl = _bound_rel_diff(la.get("lower"), lb.get("lower"))
    if du is not None and dl is not None and du <= rel_tol and dl <= rel_tol:
        return True
    return _pivot_series_homologous(
        _role_pivot_series(ha, "high"),
        _role_pivot_series(hb, "high"),
        rel_tol=rel_tol,
    ) and _pivot_series_homologous(
        _role_pivot_series(ha, "low"),
        _role_pivot_series(hb, "low"),
        rel_tol=rel_tol,
    )


def nms_overlapping_patterns(
    hits: List[Dict[str, Any]],
    *,
    rel_tol: float = NMS_BOUND_REL_TOL,
) -> List[Dict[str, Any]]:
    """巩固形态 NMS：同源重叠对只保留一条，并在 reason 注明被抑制项。

    覆盖：下降楔↔下降旗、上升楔↔上升旗、下降楔↔上升旗、上升楔↔下降旗、
    下降三角↔下降楔、上升三角↔上升楔。
    选取：已确认优先；三角/楔再按斜率几何；楔形优先于反向简化旗形；否则高置信。
    同源判定：上下沿相对差均 ≤ rel_tol，或高/低枢轴价位序列同源；且日期区间重叠。
    """
    by_type: Dict[str, List[int]] = {}
    for i, h in enumerate(hits):
        if str(h.get("status") or "") in ("invalidated", "archived"):
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
            for ib in b_idxs:
                if ib in drop or ia in drop:
                    continue
                ha = hits[ia]
                hb = hits[ib]
                if not _hits_homologous(ha, hb, rel_tol=rel_tol):
                    continue
                keeper, dropped = _pick_nms_winner(ha, hb)
                if keeper is ha:
                    drop.add(ib)
                    _annotate_nms_suppressed(ha, hb)
                else:
                    drop.add(ia)
                    _annotate_nms_suppressed(hb, ha)
                    break
    return [h for i, h in enumerate(hits) if i not in drop]


def nms_wedge_flag_overlaps(
    hits: List[Dict[str, Any]],
    *,
    rel_tol: float = NMS_BOUND_REL_TOL,
) -> List[Dict[str, Any]]:
    """兼容旧名：同 nms_overlapping_patterns。"""
    return nms_overlapping_patterns(hits, rel_tol=rel_tol)


def detect_all_counted(
    bars: Sequence[Dict[str, Any]],
    *,
    types: Optional[Iterable[str]] = None,
    pattern_cfg: Optional[Dict[str, Any]] = None,
    include_invalidated: bool = False,
    ref_bars: Optional[Sequence[Dict[str, Any]]] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """对升序日线 bars 跑所选形态族，返回 (hit 列表, 过滤前 invalidated 条数)。

    默认不返回 status=invalidated（失效）项；传 include_invalidated=True 可保留。
    invalidated_count 始终为过滤前的失效条数（便于 API 提示「另有 N 条已失效」）。
    后处理：反转形态生命周期归档 → 巩固形态同源 NMS → 同窗双顶双底交织降权。
    """
    seq = [b for b in (bars or []) if isinstance(b, dict)]
    if len(seq) < 30:
        return [], 0
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
    if "cup_handle" in families:
        hits.extend(
            detect_cup_with_handle(
                seq,
                pivots,
                pattern_cfg=pattern_cfg,
                ref_bars=ref_bars,
            )
        )

    hits = apply_pattern_lifecycle(hits, seq)
    hits = nms_overlapping_patterns(hits)
    hits = annotate_double_extremes_mix(hits)
    invalidated_count = sum(
        1 for h in hits if str(h.get("status") or "") == "invalidated"
    )
    if not include_invalidated:
        hits = [h for h in hits if str(h.get("status") or "") != "invalidated"]
    hits.sort(
        key=lambda h: (
            -float(h.get("confidence") or 0),
            str(h.get("pattern_type") or ""),
        )
    )
    return hits, invalidated_count


def detect_all(
    bars: Sequence[Dict[str, Any]],
    *,
    types: Optional[Iterable[str]] = None,
    pattern_cfg: Optional[Dict[str, Any]] = None,
    include_invalidated: bool = False,
    ref_bars: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """对升序日线 bars 跑所选形态族，返回标准化 hit 列表。

    默认不返回 status=invalidated（失效）项；传 include_invalidated=True 可保留。
    后处理：反转形态生命周期归档 → 巩固形态同源 NMS。
    若需失效计数，请用 detect_all_counted。
    """
    hits, _ = detect_all_counted(
        bars,
        types=types,
        pattern_cfg=pattern_cfg,
        include_invalidated=include_invalidated,
        ref_bars=ref_bars,
    )
    return hits
