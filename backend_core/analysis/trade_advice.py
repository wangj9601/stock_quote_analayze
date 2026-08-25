# -*- coding: utf-8 -*-
"""策略命中行 → 统一买卖建议（主依据策略+KDE/箱体；Fib/Pivot/共振带仅软参考）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

ALIGN_TOL_PCT = 0.015
# URT 买点建议：承接区最小相对宽度；止损相对支撑缓冲
URT_ENTRY_MIN_WIDTH_PCT = 0.03  # 至少约 3%，避免 7.71–7.74 这类不可执行窄带
URT_STOP_BUFFER_PCT = 0.02  # 止损参考 = 锚点 × (1 - 2%)，含噪声缓冲
# 与个股分析形态买点一致：止损/失效须严格低于可执行买入下沿
URT_ENTRY_ABOVE_STOP_PCT = 0.005  # 买入下沿至少高于止损约 0.5%
URT_NEAR_SUPPORT_BAND_PCT = 0.01  # 短线可执行区：支撑下方约 1%～支撑（仍须高于止损）
# 与 URT 结构回测一致：现价距第一支撑过近时，入场参考第二档
STRUCTURE_ENTRY_NEAR_SUPPORT_PCT = 0.03
STRUCTURE_EXIT_TARGET_PCT = 0.10
STRUCTURE_EXIT_MIN_UPSIDE_PCT = 0.05


def _position_advice_text(pa: Any) -> Optional[str]:
    """仓位建议转为可读文案；避免把 dict 整段 str() 进摘要。"""
    if not pa:
        return None
    if isinstance(pa, dict):
        msg = str(pa.get("message") or "").strip()
        return msg or None
    text = str(pa).strip()
    if not text:
        return None
    # 已序列化的 dict/json 不进摘要
    if text.startswith("{") or text.startswith("["):
        return None
    return text


def _f(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _zone(
    *,
    low: Optional[float] = None,
    high: Optional[float] = None,
    price: Optional[float] = None,
    label: str,
    basis: str,
) -> Dict[str, Any]:
    z: Dict[str, Any] = {"label": label, "basis": basis}
    if price is not None:
        z["price"] = round(float(price), 4)
    if low is not None:
        z["low"] = round(float(low), 4)
    if high is not None:
        z["high"] = round(float(high), 4)
    return z


def _kde_support(row: Dict[str, Any]) -> Optional[float]:
    ns = _f(row.get("nearest_support"))
    if ns is not None:
        return ns
    st = row.get("structure") if isinstance(row.get("structure"), dict) else {}
    return _f(st.get("nearest_support"))


def _kde_resistance(row: Dict[str, Any]) -> Optional[float]:
    nr = _f(row.get("nearest_resistance"))
    if nr is not None:
        return nr
    st = row.get("structure") if isinstance(row.get("structure"), dict) else {}
    return _f(st.get("nearest_resistance"))


def _structure_level_pool(
    row: Optional[Dict[str, Any]],
    ref: Optional[Dict[str, Any]],
    side: str,
) -> List[Any]:
    """合并策略行与 reference_levels 中的支撑/阻力档位列表。"""
    key = "support_levels" if side == "support" else "resistance_levels"
    pool: List[Any] = []
    seen: set = set()

    def _add(vals: Any) -> None:
        for x in vals or []:
            raw = x.get("center") if isinstance(x, dict) else x
            if raw is None and isinstance(x, dict):
                raw = x.get("price")
            v = _f(raw)
            if v is None:
                continue
            k = round(v, 4)
            if k in seen:
                continue
            seen.add(k)
            pool.append(k)

    for src in (row, ref):
        if not isinstance(src, dict):
            continue
        _add(src.get(key))
        st = src.get("structure")
        if isinstance(st, dict):
            _add(st.get(key))
    nearest = _kde_support(row) if side == "support" else _kde_resistance(row)
    if nearest is None and isinstance(ref, dict):
        nearest = _f(ref.get("nearest_support" if side == "support" else "nearest_resistance"))
    if nearest is not None:
        k = round(float(nearest), 4)
        if k not in seen:
            pool.append(k)
    if side == "support":
        pool.sort(reverse=True)
    else:
        pool.sort()
    return pool


def _pick_entry_structure_support(
    price: Optional[float],
    nearest_support: Optional[float],
    level_pool: List[Any],
    *,
    near_pct: float = STRUCTURE_ENTRY_NEAR_SUPPORT_PCT,
) -> tuple[Optional[float], int, Optional[float]]:
    """距第一支撑过近时退回第二档（与 URT structure_rr 第二档口径一致）。"""
    if nearest_support is None:
        return None, 1, None
    ns = float(nearest_support)
    if price is None or price <= 0:
        return ns, 1, None
    px = float(price)
    if px <= ns:
        return ns, 1, 0.0
    dist = (px - ns) / px
    if dist > float(near_pct):
        return ns, 1, dist
    try:
        from backend_core.strategies.gms.structure_levels import pick_nth_level

        s2 = pick_nth_level(level_pool, px, side="support", n=2)
    except Exception:
        s2 = None
    if s2 is not None and float(s2) < ns - 1e-6:
        return float(s2), 2, dist
    return ns, 1, dist


def _structure_stop_target_zones(
    *,
    entry_price: float,
    entry_support: Optional[float],
    nearest_resistance: Optional[float],
    target_pct: float = STRUCTURE_EXIT_TARGET_PCT,
) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], List[str]]:
    """对齐 URT structure_exit 回测：支撑缓冲止损 + 阻力/百分比止盈。"""
    from backend_core.strategies.urt.signal_detector import resolve_structure_exit_levels

    notes: List[str] = []
    struct = resolve_structure_exit_levels(
        entry_price=float(entry_price),
        nearest_support=entry_support,
        nearest_resistance=nearest_resistance,
        cfg={
            "structure_stop_buffer_pct": URT_STOP_BUFFER_PCT,
            "structure_exit_min_upside_pct": STRUCTURE_EXIT_MIN_UPSIDE_PCT,
        },
        target_pct=float(target_pct),
    )
    stop_zone = None
    if struct.get("stop_price") is not None:
        basis = str(struct.get("stop_basis") or "structure_support")
        label = "结构支撑下方视为防守失效"
        if basis == "pct_fallback_stop_above_entry":
            label = "支撑过近，回退百分比止损"
        elif basis == "pct_fallback_no_support":
            label = "无结构支撑，回退百分比止损"
        stop_zone = _zone(
            price=float(struct["stop_price"]),
            label=label,
            basis=basis,
        )
        if struct.get("structure_fallback"):
            stop_zone["structure_fallback"] = True
            stop_zone["fallback_reason"] = struct.get("fallback_reason")
    take_profit = None
    if struct.get("target_price") is not None:
        tb = str(struct.get("target_basis") or "structure_resistance")
        if tb == "structure_resistance":
            tp_label = "结构阻力止盈（上行空间充足）"
        elif tb == "pct_target_low_upside":
            tp_label = "阻力上行不足，回退百分比目标止盈"
        else:
            tp_label = "百分比目标止盈"
        take_profit = {
            "prices": [round(float(struct["target_price"]), 4)],
            "price": round(float(struct["target_price"]), 4),
            "label": tp_label,
            "basis": tb,
        }
    if struct.get("nearest_support") is not None:
        notes.append(f"结构止损锚≈{_fmt_px(struct['nearest_support'])}")
    if struct.get("nearest_resistance") is not None and take_profit:
        notes.append(f"结构止盈参考≈{_fmt_px(struct['nearest_resistance'])}")
    return stop_zone, take_profit, notes


def _build_structure_entry_zone(
    *,
    entry_anchor: Optional[float],
    close: Optional[float],
    label: str,
    basis: str,
) -> Optional[Dict[str, Any]]:
    if entry_anchor is None and close is None:
        return None
    anchor = float(entry_anchor if entry_anchor is not None else close)
    if close is not None and float(close) > anchor:
        hi = min(float(close), anchor * (1.0 + URT_NEAR_SUPPORT_BAND_PCT))
        if hi < anchor:
            hi = anchor
        return _zone(
            low=round(anchor, 4),
            high=round(hi, 4),
            label=label,
            basis=basis,
        )
    return _zone(price=round(anchor, 4), label=label, basis=basis)


def _fmt_px(v: Any) -> str:
    return f"{round(float(v), 2):.2f}"


def _within_tol(a: Optional[float], b: Optional[float], tol_pct: float = ALIGN_TOL_PCT) -> bool:
    if a is None or b is None:
        return False
    pa, pb = float(a), float(b)
    if pa <= 0:
        return False
    return abs(pb - pa) / pa <= tol_pct


def _ref_summary(ref: Optional[Dict[str, Any]]) -> str:
    if not ref:
        return ""
    classic_ok = bool(ref.get("ok"))
    parts: List[str] = []
    if classic_ok:
        fs = ref.get("nearest_fib_support")
        fr = ref.get("nearest_fib_resistance")
        cs = ref.get("nearest_cam_support")
        cr = ref.get("nearest_cam_resistance")
        ps = ref.get("nearest_pivot_support")
        pr = ref.get("nearest_pivot_resistance")
        if fs is not None:
            parts.append(f"Fib支撑≈{_fmt_px(fs)}")
        if fr is not None:
            parts.append(f"Fib压力≈{_fmt_px(fr)}")
        if cs is not None:
            parts.append(f"Cam支撑≈{_fmt_px(cs)}")
        if cr is not None:
            parts.append(f"Cam压力≈{_fmt_px(cr)}")
        if ps is not None:
            parts.append(f"Pivot支撑≈{_fmt_px(ps)}")
        if pr is not None:
            parts.append(f"Pivot压力≈{_fmt_px(pr)}")
    vp = ref.get("volume_profile") if isinstance(ref.get("volume_profile"), dict) else {}
    if vp.get("ok"):
        if vp.get("poc") is not None:
            parts.append(f"VP POC≈{_fmt_px(vp['poc'])}")
        vs = ref.get("nearest_vp_support")
        if vs is None:
            vs = vp.get("nearest_support")
        vr = ref.get("nearest_vp_resistance")
        if vr is None:
            vr = vp.get("nearest_resistance")
        if vs is not None:
            parts.append(f"VP支撑≈{_fmt_px(vs)}")
        if vr is not None:
            parts.append(f"VP压力≈{_fmt_px(vr)}")
    conf = ref.get("confluence_zones") if isinstance(ref.get("confluence_zones"), dict) else {}
    if conf.get("ok"):
        nz_s = conf.get("nearest_support_zone") or {}
        nz_r = conf.get("nearest_resistance_zone") or {}
        if nz_s.get("center") is not None:
            parts.append(f"共振支撑≈{_fmt_px(nz_s['center'])}")
        if nz_r.get("center") is not None:
            parts.append(f"共振压力≈{_fmt_px(nz_r['center'])}")
    if not parts:
        return ""
    return "参考：" + " / ".join(parts)


def _resonance_note(
    primary: Optional[float],
    ref_a: Optional[float],
    ref_b: Optional[float],
    *,
    tol_pct: float = ALIGN_TOL_PCT,
) -> Optional[str]:
    if primary is None:
        return None
    for r in (ref_a, ref_b):
        if r is None or primary <= 0:
            continue
        if abs(float(r) - float(primary)) / float(primary) <= tol_pct:
            return f"附近另有 Fib/Pivot 共振（≈{_fmt_px(r)}）"
    return None


def _soft_align_confluence(
    *,
    stop_zone: Optional[Dict[str, Any]],
    take_profit: Optional[Dict[str, Any]],
    kde_s: Optional[float],
    kde_r: Optional[float],
    ref: Dict[str, Any],
    summary_bits: List[str],
    confidence: str,
) -> tuple:
    """共振带与 KDE 同向贴近时：标注 + 展示价对齐带中心（basis=kde+confluence）。"""
    conf = ref.get("confluence_zones") if isinstance(ref.get("confluence_zones"), dict) else {}
    if not conf.get("ok"):
        return stop_zone, take_profit, confidence

    nz_s = conf.get("nearest_support_zone") if isinstance(conf.get("nearest_support_zone"), dict) else None
    nz_r = conf.get("nearest_resistance_zone") if isinstance(conf.get("nearest_resistance_zone"), dict) else None
    center_s = _f((nz_s or {}).get("center"))
    center_r = _f((nz_r or {}).get("center"))

    if center_s is not None and kde_s is not None and _within_tol(kde_s, center_s):
        summary_bits.append(
            f"共振支撑带≈{_fmt_px(center_s)}"
            f"（{nz_s.get('low')}–{nz_s.get('high')}，来源{'+'.join(nz_s.get('sources') or [])}）"
            "与 KDE 同向贴近"
        )
        if stop_zone and (stop_zone.get("basis") or "").startswith("kde"):
            band_low = _f(nz_s.get("low")) or center_s
            anchor = min(float(kde_s), float(band_low))
            stop_zone = _urt_stop_with_buffer(
                anchor,
                basis="kde+confluence",
                ref_label="共振支撑下沿",
            )
            stop_zone["kde_price"] = round(float(kde_s), 4)
            if band_low is not None:
                stop_zone["confluence_low"] = round(float(band_low), 4)
            band_high = _f(nz_s.get("high"))
            if band_high is not None:
                stop_zone["confluence_high"] = round(float(band_high), 4)
            stop_zone["label"] = "结构支撑下方视为防守失效（对齐共振带）"
            if confidence == "medium":
                confidence = "high"

    if center_r is not None and kde_r is not None and _within_tol(kde_r, center_r):
        summary_bits.append(
            f"共振压力带≈{_fmt_px(center_r)}"
            f"（{nz_r.get('low')}–{nz_r.get('high')}，来源{'+'.join(nz_r.get('sources') or [])}）"
            "与 KDE 同向贴近"
        )
        if take_profit and (take_profit.get("basis") or "").startswith("kde"):
            take_profit = dict(take_profit)
            take_profit["prices"] = [round(center_r, 4)]
            take_profit["basis"] = "kde+confluence"
            take_profit["label"] = (take_profit.get("label") or "") + "（对齐共振带）"
            take_profit["kde_price"] = round(float(kde_r), 4)
            if confidence == "medium":
                confidence = "high"

    return stop_zone, take_profit, confidence


def _urt_widen_entry_band(
    *,
    low: Optional[float],
    high: Optional[float],
    close: Optional[float],
    support: Optional[float],
    ma20: Optional[float],
    min_width_pct: float = URT_ENTRY_MIN_WIDTH_PCT,
) -> tuple[Optional[float], Optional[float]]:
    """拓宽回踩承接区：优先支撑～MA20；仅当过窄时上沿抬到 max(MA20, 支撑×(1+min_width))，且 ≤ 现价。"""
    if low is None:
        return None, None
    lo = float(low)
    hi = float(high) if high is not None else lo
    if hi < lo:
        lo, hi = hi, lo
    if close is not None:
        hi = min(hi, float(close))
        if hi < lo:
            hi = lo
    # 已有足够带宽（如支撑与 MA20 间距够大）则不再抬上沿
    if lo > 0 and (hi - lo) / lo >= float(min_width_pct) * 0.9:
        return round(lo, 4), round(hi, 4)

    candidates = [hi]
    if ma20 is not None:
        candidates.append(float(ma20))
    base = float(support) if support is not None else lo
    if base > 0:
        candidates.append(base * (1.0 + float(min_width_pct)))
    hi2 = max(candidates)
    if close is not None:
        hi2 = min(hi2, float(close))
    if hi2 < lo:
        hi2 = lo
    if lo > 0 and (hi2 - lo) / lo < float(min_width_pct) * 0.5 and close is not None:
        hi2 = min(float(close), lo * (1.0 + float(min_width_pct)))
        if hi2 < lo:
            hi2 = lo
    return round(lo, 4), round(hi2, 4)


def _urt_stop_with_buffer(
    ref_price: float,
    *,
    buffer_pct: float = URT_STOP_BUFFER_PCT,
    basis: str,
    ref_label: str,
) -> Dict[str, Any]:
    """止损参考下移缓冲，避免与可执行承接区下限重合被噪声扫损。"""
    ref = float(ref_price)
    buf = max(0.0, float(buffer_pct))
    stop_px = round(ref * (1.0 - buf), 4)
    z = _zone(
        price=stop_px,
        label=(
            f"有效跌破{ref_label}（参考 {_fmt_px(stop_px)}，"
            f"相对{_fmt_px(ref)}约下移{buf * 100:.0f}%缓冲；"
            f"亦可以收盘跌破{_fmt_px(ref)}作确认）"
        ),
        basis=f"{basis}+buffer",
    )
    z["ref_price"] = round(ref, 4)
    z["buffer_pct"] = buf
    return z


def _entry_anchor(buy_zone: Optional[Dict[str, Any]]) -> Optional[float]:
    if not buy_zone or not isinstance(buy_zone, dict):
        return None
    lo = _f(buy_zone.get("low"))
    if lo is not None:
        return lo
    return _f(buy_zone.get("price"))


def _ensure_stop_below_entry(
    buy_zone: Optional[Dict[str, Any]],
    stop_zone: Optional[Dict[str, Any]],
    *,
    kde_s: Optional[float],
    ref_label: str = "结构支撑",
) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """止损价须严格低于买入下沿；共振对齐后若被抬高则重钳为缓冲止损。"""
    if not buy_zone or not stop_zone:
        return buy_zone, stop_zone
    entry_px = _entry_anchor(buy_zone)
    s_px = _f(stop_zone.get("price"))
    if entry_px is None or s_px is None:
        return buy_zone, stop_zone
    if s_px + 1e-12 < entry_px:
        return buy_zone, stop_zone
    ref_px = _f(stop_zone.get("ref_price")) or kde_s or entry_px
    old_basis = str(stop_zone.get("basis") or "kde")
    basis_root = old_basis.split("+")[0] or "kde"
    had_confluence = "confluence" in old_basis
    stop_zone = _urt_stop_with_buffer(
        float(ref_px),
        basis=basis_root,
        ref_label=ref_label,
    )
    if had_confluence:
        stop_zone["basis"] = f"{basis_root}+confluence"
    s_px = float(stop_zone["price"])
    min_entry = s_px * (1.0 + float(URT_ENTRY_ABOVE_STOP_PCT))
    if entry_px + 1e-12 < min_entry:
        buy_zone = dict(buy_zone)
        buy_zone["low"] = round(min_entry, 4)
        if _f(buy_zone.get("high")) is not None and float(buy_zone["high"]) < min_entry:
            buy_zone["high"] = round(min_entry, 4)
        if buy_zone.get("price") is not None and float(buy_zone["price"]) < min_entry:
            buy_zone["price"] = round(min_entry, 4)
    return buy_zone, stop_zone


def _urt_reconcile_entry_stop(
    *,
    entry_low: Optional[float],
    entry_high: Optional[float],
    support: Optional[float],
    ma20: Optional[float],
    close: Optional[float],
    prefer_pullback: bool,
) -> Dict[str, Any]:
    """短线可执行区与止损联动；MA20 过低时降为中线更深回撤关注。

    口径对齐个股分析：
    - 短线：近端结构支撑一带买入，失效/止损须严格低于买入下沿；
    - 中线：MA20 等更远均线作回撤观察，不写入同一止损下的买入下沿。
    """
    stop_anchor = support if support is not None else (
        ma20 if ma20 is not None else entry_low
    )
    if stop_anchor is None:
        return {
            "entry_low": entry_low,
            "entry_high": entry_high,
            "stop_zone": None,
            "deeper_watch": None,
            "horizon_notes": [],
        }

    stop_label = "最近结构支撑" if support is not None else "MA20"
    stop_basis = "kde" if support is not None else "ma20"
    stop_zone = _urt_stop_with_buffer(
        float(stop_anchor), basis=stop_basis, ref_label=stop_label
    )
    stop_px = float(stop_zone["price"])
    min_entry = stop_px * (1.0 + float(URT_ENTRY_ABOVE_STOP_PCT))

    lo = float(entry_low) if entry_low is not None else None
    hi = float(entry_high) if entry_high is not None else lo
    deeper_watch: Optional[Dict[str, Any]] = None
    horizon_notes: List[str] = []

    demoted = False
    if lo is not None and lo + 1e-12 < min_entry:
        # 下沿已落入止损之下（常见：MA20 << 结构支撑）→ 降为中线关注
        deeper_watch = {
            "price": round(lo, 4),
            "label": (
                f"中线更深回撤关注≈{_fmt_px(lo)}"
                + ("（MA20）" if ma20 is not None and abs(float(ma20) - lo) < 1e-6 else "")
                + "：跌破短线止损后再看，不宜与上方承接共用同一止损"
            ),
            "basis": "ma20_demoted" if ma20 is not None and abs(float(ma20) - lo) < 1e-6 else "deep_pullback",
        }
        demoted = True
        horizon_notes.append(
            f"短线可执行承接钉近端结构支撑；MA20/更深位{_fmt_px(lo)}仅作中线回撤观察，"
            f"不写入买入下沿（避免低于止损{_fmt_px(stop_px)}）"
        )
        if support is not None:
            near_lo = float(support) * (1.0 - float(URT_NEAR_SUPPORT_BAND_PCT))
            lo = max(min_entry, near_lo)
            hi = float(support)
            if close is not None:
                hi = min(hi, float(close))
            if hi < lo:
                hi = lo
        else:
            lo = min_entry
            if hi is None or hi < lo:
                hi = lo if close is None else min(float(close), lo * (1.0 + URT_ENTRY_MIN_WIDTH_PCT))

    # 兜底：任何情况下买入下沿不得 ≤ 止损
    if lo is not None and lo + 1e-12 < min_entry:
        lo = min_entry
        if hi is None or hi < lo:
            hi = lo
        horizon_notes.append(
            f"买入下沿已抬至止损上方（≥{_fmt_px(min_entry)}），与个股分析失效位钳制同口径"
        )

    if prefer_pullback and not demoted:
        horizon_notes.append(
            "短线：回踩近端结构支撑～MA20 一带分批；中线：沿 MA20 趋势回撤观察"
        )
    elif prefer_pullback and demoted:
        horizon_notes.append(
            "短线：仅在近端结构支撑上方分批承接；中线：等待更深回撤至关注位再评估"
        )

    return {
        "entry_low": round(lo, 4) if lo is not None else None,
        "entry_high": round(hi, 4) if hi is not None else None,
        "stop_zone": stop_zone,
        "deeper_watch": deeper_watch,
        "horizon_notes": horizon_notes,
        "demoted_deep_low": demoted,
    }


def _soft_merge_pattern_tactical(
    *,
    buy_zone: Optional[Dict[str, Any]],
    stop_zone: Optional[Dict[str, Any]],
    summary_bits: List[str],
    confidence: str,
    tactical: Optional[Dict[str, Any]],
) -> tuple:
    """若行上已有个股形态短期三态/buy_hints，软融合进摘要与展示（不强算形态）。"""
    if not isinstance(tactical, dict):
        return buy_zone, stop_zone, confidence

    bias = tactical.get("bias") or tactical.get("bias_label")
    grade = tactical.get("grade")
    if bias or grade:
        summary_bits.append(
            "形态短线旁证："
            + (f"{bias}" if bias else "")
            + (f"·grade={grade}" if grade else "")
        )

    hints = tactical.get("buy_hints") if isinstance(tactical.get("buy_hints"), list) else []
    primary = hints[0] if hints and isinstance(hints[0], dict) else None
    if not primary:
        # 部分路径把分析文案挂在 analysis
        analysis = tactical.get("analysis") if isinstance(tactical.get("analysis"), dict) else {}
        st = analysis.get("shortTerm") or tactical.get("shortTerm")
        mt = analysis.get("mediumTerm") or tactical.get("mediumTerm")
        if st:
            summary_bits.append(f"个股短线：{str(st)[:120]}")
        if mt:
            summary_bits.append(f"个股中线：{str(mt)[:120]}")
        return buy_zone, stop_zone, confidence

    ez = primary.get("entry_zone") if isinstance(primary.get("entry_zone"), dict) else {}
    inv = _f(primary.get("invalidation"))
    ez_lo = _f(ez.get("low"))
    ez_hi = _f(ez.get("high"))
    ez_c = _f(ez.get("center") or ez.get("price"))
    anchor = ez.get("anchor") or ""
    if ez_lo is not None or ez_c is not None:
        band = (
            f"{_fmt_px(ez_lo)}–{_fmt_px(ez_hi)}"
            if ez_lo is not None and ez_hi is not None
            else _fmt_px(ez_c if ez_c is not None else ez_lo)
        )
        summary_bits.append(
            f"形态短线买点旁证≈{band}"
            + (f"（{anchor}）" if anchor else "")
            + (f"，失效≈{_fmt_px(inv)}" if inv is not None else "")
        )

    # 与 URT 止损同向贴近时标注（不覆盖 KDE 主止损）
    stop_px = _f((stop_zone or {}).get("price") or (stop_zone or {}).get("low"))
    if inv is not None and stop_px is not None and stop_px > 0 and _within_tol(stop_px, inv):
        summary_bits.append(f"形态失效位≈{_fmt_px(inv)}与 URT 止损同向贴近")
        if confidence == "medium":
            confidence = "high"
        if stop_zone:
            stop_zone = dict(stop_zone)
            stop_zone["pattern_invalidation"] = round(float(inv), 4)
            stop_zone["basis"] = (stop_zone.get("basis") or "kde") + "+pattern"

    # 买区中心贴近时软标注
    buy_mid = None
    if buy_zone:
        bl, bh = _f(buy_zone.get("low")), _f(buy_zone.get("high"))
        if bl is not None and bh is not None:
            buy_mid = (bl + bh) / 2.0
        else:
            buy_mid = _f(buy_zone.get("price"))
    ref_mid = ez_c if ez_c is not None else (
        (ez_lo + ez_hi) / 2.0 if ez_lo is not None and ez_hi is not None else ez_lo
    )
    if buy_mid is not None and ref_mid is not None and _within_tol(buy_mid, ref_mid):
        summary_bits.append("形态短线入场区与 URT 承接区同向贴近")
        if buy_zone:
            buy_zone = dict(buy_zone)
            buy_zone["basis"] = (buy_zone.get("basis") or "urt") + "+pattern"
            buy_zone["pattern_anchor"] = str(anchor) if anchor else None

    analysis = tactical.get("analysis") if isinstance(tactical.get("analysis"), dict) else {}
    st = analysis.get("shortTerm") or tactical.get("shortTerm")
    mt = analysis.get("mediumTerm") or tactical.get("mediumTerm")
    if st:
        summary_bits.append(f"个股短线：{str(st)[:120]}")
    if mt:
        summary_bits.append(f"个股中线：{str(mt)[:120]}")

    return buy_zone, stop_zone, confidence


def build_trade_advice(
    strategy: str,
    row: Dict[str, Any],
    *,
    reference_levels: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """生成 trade_advice。strategy: gms|urt|sbbr|rpe"""
    kind = (strategy or "").strip().lower()
    ref = reference_levels if isinstance(reference_levels, dict) else None
    buy_zone: Optional[Dict[str, Any]] = None
    stop_zone: Optional[Dict[str, Any]] = None
    take_profit: Optional[Dict[str, Any]] = None
    sell_triggers: List[Dict[str, Any]] = []
    deeper_watch: Optional[Dict[str, Any]] = None
    horizon: Optional[Dict[str, Any]] = None
    action = "watch"
    confidence = "medium"
    summary_bits: List[str] = []

    kde_s = _kde_support(row)
    kde_r = _kde_resistance(row)
    close = _f(row.get("close") or row.get("latest_price") or row.get("price"))

    if kind == "gms":
        buy_type = (row.get("buy_type") or "").strip()
        left = bool(row.get("left_buy_signal"))
        right = bool(row.get("right_buy_signal"))
        sell = bool(row.get("sell_signal"))
        board_weak = bool(row.get("board_weak"))
        if left or buy_type == "左侧":
            action = "buy"
            sup_pool = _structure_level_pool(row, ref, "support")
            entry_anchor, support_rank, near_dist = _pick_entry_structure_support(
                close, kde_s, sup_pool
            )
            entry_anchor = entry_anchor or kde_s
            buy_zone = _build_structure_entry_zone(
                entry_anchor=entry_anchor,
                close=close,
                label="左侧吸筹：回踩结构支撑附近分批承接",
                basis="gms_left+structure",
            )
            if buy_zone is None:
                buy_zone = _zone(
                    price=kde_s or close,
                    label="左侧吸筹：贴近均值/结构支撑附近低吸",
                    basis="gms_left+kde" if kde_s else "gms_left",
                )
            summary_bits.append("GMS左侧买点：宜在结构支撑附近分批承接")
            if support_rank >= 2 and entry_anchor is not None:
                pct_txt = f"{near_dist * 100:.1f}%" if near_dist is not None else "较近"
                summary_bits.append(
                    f"距第一支撑过近（{pct_txt}），入场参考第二档支撑≈{_fmt_px(entry_anchor)}"
                )
            ref_entry = _entry_anchor(buy_zone) or close or entry_anchor
            if ref_entry is not None and entry_anchor is not None:
                sz, tp, st_notes = _structure_stop_target_zones(
                    entry_price=float(ref_entry),
                    entry_support=float(entry_anchor),
                    nearest_resistance=kde_r,
                )
                if sz is not None:
                    stop_zone = sz
                if tp is not None:
                    take_profit = tp
                summary_bits.extend(st_notes)
        elif right or buy_type == "右侧":
            action = "buy"
            buy_zone = _zone(
                price=close,
                label="右侧动量：突破后回踩不破支撑再跟",
                basis="gms_right",
            )
            summary_bits.append("GMS右侧买点：回踩不破支撑再跟进")
        if not stop_zone and kde_s is not None:
            stop_zone = _urt_stop_with_buffer(
                float(kde_s),
                basis="kde",
                ref_label="结构支撑",
            )
        if not take_profit and kde_r is not None:
            take_profit = {
                "label": "靠近结构压力减仓/止盈",
                "basis": "kde",
                "prices": [round(kde_r, 4)],
            }
        if sell:
            sell_triggers.append(
                {"type": "gms_sell_signal", "label": "策略卖点触发，考虑减仓/离场", "basis": "sell_signal"}
            )
            if action == "buy":
                confidence = "low"
        if board_weak:
            confidence = "low"
            summary_bits.append("主行业板走弱，降低仓位与信心")
            if action == "buy":
                action = "watch"

    elif kind == "urt":
        ma20 = _f(row.get("ma20"))
        tags = row.get("risk_tags") or []
        tag_ids = {
            (t.get("id") if isinstance(t, dict) else t)
            for t in tags
            if t is not None
        }
        tag_levels = {
            (t.get("id") if isinstance(t, dict) else ""): (t.get("level") if isinstance(t, dict) else "")
            for t in tags
            if isinstance(t, dict)
        }
        overheat_soft = any(
            tid in ("recent_overheat", "ma20_overheat") and tag_levels.get(tid) == "warn"
            for tid in tag_ids
        )
        overheat_hard = any(
            tid in ("recent_overheat", "ma20_overheat") and tag_levels.get(tid) == "danger"
            for tid in tag_ids
        )
        rr = _f(row.get("structure_rr"))
        if rr is None:
            st = row.get("structure") if isinstance(row.get("structure"), dict) else {}
            rr = _f(st.get("rr"))

        trade_support = kde_s
        if bool(row.get("buy_signal")):
            action = "buy"
            sup_pool = _structure_level_pool(row, ref, "support")
            entry_support, support_rank, near_dist = _pick_entry_structure_support(
                close, kde_s, sup_pool
            )
            trade_support = entry_support if entry_support is not None else kde_s
            if support_rank >= 2 and trade_support is not None:
                pct_txt = f"{near_dist * 100:.1f}%" if near_dist is not None else "较近"
                summary_bits.append(
                    f"距第一支撑过近（{pct_txt}），入场参考第二档支撑≈{_fmt_px(trade_support)}"
                )
            # 默认：支撑～现价/MA20 的回踩承接区；已远离支撑或过热软标时强调回踩不追
            prefer_pullback = False
            if close is not None and trade_support is not None and close > 0:
                dist_pct = (float(close) - float(trade_support)) / float(close)
                if dist_pct >= 0.03 or overheat_soft:
                    prefer_pullback = True
            if overheat_hard:
                prefer_pullback = True
                confidence = "low"

            entry_low = None
            entry_high = None
            anchors = [
                x
                for x in (trade_support, ma20)
                if x is not None and (close is None or float(x) <= float(close) + 1e-12)
            ]
            if anchors:
                entry_low = min(float(x) for x in anchors)
                entry_high = max(float(x) for x in anchors)
            elif trade_support is not None:
                entry_low = float(trade_support)
            elif kde_s is not None:
                entry_low = float(kde_s)
            elif ma20 is not None:
                entry_low = float(ma20)

            if prefer_pullback and entry_low is not None:
                entry_low, entry_high = _urt_widen_entry_band(
                    low=entry_low,
                    high=entry_high,
                    close=close,
                    support=trade_support,
                    ma20=ma20,
                )
            elif entry_low is not None:
                # 贴近跟进时也给可执行带宽：支撑/MA20～现价
                entry_low, entry_high = _urt_widen_entry_band(
                    low=entry_low,
                    high=close if close is not None else entry_high,
                    close=close,
                    support=trade_support,
                    ma20=ma20,
                )

            reconciled = _urt_reconcile_entry_stop(
                entry_low=entry_low,
                entry_high=entry_high,
                support=trade_support,
                ma20=ma20,
                close=close,
                prefer_pullback=prefer_pullback,
            )
            entry_low = reconciled["entry_low"]
            entry_high = reconciled["entry_high"]
            stop_zone = reconciled["stop_zone"]
            deeper_watch = reconciled.get("deeper_watch")
            for note in reconciled.get("horizon_notes") or []:
                summary_bits.append(note)

            if prefer_pullback:
                buy_zone = _zone(
                    low=entry_low,
                    high=entry_high,
                    price=kde_s or entry_low,
                    label=(
                        "回踩承接（短线）：优先在近端结构支撑一带分批，不宜追高"
                        if reconciled.get("demoted_deep_low")
                        else "回踩承接：优先在结构支撑～MA20 一带分批，不宜追高"
                    ),
                    basis="urt_buy+pullback+kde" if kde_s else "urt_buy+pullback",
                )
                summary_bits.append(
                    "URT买点成立：价离支撑偏远或存在过热软提示，建议回踩支撑承接，不追涨"
                )
            else:
                buy_zone = _zone(
                    low=entry_low,
                    high=entry_high if entry_high is not None else close,
                    price=close or entry_low or ma20,
                    label="上升趋势买点：现价附近跟进，或回踩支撑/MA20 不破加仓",
                    basis="urt_buy+kde" if kde_s else "urt_buy",
                )
                summary_bits.append("URT买点成立：现价附近可跟，回踩支撑/MA20 不破可持有或加仓")

            horizon = {
                "short_term": {
                    "buy_zone": buy_zone,
                    "stop_zone": stop_zone,
                    "note": "近端结构支撑一带可执行；止损须低于买入下沿",
                },
                "medium_term": {
                    "watch": deeper_watch,
                    "ma20": round(float(ma20), 4) if ma20 is not None else None,
                    "note": (
                        "更深回撤/均线关注，不与短线同一止损捆绑"
                        if deeper_watch
                        else "沿 MA20 趋势回撤观察，与短线承接区可重叠"
                    ),
                },
            }

            if overheat_soft and not overheat_hard:
                confidence = "medium"
                summary_bits.append("过热软提示：控制仓位、分批，优先等回踩")
        else:
            action = "watch"
            summary_bits.append("未达正式买点：仅观察，不以现价追入")
            if kde_s is not None:
                summary_bits.append(f"关注回踩结构支撑{_fmt_px(kde_s)}附近是否企稳")
            # 观察态仍给止损锚，便于对照
            if kde_s is not None:
                stop_zone = _urt_stop_with_buffer(
                    kde_s, basis="kde", ref_label="最近结构支撑"
                )
            elif ma20 is not None:
                stop_zone = _urt_stop_with_buffer(
                    ma20, basis="ma20", ref_label="MA20"
                )

        if action == "buy" and trade_support is not None and buy_zone:
            ref_entry = _entry_anchor(buy_zone) or close or trade_support
            _, tp_struct, tp_notes = _structure_stop_target_zones(
                entry_price=float(ref_entry),
                entry_support=float(trade_support),
                nearest_resistance=kde_r,
            )
            if tp_struct is not None:
                take_profit = tp_struct
            summary_bits.extend(tp_notes)
        elif kde_r is not None:
            take_profit = {
                "label": "靠近结构压力减仓/止盈",
                "basis": "kde",
                "prices": [round(kde_r, 4)],
            }
        if "structure_rr_poor" in tag_ids or "rr_poor" in tag_ids:
            confidence = "low"
            if action == "buy":
                action = "watch"
            summary_bits.append("结构盈亏比偏弱，降级为观察")

        # 个股分析形态短/中线旁证（有则软融合，选股默认不强算）
        tactical = row.get("pattern_tactical") or row.get("tactical")
        if tactical is None and isinstance(row.get("score_detail"), dict):
            tactical = row.get("score_detail").get("tactical")
        buy_zone, stop_zone, confidence = _soft_merge_pattern_tactical(
            buy_zone=buy_zone,
            stop_zone=stop_zone,
            summary_bits=summary_bits,
            confidence=confidence,
            tactical=tactical if isinstance(tactical, dict) else None,
        )

    elif kind == "sbbr":
        entry = bool(row.get("entry_signal"))
        bottom = bool(row.get("bottom_matched"))
        entry_low = _f(row.get("entry_low"))
        d_low = _f(row.get("defense_low"))
        d_high = _f(row.get("defense_high"))
        box_s = _f(row.get("box_support"))
        box_r = _f(row.get("box_resistance"))
        if entry:
            action = "buy"
            buy_zone = _zone(
                price=entry_low or close,
                low=entry_low,
                label="做底入场：entry_low 附近承接",
                basis="sbbr_entry",
            )
            summary_bits.append("SBBR入场信号：在入场低点附近布局")
        elif bottom:
            action = "watch"
            summary_bits.append("已筑底未入场：纳入关注，等待入场确认")
        if d_low is not None or d_high is not None:
            stop_zone = _zone(
                low=d_low,
                high=d_high,
                price=d_low,
                label="防守带：收盘跌破防守下沿离场",
                basis="defense",
            )
            sell_triggers.append(
                {
                    "type": "defense_breach",
                    "label": f"收盘跌破防守下沿{d_low}",
                    "basis": "defense",
                }
            )
        elif box_s is not None:
            stop_zone = _zone(price=box_s, label="箱体下沿防守", basis="box")
        if box_r is not None:
            take_profit = {
                "label": "箱体上沿/突破看高",
                "basis": "box",
                "prices": [round(box_r, 4)],
            }
        elif kde_r is not None:
            take_profit = {"label": "结构压力止盈", "basis": "kde", "prices": [round(kde_r, 4)]}
        pa_text = _position_advice_text(row.get("position_advice"))
        if pa_text:
            summary_bits.append(pa_text)

    elif kind == "rpe":
        sig = (row.get("signal_type") or "").strip().lower()
        entry = bool(row.get("entry_signal"))
        watch_only = bool(row.get("watch_only"))
        veto = bool(row.get("trend_veto"))
        if veto:
            action = "avoid"
            confidence = "low"
            summary_bits.append("板块斜率趋势否决，避免开仓")
        elif sig == "lead" or watch_only:
            action = "watch"
            summary_bits.append("领涨/仅观察：不追高，等待回踩或补涨确认")
        elif entry or sig == "catch_up":
            action = "buy"
            buy_zone = _zone(
                price=kde_s or close,
                label="补涨：回踩比价带下沿/结构支撑附近",
                basis="rpe_catch_up+kde" if kde_s else "rpe_catch_up",
            )
            summary_bits.append("RPE补涨可交易：支撑附近低吸")
        if kde_s is not None:
            stop_zone = _zone(price=kde_s, label="跌破结构支撑离场", basis="kde")
        if kde_r is not None:
            take_profit = {"label": "结构压力减仓", "basis": "kde", "prices": [round(kde_r, 4)]}
        plan = row.get("structure_plan") if isinstance(row.get("structure_plan"), dict) else {}
        if plan.get("note"):
            summary_bits.append(str(plan["note"]))

    else:
        summary_bits.append(f"未知策略 {kind}")
        action = "watch"
        confidence = "low"

    # 共振带软融合（不删 KDE 主依据；仅展示价/summary）
    if ref:
        stop_zone, take_profit, confidence = _soft_align_confluence(
            stop_zone=stop_zone,
            take_profit=take_profit,
            kde_s=kde_s,
            kde_r=kde_r,
            ref=ref,
            summary_bits=summary_bits,
            confidence=confidence,
        )

    # Fib/Pivot 共振提示（不覆盖主 stop）
    if ref and ref.get("ok"):
        note = _resonance_note(
            (stop_zone or {}).get("price") or (stop_zone or {}).get("low"),
            ref.get("nearest_fib_support"),
            ref.get("nearest_cam_support") or ref.get("nearest_pivot_support"),
        )
        if note:
            summary_bits.append(note)
        note2 = _resonance_note(
            (take_profit or {}).get("prices", [None])[0]
            if take_profit and take_profit.get("prices")
            else None,
            ref.get("nearest_fib_resistance"),
            ref.get("nearest_cam_resistance") or ref.get("nearest_pivot_resistance"),
        )
        if note2:
            summary_bits.append(note2)
        rs = _ref_summary(ref)
        if rs:
            summary_bits.append(rs)

    if not summary_bits:
        summary_bits.append("暂无明确买卖建议，仅供观察")

    # normalize take_profit shape
    if take_profit and "prices" not in take_profit and take_profit.get("price") is not None:
        take_profit["prices"] = [take_profit["price"]]

    # 共振对齐后保证：止损仍低于买入下沿（GMS/SBBR/RPE 等同理）
    if buy_zone and stop_zone:
        buy_zone, stop_zone = _ensure_stop_below_entry(
            buy_zone,
            stop_zone,
            kde_s=kde_s,
            ref_label="结构支撑",
        )
        if kind == "urt" and _entry_anchor(buy_zone) is not None and stop_zone:
            s_px = _f(stop_zone.get("price"))
            min_entry = (
                float(s_px) * (1.0 + float(URT_ENTRY_ABOVE_STOP_PCT)) if s_px is not None else None
            )
            entry_px = _entry_anchor(buy_zone)
            if (
                min_entry is not None
                and entry_px is not None
                and entry_px + 1e-12 < min_entry
            ):
                summary_bits.append(
                    f"已重钳：买入下沿≥{_fmt_px(min_entry)}，止损{_fmt_px(s_px)}"
                )

    structure_rr = _f(row.get("structure_rr"))
    if structure_rr is None:
        st0 = row.get("structure") if isinstance(row.get("structure"), dict) else {}
        structure_rr = _f(st0.get("rr"))

    key_levels: Dict[str, Any] = {}
    if kde_s is not None:
        key_levels["support"] = round(float(kde_s), 2)
    if close is not None:
        key_levels["close"] = round(float(close), 2)
    if kde_r is not None:
        key_levels["resistance"] = round(float(kde_r), 2)

    return {
        "action": action,
        "buy_zone": buy_zone,
        "stop_zone": stop_zone,
        "take_profit": take_profit,
        "sell_triggers": sell_triggers,
        "deeper_watch": deeper_watch,
        "horizon": horizon,
        "summary": "；".join(summary_bits),
        "confidence": confidence,
        "kde_support": round(float(kde_s), 2) if kde_s is not None else None,
        "kde_resistance": round(float(kde_r), 2) if kde_r is not None else None,
        "structure_rr": round(float(structure_rr), 2) if structure_rr is not None else None,
        "key_levels": key_levels or None,
        "reference_levels": ref,
    }
