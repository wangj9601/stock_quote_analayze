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
# 高 ATR%：按 ATR 自适应缓冲（低波动仍约 1%；高波动用 k*ATR，且有上限防过宽）
INVALIDATION_ATR_PCT_LO = 0.05  # ATR/close ≥5% 进入高波动自适应
INVALIDATION_ATR_K = 0.04  # 结构锚下缓冲 ≈0.04×ATR（688110: 114.16→≈113.78）
INVALIDATION_MAX_BELOW_PCT = 0.04  # 相对买区下沿最多约 4%
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
# 买点 entry.high → target 相对空间过窄时提示（共振夹缝；相对改锚阈值更严）
ENTRY_TARGET_MIN_SPACE_PCT = 0.03
BREAK_TARGET_MIN_STRENGTH = 5.0  # 突破后「下一档有效阻力」最低强度（弱 Camarilla 等不抢主目标）
BREAK_TARGET_MIN_RR = 1.0  # 相对失效的最小盈亏比；形态上沿过薄时不得单独作 target
# 归档空窗：近端波段低点显著反弹提示（不启新形态引擎）
REBOUND_LOOKBACK_BARS = 40
REBOUND_MIN_PCT = 0.15  # 相对 swing_low 涨幅 ≥15% 才记 rebound_note
# 超强共振支撑：strength≥40 极罕见，置顶高亮（605100@33.36/40.75 类）
SUPER_SUPPORT_STRENGTH = 40.0
# RPE+Camarilla R4 动量突破旁路（无可用近端形态买点时补闭环）
R4_RETEST_NEAR_PCT = 0.02  # 现价不低于 R4 下方约 2%（已上破或贴近回踩）
MOMENTUM_R4_COVER_PCT = 0.03  # 已有买点覆盖 R4 附近则不重复注入
MOMENTUM_HINT_NEAR_ENTRY_PCT = 0.08  # 买点入场上沿距现价 >8% 视为无可用近端
# 下降楔形（看涨楔形）微幅上破 + GMS 动量联动 → 蓄势突破预警（与策略 0/4 命中解耦）
WEDGE_BREAKOUT_GMS_MIN = 60.0
WEDGE_HOLD_BUFFER_PCT = 0.012  # 上沿上方约 1.2% 小缓冲（6.46→≈6.54）
WEDGE_HOLD_ATR_K = 0.15  # 有 ATR 时用 max(缓冲%, k×ATR)
WEDGE_BREAKOUT_VOL_MULT = 1.5  # 右侧跟进：Volume > 1.5×MA20_Vol
WEDGE_FOLLOW_ENTRY_BAND_PCT = 0.008  # 站稳位入场区上沿缓冲
BULLISH_WEDGE_TYPES = frozenset({"falling_wedge"})  # 下降楔形=看涨楔形
# 极窄箱体变盘临界（Ultra-Squeeze）：近端双侧强共振夹击 → 停手等待变盘
ULTRA_SQUEEZE_WIDTH_PCT = 0.025  # (阻力-支撑)/现价 < 2.5%
ULTRA_SQUEEZE_MIN_STRENGTH = 20.0  # 双侧强度均须 > 20
ULTRA_SQUEEZE_BREAK_BUFFER_PCT = 0.004  # 无上沿时：阻力中心 +0.4% 作突破观察位
ULTRA_SQUEEZE_RISK_NOTE = "盈亏比不足，不宜追涨杀跌"
ULTRA_SQUEEZE_DISPLAY_STATUS = "极窄箱体变盘临界"
# 买点硬约束：回踩 entry 仅挂支撑带下沿附近（例 13.66–13.71），禁止贴现价追涨
ULTRA_SQUEEZE_ENTRY_BELOW_PCT = 0.004  # 下沿下方缓冲 ≈0.4%（13.71→≈13.66）
ULTRA_SQUEEZE_ENTRY_BELOW_MIN = 0.02  # 绝对价差下限（约 2 分）
ULTRA_SQUEEZE_NEAR_PRICE_PCT = 0.015  # entry 上沿距现价 ≤1.5% → 贴价追涨，过滤/降级
ULTRA_SQUEEZE_PULLBACK_NOTE = "盈亏比不足，仅支撑下沿挂单"
# 回踩类锚点：收窄到支撑带下沿；突破类仅观察
_ULTRA_SQUEEZE_PULLBACK_ANCHORS = frozenset(
    {
        "near_support",
        "near_support_pref",
        "nearest_support",
        "pattern_lower",
        "range_box_low",
        "structure",
        "neckline",
        "consol_upper",
        "pattern_neckline",
        "rpe_r4_retest",
        "camarilla_r4",
    }
)
# 高倾角风暴预警（Extreme Asymmetric Friction）：贴强压且阻力/支撑强度极度不对称
ASYMMETRY_STRENGTH_RATIO = 5.0  # 最近压制强度 / 最近支撑强度
ASYMMETRY_NEAR_RESIST_PCT = 0.015  # 现价距阻力上沿/中心 < 1.5%
ASYMMETRY_STORM_DISPLAY_STATUS = "高倾角风暴预警"
ASYMMETRY_STORM_RISK_NOTE = "头重脚轻，不宜追涨；提防向下加速下刺"


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


def _invalidation_gap(
    entry_low: float,
    *,
    atr: Optional[float] = None,
    close: Optional[float] = None,
) -> float:
    """失效位相对买区下沿的向下缓冲（价格单位）。

    - 低波动：约 1%（与最小价差取严）
    - 高 ATR%（≥约 5%）：改用 k×ATR 结构缓冲（例 0.04×ATR），
      相对现价往往更宽、相对支撑锚更贴；并封顶约 MAX_BELOW_PCT，避免过宽
    """
    low = float(entry_low)
    min_gap = max(
        float(INVALIDATION_MIN_GAP_ABS), abs(low) * float(INVALIDATION_MIN_GAP_PCT)
    )
    base = abs(low) * float(INVALIDATION_BELOW_ENTRY_PCT)
    a, c = _f(atr), _f(close)
    if a is None or c is None or a <= 0 or c <= 0 or low <= 0:
        return max(base, min_gap)
    atr_pct = a / c
    if atr_pct < float(INVALIDATION_ATR_PCT_LO):
        return max(base, min_gap)
    atr_gap = float(INVALIDATION_ATR_K) * a
    # 高波动：至少 k×ATR；若 k×ATR 大于固定 1% 则放宽，否则用结构微缓冲（相对现价仍更宽）
    gap = max(min_gap, atr_gap)
    max_gap = abs(low) * float(INVALIDATION_MAX_BELOW_PCT)
    if max_gap > min_gap:
        gap = min(gap, max_gap)
    return gap


def _clamp_invalidation(
    entry_low: Optional[float],
    inv: Optional[float],
    *,
    atr: Optional[float] = None,
    close: Optional[float] = None,
) -> Optional[float]:
    """保证 invalidation < entry_zone.low，且至少低于 low 一段缓冲（低波约 1% / 高 ATR 自适应）。"""
    low = _f(entry_low)
    if low is None or low <= 0:
        return round(_f(inv), 2) if _f(inv) is not None else None
    gap = _invalidation_gap(low, atr=atr, close=close)
    cap = low - gap
    if cap >= low:
        cap = low * (1.0 - float(INVALIDATION_BELOW_ENTRY_PCT))
    inv_f = _f(inv)
    if inv_f is None or inv_f > cap or inv_f >= low:
        return round(cap, 2)
    return round(inv_f, 2)


def _with_clamped_invalidation(
    hint: Dict[str, Any],
    *,
    atr: Optional[float] = None,
    close: Optional[float] = None,
) -> Dict[str, Any]:
    """就地钳制 buy_hint.invalidation；无 entry_zone.low 则原样返回。"""
    ez = hint.get("entry_zone")
    if not isinstance(ez, dict):
        return hint
    low = _f(ez.get("low"))
    if low is None:
        return hint
    hint["invalidation"] = _clamp_invalidation(
        low, hint.get("invalidation"), atr=atr, close=close
    )
    return hint


def _extract_atr(
    classic: Optional[Dict[str, Any]] = None,
    *,
    atr: Optional[float] = None,
) -> Optional[float]:
    a = _f(atr)
    if a is not None and a > 0:
        return a
    if not isinstance(classic, dict):
        return None
    a = _f(classic.get("atr"))
    if a is not None and a > 0:
        return a
    ap = classic.get("atr_pivot")
    if isinstance(ap, dict):
        a = _f(ap.get("atr"))
        if a is not None and a > 0:
            return a
    return None


