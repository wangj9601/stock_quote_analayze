# -*- coding: utf-8 -*-
"""短期方向（三态）与结构买点：形态定主标签，VP/RPE 仅抬 grade。

产品口径见 docs/features/支撑阻力与形态识别_算法说明.md「短期三态与结构买点」。
与前端 pattern_tool.js 的 bias / 巩固突破方向语义对齐，但不照抄整份 NLG。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from backend_core.analysis.chart_patterns.rules import (
    BREAKOUT_DOWN_MULT,
    BREAKOUT_UP_MULT,
)

DISCLAIMER = "规则模板，非投资建议"

# 高强度共振压制门槛（附件示例 >50；可配置）
RESONANCE_PRESSURE_MIN_STRENGTH = 50.0
# 主形态竞选：置信接近阈值（与前端 RANK_CONF_TIE_EPS 对齐）
RANK_CONF_TIE_EPS = 0.05
# RPE 领涨 Z 默认门槛
DEFAULT_Z_LEAD = 2.0

BEARISH_REVERSAL = frozenset({"double_top", "head_shoulders_top"})
BULLISH_REVERSAL = frozenset({"double_bottom", "head_shoulders_bottom"})
CONSOLIDATION = frozenset(
    {
        "ascending_triangle",
        "descending_triangle",
        "symmetrical_triangle",
        "rising_wedge",
        "falling_wedge",
        "bull_flag",
        "bear_flag",
    }
)

_TYPE_LABEL_ZH = {
    "double_bottom": "双底",
    "double_top": "双顶",
    "head_shoulders_top": "头肩顶",
    "head_shoulders_bottom": "头肩底",
    "ascending_triangle": "上升三角",
    "descending_triangle": "下降三角",
    "symmetrical_triangle": "对称三角",
    "rising_wedge": "上升楔形",
    "falling_wedge": "下降楔形",
    "bull_flag": "上升旗形",
    "bear_flag": "下降旗形",
}

_BIAS_LABEL = {
    "看多": "趋势确立",
    "震荡": "蓄势夹击",
    "看空": "结构破位",
    "insufficient": "信息不足",
}


def _f(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x != x:  # NaN
        return None
    return x


def _type_label(pattern_type: str) -> str:
    t = str(pattern_type or "")
    return _TYPE_LABEL_ZH.get(t, t or "形态")


def _bias_of(pattern_type: str) -> str:
    t = str(pattern_type or "")
    if t in BEARISH_REVERSAL:
        return "bear"
    if t in BULLISH_REVERSAL:
        return "bull"
    if t in ("rising_wedge", "bear_flag", "descending_triangle"):
        return "bearish_bias"
    if t in ("falling_wedge", "bull_flag", "ascending_triangle"):
        return "bullish_bias"
    return "neutral"


def _bias_conflicts(a: str, b: str) -> bool:
    bullish = {"bull", "bullish_bias"}
    bearish = {"bear", "bearish_bias"}
    return (a in bullish and b in bearish) or (a in bearish and b in bullish)


def _hit_levels(h: Dict[str, Any]) -> Dict[str, Any]:
    lv = h.get("key_levels") if isinstance(h, dict) else None
    return lv if isinstance(lv, dict) else {}


def _hit_close(h: Dict[str, Any]) -> Optional[float]:
    lv = _hit_levels(h)
    c = _f(lv.get("last_close"))
    if c is not None:
        return c
    return _f(h.get("last_close"))


def _hit_neck(h: Dict[str, Any]) -> Optional[float]:
    return _f(_hit_levels(h).get("neckline"))


def _hit_bounds(h: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    lv = _hit_levels(h)
    return _f(lv.get("upper")), _f(lv.get("lower"))


def _active_hits(hits: Optional[Sequence[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for h in hits or []:
        if not isinstance(h, dict):
            continue
        st = str(h.get("status") or "")
        if st in ("invalidated", "archived"):
            continue
        out.append(h)
    return out


def _status_rank(st: str) -> int:
    if st == "confirmed":
        return 2
    if st == "forming":
        return 1
    return 0


def rank_hits(hits: Optional[Sequence[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """confirmed > forming；同 status 按 confidence desc，再 formed_at desc。"""
    list_ = _active_hits(hits)
    return sorted(
        list_,
        key=lambda h: (
            -_status_rank(str(h.get("status") or "")),
            -(float(h.get("confidence") or 0.0)),
            str(h.get("formed_at") or h.get("confirm_date") or ""),
        ),
    )


def pick_primary(hits: Optional[Sequence[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    ranked = rank_hits(hits)
    if not ranked:
        return None
    confirmed = [h for h in ranked if str(h.get("status") or "") == "confirmed"]
    if confirmed:
        return confirmed[0]
    return ranked[0]


def consol_break_dir(h: Dict[str, Any]) -> str:
    """已确认巩固：up / down / out（与前端 _consolBreakDir 对齐）。"""
    t = str(h.get("pattern_type") or "")
    upper, lower = _hit_bounds(h)
    close = _hit_close(h)
    if close is not None and upper is not None and upper > 0 and close > upper * BREAKOUT_UP_MULT:
        return "up"
    if close is not None and lower is not None and lower > 0 and close < lower * BREAKOUT_DOWN_MULT:
        return "down"
    if t in ("falling_wedge", "bull_flag", "ascending_triangle"):
        return "up"
    if t in ("rising_wedge", "bear_flag", "descending_triangle"):
        return "down"
    return "out"


def measured_target(h: Dict[str, Any]) -> Optional[float]:
    """巩固简化测幅；反转用颈线±高度粗估。"""
    t = str(h.get("pattern_type") or "")
    st = str(h.get("status") or "")
    upper, lower = _hit_bounds(h)
    neck = _hit_neck(h)
    if t in CONSOLIDATION and st == "confirmed" and upper is not None and lower is not None:
        height = upper - lower
        if height <= 0:
            return None
        direction = consol_break_dir(h)
        if direction == "up":
            return round(upper + height, 2)
        if direction == "down":
            return round(lower - height, 2)
        return None
    if t in BULLISH_REVERSAL and neck is not None and lower is not None:
        height = neck - lower
        if height > 0:
            return round(neck + height, 2)
    if t in BEARISH_REVERSAL and neck is not None and upper is not None:
        height = upper - neck
        if height > 0:
            return round(neck - height, 2)
    return None


def _zone_strength(z: Any) -> Optional[float]:
    if not isinstance(z, dict):
        return None
    return _f(z.get("strength"))


def _nearest_resistance_pressure(
    confluence: Optional[Dict[str, Any]],
    *,
    min_strength: float,
) -> Optional[Dict[str, Any]]:
    """近端/贴身阻力带强度 ≥ 门槛则返回该带。"""
    if not isinstance(confluence, dict):
        return None
    cands: List[Dict[str, Any]] = []
    nz = confluence.get("nearest_resistance_zone")
    if isinstance(nz, dict):
        cands.append(nz)
    for z in confluence.get("resistances") or []:
        if isinstance(z, dict):
            cands.append(z)
    best: Optional[Dict[str, Any]] = None
    best_s = -1.0
    for z in cands:
        s = _zone_strength(z)
        if s is None or s < min_strength:
            continue
        if s > best_s:
            best_s = s
            best = z
    return best


def _has_bias_mix(primary: Dict[str, Any], hits: Sequence[Dict[str, Any]]) -> bool:
    """同 status、置信接近、多空 bias 冲突 → 交织。"""
    pb = _bias_of(str(primary.get("pattern_type") or ""))
    pst = str(primary.get("status") or "")
    pc = float(primary.get("confidence") or 0.0)
    for h in hits:
        if h is primary:
            continue
        if str(h.get("status") or "") != pst:
            continue
        if not _bias_conflicts(pb, _bias_of(str(h.get("pattern_type") or ""))):
            continue
        hc = float(h.get("confidence") or 0.0)
        if abs(pc - hc) < RANK_CONF_TIE_EPS:
            return True
    return False


def _vp_break_vah_ok(vp: Optional[Dict[str, Any]], close: Optional[float]) -> bool:
    if not isinstance(vp, dict):
        return False
    vah = _f(vp.get("vah"))
    last_c = close if close is not None else _f(vp.get("last_close"))
    if last_c is None or vah is None:
        return False
    if last_c <= vah:
        return False
    note = str(vp.get("resistance_note") or "")
    nr = vp.get("nearest_resistance")
    if nr is None:
        return True
    if "上方无" in note and "筹码压制" in note:
        return True
    return False


def _rpe_lead_ok(
    rpe: Optional[Dict[str, Any]],
    *,
    z_lead: float,
) -> Tuple[bool, Optional[float]]:
    if not isinstance(rpe, dict):
        return False, None
    z = None
    for k in ("z_score", "zscore", "relative_z", "score"):
        z = _f(rpe.get(k))
        if z is not None:
            break
    if z is None:
        return False, None
    return z >= float(z_lead), z


def _core_defense(h: Dict[str, Any]) -> Optional[float]:
    """核心防守：反转用颈线，巩固用下沿。"""
    t = str(h.get("pattern_type") or "")
    neck = _hit_neck(h)
    _upper, lower = _hit_bounds(h)
    if t in BULLISH_REVERSAL or t in BEARISH_REVERSAL:
        return neck if neck is not None else lower
    return lower if lower is not None else neck


def classify_short_bias(
    hits: Optional[Sequence[Dict[str, Any]]] = None,
    *,
    confluence: Optional[Dict[str, Any]] = None,
    vp: Optional[Dict[str, Any]] = None,
    rpe: Optional[Dict[str, Any]] = None,
    invalidated_count: int = 0,
    resonance_min_strength: float = RESONANCE_PRESSURE_MIN_STRENGTH,
    z_lead: float = DEFAULT_Z_LEAD,
) -> Dict[str, Any]:
    """结构主判定 + 增强证据；返回 short_bias / grade / evidence / rationale 等中间结果。"""
    active = _active_hits(hits)
    inv_n = max(0, int(invalidated_count or 0))
    evidence: List[Dict[str, Any]] = []

    if not active:
        short_bias = "insufficient" if inv_n <= 0 else "震荡"
        rationale = (
            f"有效命中 0（另有 {inv_n} 条已失效），信息不足，无进攻买点。"
            if inv_n > 0
            else "有效命中 0，暂无结构方向。"
        )
        evidence.append(
            {
                "code": "no_active_hits",
                "ok": True,
                "invalidated_count": inv_n,
            }
        )
        return {
            "short_bias": short_bias,
            "bias_label": _BIAS_LABEL.get(short_bias, short_bias),
            "grade": "base",
            "confidence": 0.25 if inv_n else 0.15,
            "rationale": rationale,
            "evidence": evidence,
            "primary": None,
            "pressure_zone": None,
        }

    primary = pick_primary(active)
    assert primary is not None
    t = str(primary.get("pattern_type") or "")
    st = str(primary.get("status") or "")
    close = _hit_close(primary)
    neck = _hit_neck(primary)
    upper, lower = _hit_bounds(primary)
    lab = _type_label(t)
    conf = float(primary.get("confidence") or 0.0)

    pressure = _nearest_resistance_pressure(
        confluence, min_strength=float(resonance_min_strength)
    )
    mix = _has_bias_mix(primary, active)

    short_bias = "震荡"
    bias_label = _BIAS_LABEL["震荡"]
    rationale_bits: List[str] = []

    # —— 看空：破位 / 确认空头且收在颈线下 ——
    bear_ok = False
    if st == "confirmed" and t in BEARISH_REVERSAL and close is not None and neck is not None:
        if close < neck * BREAKOUT_DOWN_MULT:
            bear_ok = True
            rationale_bits.append(f"已确认{lab}且收盘在颈线下方")
    if st == "confirmed" and t in CONSOLIDATION:
        if consol_break_dir(primary) == "down":
            bear_ok = True
            rationale_bits.append(f"已确认{lab}下破")
    # 有效跌破核心防守（多头反转确认后失守颈线 / 巩固下沿）
    defense = _core_defense(primary)
    if (
        not bear_ok
        and st == "confirmed"
        and t in BULLISH_REVERSAL
        and close is not None
        and neck is not None
        and close < neck * BREAKOUT_DOWN_MULT
    ):
        bear_ok = True
        rationale_bits.append(f"已确认{lab}后有效跌破颈线防守")
    if (
        not bear_ok
        and st == "confirmed"
        and t in CONSOLIDATION
        and close is not None
        and lower is not None
        and lower > 0
        and close < lower * BREAKOUT_DOWN_MULT
    ):
        bear_ok = True
        rationale_bits.append(f"有效跌破{lab}下沿")

    evidence.append(
        {
            "code": "pattern_breakdown",
            "ok": bear_ok,
            "pattern_type": t,
            "status": st,
            "close": close,
            "neckline": neck,
            "lower": lower,
        }
    )

    # —— 看多：确认多头站上颈线 / 巩固上破 ——
    bull_ok = False
    if st == "confirmed" and t in BULLISH_REVERSAL and close is not None and neck is not None:
        if close > neck * BREAKOUT_UP_MULT:
            bull_ok = True
            rationale_bits.append(f"已确认{lab}且站上颈线")
    if st == "confirmed" and t in CONSOLIDATION:
        if consol_break_dir(primary) == "up":
            bull_ok = True
            if f"已确认{lab}上破" not in "".join(rationale_bits):
                rationale_bits.append(f"已确认{lab}上破")

    evidence.append(
        {
            "code": "pattern_confirmed_neck",
            "ok": bull_ok and t in BULLISH_REVERSAL,
            "pattern_type": t,
            "status": st,
            "close": close,
            "neckline": neck,
        }
    )
    evidence.append(
        {
            "code": "pattern_consol_break_up",
            "ok": bull_ok and t in CONSOLIDATION,
            "pattern_type": t,
            "status": st,
            "dir": consol_break_dir(primary) if t in CONSOLIDATION else None,
        }
    )

    # —— 震荡：forming / 交织 / 强压 ——
    forming_ok = st == "forming"
    pressure_ok = pressure is not None
    evidence.append({"code": "pattern_forming", "ok": forming_ok, "pattern_type": t})
    evidence.append(
        {
            "code": "bias_mix",
            "ok": mix,
        }
    )
    evidence.append(
        {
            "code": "resonance_pressure",
            "ok": pressure_ok,
            "min_strength": float(resonance_min_strength),
            "strength": _zone_strength(pressure) if pressure else None,
            "center": _f(pressure.get("center")) if pressure else None,
        }
    )

    if bear_ok:
        short_bias = "看空"
        bias_label = _BIAS_LABEL["看空"]
    elif bull_ok:
        # 主标签只由形态确认站上/上破决定；强压仅写入旁证，不改看多
        short_bias = "看多"
        bias_label = _BIAS_LABEL["看多"]
        if pressure_ok:
            rationale_bits.append("上方仍有高强度共振压力，注意回踩节奏")
    elif forming_ok or mix or pressure_ok:
        short_bias = "震荡"
        bias_label = _BIAS_LABEL["震荡"]
        if forming_ok:
            rationale_bits.append(f"形成中的{lab}，边界未完全突破")
        if mix:
            rationale_bits.append("多空形态交织，宜按宽幅箱体观察")
        if pressure_ok:
            rationale_bits.append(
                f"近端共振压力强度≥{float(resonance_min_strength):.0f}，蓄势夹击"
            )
    else:
        short_bias = "震荡"
        bias_label = _BIAS_LABEL["震荡"]
        rationale_bits.append(f"主导{lab}（{st}）暂无明确突破方向")

    # —— 增强：仅抬 grade，不改 short_bias ——
    vp_ok = _vp_break_vah_ok(vp, close)
    rpe_ok, z_val = _rpe_lead_ok(rpe, z_lead=float(z_lead))
    evidence.append(
        {
            "code": "vp_break_vah",
            "ok": vp_ok,
            "vah": _f(vp.get("vah")) if isinstance(vp, dict) else None,
            "nearest_resistance": (
                vp.get("nearest_resistance") if isinstance(vp, dict) else None
            ),
        }
    )
    evidence.append(
        {
            "code": "rpe_lead",
            "ok": rpe_ok,
            "z_score": z_val,
            "z_lead": float(z_lead),
            "signal_type": (rpe.get("signal_type") if isinstance(rpe, dict) else None),
        }
    )

    enhancers = 0
    if vp_ok:
        enhancers += 1
        rationale_bits.append("已破VAH且上方无近端筹码压制")
    if rpe_ok:
        enhancers += 1
        rationale_bits.append(f"RPE Z≥{float(z_lead):.1f}")

    if enhancers >= 2:
        grade = "strong"
    elif enhancers == 1:
        grade = "enhanced"
    else:
        grade = "base"

    # 置信：结构底分 + 形态 conf + 增强
    base_c = 0.45 + 0.35 * min(1.0, conf)
    if short_bias == "看空":
        base_c = 0.5 + 0.3 * min(1.0, conf)
    elif short_bias == "震荡":
        base_c = 0.35 + 0.25 * min(1.0, conf)
    base_c += 0.08 * enhancers
    confidence = round(max(0.05, min(0.95, base_c)), 3)

    if not rationale_bits:
        rationale_bits.append(f"主导形态 {lab}（{st}）")
    rationale = "；".join(rationale_bits)

    return {
        "short_bias": short_bias,
        "bias_label": bias_label,
        "grade": grade,
        "confidence": confidence,
        "rationale": rationale,
        "evidence": evidence,
        "primary": primary,
        "pressure_zone": pressure,
    }


def build_buy_hints(
    short_bias: str,
    primary: Optional[Dict[str, Any]] = None,
    *,
    confluence: Optional[Dict[str, Any]] = None,
    grade: str = "base",
    pressure_zone: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """按三态输出买点；看空返回空列表 + risk_note。"""
    hints: List[Dict[str, Any]] = []
    risk_note: Optional[str] = None

    if short_bias == "看空":
        defense = _core_defense(primary) if primary else None
        neck = _hit_neck(primary) if primary else None
        upper, lower = _hit_bounds(primary) if primary else (None, None)
        bits = ["结构破位，不宜抄底"]
        if defense is not None:
            bits.append(f"破位参考 {defense:.2f}")
        press = neck if neck is not None else upper
        if press is not None:
            bits.append(f"上方反抽压制关注 {press:.2f}")
        if lower is not None and defense is None:
            bits.append(f"下沿 {lower:.2f}")
        risk_note = "；".join(bits) + "。"
        return hints, risk_note

    if short_bias == "insufficient" or primary is None:
        return hints, risk_note

    neck = _hit_neck(primary)
    upper, lower = _hit_bounds(primary)
    defense = _core_defense(primary)
    target = measured_target(primary)
    # 近端阻力作目标候选
    if target is None and isinstance(confluence, dict):
        nz = confluence.get("nearest_resistance_zone")
        if isinstance(nz, dict):
            target = _f(nz.get("center")) or _f(nz.get("low"))

    nearest_support = None
    if isinstance(confluence, dict):
        ns = confluence.get("nearest_support_zone")
        if isinstance(ns, dict):
            nearest_support = _f(ns.get("center")) or _f(ns.get("high"))

    if short_bias == "看多":
        anchor_px = neck if neck is not None else (upper if upper is not None else defense)
        if anchor_px is None:
            return hints, risk_note
        band = max(0.02, abs(anchor_px) * 0.008)
        entry = {
            "low": round(anchor_px - band, 2),
            "high": round(anchor_px + band * 0.5, 2),
            "anchor": "neckline" if neck is not None else "structure",
        }
        # strong/enhanced 用 pullback_buy；base 降为 watch 或降低 priority
        if grade in ("strong", "enhanced"):
            hint_type = "pullback_buy"
            priority = 1 if grade == "strong" else 2
            trigger = "回踩颈线/翻支撑企稳"
        else:
            hint_type = "watch"
            priority = 3
            trigger = "回踩结构位企稳（缺 VP/RPE 增强，仅观察）"
        hints.append(
            {
                "type": hint_type,
                "entry_zone": entry,
                "trigger": trigger,
                "invalidation": round(defense, 2) if defense is not None else None,
                "target": round(target, 2) if target is not None else None,
                "priority": priority,
            }
        )
        return hints, risk_note

    # 震荡：watch → 下沿/近端支撑；强压下不追多
    if pressure_zone is not None:
        risk_note = "近端高强度共振压力压制，不在强压力下追多；等下沿承接或有效突破压力。"
    anchor = lower if lower is not None else nearest_support
    if anchor is None and nearest_support is not None:
        anchor = nearest_support
    if anchor is None:
        return hints, risk_note
    band = max(0.02, abs(anchor) * 0.008)
    hints.append(
        {
            "type": "watch",
            "entry_zone": {
                "low": round(anchor - band, 2),
                "high": round(anchor + band, 2),
                "anchor": "pattern_lower" if lower is not None else "nearest_support",
            },
            "trigger": "回踩形态下沿/近端支撑企稳",
            "invalidation": round(anchor * BREAKOUT_DOWN_MULT, 2),
            "target": round(upper, 2) if upper is not None else (
                round(target, 2) if target is not None else None
            ),
            "priority": 2,
        }
    )
    return hints, risk_note


def build_pattern_tactical(
    hits: Optional[Sequence[Dict[str, Any]]] = None,
    *,
    confluence: Optional[Dict[str, Any]] = None,
    vp: Optional[Dict[str, Any]] = None,
    rpe: Optional[Dict[str, Any]] = None,
    invalidated_count: int = 0,
    resonance_min_strength: float = RESONANCE_PRESSURE_MIN_STRENGTH,
    z_lead: float = DEFAULT_Z_LEAD,
    trade_advice: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """统一出口：short_bias + grade + buy_hints + disclaimer。"""
    classified = classify_short_bias(
        hits,
        confluence=confluence,
        vp=vp,
        rpe=rpe,
        invalidated_count=invalidated_count,
        resonance_min_strength=resonance_min_strength,
        z_lead=z_lead,
    )
    evidence = list(classified.get("evidence") or [])

    # 四策略 trade_advice 软旁证，不硬绑
    if isinstance(trade_advice, dict):
        action = str(trade_advice.get("action") or "").strip().lower()
        evidence.append(
            {
                "code": "trade_advice_soft",
                "ok": action == "buy",
                "action": action or None,
            }
        )

    hints, risk_note = build_buy_hints(
        str(classified.get("short_bias") or "insufficient"),
        classified.get("primary"),
        confluence=confluence,
        grade=str(classified.get("grade") or "base"),
        pressure_zone=classified.get("pressure_zone"),
    )

    return {
        "short_bias": classified.get("short_bias"),
        "bias_label": classified.get("bias_label"),
        "grade": classified.get("grade"),
        "confidence": classified.get("confidence"),
        "rationale": classified.get("rationale"),
        "evidence": evidence,
        "buy_hints": hints,
        "risk_note": risk_note,
        "disclaimer": DISCLAIMER,
    }
