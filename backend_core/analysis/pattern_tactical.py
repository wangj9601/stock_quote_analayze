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

# 高强度共振压制门槛（附件示例 >50；可配置）——仅用于 short_bias 震荡旁证，不改买点贴压门槛
RESONANCE_PRESSURE_MIN_STRENGTH = 50.0
# 买点侧贴身超强压：与 bias 的 50 解耦，强度≥10 且贴压 → 强制 break_upper
BUY_PRESSURE_MIN_STRENGTH = 10.0
BUY_PRESSURE_NEAR_PCT = 0.02  # 现价在带内，或距阻力中心/下沿 ≤约 2%
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
    "箱体震荡": "箱体震荡",
}

# 旁路：归档空头「仍在颈线下」收紧（600722：贴颈回攻≠结构破位）
BYPASS_BEAR_NEAR_PCT = 0.015  # 距颈线 ≤1.5% → 逼近压力（震荡），不看空
BYPASS_BEAR_DEEP_PCT = 0.03  # 至少深破 3% 才允许旁路看空
BYPASS_BEAR_STALE_DAYS = 90  # 形成日距 asof 超过该日历日 → 陈旧
BYPASS_BEAR_STALE_DEEP_PCT = 0.08  # 陈旧归档空头须更深破才看空
# 放量长阳：否决旁路看空 → 震荡
MOMENTUM_UP_PCT = 0.04
MOMENTUM_VOL_RATIO = 1.8
MOMENTUM_UP_PCT_STRONG = 0.055  # 单日涨幅足够大时可只靠涨幅否决
# 失效位须严格低于买入下沿（相对 1%，再与最小价差取严）
INVALIDATION_BELOW_ENTRY_PCT = 0.01
INVALIDATION_MIN_GAP_ABS = 0.01
INVALIDATION_MIN_GAP_PCT = 0.002
# 近端超强共振优先于远端形态下沿（震荡 watch / 看多旁路可复用）
NEAR_SUPPORT_PREF_MIN_STRENGTH = 10.0  # A 档：近端共振优先的最低强度
PATTERN_LOWER_FAR_PCT = 0.25  # 形态下沿相对现价偏离 ≥25% 视为「过远」→ 禁止作 p≤2 主锚
NEAR_SUPPORT_MAX_BELOW_PCT = 0.06  # A 档：近端支撑须在现价下方且距现价 ≤6%
# 仅 floor_far 分支启用的 B 档 / 第二档 watch（非 floor_far 仍只用 A 档，避免伤正常路径）
NEAR_SUPPORT_B_MIN_STRENGTH = 5.0
NEAR_SUPPORT_B_MAX_BELOW_PCT = 0.08
NEAR_SUPPORT_WATCH2_MIN_STRENGTH = 5.0
NEAR_SUPPORT_WATCH2_MAX_BELOW_PCT = 0.15  # 更远近端约 12–15%
TARGET_MIN_UPSIDE_PCT = 0.02  # 主目标相对现价/突破入场 upside 不足约 2% 时触发 RR 改锚
BREAK_TARGET_MIN_STRENGTH = 5.0  # 突破后「下一档有效阻力」最低强度（弱 Camarilla 等不抢主目标）
BREAK_TARGET_MIN_RR = 1.0  # 相对失效的最小盈亏比；形态上沿过薄时不得单独作 target
FIB_0382_RATIO = 0.382  # 左右侧近端 watch 共用失效位优先对齐 Fib 0.382


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


def _clamp_invalidation(
    entry_low: Optional[float], inv: Optional[float]
) -> Optional[float]:
    """保证 invalidation < entry_zone.low，且至少低于 low 约 1%（与最小价差取严）。"""
    low = _f(entry_low)
    if low is None or low <= 0:
        return round(_f(inv), 2) if _f(inv) is not None else None
    cap_pct = low * (1.0 - float(INVALIDATION_BELOW_ENTRY_PCT))
    gap = max(float(INVALIDATION_MIN_GAP_ABS), abs(low) * float(INVALIDATION_MIN_GAP_PCT))
    cap_gap = low - gap
    cap = min(cap_pct, cap_gap)
    if cap >= low:
        cap = low * (1.0 - float(INVALIDATION_BELOW_ENTRY_PCT))
    inv_f = _f(inv)
    if inv_f is None or inv_f > cap or inv_f >= low:
        return round(cap, 2)
    return round(inv_f, 2)


def _with_clamped_invalidation(hint: Dict[str, Any]) -> Dict[str, Any]:
    """就地钳制 buy_hint.invalidation；无 entry_zone.low 则原样返回。"""
    ez = hint.get("entry_zone")
    if not isinstance(ez, dict):
        return hint
    low = _f(ez.get("low"))
    if low is None:
        return hint
    hint["invalidation"] = _clamp_invalidation(low, hint.get("invalidation"))
    return hint