def _breakout_probe_payload(
    primary: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """forming 巩固且 close>上沿（微幅上破、未改引擎 confirmed）→ 试探突破盘口态。"""
    if not isinstance(primary, dict):
        return None
    if str(primary.get("status") or "") != "forming":
        return None
    t = str(primary.get("pattern_type") or "")
    if t not in CONSOLIDATION:
        return None
    upper, _lower = _hit_bounds(primary)
    close = _hit_close(primary)
    if close is None or upper is None or upper <= 0:
        return None
    if close <= upper:
        return None
    lab = _type_label(t)
    note = (
        f"现价已微幅上破{lab}上沿 ({upper:.2f})，密切关注确认突破或假突破回落"
    )
    return {
        "ok": True,
        "pattern_type": t,
        "label": lab,
        "upper": round(float(upper), 2),
        "close": round(float(close), 2),
        "engine_status": "forming",
        "display_status": "试探突破",
        "status_note": note,
        "text": note,
    }


def _gms_score_total(gms: Optional[Dict[str, Any]]) -> Optional[float]:
    """读取 GMS 总分：优先 score / score_total / total_score（detail 兜底）。"""
    if not isinstance(gms, dict):
        return None
    for k in ("score", "score_total", "total_score", "gms_score"):
        v = _f(gms.get(k))
        if v is not None:
            return v
    detail = gms.get("detail")
    if isinstance(detail, dict):
        for k in ("score_total", "total_score", "score"):
            v = _f(detail.get(k))
            if v is not None:
                return v
    return None


def _camarilla_level_candidates(
    classic: Optional[Dict[str, Any]] = None,
    *,
    camarilla: Optional[Dict[str, Any]] = None,
) -> List[Tuple[float, str]]:
    """Camarilla 各档位 → (价, 来源标签)。"""
    cam = camarilla if isinstance(camarilla, dict) else None
    if cam is None and isinstance(classic, dict):
        raw = classic.get("camarilla")
        cam = raw if isinstance(raw, dict) else None
    if not isinstance(cam, dict):
        return []
    out: List[Tuple[float, str]] = []
    for key in ("R4", "R3", "R2", "R1", "S1", "S2", "S3", "S4", "H4", "H3", "L3", "L4"):
        px = _f(cam.get(key))
        if px is not None and px > 0:
            out.append((float(px), f"camarilla_{key}"))
    return out


def _resolve_wedge_hold_level(
    upper: float,
    close: Optional[float],
    *,
    classic: Optional[Dict[str, Any]] = None,
    confluence: Optional[Dict[str, Any]] = None,
    camarilla: Optional[Dict[str, Any]] = None,
    atr: Optional[float] = None,
) -> Tuple[Optional[float], Optional[str]]:
    """站稳观察位：上沿上方最近弱阻力/Camarilla，否则上沿小缓冲。

    不以个股写死价位；601991 类可由 Camarilla S4≈6.54 自然推出。
    """
    u = float(upper)
    if u <= 0:
        return None, None
    gate = u
    c = _f(close)
    # 候选须严格高于上沿；现价已略高于上沿时仍取「上沿之上」的站稳位
    cands: List[Tuple[float, str]] = []
    for px, src in _camarilla_level_candidates(classic, camarilla=camarilla):
        if px > gate:
            cands.append((px, src))
    for z in _iter_confluence_resistances(confluence):
        for ref, tag in (
            (_f(z.get("high")), "confluence_high"),
            (_f(z.get("center")), "confluence_center"),
            (_f(z.get("low")), "confluence_low"),
        ):
            if ref is not None and ref > gate:
                cands.append((float(ref), tag))
                break
    atr_v = _f(atr)
    buf = max(u * float(WEDGE_HOLD_BUFFER_PCT), 0.01)
    if atr_v is not None and atr_v > 0:
        buf = max(buf, float(WEDGE_HOLD_ATR_K) * atr_v)
    fallback = round(u + buf, 2)
    cands.append((float(fallback), "upper_buffer"))
    # 取上沿上方最近一档（优先略高于现价的站稳位）
    above_close = [(p, s) for p, s in cands if c is None or p >= c]
    pool = above_close if above_close else cands
    if not pool:
        return fallback, "upper_buffer"
    best_px, best_src = min(pool, key=lambda x: (x[0], x[1]))
    return round(float(best_px), 2), best_src


def _resolve_wedge_alert_target(
    confluence: Optional[Dict[str, Any]],
    *,
    upper: float,
    close: Optional[float],
    min_strength: float = BREAK_TARGET_MIN_STRENGTH,
) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """预警目标：形态上沿之上有效共振阻力（门槛对齐 break_upper）。

    在 strength≥门槛的候选中优先强度更高者（同强度取更近），
    以贴合 601991 类「7.12@12.2」高强档示例；无强档则退回最近任意足够 upside 阻力。

    Returns: (target_px, strength, source_tag)
    """
    u = float(upper)
    entry_ref = float(close) if close is not None and close > 0 else u
    entry_ref = max(u, entry_ref)
    best_strong: Optional[Dict[str, Any]] = None
    best_strong_key: Optional[Tuple[float, float]] = None  # (-strength, center)
    best_any: Optional[Dict[str, Any]] = None
    best_any_px: Optional[float] = None
    for z in _iter_confluence_resistances(confluence):
        center = _f(z.get("center")) or _f(z.get("low"))
        if center is None or center <= u:
            continue
        if not _target_upside_ok(entry_ref, center):
            continue
        strength = _f(z.get("strength")) or 0.0
        if best_any_px is None or center < best_any_px:
            best_any_px = center
            best_any = z
        if strength < float(min_strength):
            continue
        key = (-float(strength), float(center))
        if best_strong_key is None or key < best_strong_key:
            best_strong_key = key
            best_strong = z
    zone = best_strong if best_strong is not None else best_any
    if not isinstance(zone, dict):
        return None, None, None
    px = _f(zone.get("center")) or _f(zone.get("low"))
    if px is None:
        return None, None, None
    strength = _f(zone.get("strength"))
    return round(float(px), 2), (
        round(float(strength), 2) if strength is not None else None
    ), "confluence_resistance"


def _apply_wedge_alert_targets_to_hints(
    hints: List[Dict[str, Any]],
    alert: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """预警态：break_upper / momentum / 右侧跟进，以及目标仍挂形态上沿的 watch，改挂预警目标。"""
    if not isinstance(alert, dict) or not alert.get("ok"):
        return hints
    tgt = _f(alert.get("target")) or _f(alert.get("alert_target"))
    if tgt is None:
        return hints
    upper = _f(alert.get("upper"))
    out: List[Dict[str, Any]] = []
    for h in hints:
        if not isinstance(h, dict):
            out.append(h)
            continue
        nh = dict(h)
        htype = str(nh.get("type") or "").lower()
        ez = nh.get("entry_zone") if isinstance(nh.get("entry_zone"), dict) else {}
        anchor = str(ez.get("anchor") or "").lower()
        is_breakish = htype in (
            "break_upper",
            "momentum",
            "momentum_breakout",
            "breakout_follow",
            "right_breakout",
        ) or "break_upper" in anchor or anchor in (
            "wedge_hold_level",
            "gms_volume_breakout",
        )
        old_tgt = _f(nh.get("target"))
        thin_upper = (
            upper is not None
            and old_tgt is not None
            and abs(float(old_tgt) - float(upper))
            <= max(0.02, abs(float(upper)) * 0.003)
        )
        if is_breakish or thin_upper or old_tgt is None:
            nh["target"] = round(float(tgt), 2)
        out.append(nh)
    return out


def _build_wedge_breakout_follow_hint(
    alert: Dict[str, Any],
    *,
    close: Optional[float] = None,
    market: Optional[Dict[str, Any]] = None,
    grade: str = "base",
    atr: Optional[float] = None,
    vol_mult: float = WEDGE_BREAKOUT_VOL_MULT,
) -> Optional[Dict[str, Any]]:
    """楔形蓄势突破预警 + GMS>门槛后的右侧带量跟进买点（与左侧回踩并存）。"""
    if not isinstance(alert, dict) or not alert.get("ok"):
        return None
    hold = _f(alert.get("hold_level"))
    if hold is None or hold <= 0:
        return None
    upper = _f(alert.get("upper"))
    inv = _f(alert.get("alert_invalidation"))
    if inv is None and upper is not None and upper > 0:
        inv = round(float(upper) * float(BREAKOUT_DOWN_MULT), 2)
    tgt = _f(alert.get("target")) or _f(alert.get("alert_target"))
    band = max(0.02, abs(float(hold)) * float(WEDGE_FOLLOW_ENTRY_BAND_PCT))
    c = _f(close)
    if c is None and isinstance(market, dict):
        c = _f(market.get("last_close"))
    vol_r = _f(market.get("volume_ratio")) if isinstance(market, dict) else None
    close_ok = c is not None and float(c) > float(hold)
    vol_ok: Optional[bool] = None
    if vol_r is not None:
        vol_ok = float(vol_r) > float(vol_mult)
    if close_ok and vol_ok is True:
        trigger_status = "triggered"
    else:
        trigger_status = "pending"
    hold_txt = f"{float(hold):.2f}"
    vol_txt = f"{float(vol_mult):g}"
    trigger = (
        f"日线带量站稳 {hold_txt} 以上跟进/加仓"
        f"（Close>{hold_txt} 且 Volume>{vol_txt}×MA20_Vol）"
    )
    if vol_r is not None:
        trigger = f"{trigger}；当前量比 {float(vol_r):.2f}"
    hint: Dict[str, Any] = {
        "type": "breakout_follow",
        "entry_zone": {
            "low": round(float(hold), 2),
            "high": round(float(hold) + band, 2),
            "center": round(float(hold), 2),
            "anchor": "wedge_hold_level",
        },
        "trigger": trigger,
        "invalidation": round(float(inv), 2) if inv is not None else None,
        "target": round(float(tgt), 2) if tgt is not None else None,
        "priority": 1 if grade in ("strong", "enhanced") else 2,
        "volume_condition": {
            "min_ratio": float(vol_mult),
            "vs": "MA20_Vol",
            "close_above": round(float(hold), 2),
            "volume_ratio": round(float(vol_r), 4) if vol_r is not None else None,
        },
        "trigger_status": trigger_status,
        "conditions_met": {
            "close_above_hold": bool(close_ok),
            "volume_above_ma20": vol_ok,
        },
    }
    return _with_clamped_invalidation(hint, atr=atr, close=c)


def _demote_left_side_hint_priority(hints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """右侧跟进注入后，左侧回踩/观察锚降为较低优先级（仍保留远端参考）。"""
    out: List[Dict[str, Any]] = []
    for h in hints:
        if not isinstance(h, dict):
            out.append(h)
            continue
        nh = dict(h)
        htype = str(nh.get("type") or "").lower()
        ez = nh.get("entry_zone") if isinstance(nh.get("entry_zone"), dict) else {}
        anchor = str(ez.get("anchor") or "").lower()
        is_left = htype in ("watch", "pullback_buy") or anchor in (
            "pattern_lower",
            "near_support_pref",
            "box_low",
            "neckline",
        )
        if is_left:
            try:
                p = int(nh.get("priority") or 3)
            except (TypeError, ValueError):
                p = 3
            nh["priority"] = max(p, 3)
            note = "左侧远端参考（右侧突破跟进优先）"
            prev = nh.get("risk_note")
            if prev and str(prev).strip() and note not in str(prev):
                nh["risk_note"] = f"{prev}；{note}"
            elif not prev:
                nh["risk_note"] = note
        out.append(nh)
    return out


def _zone_px_center(z: Optional[Dict[str, Any]]) -> Optional[float]:
    if not isinstance(z, dict):
        return None
    return _f(z.get("center")) or _f(z.get("high")) or _f(z.get("low"))


def _pick_ultra_squeeze_support(
    confluence: Optional[Dict[str, Any]],
    close: Optional[float],
    *,
    min_strength: float = ULTRA_SQUEEZE_MIN_STRENGTH,
) -> Optional[Dict[str, Any]]:
    """近端支撑：优先 nearest_support_zone（强度达标），否则列表中现价下方最近且强度达标。"""
    c = _f(close)
    if c is None or c <= 0 or not isinstance(confluence, dict):
        return None
    min_s = float(min_strength)
    ns = confluence.get("nearest_support_zone")
    if isinstance(ns, dict):
        s = _zone_effective_strength(ns) or 0.0
        px = _zone_px_center(ns)
        if s > min_s and px is not None and px < c:
            return ns
    best: Optional[Dict[str, Any]] = None
    best_dist = float("inf")
    for z in _iter_confluence_supports(confluence):
        s = _zone_effective_strength(z) or 0.0
        if s <= min_s:
            continue
        px = _zone_px_center(z)
        if px is None or px >= c:
            continue
        dist = c - px
        if dist < best_dist:
            best_dist = dist
            best = z
    return best


def _pick_ultra_squeeze_resistance(
    confluence: Optional[Dict[str, Any]],
    close: Optional[float],
    *,
    min_strength: float = ULTRA_SQUEEZE_MIN_STRENGTH,
) -> Optional[Dict[str, Any]]:
    """近端阻力：优先 nearest_resistance_zone（强度达标），否则列表中现价上方最近且强度达标。"""
    c = _f(close)
    if c is None or c <= 0 or not isinstance(confluence, dict):
        return None
    min_s = float(min_strength)
    nr = confluence.get("nearest_resistance_zone")
    if isinstance(nr, dict):
        s = _zone_effective_strength(nr) or 0.0
        px = _zone_px_center(nr)
        # 可贴身/在带内：中心可略低于现价（现价压在阻力带下沿）
        lo = _f(nr.get("low"))
        hi = _f(nr.get("high"))
        inside = lo is not None and hi is not None and lo <= c <= hi
        near_above = px is not None and px >= c * 0.998
        if s > min_s and px is not None and (inside or near_above or px >= c):
            return nr
    best: Optional[Dict[str, Any]] = None
    best_dist = float("inf")
    for z in _iter_confluence_resistances(confluence):
        s = _zone_effective_strength(z) or 0.0
        if s <= min_s:
            continue
        px = _zone_px_center(z)
        if px is None:
            continue
        lo = _f(z.get("low"))
        hi = _f(z.get("high"))
        inside = lo is not None and hi is not None and lo <= c <= hi
        if not inside and px < c:
            continue
        dist = abs(px - c)
        if dist < best_dist:
            best_dist = dist
            best = z
    return best


def _ultra_squeeze_break_observe(resistance: Dict[str, Any]) -> Optional[float]:
    """突破观察位：阻力上沿；无上沿则中心 + 小缓冲。"""
    high = _f(resistance.get("high"))
    center = _f(resistance.get("center"))
    if high is not None and high > 0:
        return round(float(high), 2)
    if center is not None and center > 0:
        return round(float(center) * (1.0 + float(ULTRA_SQUEEZE_BREAK_BUFFER_PCT)), 2)
    return None


def _ultra_squeeze_payload(
    confluence: Optional[Dict[str, Any]],
    close: Optional[float],
    *,
    width_pct: float = ULTRA_SQUEEZE_WIDTH_PCT,
    min_strength: float = ULTRA_SQUEEZE_MIN_STRENGTH,
) -> Optional[Dict[str, Any]]:
    """近端双侧强共振夹击且带宽极窄 → 极窄箱体变盘临界。"""
    c = _f(close)
    if c is None or c <= 0:
        return None
    support = _pick_ultra_squeeze_support(
        confluence, c, min_strength=float(min_strength)
    )
    resistance = _pick_ultra_squeeze_resistance(
        confluence, c, min_strength=float(min_strength)
    )
    if support is None or resistance is None:
        return None
    s_px = _zone_px_center(support)
    r_px = _zone_px_center(resistance)
    if s_px is None or r_px is None or r_px <= s_px:
        return None
    width = (r_px - s_px) / c
    if width >= float(width_pct):
        return None
    s_str = _zone_effective_strength(support)
    r_str = _zone_effective_strength(resistance)
    if s_str is None or r_str is None:
        return None
    if s_str <= float(min_strength) or r_str <= float(min_strength):
        return None
    break_obs = _ultra_squeeze_break_observe(resistance)
    if break_obs is None:
        break_obs = round(float(r_px), 2)
    pullback = round(float(s_px), 2)
    fen = max(1, int(round(abs(float(r_px) - float(s_px)) * 100)))
    note = (
        f"当前处于 {fen} 分钱极窄空间夹击，盈亏比不足，"
        f"静待带量突破 {float(break_obs):.2f} 或缩量回踩 {pullback:.2f}"
    )
    return {
        "ok": True,
        "code": "ultra_squeeze",
        "display_status": ULTRA_SQUEEZE_DISPLAY_STATUS,
        "status_note": note,
        "text": note,
        "close": round(float(c), 2),
        "support": round(float(s_px), 2),
        "resistance": round(float(r_px), 2),
        "support_strength": round(float(s_str), 2),
        "resistance_strength": round(float(r_str), 2),
        "width": round(float(r_px) - float(s_px), 4),
        "width_pct": round(float(width), 6),
        "width_pct_max": float(width_pct),
        "break_observe": round(float(break_obs), 2),
        "pullback": pullback,
        "fen": fen,
        "support_zone": {
            "center": round(float(s_px), 2),
            "low": _f(support.get("low")),
            "high": _f(support.get("high")),
            "strength": round(float(s_str), 2),
        },
        "resistance_zone": {
            "center": round(float(r_px), 2),
            "low": _f(resistance.get("low")),
            "high": _f(resistance.get("high")),
            "strength": round(float(r_str), 2),
        },
    }


def _ultra_squeeze_support_low(ultra: Dict[str, Any]) -> Optional[float]:
    """支撑带下沿：优先 support_zone.low，否则 pullback/support 中心。"""
    sz = ultra.get("support_zone") if isinstance(ultra.get("support_zone"), dict) else {}
    lo = _f(sz.get("low")) if isinstance(sz, dict) else None
    if lo is not None and lo > 0:
        return float(lo)
    for key in ("pullback", "support"):
        px = _f(ultra.get(key))
        if px is not None and px > 0:
            return float(px)
    return None


def _narrow_entry_to_support_low(
    ez: Dict[str, Any],
    *,
    zone_low: float,
) -> Dict[str, Any]:
    """回踩 entry 收窄到支撑带下沿附近：low≈下沿−缓冲，high≈下沿（不含现价中轨）。"""
    below = max(
        float(ULTRA_SQUEEZE_ENTRY_BELOW_MIN),
        abs(float(zone_low)) * float(ULTRA_SQUEEZE_ENTRY_BELOW_PCT),
    )
    entry_lo = round(float(zone_low) - below, 2)
    entry_hi = round(float(zone_low), 2)
    if entry_lo > entry_hi:
        entry_lo, entry_hi = entry_hi, entry_lo
    out = dict(ez) if isinstance(ez, dict) else {}
    out["low"] = entry_lo
    out["high"] = entry_hi
    out["center"] = round((entry_lo + entry_hi) / 2.0, 2)
    out["ultra_squeeze_narrowed"] = True
    out["support_low"] = round(float(zone_low), 2)
    return out


def _entry_near_close(
    ez: Optional[Dict[str, Any]],
    close: Optional[float],
    *,
    near_pct: float = ULTRA_SQUEEZE_NEAR_PRICE_PCT,
) -> bool:
    """入场上沿贴近现价 → 视为追涨/中轨买点。"""
    c = _f(close)
    if c is None or c <= 0 or not isinstance(ez, dict):
        return False
    hi = _f(ez.get("high"))
    mid = _f(ez.get("center"))
    ref = hi if hi is not None else mid
    if ref is None:
        return False
    # 上沿已不低于现价，或距现价过近
    if ref >= c * (1.0 - float(near_pct)):
        return True
    return False


def _apply_ultra_squeeze_to_hints(
    hints: List[Dict[str, Any]],
    ultra: Dict[str, Any],
    risk_note: Optional[str],
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """夹缝态硬约束：回踩 entry 仅挂支撑下沿；贴压/贴价不追；盈亏比不足提示。"""
    bit = ULTRA_SQUEEZE_RISK_NOTE
    pull_bit = ULTRA_SQUEEZE_PULLBACK_NOTE
    # 合并顶层风险：空间不足类提示保留，再叠夹缝硬约束
    merged_bits = [pull_bit, bit]
    for b in merged_bits:
        if risk_note and b in str(risk_note):
            continue
        risk_note = f"{risk_note}；{b}" if risk_note else b
    break_obs = _f(ultra.get("break_observe"))
    close = _f(ultra.get("close"))
    zone_low = _ultra_squeeze_support_low(ultra)
    out: List[Dict[str, Any]] = []
    for h in hints:
        if not isinstance(h, dict):
            continue
        nh = dict(h)
        htype = str(nh.get("type") or "").lower()
        ez_raw = nh.get("entry_zone") if isinstance(nh.get("entry_zone"), dict) else {}
        ez = dict(ez_raw)
        anchor = str(ez.get("anchor") or "").lower()
        trig = str(nh.get("trigger") or "")
        is_breakish = (
            htype in (
                "break_upper",
                "momentum",
                "momentum_breakout",
                "breakout_follow",
                "right_breakout",
                "breakout_buy",
            )
            or "break_upper" in anchor
            or anchor in ("wedge_hold_level", "gms_volume_breakout")
        )
        is_pullbackish = (
            htype in ("watch", "pullback_buy")
            and (
                anchor in _ULTRA_SQUEEZE_PULLBACK_ANCHORS
                or "near_support" in anchor
                or "support" in anchor
                or "lower" in anchor
                or "box_low" in anchor
                or "回踩" in trig
            )
            and not is_breakish
        )
        if is_breakish:
            # 贴压突破仅观察：变盘前不追
            nh["type"] = "watch"
            try:
                pri = int(nh.get("priority") or 3)
            except (TypeError, ValueError):
                pri = 3
            nh["priority"] = max(pri, 3)
            note_bits = ["极窄箱体夹击，变盘前不追"]
            if break_obs is not None:
                note_bits.append(f"仅观察带量突破 {break_obs:.2f}")
            merged_trig = trig
            for nb in note_bits:
                if nb not in merged_trig:
                    merged_trig = f"{merged_trig}；{nb}" if merged_trig else nb
            nh["trigger"] = merged_trig
        elif is_pullbackish and zone_low is not None:
            # 回踩买点：entry 硬收窄到支撑带下沿附近
            ez = _narrow_entry_to_support_low(ez, zone_low=zone_low)
            nh["entry_zone"] = ez
            nh["type"] = "watch"
            if "下沿" not in trig and "挂单" not in trig:
                nh["trigger"] = (
                    f"{trig}（仅支撑下沿挂单）" if trig else "回踩支撑带下沿挂单企稳"
                )
            # 收窄后重算失效位（须严格低于新 entry.low）
            nh = _with_clamped_invalidation(nh, close=close)
            # 贴现价残留区间 → 丢弃（禁止在现价附近直接买入）
            if _entry_near_close(ez, close):
                continue
            space = (
                f"{pull_bit} {float(ez['low']):.2f}–{float(ez['high']):.2f}"
            )
            nh["space_note"] = space
            prev_r = nh.get("risk_note")
            if prev_r and str(prev_r).strip() and pull_bit not in str(prev_r):
                nh["risk_note"] = f"{prev_r}；{space}"
            else:
                nh["risk_note"] = space
        elif is_pullbackish:
            # 无支撑下沿可绑定时：至少过滤贴现价区间
            if _entry_near_close(ez, close):
                continue
            nh["type"] = "watch"
        elif htype in ("pullback_buy", "breakout_buy"):
            # 其它激进类型降级
            nh["type"] = "watch"
            nh["trigger"] = (
                f"极窄箱体变盘临界，不宜追涨杀跌；"
                f"静待带量突破 {break_obs:.2f}"
                if break_obs is not None
                else "极窄箱体变盘临界，不宜追涨杀跌，静待变盘"
            )
            if _entry_near_close(ez, close):
                continue
        else:
            # 未知锚点：贴现价则过滤
            if _entry_near_close(ez, close) and htype not in ("watch",):
                continue

        # 统一叠夹缝风险提示
        prev = nh.get("risk_note")
        for extra in (pull_bit, bit):
            if prev and extra in str(prev):
                continue
            if prev and str(prev).strip():
                prev = f"{prev}；{extra}"
            else:
                prev = extra
        nh["risk_note"] = prev
        out.append(nh)
    return out, risk_note


def _pick_asymmetry_support(
    confluence: Optional[Dict[str, Any]],
    close: Optional[float],
) -> Optional[Dict[str, Any]]:
    """最近支撑：优先 nearest_support_zone（现价下方），否则列表中最近下方带。"""
    c = _f(close)
    if c is None or c <= 0 or not isinstance(confluence, dict):
        return None
    ns = confluence.get("nearest_support_zone")
    if isinstance(ns, dict):
        px = _zone_px_center(ns)
        if px is not None and px < c:
            return ns
    best: Optional[Dict[str, Any]] = None
    best_dist = float("inf")
    for z in _iter_confluence_supports(confluence):
        px = _zone_px_center(z)
        if px is None or px >= c:
            continue
        dist = c - px
        if dist < best_dist:
            best_dist = dist
            best = z
    return best


def _pick_asymmetry_resistance(
    confluence: Optional[Dict[str, Any]],
    close: Optional[float],
) -> Optional[Dict[str, Any]]:
    """最近阻力：优先 nearest_resistance_zone（贴身/上方），否则列表中最近上方带。"""
    c = _f(close)
    if c is None or c <= 0 or not isinstance(confluence, dict):
        return None
    nr = confluence.get("nearest_resistance_zone")
    if isinstance(nr, dict):
        px = _zone_px_center(nr)
        lo = _f(nr.get("low"))
        hi = _f(nr.get("high"))
        inside = lo is not None and hi is not None and lo <= c <= hi
        near_above = px is not None and px >= c * 0.998
        if px is not None and (inside or near_above or px >= c):
            return nr
    best: Optional[Dict[str, Any]] = None
    best_dist = float("inf")
    for z in _iter_confluence_resistances(confluence):
        px = _zone_px_center(z)
        if px is None:
            continue
        lo = _f(z.get("low"))
        hi = _f(z.get("high"))
        inside = lo is not None and hi is not None and lo <= c <= hi
        if not inside and px < c:
            continue
        dist = abs(px - c)
        if dist < best_dist:
            best_dist = dist
            best = z
    return best


def _asymmetry_resist_dist_pct(
    resistance: Dict[str, Any],
    close: float,
) -> Optional[float]:
    """现价距阻力上沿/中心的相对距离；已在阻力带内视为 0。"""
    c = float(close)
    if c <= 0:
        return None
    lo = _f(resistance.get("low"))
    hi = _f(resistance.get("high"))
    if lo is not None and hi is not None and lo <= c <= hi:
        return 0.0
    # 上沿优先：带下沿（首道压制）→ 中心 → 上沿
    ref = lo if lo is not None and lo >= c else None
    if ref is None:
        ref = _zone_px_center(resistance)
    if ref is None:
        ref = hi
    if ref is None:
        return None
    return max(0.0, (float(ref) - c) / c)


def _asymmetry_storm_payload(
    confluence: Optional[Dict[str, Any]],
    close: Optional[float],
    *,
    strength_ratio: float = ASYMMETRY_STRENGTH_RATIO,
    near_resist_pct: float = ASYMMETRY_NEAR_RESIST_PCT,
) -> Optional[Dict[str, Any]]:
    """最近阻力/支撑强度比过大且贴压 → 高倾角风暴预警（头重脚轻）。"""
    c = _f(close)
    if c is None or c <= 0:
        return None
    support = _pick_asymmetry_support(confluence, c)
    resistance = _pick_asymmetry_resistance(confluence, c)
    if support is None or resistance is None:
        return None
    s_str = _zone_effective_strength(support)
    r_str = _zone_effective_strength(resistance)
    if s_str is None or r_str is None or s_str <= 0:
        return None
    ratio = float(r_str) / float(s_str)
    if ratio <= float(strength_ratio):
        return None
    dist_pct = _asymmetry_resist_dist_pct(resistance, float(c))
    if dist_pct is None or dist_pct >= float(near_resist_pct):
        return None
    s_px = _zone_px_center(support)
    r_px = _zone_px_center(resistance)
    # 文案口径：一位小数（例 65.5 / 1.9）
    r_txt = f"{float(r_str):.1f}"
    s_txt = f"{float(s_str):.1f}"
    note = (
        f"上方阻力 ({r_txt}) 极度碾压下方支撑 ({s_txt})，"
        f"向上空间已被封死，提防向下加速下刺风险"
    )
    return {
        "ok": True,
        "code": "asymmetry_storm",
        "display_status": ASYMMETRY_STORM_DISPLAY_STATUS,
        "status_note": note,
        "text": note,
        "close": round(float(c), 2),
        "support": round(float(s_px), 2) if s_px is not None else None,
        "resistance": round(float(r_px), 2) if r_px is not None else None,
        "support_strength": round(float(s_str), 2),
        "resistance_strength": round(float(r_str), 2),
        "strength_ratio": round(float(ratio), 2),
        "strength_ratio_min": float(strength_ratio),
        "dist_to_resist_pct": round(float(dist_pct), 6),
        "near_resist_pct_max": float(near_resist_pct),
        "support_zone": {
            "center": round(float(s_px), 2) if s_px is not None else None,
            "low": _f(support.get("low")),
            "high": _f(support.get("high")),
            "strength": round(float(s_str), 2),
        },
        "resistance_zone": {
            "center": round(float(r_px), 2) if r_px is not None else None,
            "low": _f(resistance.get("low")),
            "high": _f(resistance.get("high")),
            "strength": round(float(r_str), 2),
        },
    }


def _apply_asymmetry_storm_to_hints(
    hints: List[Dict[str, Any]],
    storm: Dict[str, Any],
    risk_note: Optional[str],
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """头重脚轻贴压：强化不宜追涨，买点侧避免激进 break_upper 追入。"""
    bit = ASYMMETRY_STORM_RISK_NOTE
    risk_note = f"{risk_note}；{bit}" if risk_note else bit
    r_str = _f(storm.get("resistance_strength"))
    s_str = _f(storm.get("support_strength"))
    ratio = _f(storm.get("strength_ratio"))
    watch_trig = "高倾角风暴预警，贴压不追，仅观察"
    if r_str is not None and s_str is not None:
        watch_trig = (
            f"高倾角风暴预警：上方阻力 ({r_str:.1f}) 碾压下方支撑 ({s_str:.1f})"
            f"{f'，比约 {ratio:.1f}:1' if ratio is not None else ''}；贴压不追，仅观察"
        )
    out: List[Dict[str, Any]] = []
    for h in hints:
        if not isinstance(h, dict):
            continue
        nh = dict(h)
        htype = str(nh.get("type") or "").lower()
        ez = nh.get("entry_zone") if isinstance(nh.get("entry_zone"), dict) else {}
        anchor = str(ez.get("anchor") or "").lower()
        trig = str(nh.get("trigger") or "")
        is_breakish = (
            htype in (
                "break_upper",
                "momentum",
                "momentum_breakout",
                "breakout_follow",
                "right_breakout",
            )
            or "break_upper" in anchor
            or anchor in ("wedge_hold_level", "gms_volume_breakout")
        )
        is_aggressive = htype in ("pullback_buy", "breakout_buy")
        if is_breakish or is_aggressive:
            nh["type"] = "watch"
            nh["trigger"] = watch_trig
        elif "贴压" not in trig and "不追" not in trig and "风暴" not in trig:
            nh["trigger"] = f"{trig}；贴压不追，仅观察" if trig else watch_trig
        prev = nh.get("risk_note")
        if prev and str(prev).strip() and bit not in str(prev):
            nh["risk_note"] = f"{prev}；{bit}"
        else:
            nh["risk_note"] = bit if not prev else str(prev)
        out.append(nh)
    return out, risk_note


def _wedge_breakout_alert_payload(
    probe: Optional[Dict[str, Any]],
    primary: Optional[Dict[str, Any]],
    *,
    gms: Optional[Dict[str, Any]] = None,
    classic: Optional[Dict[str, Any]] = None,
    confluence: Optional[Dict[str, Any]] = None,
    camarilla: Optional[Dict[str, Any]] = None,
    atr: Optional[float] = None,
    gms_min: float = WEDGE_BREAKOUT_GMS_MIN,
) -> Optional[Dict[str, Any]]:
    """试探突破基础上：下降楔形 + GMS>门槛 → 楔形蓄势突破预警。

    与四策略选股命中（0/4）解耦：只要能取到 GMS 分数且达标即可升级。
    预警触发后自动映射上沿之上下一档有效共振阻力为预警目标（有则写入，无则允许真空）。
    """
    if not isinstance(probe, dict) or not probe.get("ok"):
        return None
    t = str(probe.get("pattern_type") or "")
    if t not in BULLISH_WEDGE_TYPES:
        return None
    gms_sc = _gms_score_total(gms)
    if gms_sc is None or gms_sc <= float(gms_min):
        return None
    upper = _f(probe.get("upper"))
    close = _f(probe.get("close"))
    if upper is None or upper <= 0:
        return None
    hold, hold_src = _resolve_wedge_hold_level(
        float(upper),
        close,
        classic=classic,
        confluence=confluence,
        camarilla=camarilla,
        atr=atr,
    )
    lab = str(probe.get("label") or _type_label(t))
    hold_txt = f"{hold:.2f}" if hold is not None else "上沿上方"
    note = (
        f"楔形蓄势突破预警：现价已上破{lab}上沿 ({float(upper):.2f})，"
        f"GMS {gms_sc:.1f}>{float(gms_min):.0f}；关注放量，以及 {hold_txt} 元站稳信号"
    )
    tgt_px, tgt_str, tgt_src = _resolve_wedge_alert_target(
        confluence, upper=float(upper), close=close
    )
    # 防守：跌回形态上沿下方视为预警失效（不改写夹杀买点失效位）
    alert_inv = round(float(upper) * float(BREAKOUT_DOWN_MULT), 2)
    if tgt_px is not None:
        if tgt_str is not None:
            note = (
                f"{note}；预警目标：{tgt_px:.2f} 附近"
                f"（强度 {tgt_str:g} 共振阻力带）"
            )
        else:
            note = f"{note}；预警目标：{tgt_px:.2f} 附近（共振阻力带）"
    return {
        "ok": True,
        "code": "wedge_breakout_alert",
        "pattern_type": t,
        "label": lab,
        "upper": round(float(upper), 2),
        "close": round(float(close), 2) if close is not None else None,
        "gms_score": round(float(gms_sc), 1),
        "gms_min": float(gms_min),
        "hold_level": hold,
        "hold_source": hold_src,
        "target": tgt_px,
        "alert_target": tgt_px,
        "target_strength": tgt_str,
        "target_source": tgt_src,
        "alert_invalidation": alert_inv,
        "engine_status": "forming",
        "display_status": "楔形蓄势突破预警",
        "status_note": note,
        "text": note,
    }


def _entry_to_target_upside(
    entry_high: Optional[float], target: Optional[float]
) -> Optional[float]:
    """(target - entry_high) / entry_high；缺字段或非正入场上沿则 None。"""
    eh = _f(entry_high)
    t = _f(target)
    if eh is None or t is None or eh <= 0:
        return None
    return (t - eh) / eh


def _space_note_for_hint(hint: Dict[str, Any]) -> Optional[str]:
    """entry.high→target 相对空间 < ENTRY_TARGET_MIN_SPACE_PCT 时给挂单下沿提示。"""
    if not isinstance(hint, dict):
        return None
    ez = hint.get("entry_zone") if isinstance(hint.get("entry_zone"), dict) else {}
    ups = _entry_to_target_upside(_f(ez.get("high")), hint.get("target"))
    if ups is None or ups >= float(ENTRY_TARGET_MIN_SPACE_PCT):
        return None
    el = _f(ez.get("low"))
    low_txt = f"{el:.2f}" if el is not None else "下沿"
    pct = int(round(float(ENTRY_TARGET_MIN_SPACE_PCT) * 100))
    return f"空间不足 {pct}%，建议仅挂单靠近下沿 {low_txt} 操作"


def _annotate_hints_entry_space(
    hints: List[Dict[str, Any]], risk_note: Optional[str]
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """为买点标注 space_note/risk_note，并并入顶层 risk_note（供 PDF/前端提示露出）。"""
    notes: List[str] = []
    for h in hints:
        if not isinstance(h, dict):
            continue
        note = _space_note_for_hint(h)
        if not note:
            continue
        h["space_note"] = note
        prev = h.get("risk_note")
        if prev and str(prev).strip() and str(prev).strip() != note:
            h["risk_note"] = f"{prev}；{note}"
        else:
            h["risk_note"] = note
        if note not in notes:
            notes.append(note)
    if notes:
        bit = "；".join(notes)
        risk_note = f"{risk_note}；{bit}" if risk_note else bit
    return hints, risk_note


def _build_rebound_note(
    market: Optional[Dict[str, Any]],
    *,
    has_archived: bool,
) -> Optional[str]:
    """活跃命中空 + 有归档背景 + 近端低点显著反弹 → 一句前瞻，不启新形态。"""
    if not has_archived or not isinstance(market, dict):
        return None
    close = _f(market.get("last_close"))
    lo = _f(market.get("swing_low"))
    lo_d = _parse_ymd(market.get("swing_low_date"))
    hi = _f(market.get("swing_high"))
    hi_d = _parse_ymd(market.get("swing_high_date"))
    if close is None or lo is None or lo <= 0:
        return None
    rebound = (close - lo) / lo
    if rebound < float(REBOUND_MIN_PCT):
        return None
    # 高点须不早于低点，才视为「自低点反弹」波段
    if hi is not None and lo_d and hi_d and hi_d < lo_d:
        return None
    lo_bit = f"{lo:.2f}" + (f"（{lo_d}）" if lo_d else "")
    hi_bit = ""
    if hi is not None and hi_d and (lo_d is None or hi_d >= lo_d):
        hi_bit = f"，波段高点 {hi:.2f}（{hi_d}）"
    return (
        f"主形态归档空窗：近端自低点 {lo_bit} 已反弹约 {rebound * 100:.0f}%"
        f"{hi_bit}；暂无活跃主导，可关注更小周期双底/上升通道是否形成（仅前瞻，非确认）"
    )


def _iter_confluence_supports(confluence: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """合并 nearest_support_zone + supports[]，按有效强度（含真空折减）降序去重。"""
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
            -(_zone_effective_strength(z) or 0.0),
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
        strength = _zone_effective_strength(z) or 0.0
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
        strength = _zone_effective_strength(z) or 0.0
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


def _next_resistance_zone_above(
    confluence: Optional[Dict[str, Any]],
    *,
    gate: float,
    entry_ref: float,
    min_strength: float = BREAK_TARGET_MIN_STRENGTH,
) -> Optional[Dict[str, Any]]:
    """gate 之上最近一档阻力带；优先 strength≥门槛，否则退回任意足够 upside 的阻力。"""
    best_strong: Optional[Dict[str, Any]] = None
    best_strong_px: Optional[float] = None
    best_any: Optional[Dict[str, Any]] = None
    best_any_px: Optional[float] = None
    g = float(gate)
    for z in _iter_confluence_resistances(confluence):
        center = _f(z.get("center")) or _f(z.get("low"))
        if center is None or center <= g:
            continue
        if not _target_upside_ok(entry_ref, center):
            continue
        strength = _f(z.get("strength")) or 0.0
        if best_any_px is None or center < best_any_px:
            best_any_px = center
            best_any = z
        if strength < float(min_strength):
            continue
        if best_strong_px is None or center < best_strong_px:
            best_strong_px = center
            best_strong = z
    return best_strong if best_strong is not None else best_any


def _next_resistance_above(
    confluence: Optional[Dict[str, Any]],
    *,
    gate: float,
    entry_ref: float,
    min_strength: float = BREAK_TARGET_MIN_STRENGTH,
) -> Optional[float]:
    """gate 之上最近一档阻力；优先 strength≥门槛，否则退回任意足够 upside 的阻力。"""
    z = _next_resistance_zone_above(
        confluence,
        gate=gate,
        entry_ref=entry_ref,
        min_strength=min_strength,
    )
    if not isinstance(z, dict):
        return None
    return _f(z.get("center")) or _f(z.get("low"))


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
    eff = _zone_effective_strength(zone)
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
    if eff is not None and (strength is None or abs(eff - strength) > 1e-9):
        ez["strength_adjusted"] = round(eff, 3)
    if zone.get("chips_void"):
        ez["chips_void"] = True
        if zone.get("void_note"):
            ez["void_note"] = zone.get("void_note")
    return ez


def _hint_near_support_pref(
    zone: Dict[str, Any],
    *,
    target: Optional[float],
    priority: int = 2,
    trigger: str = "回踩近端高强度共振支撑企稳（形态下沿过远，优先近端）",
    atr: Optional[float] = None,
    close: Optional[float] = None,
) -> Dict[str, Any]:
    """近端共振买点：失效位绑定**本档**支撑带下沿（再经 _clamp_invalidation），不与更远档共用。"""
    ez = _entry_zone_from_support(zone)
    # 本档下沿为失效锚；高 ATR 时可用中心 − k×ATR 作结构缓冲（再经 clamp）
    raw_inv = _f(zone.get("low"))
    if raw_inv is None:
        raw_inv = _f(ez.get("low"))
    center = _f(zone.get("center"))
    a = _f(atr)
    c = _f(close)
    if (
        a is not None
        and a > 0
        and center is not None
        and c is not None
        and c > 0
        and (a / c) >= float(INVALIDATION_ATR_PCT_LO)
    ):
        structural = center - float(INVALIDATION_ATR_K) * a
        if raw_inv is None or structural < raw_inv:
            raw_inv = structural
    return _with_clamped_invalidation(
        {
            "type": "watch",
            "entry_zone": ez,
            "trigger": trigger,
            "invalidation": round(raw_inv, 2) if raw_inv is not None else None,
            "target": round(target, 2) if target is not None else None,
            "priority": priority,
        },
        atr=atr,
        close=close,
    )


def _hint_far_pattern_lower(
    floor: float,
    *,
    target: Optional[float],
    anchor: str = "pattern_lower_far",
    atr: Optional[float] = None,
    close: Optional[float] = None,
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
        },
        atr=atr,
        close=close,
    )


def _hint_watch_break_upper(
    upper: float,
    *,
    target: Optional[float],
    trigger: Optional[str] = None,
    priority: int = 2,
    atr: Optional[float] = None,
    close: Optional[float] = None,
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
        },
        atr=atr,
        close=close,
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
    """从日线末两根推算涨跌幅与量比（相对前 20 日均量）；附带近端 swing 高低点。"""
    seq = [b for b in (bars or []) if isinstance(b, dict)]
    out: Dict[str, Any] = {
        "change_pct": None,
        "volume_ratio": None,
        "last_close": None,
        "swing_low": None,
        "swing_low_date": None,
        "swing_high": None,
        "swing_high_date": None,
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

    window = seq[-int(REBOUND_LOOKBACK_BARS) :]
    best_lo: Optional[Tuple[float, str]] = None
    best_hi: Optional[Tuple[float, str]] = None
    for b in window:
        d = _parse_ymd(b.get("date") or b.get("trade_date")) or ""
        lo = _f(b.get("low"))
        hi = _f(b.get("high"))
        if lo is not None and (best_lo is None or lo < best_lo[0]):
            best_lo = (lo, d)
        if hi is not None and (best_hi is None or hi > best_hi[0]):
            best_hi = (hi, d)
    if best_lo is not None:
        out["swing_low"] = round(best_lo[0], 4)
        out["swing_low_date"] = best_lo[1] or None
    if best_hi is not None:
        out["swing_high"] = round(best_hi[0], 4)
        out["swing_high_date"] = best_hi[1] or None
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


def _zone_effective_strength(z: Any) -> Optional[float]:
    """选型用有效强度：优先 strength_adjusted（支撑 void 折减 / 阻力 HVZ 增益），否则 strength。"""
    if not isinstance(z, dict):
        return None
    adj = _f(z.get("strength_adjusted"))
    if adj is not None:
        return adj
    return _f(z.get("strength"))


def _nearest_resistance_pressure(
    confluence: Optional[Dict[str, Any]],
    *,
    min_strength: float,
) -> Optional[Dict[str, Any]]:
    """近端/贴身阻力带有效强度 ≥ 门槛则返回该带。"""
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
        s = _zone_effective_strength(z)
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


def _rpe_signal_is_lead(rpe: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(rpe, dict):
        return False
    sig = str(rpe.get("signal_type") or rpe.get("label") or "").strip()
    if not sig:
        return False
    low = sig.lower()
    return ("领涨" in sig) or low in ("lead", "leading", "rpe_lead")


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
    lead_sig = _rpe_signal_is_lead(rpe)
    if z is None:
        return lead_sig, None
    return (z >= float(z_lead) or lead_sig), z


def _extract_camarilla_r4(
    classic: Optional[Dict[str, Any]] = None,
    *,
    camarilla: Optional[Dict[str, Any]] = None,
) -> Optional[float]:
    cam = camarilla if isinstance(camarilla, dict) else None
    if cam is None and isinstance(classic, dict):
        raw = classic.get("camarilla")
        cam = raw if isinstance(raw, dict) else None
    if not isinstance(cam, dict):
        return None
    return _f(cam.get("R4"))


def _resolve_close_px(
    *,
    market: Optional[Dict[str, Any]],
    primary: Optional[Dict[str, Any]],
    hits: Optional[Sequence[Dict[str, Any]]],
) -> Optional[float]:
    if isinstance(market, dict):
        c = _f(market.get("last_close"))
        if c is not None:
            return c
    if primary is not None:
        c = _hit_close(primary)
        if c is not None:
            return c
    for h in _active_hits(hits):
        c = _hit_close(h)
        if c is not None:
            return c
    return None


def _r4_break_or_retest(
    close: Optional[float],
    r4: Optional[float],
    *,
    near_pct: float = R4_RETEST_NEAR_PCT,
) -> bool:
    c, r = _f(close), _f(r4)
    if c is None or r is None or r <= 0:
        return False
    return c >= r * (1.0 - float(near_pct))


def _hints_cover_level(
    hints: Optional[Sequence[Dict[str, Any]]],
    level: Optional[float],
    *,
    tol_pct: float = MOMENTUM_R4_COVER_PCT,
) -> bool:
    lv = _f(level)
    if lv is None or lv <= 0:
        return False
    for h in hints or []:
        if not isinstance(h, dict):
            continue
        if str(h.get("type") or "") == "momentum_breakout":
            return True
        ez = h.get("entry_zone") if isinstance(h.get("entry_zone"), dict) else {}
        if str(ez.get("anchor") or "") in ("rpe_r4_retest", "camarilla_r4"):
            return True
        lo, hi = _f(ez.get("low")), _f(ez.get("high"))
        if lo is not None and hi is not None and lo <= lv <= hi:
            return True
        for ref in (ez.get("center"), lo, hi):
            rf = _f(ref)
            if rf is not None and abs(rf - lv) / lv <= float(tol_pct):
                return True
    return False


def _hints_lack_near_entry(
    hints: Optional[Sequence[Dict[str, Any]]],
    close: Optional[float],
    *,
    max_below_pct: float = MOMENTUM_HINT_NEAR_ENTRY_PCT,
) -> bool:
    """所有买点入场区相对现价过远（或缺失）→ 视为无可用近端买点。"""
    c = _f(close)
    if c is None or c <= 0:
        return True
    usable = False
    for h in hints or []:
        if not isinstance(h, dict):
            continue
        ez = h.get("entry_zone") if isinstance(h.get("entry_zone"), dict) else {}
        refs = [_f(ez.get("high")), _f(ez.get("center")), _f(ez.get("low"))]
        refs = [x for x in refs if x is not None]
        if not refs:
            continue
        # 入场参考落在现价下方 max_below 内，或已在现价上方（突破跟进）
        for ref in refs:
            if ref >= c:
                usable = True
                break
            if (c - ref) / c <= float(max_below_pct):
                usable = True
                break
        if usable:
            break
    return not usable


def _pick_super_support(
    confluence: Optional[Dict[str, Any]],
    *,
    min_strength: float = SUPER_SUPPORT_STRENGTH,
) -> Optional[Dict[str, Any]]:
    best: Optional[Dict[str, Any]] = None
    best_s = -1.0
    for z in _iter_confluence_supports(confluence):
        s = _zone_effective_strength(z) or 0.0
        if s < float(min_strength):
            continue
        if s > best_s:
            best_s = s
            best = z
    return best


def _build_super_support_highlight(
    confluence: Optional[Dict[str, Any]],
    *,
    min_strength: float = SUPER_SUPPORT_STRENGTH,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    z = _pick_super_support(confluence, min_strength=min_strength)
    if z is None:
        return None, None
    center = _f(z.get("center")) or _f(z.get("high")) or _f(z.get("low"))
    strength = _zone_effective_strength(z)
    raw_strength = _f(z.get("strength"))
    if center is None or strength is None:
        return None, None
    note = f"发现 {strength:.2f} 级超强结构垫（{center:.2f}），中线支撑极强"
    if z.get("chips_void") and z.get("void_note"):
        note = f"{note}；注：{z.get('void_note')}"
    lo, hi = _f(z.get("low")), _f(z.get("high"))
    highlight: Dict[str, Any] = {
        "kind": "super_support",
        "center": round(center, 2),
        "strength": round(strength, 2),
        "text": note,
    }
    if raw_strength is not None:
        highlight["strength_raw"] = round(raw_strength, 2)
    if z.get("chips_void"):
        highlight["chips_void"] = True
        if z.get("void_note"):
            highlight["void_note"] = z.get("void_note")
        adj = _f(z.get("strength_adjusted"))
        if adj is not None:
            highlight["strength_adjusted"] = round(adj, 2)
    if lo is not None:
        highlight["low"] = round(lo, 2)
    if hi is not None:
        highlight["high"] = round(hi, 2)
    return highlight, note


def _build_momentum_r4_hint(
    close: Optional[float],
    r4: float,
    confluence: Optional[Dict[str, Any]],
    *,
    grade: str = "enhanced",
    atr: Optional[float] = None,
) -> Dict[str, Any]:
    r4f = float(r4)
    band = max(0.02, abs(r4f) * 0.008)
    c = _f(close)
    gate = max(c, r4f) if c is not None else r4f
    tgt = _next_resistance_above(
        confluence, gate=gate, entry_ref=r4f, min_strength=float(BREAK_TARGET_MIN_STRENGTH)
    )
    if tgt is None:
        tgt = _farther_resistance_target(confluence, close, above=r4f, upper=None)
    if tgt is None:
        tgt = _nearest_resistance_px(confluence)
    if tgt is not None and c is not None and tgt <= c:
        alt = _farther_resistance_target(confluence, close, above=c, upper=None)
        if alt is not None:
            tgt = alt
    return _with_clamped_invalidation(
        {
            "type": "momentum_breakout",
            "entry_zone": {
                "low": round(r4f - band * 0.25, 2),
                "high": round(r4f + band, 2),
                "center": round(r4f, 2),
                "anchor": "rpe_r4_retest",
            },
            "trigger": f"回踩 Camarilla R4 {r4f:.2f} 企稳买入（RPE领涨·动量突破）",
            "invalidation": round(r4f * BREAKOUT_DOWN_MULT, 2),
            "target": round(tgt, 2) if tgt is not None else None,
            "priority": 1 if grade in ("strong", "enhanced") else 2,
        },
        atr=atr,
        close=close,
    )


def _should_inject_momentum_r4(
    *,
    active: Sequence[Dict[str, Any]],
    short_bias: str,
    hints: Sequence[Dict[str, Any]],
    rpe_ok: bool,
    r4_ok: bool,
    close: Optional[float],
    r4: Optional[float],
) -> bool:
    if not rpe_ok or not r4_ok:
        return False
    if short_bias == "看空":
        return False
    if _hints_cover_level(hints, r4):
        return False
    if not active or short_bias == "insufficient" or not hints:
        return True
    # 有活跃命中但买点无近端可用（如 forming 远端下沿）→ 仍补 R4 动量闭环
    return _hints_lack_near_entry(hints, close)


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
            "strength": _zone_effective_strength(pressure) if pressure else None,
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
    atr: Optional[float] = None,
    close: Optional[float] = None,
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
    close_px = _f(close) if _f(close) is not None else _hit_close(primary)
    atr_v = _f(atr)
    close = close_px  # 下方原逻辑沿用 close 变量名
    def _ci(h: Dict[str, Any]) -> Dict[str, Any]:
        return _with_clamped_invalidation(h, atr=atr_v, close=close)

    def _nsp(zone: Dict[str, Any], **kw: Any) -> Dict[str, Any]:
        return _hint_near_support_pref(zone, atr=atr_v, close=close, **kw)

    def _fpl(floor: float, **kw: Any) -> Dict[str, Any]:
        return _hint_far_pattern_lower(floor, atr=atr_v, close=close, **kw)

    def _wbu(upper: float, **kw: Any) -> Dict[str, Any]:
        return _hint_watch_break_upper(upper, atr=atr_v, close=close, **kw)

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
                    _nsp(
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
                _ci(
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
            _ci(
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

    def _append_far_floor_hint(*, with_note: bool = True) -> None:
        nonlocal risk_note
        if pattern_floor is None:
            return
        hints.append(
            _fpl(
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
                    _wbu(
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
                        _nsp(
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
                            _nsp(
                                watch2,
                                target=watch_tgt,
                                priority=3,
                                trigger="回踩更远近端共振支撑企稳（第二档观察）",
                            )
                        )
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
                _nsp(
                    near_main,
                    target=watch_tgt,
                    priority=2,
                    trigger=trig,
                )
            )
            watch2 = _pick_near_support_watch2(confluence, close, primary=near_main)
            if watch2 is not None:
                hints.append(
                    _nsp(
                        watch2,
                        target=watch_tgt,
                        priority=3,
                        trigger="回踩更远近端共振支撑企稳（第二档观察）",
                    )
                )
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
                _wbu(break_px, target=bu_tgt, trigger=trig)
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
            _ci(
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
            _ci(
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
        _ci(
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
    gms: Optional[Dict[str, Any]] = None,
    invalidated_count: int = 0,
    resonance_min_strength: float = RESONANCE_PRESSURE_MIN_STRENGTH,
    z_lead: float = DEFAULT_Z_LEAD,
    trade_advice: Optional[Dict[str, Any]] = None,
    asof: Optional[str] = None,
    market: Optional[Dict[str, Any]] = None,
    classic: Optional[Dict[str, Any]] = None,
    camarilla: Optional[Dict[str, Any]] = None,
    super_support_min_strength: float = SUPER_SUPPORT_STRENGTH,
    atr: Optional[float] = None,
    wedge_gms_min: float = WEDGE_BREAKOUT_GMS_MIN,
) -> Dict[str, Any]:
    """统一出口：short_bias + grade + buy_hints + disclaimer。

    gms 可选：提供 score 时，下降楔形微幅上破可升为「楔形蓄势突破预警」。
    """
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
    short_bias = str(classified.get("short_bias") or "insufficient")
    bias_label = classified.get("bias_label")
    grade = str(classified.get("grade") or "base")
    confidence = classified.get("confidence")
    rationale = str(classified.get("rationale") or "")

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

    atr_v = _extract_atr(classic, atr=atr)
    close_px = _resolve_close_px(
        market=market, primary=classified.get("primary"), hits=hits
    )

    hints, risk_note = build_buy_hints(
        short_bias,
        classified.get("primary"),
        confluence=confluence,
        grade=grade,
        pressure_zone=classified.get("pressure_zone"),
        atr=atr_v,
        close=close_px,
    )
    hints, risk_note = _annotate_hints_entry_space(hints, risk_note)

    active = _active_hits(hits)
    r4 = _extract_camarilla_r4(classic, camarilla=camarilla)
    rpe_ok, z_val = _rpe_lead_ok(rpe, z_lead=float(z_lead))
    r4_ok = _r4_break_or_retest(close_px, r4)
    if _should_inject_momentum_r4(
        active=active,
        short_bias=short_bias,
        hints=hints,
        rpe_ok=rpe_ok,
        r4_ok=r4_ok,
        close=close_px,
        r4=r4,
    ):
        assert r4 is not None
        mom = _build_momentum_r4_hint(
            close_px, float(r4), confluence, grade=grade, atr=atr_v
        )
        hints = [mom] + [h for h in hints if isinstance(h, dict)]
        hints, risk_note = _annotate_hints_entry_space(hints, risk_note)
        bit = f"RPE领涨且已上破/贴近 Camarilla R4 {float(r4):.2f}，补动量突破回踩买点"
        rationale = f"{rationale}；{bit}" if rationale else bit
        if short_bias == "insufficient":
            short_bias = "看多"
            bias_label = "动量突破"
            # 无形态时仍可按 RPE 增强档展示（与 _apply_grade_enhancers 旁证一致）
            if grade == "base" and rpe_ok:
                grade = "enhanced"
            if confidence is not None:
                try:
                    confidence = round(min(0.95, max(float(confidence), 0.45)), 3)
                except (TypeError, ValueError):
                    confidence = 0.45
            else:
                confidence = 0.45
        evidence.append(
            {
                "code": "momentum_r4_breakout",
                "ok": True,
                "r4": round(float(r4), 2),
                "close": round(float(close_px), 2) if close_px is not None else None,
                "z_score": z_val,
                "signal_type": (rpe.get("signal_type") if isinstance(rpe, dict) else None),
            }
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

    rebound_note: Optional[str] = None
    if not active:
        has_archived = any(
            isinstance(h, dict) and str(h.get("status") or "") == "archived"
            for h in (hits or [])
        )
        rebound_note = _build_rebound_note(market, has_archived=has_archived)
        if rebound_note:
            evidence.append(
                {
                    "code": "archive_rebound_note",
                    "ok": True,
                    "swing_low": (market or {}).get("swing_low")
                    if isinstance(market, dict)
                    else None,
                    "swing_high": (market or {}).get("swing_high")
                    if isinstance(market, dict)
                    else None,
                }
            )

    highlight, structure_note = _build_super_support_highlight(
        confluence, min_strength=float(super_support_min_strength)
    )
    if highlight:
        evidence.append(
            {
                "code": "super_support_highlight",
                "ok": True,
                "center": highlight.get("center"),
                "strength": highlight.get("strength"),
                "min_strength": float(super_support_min_strength),
            }
        )

    # A P0：forming 微幅上破上沿 → 试探突破（不改引擎 confirmed）
    probe = _breakout_probe_payload(classified.get("primary"))
    # B P0：下降楔形 + GMS>门槛 → 升为楔形蓄势突破预警（与策略选股命中解耦）
    wedge_alert = _wedge_breakout_alert_payload(
        probe,
        classified.get("primary"),
        gms=gms,
        classic=classic,
        confluence=confluence,
        camarilla=camarilla,
        atr=atr_v,
        gms_min=float(wedge_gms_min),
    )
    if wedge_alert and wedge_alert.get("ok"):
        hints = _apply_wedge_alert_targets_to_hints(hints, wedge_alert)
        # 右侧突破跟进买点：与左侧回踩并存，覆盖低位突破爆发
        if short_bias != "看空":
            follow = _build_wedge_breakout_follow_hint(
                wedge_alert,
                close=close_px,
                market=market,
                grade=grade,
                atr=atr_v,
            )
            if follow:
                left = _demote_left_side_hint_priority(
                    [h for h in hints if isinstance(h, dict)]
                )
                hints = [follow] + left
                hints, risk_note = _annotate_hints_entry_space(hints, risk_note)
                hold_v = _f(
                    (follow.get("entry_zone") or {}).get("center")
                ) or _f(wedge_alert.get("hold_level"))
                bit = (
                    f"楔形预警右侧跟进：带量站稳 {hold_v:.2f} 以上"
                    if hold_v is not None
                    else "楔形预警右侧跟进"
                )
                rationale = f"{rationale}；{bit}" if rationale else bit
                evidence.append(
                    {
                        "code": "wedge_breakout_follow",
                        "ok": True,
                        "hold_level": wedge_alert.get("hold_level"),
                        "trigger_status": follow.get("trigger_status"),
                        "invalidation": follow.get("invalidation"),
                        "target": follow.get("target"),
                    }
                )
    # C P0：极窄箱体变盘临界（与 probe/楔形并存）
    ultra = _ultra_squeeze_payload(confluence, close_px)
    # D P0：高倾角风暴预警（贴强压 + 阻力/支撑强度极度不对称）
    storm = _asymmetry_storm_payload(confluence, close_px)
    display_status: Optional[str] = None
    status_note: Optional[str] = None
    storm_wins = bool(storm and storm.get("ok"))
    wedge_wins = bool(wedge_alert and wedge_alert.get("ok")) and not storm_wins
    if probe and probe.get("ok"):
        if wedge_wins:
            display_status = str(
                wedge_alert.get("display_status") or "楔形蓄势突破预警"
            )
            status_note = str(
                wedge_alert.get("status_note") or wedge_alert.get("text") or ""
            )
        else:
            display_status = str(probe.get("display_status") or "试探突破")
            status_note = str(probe.get("status_note") or probe.get("text") or "")
        if status_note and not storm_wins:
            rationale = f"{rationale}；{status_note}" if rationale else status_note
            risk_note = f"{risk_note}；{status_note}" if risk_note else status_note
        evidence.append(
            {
                "code": "breakout_probe",
                "ok": True,
                "pattern_type": probe.get("pattern_type"),
                "upper": probe.get("upper"),
                "close": probe.get("close"),
                "display_status": display_status,
            }
        )
        if wedge_alert and wedge_alert.get("ok"):
            ev_wedge: Dict[str, Any] = {
                "code": "wedge_breakout_alert",
                "ok": True,
                "pattern_type": wedge_alert.get("pattern_type"),
                "upper": wedge_alert.get("upper"),
                "close": wedge_alert.get("close"),
                "gms_score": wedge_alert.get("gms_score"),
                "hold_level": wedge_alert.get("hold_level"),
                "hold_source": wedge_alert.get("hold_source"),
                "target": wedge_alert.get("target"),
                "target_strength": wedge_alert.get("target_strength"),
                "alert_invalidation": wedge_alert.get("alert_invalidation"),
                "display_status": (
                    wedge_alert.get("display_status") or "楔形蓄势突破预警"
                ),
            }
            if storm_wins:
                ev_wedge["suppressed_by"] = "asymmetry_storm"
            evidence.append(ev_wedge)

    # 优先级：高倾角风暴预警 ≥ 极窄箱体 > 楔形蓄势突破预警 > 试探突破 / 空态
    # （头重脚轻贴强压时不鼓励追涨，风暴覆盖楔形突破预警盘口态）
    if storm_wins:
        display_status = str(
            storm.get("display_status") or ASYMMETRY_STORM_DISPLAY_STATUS
        )
        status_note = str(storm.get("status_note") or storm.get("text") or "")
        if status_note:
            rationale = f"{rationale}；{status_note}" if rationale else status_note
        hints, risk_note = _apply_asymmetry_storm_to_hints(hints, storm, risk_note)
        evidence.append(
            {
                "code": "asymmetry_storm",
                "ok": True,
                "support_strength": storm.get("support_strength"),
                "resistance_strength": storm.get("resistance_strength"),
                "strength_ratio": storm.get("strength_ratio"),
                "dist_to_resist_pct": storm.get("dist_to_resist_pct"),
                "support": storm.get("support"),
                "resistance": storm.get("resistance"),
                "display_status": display_status,
            }
        )
        if ultra and ultra.get("ok"):
            evidence.append(
                {
                    "code": "ultra_squeeze",
                    "ok": True,
                    "suppressed_by": "asymmetry_storm",
                    "support": ultra.get("support"),
                    "resistance": ultra.get("resistance"),
                    "width_pct": ultra.get("width_pct"),
                    "display_status": ULTRA_SQUEEZE_DISPLAY_STATUS,
                }
            )
    elif ultra and ultra.get("ok") and not wedge_wins:
        display_status = str(
            ultra.get("display_status") or ULTRA_SQUEEZE_DISPLAY_STATUS
        )
        status_note = str(ultra.get("status_note") or ultra.get("text") or "")
        if status_note:
            # 覆盖普通试探文案；若此前无 probe 文案则写入 rationale
            rationale = f"{rationale}；{status_note}" if rationale else status_note
        hints, risk_note = _apply_ultra_squeeze_to_hints(hints, ultra, risk_note)
        evidence.append(
            {
                "code": "ultra_squeeze",
                "ok": True,
                "support": ultra.get("support"),
                "resistance": ultra.get("resistance"),
                "width_pct": ultra.get("width_pct"),
                "break_observe": ultra.get("break_observe"),
                "pullback": ultra.get("pullback"),
                "display_status": display_status,
            }
        )
    elif ultra and ultra.get("ok") and wedge_wins:
        # 仍记录证据，但不覆盖更强突破预警盘口态
        evidence.append(
            {
                "code": "ultra_squeeze",
                "ok": True,
                "suppressed_by": "wedge_breakout_alert",
                "support": ultra.get("support"),
                "resistance": ultra.get("resistance"),
                "width_pct": ultra.get("width_pct"),
                "display_status": ULTRA_SQUEEZE_DISPLAY_STATUS,
            }
        )

    gms_score_out = _gms_score_total(gms)
    out: Dict[str, Any] = {
        "short_bias": short_bias,
        "bias_label": bias_label,
        "grade": grade,
        "confidence": confidence,
        "rationale": rationale,
        "evidence": evidence,
        "buy_hints": hints,
        "risk_note": risk_note,
        "rebound_note": rebound_note,
        "highlight": highlight,
        "structure_note": structure_note,
        "disclaimer": DISCLAIMER,
        "pattern_hierarchy": hierarchy,
        "nesting_note": (hierarchy or {}).get("nesting_note") if hierarchy else None,
        "breakout_probe": probe,
        "wedge_breakout_alert": wedge_alert,
        "ultra_squeeze": ultra,
        "asymmetry_storm": storm,
        "status_note": status_note,
        "display_status": display_status,
        "gms_score": round(float(gms_score_out), 1) if gms_score_out is not None else None,
        "atr": round(float(atr_v), 4) if atr_v is not None else None,
    }
    return out


def annotate_hits_breakout_probe(
    hits: Optional[Sequence[Dict[str, Any]]],
    tactical: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """把 tactical 试探突破/楔形蓄势预警/极窄箱体/高倾角风暴写回命中项。"""
    out: List[Dict[str, Any]] = [h for h in (hits or []) if isinstance(h, dict)]
    if not isinstance(tactical, dict):
        return out
    probe = tactical.get("breakout_probe")
    alert = tactical.get("wedge_breakout_alert")
    ultra = tactical.get("ultra_squeeze")
    storm = tactical.get("asymmetry_storm")
    disp_now = str(tactical.get("display_status") or "")
    use_storm = (
        isinstance(storm, dict)
        and storm.get("ok")
        and disp_now == ASYMMETRY_STORM_DISPLAY_STATUS
    )
    use_alert = isinstance(alert, dict) and alert.get("ok") and not use_storm
    use_probe = isinstance(probe, dict) and probe.get("ok")
    use_ultra = (
        isinstance(ultra, dict)
        and ultra.get("ok")
        and disp_now == ULTRA_SQUEEZE_DISPLAY_STATUS
    )
    if not use_probe and not use_ultra and not use_storm:
        return out

    def _annotate_forming(disp: str, note: str, **flags: Any) -> None:
        ptype = str(flags.pop("_ptype", "") or "")
        for h in out:
            if str(h.get("status") or "") != "forming":
                continue
            if ptype and str(h.get("pattern_type") or "") != ptype:
                continue
            h["display_status"] = disp
            h["status_note"] = note
            for k, v in flags.items():
                if v:
                    h[k] = True

    if use_storm:
        note = str(
            storm.get("status_note")
            or storm.get("text")
            or tactical.get("status_note")
            or ""
        )
        ptype = ""
        if use_probe:
            src = alert if (isinstance(alert, dict) and alert.get("ok")) else probe
            ptype = str(
                (src.get("pattern_type") if isinstance(src, dict) else None)
                or probe.get("pattern_type")
                or ""
            )
        _annotate_forming(
            ASYMMETRY_STORM_DISPLAY_STATUS,
            note,
            _ptype=ptype,
            asymmetry_storm=True,
            breakout_probe=bool(use_probe),
        )
        return out

    if use_probe:
        src = alert if use_alert else probe
        ptype = str(src.get("pattern_type") or probe.get("pattern_type") or "")
        disp = str(
            (src.get("display_status") if isinstance(src, dict) else None)
            or tactical.get("display_status")
            or ("楔形蓄势突破预警" if use_alert else "试探突破")
        )
        # 极窄箱体可覆盖普通试探（楔形预警仍优先；风暴已在上方处理）
        if use_ultra and not use_alert:
            disp = ULTRA_SQUEEZE_DISPLAY_STATUS
            note = str(
                ultra.get("status_note")
                or ultra.get("text")
                or tactical.get("status_note")
                or ""
            )
        else:
            note = str(
                (src.get("status_note") if isinstance(src, dict) else None)
                or tactical.get("status_note")
                or ""
            )
        _annotate_forming(
            disp,
            note,
            _ptype=ptype,
            breakout_probe=True,
            wedge_breakout_alert=bool(use_alert),
            ultra_squeeze=bool(use_ultra and not use_alert),
        )
        return out
    # 无 probe：仅极窄箱体 → 标注 forming 主命中
    if use_ultra:
        note = str(
            ultra.get("status_note")
            or ultra.get("text")
            or tactical.get("status_note")
            or ""
        )
        _annotate_forming(ULTRA_SQUEEZE_DISPLAY_STATUS, note, ultra_squeeze=True)
    return out