def _iter_confluence_supports(confluence: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """合并 nearest_support_zone + supports[]，按 strength 降序去重。"""
    if not isinstance(confluence, dict):
        return []
    raw: List[Dict[str, Any]] = []
    ns = confluence.get("nearest_support_zone")
    if isinstance(ns, dict):
        raw.append(ns)
    for z in confluence.get("supports") or []:
        if isinstance(z, dict):
            raw.append(z)
    seen = set()
    out: List[Dict[str, Any]] = []
    for z in raw:
        center = _f(z.get("center"))
        lo = _f(z.get("low"))
        hi = _f(z.get("high"))
        key = (round(center, 4) if center is not None else None, lo, hi)
        if key in seen:
            continue
        seen.add(key)
        out.append(z)
    out.sort(
        key=lambda z: (
            -(_f(z.get("strength")) or 0.0),
            -(_f(z.get("center")) or 0.0),
        )
    )
    return out


def _pick_near_strong_support(
    confluence: Optional[Dict[str, Any]],
    close: Optional[float],
    *,
    min_strength: Optional[float] = None,
    max_below_pct: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """现价下方、距现价达标、强度达标的最优近端共振支撑。

    默认 A 档：strength≥10 且 ≤6%。floor_far 分支可放宽为 B 档（5/8%）。
    """
    c = _f(close)
    if c is None or c <= 0:
        return None
    min_s = float(
        NEAR_SUPPORT_PREF_MIN_STRENGTH if min_strength is None else min_strength
    )
    max_pct = float(
        NEAR_SUPPORT_MAX_BELOW_PCT if max_below_pct is None else max_below_pct
    )
    for z in _iter_confluence_supports(confluence):
        center = _f(z.get("center"))
        high = _f(z.get("high"))
        strength = _f(z.get("strength")) or 0.0
        if strength < min_s:
            continue
        # center/high 均须在 close 下方
        if center is not None and center >= c:
            continue
        if high is not None and high >= c:
            continue
        ref = center if center is not None else high
        if ref is None:
            continue
        below_pct = (c - ref) / c
        if below_pct < 0 or below_pct > max_pct:
            continue
        return z
    return None


def _zone_key(z: Optional[Dict[str, Any]]) -> Tuple[Any, Any, Any]:
    if not isinstance(z, dict):
        return (None, None, None)
    center = _f(z.get("center"))
    return (
        round(center, 4) if center is not None else None,
        _f(z.get("low")),
        _f(z.get("high")),
    )


def _pick_near_support_floor_far(
    confluence: Optional[Dict[str, Any]],
    close: Optional[float],
) -> Optional[Dict[str, Any]]:
    """floor_far 专用：先 A 档（10/6%），再 B 档（5/8%）。"""
    a = _pick_near_strong_support(confluence, close)
    if a is not None:
        return a
    return _pick_near_strong_support(
        confluence,
        close,
        min_strength=float(NEAR_SUPPORT_B_MIN_STRENGTH),
        max_below_pct=float(NEAR_SUPPORT_B_MAX_BELOW_PCT),
    )


def _pick_near_support_watch2(
    confluence: Optional[Dict[str, Any]],
    close: Optional[float],
    *,
    primary: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """floor_far 第二档：更远近端（strength≥5，距离可到约 12–15%），排除主近端。"""
    c = _f(close)
    if c is None or c <= 0:
        return None
    primary_key = _zone_key(primary)
    primary_ref = None
    if isinstance(primary, dict):
        primary_ref = _f(primary.get("center"))
        if primary_ref is None:
            primary_ref = _f(primary.get("high"))
    best: Optional[Dict[str, Any]] = None
    best_ref = -1.0
    for z in _iter_confluence_supports(confluence):
        if _zone_key(z) == primary_key:
            continue
        center = _f(z.get("center"))
        high = _f(z.get("high"))
        strength = _f(z.get("strength")) or 0.0
        if strength < float(NEAR_SUPPORT_WATCH2_MIN_STRENGTH):
            continue
        if center is not None and center >= c:
            continue
        if high is not None and high >= c:
            continue
        ref = center if center is not None else high
        if ref is None:
            continue
        below_pct = (c - ref) / c
        if below_pct <= 0 or below_pct > float(NEAR_SUPPORT_WATCH2_MAX_BELOW_PCT):
            continue
        # 须明显远于主近端（若有）
        if primary_ref is not None and ref >= primary_ref - 1e-9:
            continue
        if ref > best_ref:
            best_ref = ref
            best = z
    return best


def _iter_confluence_resistances(
    confluence: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not isinstance(confluence, dict):
        return []
    raw: List[Dict[str, Any]] = []
    nz = confluence.get("nearest_resistance_zone")
    if isinstance(nz, dict):
        raw.append(nz)
    for z in confluence.get("resistances") or []:
        if isinstance(z, dict):
            raw.append(z)
    seen = set()
    out: List[Dict[str, Any]] = []
    for z in raw:
        key = _zone_key(z)
        if key in seen:
            continue
        seen.add(key)
        out.append(z)
    return out


def _pressing_resistance_for_buy(
    confluence: Optional[Dict[str, Any]],
    close: Optional[float],
    *,
    min_strength: float = BUY_PRESSURE_MIN_STRENGTH,
    near_pct: float = BUY_PRESSURE_NEAR_PCT,
) -> Optional[Dict[str, Any]]:
    """贴身超强压：在带内或距中心/下沿 ≤near_pct，且 strength≥买点门槛。"""
    c = _f(close)
    if c is None or c <= 0:
        return None
    best: Optional[Dict[str, Any]] = None
    best_dist = float("inf")
    for z in _iter_confluence_resistances(confluence):
        strength = _f(z.get("strength")) or 0.0
        if strength < float(min_strength):
            continue
        lo = _f(z.get("low"))
        hi = _f(z.get("high"))
        center = _f(z.get("center"))
        inside = lo is not None and hi is not None and lo <= c <= hi
        near = False
        for ref in (center, lo):
            if ref is None or ref <= 0:
                continue
            if abs(c - ref) / c <= float(near_pct):
                near = True
                break
        if not inside and not near:
            continue
        anchor = center if center is not None else (lo if lo is not None else hi)
        dist = abs(c - anchor) if anchor is not None else float("inf")
        if dist < best_dist:
            best_dist = dist
            best = z
    return best


def _break_level_from_resistance(zone: Dict[str, Any]) -> Optional[float]:
    """上破观察位：优先带上沿，其次中心。"""
    hi = _f(zone.get("high"))
    if hi is not None:
        return hi
    return _f(zone.get("center")) or _f(zone.get("low"))


def _farther_resistance_target(
    confluence: Optional[Dict[str, Any]],
    close: Optional[float],
    *,
    above: Optional[float],
    upper: Optional[float],
) -> Optional[float]:
    """突破目标：更远阻力中心，否则形态上沿。"""
    c = _f(close)
    floor_ref = _f(above) or (c if c is not None else None)
    best: Optional[float] = None
    for z in _iter_confluence_resistances(confluence):
        center = _f(z.get("center")) or _f(z.get("low"))
        if center is None or c is None:
            continue
        if center <= c:
            continue
        if floor_ref is not None and center <= floor_ref * (1.0 + float(TARGET_MIN_UPSIDE_PCT)):
            continue
        if best is None or center < best:
            best = center
    if best is not None:
        return best
    u = _f(upper)
    if u is not None and c is not None and u > c:
        return u
    return u


def _break_entry_refs(break_px: float) -> Tuple[float, float, float]:
    """突破观察入场：中位参考、入场上沿、失效位（与 _hint_watch_break_upper 同口径）。"""
    bp = float(break_px)
    band = max(0.02, abs(bp) * 0.008)
    entry_hi = bp + band
    inv = bp * float(BREAKOUT_DOWN_MULT)
    return bp, entry_hi, inv


def _target_upside_ok(entry_ref: float, target: float) -> bool:
    return float(target) > float(entry_ref) * (1.0 + float(TARGET_MIN_UPSIDE_PCT))


def _target_rr_ok(entry_hi: float, inv: float, target: float) -> bool:
    risk = float(entry_hi) - float(inv)
    reward = float(target) - float(entry_hi)
    if risk <= 1e-12:
        return reward > 0
    return (reward / risk) >= float(BREAK_TARGET_MIN_RR)


def _pattern_upper_viable_as_break_target(break_px: float, upper: float) -> bool:
    """形态上沿可作突破目标：相对入场 upside 足够，且相对失效 RR 不倒挂。"""
    _, entry_hi, inv = _break_entry_refs(break_px)
    u = float(upper)
    if not _target_upside_ok(break_px, u):
        return False
    if not _target_upside_ok(entry_hi, u):
        return False
    return _target_rr_ok(entry_hi, inv, u)


def _next_resistance_above(
    confluence: Optional[Dict[str, Any]],
    *,
    gate: float,
    entry_ref: float,
    min_strength: float = BREAK_TARGET_MIN_STRENGTH,
) -> Optional[float]:
    """gate 之上最近一档阻力；优先 strength≥门槛，否则退回任意足够 upside 的阻力。"""
    best_strong: Optional[float] = None
    best_any: Optional[float] = None
    g = float(gate)
    for z in _iter_confluence_resistances(confluence):
        center = _f(z.get("center")) or _f(z.get("low"))
        if center is None or center <= g:
            continue
        if not _target_upside_ok(entry_ref, center):
            continue
        strength = _f(z.get("strength")) or 0.0
        if best_any is None or center < best_any:
            best_any = center
        if strength < float(min_strength):
            continue
        if best_strong is None or center < best_strong:
            best_strong = center
    return best_strong if best_strong is not None else best_any


def _resolve_break_upper_target(
    confluence: Optional[Dict[str, Any]],
    close: Optional[float],
    *,
    break_px: float,
    upper: Optional[float],
    primary_tgt: Optional[float],
) -> Optional[float]:
    """break_upper 主目标：优先 max(合格形态上沿, 上沿之上下一档有效阻力)。

    形态上沿是突破确认位，不是默认可单独落袋的盈利目标；
    相对突破入场区 upside 过薄或 RR 倒挂时，不得单独用形态上沿作唯一 target。
    """
    bp = float(break_px)
    u_pref = _f(upper) if upper is not None else _f(primary_tgt)
    # 下一档搜索门闸：有形态上沿则从其上方找；否则从突破位+最小 upside 起
    if u_pref is not None:
        gate = max(u_pref, bp * (1.0 + float(TARGET_MIN_UPSIDE_PCT)))
    else:
        gate = bp * (1.0 + float(TARGET_MIN_UPSIDE_PCT))

    next_res = _next_resistance_above(
        confluence, gate=gate, entry_ref=bp
    )
    upper_cand = None
    if u_pref is not None and _pattern_upper_viable_as_break_target(bp, u_pref):
        upper_cand = u_pref

    if next_res is not None and upper_cand is not None:
        return max(float(next_res), float(upper_cand))
    if next_res is not None:
        return float(next_res)
    if upper_cand is not None:
        return float(upper_cand)

    alt = _farther_resistance_target(
        confluence, close, above=bp, upper=upper or primary_tgt
    )
    if alt is not None:
        return alt
    return u_pref


def _fib_ratio_price(
    confluence: Optional[Dict[str, Any]],
    *,
    ratio: float = FIB_0382_RATIO,
) -> Optional[float]:
    """从 confluence 带 labels 或嵌套 fibonacci.retracements 取指定回撤价。"""
    if not isinstance(confluence, dict):
        return None
    ratio_f = float(ratio)
    ratio_tags = (
        f"fib_{ratio_f}",
        f"fib_{ratio_f:.3f}",
        f"fib_{ratio_f:.2f}",
        "fib_0.382",
        "fib_0.38",
    )

    def _from_zone(z: Dict[str, Any]) -> Optional[float]:
        labels = z.get("labels") or z.get("methods") or []
        labs = [str(x) for x in labels] if isinstance(labels, (list, tuple)) else []
        joined = " ".join(labs).lower()
        hit = any(tag in joined for tag in ratio_tags) or (
            "fib" in joined and "0.382" in joined
        )
        if not hit:
            return None
        return _f(z.get("center")) or _f(z.get("low"))

    for z in _iter_confluence_supports(confluence):
        px = _from_zone(z)
        if px is not None:
            return px
    for z in _iter_confluence_resistances(confluence):
        px = _from_zone(z)
        if px is not None:
            return px

    fib = confluence.get("fibonacci")
    if isinstance(fib, dict):
        for x in fib.get("retracements") or []:
            if not isinstance(x, dict):
                continue
            r = _f(x.get("ratio"))
            if r is None:
                continue
            if abs(r - ratio_f) <= 0.01:
                px = _f(x.get("price"))
                if px is not None:
                    return px
    return None


def _apply_shared_near_invalidation(
    hints: List[Dict[str, Any]],
    *,
    fib_px: Optional[float],
) -> None:
    """左右侧 near_support_pref watch 共用更紧失效位（优先 Fib 0.382），再经 clamp。"""
    near_hints = [
        h
        for h in hints
        if isinstance(h, dict)
        and isinstance(h.get("entry_zone"), dict)
        and h["entry_zone"].get("anchor") == "near_support_pref"
    ]
    if not near_hints:
        return
    raw_cands: List[float] = []
    for h in near_hints:
        lo = _f(h["entry_zone"].get("low"))
        if lo is not None:
            raw_cands.append(lo)
        inv0 = _f(h.get("invalidation"))
        if inv0 is not None:
            raw_cands.append(inv0)
    fib = _f(fib_px)
    if fib is not None:
        raw_cands.append(fib)
    if not raw_cands:
        return
    shared_raw = min(raw_cands)
    for h in near_hints:
        lo = _f(h["entry_zone"].get("low"))
        h["invalidation"] = _clamp_invalidation(lo, shared_raw)


def _level_far_below(close: Optional[float], level: Optional[float]) -> bool:
    c = _f(close)
    lv = _f(level)
    if c is None or lv is None or c <= 0:
        return False
    if lv >= c:
        return False
    return (c - lv) / c >= float(PATTERN_LOWER_FAR_PCT)


def _target_thin_upside(close: Optional[float], target: Optional[float]) -> bool:
    """目标相对现价 upside < 约 2%（或 target <= close*1.02）。"""
    c = _f(close)
    t = _f(target)
    if c is None or t is None or c <= 0:
        return False
    return t <= c * (1.0 + float(TARGET_MIN_UPSIDE_PCT))


def _nearest_resistance_px(confluence: Optional[Dict[str, Any]]) -> Optional[float]:
    if not isinstance(confluence, dict):
        return None
    nz = confluence.get("nearest_resistance_zone")
    if isinstance(nz, dict):
        px = _f(nz.get("center")) or _f(nz.get("low"))
        if px is not None:
            return px
    for z in confluence.get("resistances") or []:
        if not isinstance(z, dict):
            continue
        px = _f(z.get("center")) or _f(z.get("low"))
        if px is not None:
            return px
    return None


def _entry_zone_from_support(zone: Dict[str, Any]) -> Dict[str, Any]:
    """entry 用 zone low/high，否则 center±band。"""
    center = _f(zone.get("center"))
    lo = _f(zone.get("low"))
    hi = _f(zone.get("high"))
    strength = _f(zone.get("strength"))
    if lo is not None and hi is not None and lo <= hi:
        entry_lo, entry_hi = lo, hi
    else:
        anchor = center if center is not None else (lo if lo is not None else hi)
        if anchor is None:
            return {"low": None, "high": None, "anchor": "near_support_pref"}
        band = max(0.02, abs(anchor) * 0.008)
        entry_lo = lo if lo is not None else (anchor - band)
        entry_hi = hi if hi is not None else (anchor + band)
    ez: Dict[str, Any] = {
        "low": round(entry_lo, 2),
        "high": round(entry_hi, 2),
        "anchor": "near_support_pref",
    }
    if center is not None:
        ez["center"] = round(center, 2)
    if strength is not None:
        ez["strength"] = round(strength, 3)
    return ez


def _hint_near_support_pref(
    zone: Dict[str, Any],
    *,
    target: Optional[float],
    priority: int = 2,
    trigger: str = "回踩近端高强度共振支撑企稳（形态下沿过远，优先近端）",
) -> Dict[str, Any]:
    ez = _entry_zone_from_support(zone)
    raw_inv = _f(zone.get("low"))
    if raw_inv is None:
        raw_inv = _f(ez.get("low"))
    return _with_clamped_invalidation(
        {
            "type": "watch",
            "entry_zone": ez,
            "trigger": trigger,
            "invalidation": round(raw_inv, 2) if raw_inv is not None else None,
            "target": round(target, 2) if target is not None else None,
            "priority": priority,
        }
    )


def _hint_far_pattern_lower(
    floor: float,
    *,
    target: Optional[float],
    anchor: str = "pattern_lower_far",
) -> Dict[str, Any]:
    band = max(0.02, abs(floor) * 0.008)
    return _with_clamped_invalidation(
        {
            "type": "watch",
            "entry_zone": {
                "low": round(floor - band, 2),
                "high": round(floor + band, 2),
                "anchor": anchor,
            },
            "trigger": "远端形态下沿仅作极限参考",
            "invalidation": round(floor * BREAKOUT_DOWN_MULT, 2),
            "target": round(target, 2) if target is not None else None,
            "priority": 4,
        }
    )


def _hint_watch_break_upper(
    upper: float,
    *,
    target: Optional[float],
    trigger: Optional[str] = None,
    priority: int = 2,
) -> Dict[str, Any]:
    band = max(0.02, abs(upper) * 0.008)
    trig = trigger or (
        f"观察上破 {upper:.2f} 再跟；远端下沿不作主买点（目标空间不足）"
    )
    return _with_clamped_invalidation(
        {
            "type": "watch",
            "entry_zone": {
                "low": round(upper - band * 0.25, 2),
                "high": round(upper + band, 2),
                "anchor": "break_upper",
            },
            "trigger": trig,
            "invalidation": round(upper * BREAKOUT_DOWN_MULT, 2),
            "target": round(target, 2) if target is not None else None,
            "priority": priority,
        }
    )


def _resolve_watch_target(
    close: Optional[float],
    primary_target: Optional[float],
    confluence: Optional[Dict[str, Any]],
    upper: Optional[float],
) -> Optional[float]:
    """主目标 upside 过薄时改用 confluence 上方阻力。"""
    tgt = primary_target
    if not _target_thin_upside(close, tgt):
        return tgt
    alt = _nearest_resistance_px(confluence)
    c = _f(close)
    if alt is not None and c is not None and alt > c * (1.0 + float(TARGET_MIN_UPSIDE_PCT)):
        return alt
    # 仍薄则保留 upper / 原 target，由调用方决定是否改「上破再跟」
    if upper is not None and c is not None and upper > c:
        return upper
    return tgt


def _hit_box_bounds(
    h: Optional[Dict[str, Any]],
) -> Tuple[Optional[float], Optional[float]]:
    if not isinstance(h, dict):
        return None, None
    lv = _hit_levels(h)
    bl = _f(lv.get("box_low"))
    bh = _f(lv.get("box_high"))
    if bl is None:
        bl = _f(h.get("box_low"))
    if bh is None:
        bh = _f(h.get("box_high"))
    return bl, bh


def _flag_bias_mix(h: Dict[str, Any]) -> bool:
    if h.get("bias_mix") or h.get("range_box"):
        return True
    lv = _hit_levels(h)
    return bool(lv.get("bias_mix") or lv.get("range_box"))


def _has_double_top_bottom(hits: Sequence[Dict[str, Any]]) -> bool:
    types = {str(h.get("pattern_type") or "") for h in hits if isinstance(h, dict)}
    return "double_top" in types and "double_bottom" in types


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


def _is_bullish_side(bias: str) -> bool:
    return bias in ("bull", "bullish_bias")


def _is_bearish_side(bias: str) -> bool:
    return bias in ("bear", "bearish_bias")


def _reason_upside_invalidate(h: Dict[str, Any]) -> bool:
    """空头巩固/反转因向上脱离而失效（reason 文案或价位）。"""
    reason = str(h.get("reason") or "")
    if "向上脱离" in reason or "向上突破" in reason:
        return True
    close = _hit_close(h)
    upper, _lower = _hit_bounds(h)
    if close is not None and upper is not None and upper > 0 and close > upper * BREAKOUT_UP_MULT:
        return True
    # 空头反转：收盘重新站上颈线 → 失效语义偏多
    neck = _hit_neck(h)
    t = str(h.get("pattern_type") or "")
    if (
        t in BEARISH_REVERSAL
        and close is not None
        and neck is not None
        and neck > 0
        and close > neck * BREAKOUT_UP_MULT
    ):
        return True
    return False


def _reason_downside_invalidate(h: Dict[str, Any]) -> bool:
    reason = str(h.get("reason") or "")
    if "向下脱离" in reason or "向下跌破" in reason:
        return True
    close = _hit_close(h)
    _upper, lower = _hit_bounds(h)
    if close is not None and lower is not None and lower > 0 and close < lower * BREAKOUT_DOWN_MULT:
        return True
    neck = _hit_neck(h)
    t = str(h.get("pattern_type") or "")
    if (
        t in BULLISH_REVERSAL
        and close is not None
        and neck is not None
        and neck > 0
        and close < neck * BREAKOUT_DOWN_MULT
    ):
        return True
    return False


def _hit_formed_at(h: Dict[str, Any]) -> str:
    return str(h.get("formed_at") or h.get("confirm_date") or "")[:10]


def _calendar_days_between(a: str, b: str) -> Optional[int]:
    """两日期间隔（日历日）；解析失败返回 None。"""
    if not a or not b:
        return None
    try:
        from datetime import date

        d0 = date.fromisoformat(str(a)[:10])
        d1 = date.fromisoformat(str(b)[:10])
        return abs((d1 - d0).days)
    except ValueError:
        return None


def _neck_gap_pct_below(close: float, neck: float) -> Optional[float]:
    """现价在颈线下方的相对距离 (neck-close)/neck；上方则 None。"""
    if neck is None or neck <= 0 or close is None:
        return None
    if close >= neck:
        return None
    return (neck - close) / neck


def _is_stale_archive(h: Dict[str, Any], asof: Optional[str]) -> bool:
    formed = _hit_formed_at(h)
    days = _calendar_days_between(formed, str(asof or "")[:10])
    if days is None:
        return False
    return days >= int(BYPASS_BEAR_STALE_DAYS)


def _strong_up_momentum(market: Optional[Dict[str, Any]]) -> bool:
    """放量长阳：否决旁路看空。"""
    if not isinstance(market, dict):
        return False
    chg = _f(market.get("change_pct"))
    vol_r = _f(market.get("volume_ratio"))
    if chg is None or chg < float(MOMENTUM_UP_PCT):
        return False
    if chg >= float(MOMENTUM_UP_PCT_STRONG):
        return True
    return vol_r is not None and vol_r >= float(MOMENTUM_VOL_RATIO)


def market_snapshot_from_bars(bars: Optional[Sequence[Dict[str, Any]]]) -> Dict[str, Any]:
    """从日线末两根推算涨跌幅与量比（相对前 20 日均量）。"""
    seq = [b for b in (bars or []) if isinstance(b, dict)]
    out: Dict[str, Any] = {
        "change_pct": None,
        "volume_ratio": None,
        "last_close": None,
    }
    if len(seq) < 2:
        return out
    c0 = _f(seq[-1].get("close"))
    c1 = _f(seq[-2].get("close"))
    out["last_close"] = c0
    if c0 is not None and c1 is not None and c1 > 0:
        out["change_pct"] = round((c0 - c1) / c1, 6)
    vols: List[float] = []
    for b in seq[-21:-1]:
        v = _f(b.get("volume"))
        if v is not None and v > 0:
            vols.append(v)
    v_last = _f(seq[-1].get("volume"))
    if v_last is not None and vols:
        avg = sum(vols) / len(vols)
        if avg > 0:
            out["volume_ratio"] = round(v_last / avg, 4)
    return out


def _inactive_bypass(
    hits: Optional[Sequence[Dict[str, Any]]],
    *,
    asof: Optional[str] = None,
    market: Optional[Dict[str, Any]] = None,
    vp: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[str], Optional[Dict[str, Any]], str, Optional[str]]:
    """无活跃命中时的结构旁路。

    返回 (short_bias|None, primary_for_hints, rationale_bit, bias_label_override|None)。

    - 空头形态向上失效 → 看多
    - 多头形态向下失效 → 看空
    - 归档多头且现价仍在颈线上方 → 看多（测幅兑现后的趋势延伸）
    - 归档空头：须深破颈线才看空；贴颈/陈旧回攻 → 震荡（逼近压力）
    - 旁路冲突：按形成日新旧择主；接近则震荡
    - 放量长阳 / 破 VAH 贴颈：否决旁路看空 → 震荡
    """
    bull_cand: Optional[Dict[str, Any]] = None
    bear_cand: Optional[Dict[str, Any]] = None
    range_cand: Optional[Dict[str, Any]] = None
    bull_why = ""
    bear_why = ""
    range_why = ""
    range_label: Optional[str] = None

    for h in hits or []:
        if not isinstance(h, dict):
            continue
        st = str(h.get("status") or "")
        t = str(h.get("pattern_type") or "")
        bias = _bias_of(t)
        lab = _type_label(t)
        close = _hit_close(h)
        neck = _hit_neck(h)

        if st == "invalidated" and _is_bearish_side(bias) and _reason_upside_invalidate(h):
            if bull_cand is None or float(h.get("confidence") or 0) >= float(
                bull_cand.get("confidence") or 0
            ):
                bull_cand = h
                bull_why = f"空头形态「{lab}」向上脱离失效，视为突破旁路看多"
        elif st == "invalidated" and _is_bullish_side(bias) and _reason_downside_invalidate(h):
            if bear_cand is None or float(h.get("confidence") or 0) >= float(
                bear_cand.get("confidence") or 0
            ):
                bear_cand = h
                bear_why = f"多头形态「{lab}」向下脱离失效，视为破位旁路看空"
        elif st == "archived" and t in BULLISH_REVERSAL:
            if (
                close is not None
                and neck is not None
                and neck > 0
                and close > neck * BREAKOUT_UP_MULT
            ):
                if bull_cand is None or float(h.get("confidence") or 0) >= float(
                    bull_cand.get("confidence") or 0
                ):
                    bull_cand = h
                    bull_why = f"「{lab}」已测幅归档且现价仍在颈线上方，趋势延伸看多"
        elif st == "archived" and t in BEARISH_REVERSAL:
            if close is None or neck is None or neck <= 0:
                continue
            # 已站上颈线：空头旁路不成立
            if close >= neck * BREAKOUT_UP_MULT:
                continue
            if close >= neck * BREAKOUT_DOWN_MULT:
                # 极贴颈线上方缓冲区：不算深破
                gap = 0.0
            else:
                gap = _neck_gap_pct_below(close, neck)
                if gap is None:
                    continue
            stale = _is_stale_archive(h, asof)
            # 贴颈 / 浅破 → 逼近压力（震荡）
            if gap is not None and gap <= float(BYPASS_BEAR_NEAR_PCT):
                if range_cand is None or float(h.get("confidence") or 0) >= float(
                    range_cand.get("confidence") or 0
                ):
                    range_cand = h
                    range_why = (
                        f"「{lab}」已归档，现价贴近颈线 {neck:.2f}（下方约 {gap*100:.1f}%），"
                        f"属回攻压力而非结构破位"
                    )
                    range_label = "逼近压力"
                continue
            # 浅破但未达深破阈值 → 观望震荡
            if gap is not None and gap < float(BYPASS_BEAR_DEEP_PCT):
                if range_cand is None or float(h.get("confidence") or 0) >= float(
                    range_cand.get("confidence") or 0
                ):
                    range_cand = h
                    range_why = (
                        f"「{lab}」已归档，现价未有效深破颈线 {neck:.2f}，"
                        f"观望站稳/失守，不作破位看空"
                    )
                    range_label = "逼近压力"
                continue
            # 深破：陈旧须更苛刻
            need = float(BYPASS_BEAR_STALE_DEEP_PCT) if stale else float(BYPASS_BEAR_DEEP_PCT)
            if gap is not None and gap < need:
                if range_cand is None or float(h.get("confidence") or 0) >= float(
                    range_cand.get("confidence") or 0
                ):
                    range_cand = h
                    range_why = (
                        f"「{lab}」归档已久，深破幅度不足（相对颈线 {gap*100:.1f}%），"
                        f"降权为观望"
                    )
                    range_label = "逼近压力"
                continue
            if bear_cand is None or float(h.get("confidence") or 0) >= float(
                bear_cand.get("confidence") or 0
            ):
                bear_cand = h
                bear_why = (
                    f"「{lab}」已归档且现价相对颈线深破约 {(gap or 0)*100:.1f}%，"
                    f"旁路结构破位看空"
                )

    def _pick_conflict() -> Tuple[Optional[str], Optional[Dict[str, Any]], str, Optional[str]]:
        """多空旁路并存：较新形成日优先；接近则震荡。"""
        assert bull_cand is not None and bear_cand is not None
        bf = _hit_formed_at(bear_cand)
        uf = _hit_formed_at(bull_cand)
        bc = float(bear_cand.get("confidence") or 0)
        uc = float(bull_cand.get("confidence") or 0)
        if uf and bf and uf != bf:
            if uf > bf:
                return "看多", bull_cand, bull_why + "（旁路冲突取较新多头）", None
            return "看空", bear_cand, bear_why + "（旁路冲突取较新空头）", None
        if abs(bc - uc) >= float(RANK_CONF_TIE_EPS):
            if uc > bc:
                return "看多", bull_cand, bull_why + "（旁路冲突取更高置信多头）", None
            return "看空", bear_cand, bear_why + "（旁路冲突取更高置信空头）", None
        # 交织 → 震荡；锚取距现价更近的颈线
        c_b = _hit_close(bear_cand) or _hit_close(bull_cand)
        n_b, n_u = _hit_neck(bear_cand), _hit_neck(bull_cand)
        primary = bear_cand
        if c_b is not None and n_b is not None and n_u is not None:
            if abs(c_b - n_u) < abs(c_b - n_b):
                primary = bull_cand
        why = f"旁路多空交织（{bull_why}；{bear_why}），改震荡观望"
        return "震荡", primary, why, "蓄势夹击"

    chosen: Tuple[Optional[str], Optional[Dict[str, Any]], str, Optional[str]]
    if bear_cand is not None and bull_cand is not None:
        chosen = _pick_conflict()
    elif bear_cand is not None:
        chosen = ("看空", bear_cand, bear_why, None)
    elif bull_cand is not None and range_cand is not None:
        # P2：远端归档多头延伸 vs 近端归档空头贴颈压力 → 震荡（不以趋势延伸盖过遇压）
        chosen = (
            "震荡",
            range_cand,
            f"{range_why}；另有{bull_why}，近端压力优先故改震荡",
            range_label or "逼近压力",
        )
    elif bull_cand is not None:
        chosen = ("看多", bull_cand, bull_why, None)
    elif range_cand is not None:
        chosen = ("震荡", range_cand, range_why, range_label or "逼近压力")
    else:
        return None, None, "", None

    bias, hit, why, label_ov = chosen

    # P1：放量长阳否决旁路看空
    if bias == "看空" and hit is not None and _strong_up_momentum(market):
        chg = _f((market or {}).get("change_pct"))
        vol_r = _f((market or {}).get("volume_ratio"))
        bits = []
        if chg is not None:
            bits.append(f"日涨幅 {chg*100:.1f}%")
        if vol_r is not None:
            bits.append(f"量比 {vol_r:.1f}")
        why2 = (
            f"{why}；但出现放量长阳（{'、'.join(bits) or '动量偏强'}），"
            f"否决破位看空，改为逼近/观望"
        )
        return "震荡", hit, why2, "逼近压力"

    # 破 VAH 且仅浅贴颈的看空（兜底）：改震荡
    if bias == "看空" and hit is not None:
        close = _hit_close(hit)
        neck = _hit_neck(hit)
        gap = _neck_gap_pct_below(close, neck) if close is not None and neck is not None else None
        if (
            gap is not None
            and gap <= float(BYPASS_BEAR_DEEP_PCT)
            and _vp_break_vah_ok(vp, close)
        ):
            why2 = f"{why}；已破VAH且深破不足，筹码真空下改为观望"
            return "震荡", hit, why2, "逼近压力"

    return bias, hit, why, label_ov


def _apply_grade_enhancers(
    *,
    short_bias: str,
    conf: float,
    close: Optional[float],
    vp: Optional[Dict[str, Any]],
    rpe: Optional[Dict[str, Any]],
    z_lead: float,
    rationale_bits: List[str],
    evidence: List[Dict[str, Any]],
) -> Tuple[str, float]:
    """VP/RPE 只抬 grade/confidence，不改 short_bias。返回 (grade, confidence)。"""
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

    base_c = 0.45 + 0.35 * min(1.0, conf)
    if short_bias == "看空":
        base_c = 0.5 + 0.3 * min(1.0, conf)
    elif short_bias == "震荡":
        base_c = 0.35 + 0.25 * min(1.0, conf)
    elif short_bias == "insufficient":
        base_c = 0.2 + 0.1 * min(1.0, conf)
    base_c += 0.08 * enhancers
    confidence = round(max(0.05, min(0.95, base_c)), 3)
    return grade, confidence


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
    """同 status、置信接近、多空 bias 冲突 → 交织；或引擎已标 bias_mix/range_box。"""
    if _flag_bias_mix(primary):
        return True
    pb = _bias_of(str(primary.get("pattern_type") or ""))
    pst = str(primary.get("status") or "")
    pc = float(primary.get("confidence") or 0.0)
    for h in hits:
        if h is primary:
            continue
        if str(h.get("status") or "") != pst:
            continue
        if _flag_bias_mix(h) and _bias_conflicts(
            pb, _bias_of(str(h.get("pattern_type") or ""))
        ):
            return True
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
    asof: Optional[str] = None,
    market: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """结构主判定 + 增强证据；返回 short_bias / grade / evidence / rationale 等中间结果。"""
    active = _active_hits(hits)
    inv_n = max(0, int(invalidated_count or 0))
    evidence: List[Dict[str, Any]] = []

    if not active:
        bypass_bias, bypass_hit, bypass_why, label_ov = _inactive_bypass(
            hits, asof=asof, market=market, vp=vp
        )
        evidence.append(
            {
                "code": "no_active_hits",
                "ok": True,
                "invalidated_count": inv_n,
            }
        )
        if bypass_bias in ("看多", "看空", "震荡") and bypass_hit is not None:
            evidence.append(
                {
                    "code": "inactive_bypass",
                    "ok": True,
                    "short_bias": bypass_bias,
                    "pattern_type": bypass_hit.get("pattern_type"),
                    "status": bypass_hit.get("status"),
                    "reason": bypass_why,
                }
            )
            if isinstance(market, dict) and (
                market.get("change_pct") is not None or market.get("volume_ratio") is not None
            ):
                evidence.append(
                    {
                        "code": "momentum_veto_bear",
                        "ok": bypass_bias == "震荡" and _strong_up_momentum(market),
                        "change_pct": market.get("change_pct"),
                        "volume_ratio": market.get("volume_ratio"),
                    }
                )
            rationale_bits = [bypass_why]
            conf = float(bypass_hit.get("confidence") or 0.0)
            close = _hit_close(bypass_hit)
            grade, confidence = _apply_grade_enhancers(
                short_bias=bypass_bias,
                conf=conf,
                close=close,
                vp=vp,
                rpe=rpe,
                z_lead=float(z_lead),
                rationale_bits=rationale_bits,
                evidence=evidence,
            )
            bias_label = label_ov or _BIAS_LABEL.get(bypass_bias, bypass_bias)
            return {
                "short_bias": bypass_bias,
                "bias_label": bias_label,
                "grade": grade,
                "confidence": confidence,
                "rationale": "；".join(rationale_bits),
                "evidence": evidence,
                "primary": bypass_hit,
                "pressure_zone": None,
            }

        # 无旁路：一律信息不足（不再把 inv_n>0 映射成「震荡」）
        short_bias = "insufficient"
        rationale = (
            f"有效命中 0（另有 {inv_n} 条已失效/归档不可用），信息不足，无进攻买点。"
            if inv_n > 0
            else "有效命中 0，暂无结构方向。"
        )
        rationale_bits = [rationale]
        grade, confidence = _apply_grade_enhancers(
            short_bias=short_bias,
            conf=0.0,
            close=None,
            vp=vp,
            rpe=rpe,
            z_lead=float(z_lead),
            rationale_bits=rationale_bits,
            evidence=evidence,
        )
        # insufficient 不因 VP/RPE 抬成进攻档展示：grade 仍可增强作旁证，但置信压低
        return {
            "short_bias": short_bias,
            "bias_label": _BIAS_LABEL.get(short_bias, short_bias),
            "grade": grade,
            "confidence": min(confidence, 0.35),
            "rationale": "；".join(rationale_bits) if len(rationale_bits) > 1 else rationale,
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
        box_lo, box_hi = _hit_box_bounds(primary)
        if box_lo is None or box_hi is None:
            for h in active:
                box_lo, box_hi = _hit_box_bounds(h)
                if box_lo is not None and box_hi is not None:
                    break
        double_mix = mix and _has_double_top_bottom(active)
        if double_mix:
            bias_label = _BIAS_LABEL["箱体震荡"]
            if box_lo is not None and box_hi is not None:
                rationale_bits.insert(
                    0, f"箱体震荡下沿 {box_lo:.2f}、上沿 {box_hi:.2f}"
                )
            else:
                rationale_bits.append("双顶双底互斥，合并观察为箱体震荡")
        if forming_ok:
            rationale_bits.append(f"形成中的{lab}，边界未完全突破")
        if mix and not double_mix:
            rationale_bits.append("多空形态交织，宜按宽幅箱体观察")
        if pressure_ok:
            rationale_bits.append(
                f"近端共振压力强度≥{float(resonance_min_strength):.0f}，蓄势夹击"
            )
    else:
        short_bias = "震荡"
        bias_label = _BIAS_LABEL["震荡"]
        rationale_bits.append(f"主导{lab}（{st}）暂无明确突破方向")

    grade, confidence = _apply_grade_enhancers(
        short_bias=short_bias,
        conf=conf,
        close=close,
        vp=vp,
        rpe=rpe,
        z_lead=float(z_lead),
        rationale_bits=rationale_bits,
        evidence=evidence,
    )

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

    # 震荡且 bias 场景由 classify 标「逼近压力」时：提示观察颈线站稳，保留近端支撑 watch（P3）
    neck = _hit_neck(primary)
    upper, lower = _hit_bounds(primary)
    defense = _core_defense(primary)
    close = _hit_close(primary)
    target = measured_target(primary)
    # 近端阻力作目标候选
    if target is None and isinstance(confluence, dict):
        nz = confluence.get("nearest_resistance_zone")
        if isinstance(nz, dict):
            target = _f(nz.get("center")) or _f(nz.get("low"))

    nearest_support = None
    near_zone = _pick_near_strong_support(confluence, close)
    if isinstance(confluence, dict):
        ns = confluence.get("nearest_support_zone")
        if isinstance(ns, dict):
            nearest_support = _f(ns.get("center")) or _f(ns.get("high"))
    if nearest_support is None and near_zone is not None:
        nearest_support = _f(near_zone.get("center")) or _f(near_zone.get("high"))

    if short_bias == "看多":
        st_p = str(primary.get("status") or "") if primary else ""
        # 归档/失效旁路：颈线往往已远离现价，改近端支撑或巩固上沿翻支撑
        if st_p in ("archived", "invalidated"):
            # 复用近端超强共振：有合格带则用 zone；否则退回点锚
            if near_zone is not None:
                tgt = _resolve_watch_target(close, target, confluence, upper)
                hints.append(
                    _hint_near_support_pref(
                        near_zone,
                        target=tgt,
                        priority=2 if grade in ("strong", "enhanced") else 3,
                        trigger="突破/归档后回踩近端共振支撑企稳（颈线已远离，不作回踩锚）",
                    )
                )
                return hints, risk_note
            anchor_px = nearest_support
            if anchor_px is None and upper is not None:
                anchor_px = upper
            if anchor_px is None:
                anchor_px = neck if neck is not None else defense
            if anchor_px is None:
                return hints, "趋势旁路看多，但缺少近端结构锚点，仅作方向参考。"
            band = max(0.02, abs(anchor_px) * 0.008)
            hints.append(
                _with_clamped_invalidation(
                    {
                        "type": "watch",
                        "entry_zone": {
                            "low": round(anchor_px - band, 2),
                            "high": round(anchor_px + band, 2),
                            "anchor": "nearest_support"
                            if nearest_support is not None
                            else ("consol_upper" if upper is not None else "structure"),
                        },
                        "trigger": "突破/归档后回踩近端支撑企稳（颈线已远离，不作回踩锚）",
                        "invalidation": round(anchor_px * BREAKOUT_DOWN_MULT, 2),
                        "target": round(target, 2) if target is not None else None,
                        "priority": 2 if grade in ("strong", "enhanced") else 3,
                    }
                )
            )
            return hints, risk_note

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
            _with_clamped_invalidation(
                {
                    "type": hint_type,
                    "entry_zone": entry,
                    "trigger": trigger,
                    "invalidation": round(defense, 2) if defense is not None else None,
                    "target": round(target, 2) if target is not None else None,
                    "priority": priority,
                }
            )
        )
        return hints, risk_note

    # 震荡：watch → 下沿/近端支撑；强压下不追多；箱体优先用 box 上下沿
    if pressure_zone is not None:
        risk_note = "近端高强度共振压力压制，不在强压力下追多；等下沿承接或有效突破压力。"
    box_lo, box_hi = _hit_box_bounds(primary)
    pattern_floor = box_lo if box_lo is not None else lower
    floor_far = _level_far_below(close, pattern_floor)
    # 主目标：箱体上沿 > 楔/形态上沿 > measured/confluence
    primary_tgt = box_hi if box_hi is not None else (
        upper if upper is not None else target
    )
    thin_rr = _target_thin_upside(close, primary_tgt)
    watch_tgt = _resolve_watch_target(close, primary_tgt, confluence, upper)
    fib_0382 = _fib_ratio_price(confluence)

    def _append_far_floor_hint(*, with_note: bool = True) -> None:
        nonlocal risk_note
        if pattern_floor is None:
            return
        hints.append(
            _hint_far_pattern_lower(
                pattern_floor,
                target=watch_tgt,
                anchor="range_box_low_far" if box_lo is not None else "pattern_lower_far",
            )
        )
        if with_note:
            note_bit = "远端形态下沿仅作极限参考"
            risk_note = f"{risk_note}；{note_bit}" if risk_note else note_bit

    # —— floor_far（≥25%）：远端下沿永不为 p≤2 主锚；贴超强压 > 近端 A/B > 上破兜底 ——
    if floor_far:
        press_buy = _pressing_resistance_for_buy(confluence, close)
        near_main = _pick_near_support_floor_far(confluence, close)

        if press_buy is not None:
            break_px = _break_level_from_resistance(press_buy)
            if break_px is None and upper is not None:
                break_px = upper
            if break_px is not None:
                # 目标：上沿之上下一档有效阻力优先；薄 upside 形态上沿不得单独作 target
                bu_tgt = _resolve_break_upper_target(
                    confluence,
                    close,
                    break_px=break_px,
                    upper=upper,
                    primary_tgt=primary_tgt,
                )
                if bu_tgt is None:
                    bu_tgt = watch_tgt
                hints.append(
                    _hint_watch_break_upper(
                        break_px,
                        target=bu_tgt,
                        trigger=(
                            f"观察上破 {break_px:.2f} 再跟；贴身超强压下不新开/不追"
                        ),
                        priority=2,
                    )
                )
                press_note = "强压下不新开/不追；等有效上破压力或回踩近端承接"
                risk_note = f"{risk_note}；{press_note}" if risk_note else press_note
                # 左侧近端降为次级 watch（不盖过 break_upper）
                if near_main is not None:
                    hints.append(
                        _hint_near_support_pref(
                            near_main,
                            target=watch_tgt,
                            priority=3,
                            trigger="回踩近端共振支撑企稳（贴压时作左侧备选）",
                        )
                    )
                    watch2 = _pick_near_support_watch2(
                        confluence, close, primary=near_main
                    )
                    if watch2 is not None:
                        hints.append(
                            _hint_near_support_pref(
                                watch2,
                                target=watch_tgt,
                                priority=3,
                                trigger="回踩更远近端共振支撑企稳（第二档观察）",
                            )
                        )
                    _apply_shared_near_invalidation(hints, fib_px=fib_0382)
                _append_far_floor_hint()
                return hints, risk_note

        if near_main is not None:
            trig = (
                "回踩近端共振支撑企稳（远端下沿目标空间不足，改近端）"
                if thin_rr
                else "回踩近端高强度共振支撑企稳（形态下沿过远，优先近端）"
            )
            # B 档略弱时改文案
            near_s = _f(near_main.get("strength")) or 0.0
            if near_s < float(NEAR_SUPPORT_PREF_MIN_STRENGTH):
                trig = "回踩近端共振支撑企稳（floor 过远，B 档近端优先）"
            hints.append(
                _hint_near_support_pref(
                    near_main,
                    target=watch_tgt,
                    priority=2,
                    trigger=trig,
                )
            )
            watch2 = _pick_near_support_watch2(confluence, close, primary=near_main)
            if watch2 is not None:
                hints.append(
                    _hint_near_support_pref(
                        watch2,
                        target=watch_tgt,
                        priority=3,
                        trigger="回踩更远近端共振支撑企稳（第二档观察）",
                    )
                )
            _apply_shared_near_invalidation(hints, fib_px=fib_0382)
            _append_far_floor_hint()
            return hints, risk_note

        # 无贴压、无近端：改上破再跟，远端下沿仅 p4
        break_px = upper if upper is not None else (
            box_hi if box_hi is not None else None
        )
        if break_px is not None:
            bu_tgt = _resolve_break_upper_target(
                confluence,
                close,
                break_px=break_px,
                upper=upper,
                primary_tgt=primary_tgt,
            )
            if bu_tgt is None:
                bu_tgt = watch_tgt
            trig = (
                f"观察上破 {break_px:.2f} 再跟；远端下沿不作主买点"
                + ("（目标空间不足）" if thin_rr else "")
            )
            hints.append(
                _hint_watch_break_upper(break_px, target=bu_tgt, trigger=trig)
            )
            note_bit = "远端形态下沿仅作极限参考（改观察上破）"
            risk_note = f"{risk_note}；{note_bit}" if risk_note else note_bit
            _append_far_floor_hint(with_note=False)
            return hints, risk_note

        # 连上沿都没有：仅保留 p4 远端参考
        if pattern_floor is not None:
            _append_far_floor_hint()
            return hints, risk_note

    if box_lo is not None:
        anchor = box_lo
        if box_hi is not None:
            watch_tgt = box_hi
        band = max(0.02, abs(anchor) * 0.008)
        hints.append(
            _with_clamped_invalidation(
                {
                    "type": "watch",
                    "entry_zone": {
                        "low": round(anchor - band, 2),
                        "high": round(anchor + band, 2),
                        "anchor": "range_box_low",
                    },
                    "trigger": "回踩箱体下沿企稳",
                    "invalidation": round(anchor * BREAKOUT_DOWN_MULT, 2),
                    "target": round(watch_tgt, 2) if watch_tgt is not None else None,
                    "priority": 2,
                }
            )
        )
        return hints, risk_note
    anchor = lower if lower is not None else nearest_support
    if anchor is None and nearest_support is not None:
        anchor = nearest_support
    # P3：逼近归档空头颈线时，无下沿也可用颈线作观察锚（不编假买点）
    if anchor is None and neck is not None:
        band = max(0.02, abs(neck) * 0.008)
        hints.append(
            _with_clamped_invalidation(
                {
                    "type": "watch",
                    "entry_zone": {
                        "low": round(neck - band * 2, 2),
                        "high": round(neck + band, 2),
                        "anchor": "pattern_neckline",
                    },
                    "trigger": f"观察能否放量站稳颈线 {neck:.2f}；未站稳前不追高",
                    "invalidation": round(neck * BREAKOUT_DOWN_MULT, 2),
                    "target": round(watch_tgt, 2) if watch_tgt is not None else None,
                    "priority": 2,
                }
            )
        )
        return hints, None
    if anchor is None:
        return hints, risk_note
    band = max(0.02, abs(anchor) * 0.008)
    hints.append(
        _with_clamped_invalidation(
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
                    round(watch_tgt, 2) if watch_tgt is not None else None
                ),
                "priority": 2,
            }
        )
    )
    return hints, risk_note


def _parse_ymd(v: Any) -> Optional[str]:
    if v is None or v == "":
        return None
    s = str(v).strip()[:10]
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s
    return None


def _hit_span_meta(h: Dict[str, Any]) -> Dict[str, Any]:
    """用枢轴日估计跨度；形成/确认日仅可向后延长终点，不可早于首枢轴。"""
    from datetime import datetime

    pivot_dates: List[str] = []
    for p in h.get("pivots") or []:
        if not isinstance(p, dict):
            continue
        d = _parse_ymd(p.get("date") or p.get("trade_date"))
        if d:
            pivot_dates.append(d)
    fa = _parse_ymd(h.get("formed_at") or h.get("confirm_date"))
    if pivot_dates:
        dates = sorted(set(pivot_dates))
        start, end = dates[0], dates[-1]
        if fa and fa > end:
            end = fa
    elif fa:
        start = end = fa
    else:
        return {"span_days": 0, "start": None, "end": None}
    try:
        span = (
            datetime.strptime(end, "%Y-%m-%d") - datetime.strptime(start, "%Y-%m-%d")
        ).days
    except ValueError:
        span = 0
    return {"span_days": max(0, int(span)), "start": start, "end": end}


def _hierarchy_node(h: Dict[str, Any], meta: Dict[str, Any]) -> Dict[str, Any]:
    lv = _hit_levels(h)
    return {
        "pattern_type": h.get("pattern_type"),
        "label": _TYPE_LABEL_ZH.get(str(h.get("pattern_type") or ""), str(h.get("pattern_type") or "")),
        "status": h.get("status"),
        "confidence": h.get("confidence"),
        "formed_at": h.get("formed_at") or h.get("confirm_date"),
        "neckline": _f(lv.get("neckline")),
        "span_days": meta.get("span_days"),
        "span_start": meta.get("start"),
        "span_end": meta.get("end"),
    }


def _nesting_note_zh(dom: Dict[str, Any], sub: Dict[str, Any]) -> str:
    """大周期主导 + 小周期从属的一句中文。"""
    dlab = _TYPE_LABEL_ZH.get(str(dom.get("pattern_type") or ""), "主导形态")
    slab = _TYPE_LABEL_ZH.get(str(sub.get("pattern_type") or ""), "从属形态")
    dn = _f((_hit_levels(dom) or {}).get("neckline"))
    sn = _f((_hit_levels(sub) or {}).get("neckline"))
    dneck = f"（颈线{dn:.2f}）" if dn is not None else ""
    sneck = f"（颈线{sn:.2f}）" if sn is not None else ""
    db = _bias_of(str(dom.get("pattern_type") or ""))
    sb = _bias_of(str(sub.get("pattern_type") or ""))
    if _is_bearish_side(db) and _is_bullish_side(sb):
        return (
            f"大周期{dlab}{dneck}下压中，"
            f"小周期{slab}{sneck}反弹形态受阻"
        )
    if _is_bullish_side(db) and _is_bearish_side(sb):
        return (
            f"大周期{dlab}{dneck}支撑框架中，"
            f"小周期{slab}{sneck}回撤形态受压"
        )
    return f"大周期{dlab}{dneck}为主导，小周期{slab}{sneck}为从属嵌套"


def build_pattern_hierarchy(
    hits: Optional[Sequence[Dict[str, Any]]] = None,
    *,
    min_span_gap_days: int = 14,
) -> Optional[Dict[str, Any]]:
    """跨周期层级：按时间跨度挑选反向嵌套对，产出 nesting_note。

    候选含 confirmed / forming / archived（不含 invalidated）。
    优先头肩顶底对；主导=更长跨度（同跨度取更早起点）。
    """
    cand: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for h in hits or []:
        if not isinstance(h, dict):
            continue
        t = str(h.get("pattern_type") or "")
        if t not in BEARISH_REVERSAL and t not in BULLISH_REVERSAL:
            continue
        st = str(h.get("status") or "")
        if st not in ("confirmed", "forming", "archived"):
            continue
        cand.append((h, _hit_span_meta(h)))
    if len(cand) < 2:
        return None

    best: Optional[Tuple[float, Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]] = None
    for i, (a, ma) in enumerate(cand):
        for b, mb in cand[i + 1 :]:
            if not _bias_conflicts(
                _bias_of(str(a.get("pattern_type") or "")),
                _bias_of(str(b.get("pattern_type") or "")),
            ):
                continue
            both_hs = str(a.get("pattern_type") or "").startswith("head_shoulders") and str(
                b.get("pattern_type") or ""
            ).startswith("head_shoulders")
            # 头肩对：更早起点=大周期（002300 类时序嵌套）；其它反转对按跨度
            if both_hs:
                if str(ma.get("start") or "") <= str(mb.get("start") or ""):
                    dom, sub, dm, sm = a, b, ma, mb
                else:
                    dom, sub, dm, sm = b, a, mb, ma
            elif int(ma.get("span_days") or 0) >= int(mb.get("span_days") or 0):
                if int(ma.get("span_days") or 0) == int(mb.get("span_days") or 0) and (
                    str(ma.get("start") or "") > str(mb.get("start") or "")
                ):
                    dom, sub, dm, sm = b, a, mb, ma
                else:
                    dom, sub, dm, sm = a, b, ma, mb
            else:
                dom, sub, dm, sm = b, a, mb, ma
            gap = abs(int(dm.get("span_days") or 0) - int(sm.get("span_days") or 0))
            if gap < int(min_span_gap_days) and not both_hs:
                continue
            # 避免两个 forming 空谈嵌套；至少一侧已确认或归档
            st_pair = {str(dom.get("status") or ""), str(sub.get("status") or "")}
            if st_pair <= {"forming"}:
                continue
            score = float(gap)
            if both_hs:
                score += 100.0
                # 起点越早越像大周期
                try:
                    from datetime import datetime

                    sa = datetime.strptime(str(dm.get("start")), "%Y-%m-%d")
                    sb = datetime.strptime(str(sm.get("start")), "%Y-%m-%d")
                    score += max(0.0, (sb - sa).days)
                except Exception:
                    pass
            if str(dom.get("status") or "") in ("confirmed", "archived"):
                score += 30.0
            if str(sub.get("status") or "") in ("confirmed", "forming"):
                score += 20.0
            if best is None or score > best[0]:
                best = (score, dom, sub, dm, sm)
    if best is None:
        return None
    _score, dom, sub, dm, sm = best
    note = _nesting_note_zh(dom, sub)
    return {
        "dominant": _hierarchy_node(dom, dm),
        "subordinate": _hierarchy_node(sub, sm),
        "nesting_note": note,
        "relation": "nested_opposite",
        "span_gap_days": abs(int(dm.get("span_days") or 0) - int(sm.get("span_days") or 0)),
    }


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
    asof: Optional[str] = None,
    market: Optional[Dict[str, Any]] = None,
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
        asof=asof,
        market=market,
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

    for h in hints:
        if not isinstance(h, dict):
            continue
        ez = h.get("entry_zone") if isinstance(h.get("entry_zone"), dict) else {}
        if ez.get("anchor") == "near_support_pref":
            evidence.append(
                {
                    "code": "near_support_pref",
                    "ok": True,
                    "center": ez.get("center"),
                    "strength": ez.get("strength"),
                }
            )
            break

    hierarchy = build_pattern_hierarchy(hits)
    if hierarchy:
        evidence.append(
            {
                "code": "pattern_hierarchy",
                "ok": True,
                "dominant": (hierarchy.get("dominant") or {}).get("pattern_type"),
                "subordinate": (hierarchy.get("subordinate") or {}).get("pattern_type"),
                "span_gap_days": hierarchy.get("span_gap_days"),
            }
        )

    out: Dict[str, Any] = {
        "short_bias": classified.get("short_bias"),
        "bias_label": classified.get("bias_label"),
        "grade": classified.get("grade"),
        "confidence": classified.get("confidence"),
        "rationale": classified.get("rationale"),
        "evidence": evidence,
        "buy_hints": hints,
        "risk_note": risk_note,
        "disclaimer": DISCLAIMER,
        "pattern_hierarchy": hierarchy,
        "nesting_note": (hierarchy or {}).get("nesting_note") if hierarchy else None,
    }
    return out
