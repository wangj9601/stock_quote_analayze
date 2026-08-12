# -*- coding: utf-8 -*-
"""已确认形态生命周期：测幅兑现 / 反向突破 / 大幅回吐后归档，避免过期主形态霸榜。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from .rules import (
    LIFECYCLE_GIVEBACK_RATIO,
    LIFECYCLE_MIN_BARS,
    LIFECYCLE_MIN_EXCURSION_PCT,
    LIFECYCLE_TARGET_RATIO,
)

# 仅对反转类做归档（巩固形态时效较短，另议）
_REVERSAL_TYPES = frozenset(
    {
        "double_bottom",
        "double_top",
        "head_shoulders_bottom",
        "head_shoulders_top",
    }
)

# 已确认巩固突破：与反转方向冲突时用于降权旧反转
_BULLISH_CONSOL = frozenset(
    {"falling_wedge", "bull_flag", "ascending_triangle"}
)
_BEARISH_CONSOL = frozenset(
    {"rising_wedge", "bear_flag", "descending_triangle"}
)


def _bar_close(b: Dict[str, Any]) -> Optional[float]:
    try:
        c = float(b.get("close"))
        return c if c == c else None
    except (TypeError, ValueError):
        return None


def _bar_high(b: Dict[str, Any]) -> Optional[float]:
    try:
        h = float(b.get("high"))
        return h if h == h else None
    except (TypeError, ValueError):
        return None


def _bar_low(b: Dict[str, Any]) -> Optional[float]:
    try:
        lo = float(b.get("low"))
        return lo if lo == lo else None
    except (TypeError, ValueError):
        return None


def _bar_date(b: Dict[str, Any]) -> str:
    return str(b.get("date") or b.get("trade_date") or "")[:10]


def _f(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def _index_on_or_after(bars: Sequence[Dict[str, Any]], date_s: str) -> Optional[int]:
    if not date_s:
        return None
    for i, b in enumerate(bars):
        if _bar_date(b) >= date_s:
            return i
    return None


def _is_bullish_reversal(pattern_type: str) -> bool:
    return pattern_type in ("double_bottom", "head_shoulders_bottom")


def _hit_formed_at(hit: Dict[str, Any]) -> str:
    return str(hit.get("formed_at") or hit.get("confirm_date") or "")[:10]


def _mark_archived(hit: Dict[str, Any], note: str) -> Dict[str, Any]:
    hit = dict(hit)
    hit["status"] = "archived"
    hit["lifecycle"] = "archived"
    reason = str(hit.get("reason") or "").strip()
    if note and note not in reason:
        hit["reason"] = f"{reason}；{note}" if reason else note
    return hit


def _measured_target(
    hit: Dict[str, Any],
    *,
    target_ratio: float,
) -> Optional[Tuple[float, bool]]:
    """返回 (目标价, 是否看多目标)；无法计算则 None。

    双顶/头肩顶：目标 = 颈线 − (峰−颈线)×ratio（向下）
    双底/头肩底：目标 = 颈线 + (颈线−谷)×ratio（向上）
    """
    lv = hit.get("key_levels") if isinstance(hit.get("key_levels"), dict) else {}
    ptype = str(hit.get("pattern_type") or "")
    neck = _f(lv.get("neckline"))
    if neck is None or neck <= 0:
        return None
    ratio = max(0.5, min(1.2, float(target_ratio)))

    if ptype == "double_top":
        peak = max(x for x in (_f(lv.get("h1")), _f(lv.get("h2"))) if x is not None) if (
            _f(lv.get("h1")) is not None or _f(lv.get("h2")) is not None
        ) else None
        if peak is None or peak <= neck:
            return None
        return neck - (peak - neck) * ratio, False

    if ptype == "double_bottom":
        trough = min(x for x in (_f(lv.get("l1")), _f(lv.get("l2"))) if x is not None) if (
            _f(lv.get("l1")) is not None or _f(lv.get("l2")) is not None
        ) else None
        if trough is None or neck <= trough:
            return None
        return neck + (neck - trough) * ratio, True

    if ptype == "head_shoulders_top":
        peak = _f(lv.get("head"))
        if peak is None or peak <= neck:
            return None
        return neck - (peak - neck) * ratio, False

    if ptype == "head_shoulders_bottom":
        trough = _f(lv.get("head"))
        if trough is None or neck <= trough:
            return None
        return neck + (neck - trough) * ratio, True

    return None


def _target_realized(
    hit: Dict[str, Any],
    bars: Sequence[Dict[str, Any]],
    *,
    target_ratio: float,
) -> Optional[str]:
    """测幅目标已兑现则返回归档说明，否则 None。"""
    mt = _measured_target(hit, target_ratio=target_ratio)
    if mt is None:
        return None
    target, bullish = mt
    formed = _hit_formed_at(hit)
    start_i = _index_on_or_after(bars, formed) if formed else 0
    if start_i is None:
        start_i = 0
    window = bars[start_i:]
    if bullish:
        highs = [h for h in (_bar_high(b) for b in window) if h is not None]
        if highs and max(highs) >= target:
            return (
                f"生命周期已结束（测幅目标已兑现≥{target:.2f}，已归档）"
            )
    else:
        lows = [lo for lo in (_bar_low(b) for b in window) if lo is not None]
        if lows and min(lows) <= target:
            return (
                f"生命周期已结束（测幅目标已兑现≤{target:.2f}，已归档）"
            )
    return None


def _consol_bias(pattern_type: str) -> Optional[str]:
    if pattern_type in _BULLISH_CONSOL:
        return "bull"
    if pattern_type in _BEARISH_CONSOL:
        return "bear"
    if pattern_type == "symmetric_triangle":
        return "neutral"
    return None


def _newer_opposite_consol_breakout(
    hit: Dict[str, Any],
    hits: Sequence[Dict[str, Any]],
) -> Optional[str]:
    """若存在更晚形成的、方向相反的已确认巩固突破，返回归档说明。"""
    ptype = str(hit.get("pattern_type") or "")
    bullish_rev = _is_bullish_reversal(ptype)
    formed = _hit_formed_at(hit)
    for other in hits:
        if str(other.get("pattern_type") or "") == ptype and _hit_formed_at(other) == formed:
            continue
        if str(other.get("status") or "") != "confirmed":
            continue
        ot = str(other.get("pattern_type") or "")
        bias = _consol_bias(ot)
        if bias is None or bias == "neutral":
            # 对称三角：用上下沿相对收盘粗判突破方向
            if ot != "symmetric_triangle":
                continue
            lv = other.get("key_levels") if isinstance(other.get("key_levels"), dict) else {}
            c = _f(lv.get("last_close"))
            up = _f(lv.get("upper"))
            lo = _f(lv.get("lower"))
            if c is not None and up is not None and c > up * 1.005:
                bias = "bull"
            elif c is not None and lo is not None and c < lo * 0.995:
                bias = "bear"
            else:
                continue
        # 空头反转 vs 偏多巩固突破；多头反转 vs 偏空巩固突破
        if bullish_rev and bias != "bear":
            continue
        if (not bullish_rev) and bias != "bull":
            continue
        oformed = _hit_formed_at(other)
        if formed and oformed and oformed < formed:
            continue
        lab = ot
        return (
            f"生命周期已结束（后续反向巩固突破「{lab}」已确认，旧反转降权归档）"
        )
    return None


def _giveback_archive_note(
    hit: Dict[str, Any],
    bars: Sequence[Dict[str, Any]],
    *,
    min_bars: int,
    min_excursion_pct: float,
    giveback_ratio: float,
) -> Optional[str]:
    """原有：时间+有利方向极值+回吐 → 归档说明。"""
    formed = _hit_formed_at(hit)
    start_i = _index_on_or_after(bars, formed)
    if start_i is None:
        return None
    last_i = len(bars) - 1
    if last_i - start_i < int(min_bars):
        return None
    last_c = _bar_close(bars[-1])
    if last_c is None or last_c <= 0:
        return None

    window = bars[start_i:]
    closes = [c for c in (_bar_close(b) for b in window) if c is not None]
    if len(closes) < 5:
        return None
    base = closes[0]
    if base <= 0:
        return None

    ptype = str(hit.get("pattern_type") or "")
    bullish = _is_bullish_reversal(ptype)
    if bullish:
        peak = max(closes)
        excursion = (peak - base) / base
        if excursion < float(min_excursion_pct):
            return None
        giveback = (peak - last_c) / max(peak - base, 1e-12)
        if giveback < float(giveback_ratio):
            return None
    else:
        trough = min(closes)
        excursion = (base - trough) / base
        if excursion < float(min_excursion_pct):
            return None
        giveback = (last_c - trough) / max(base - trough, 1e-12)
        if giveback < float(giveback_ratio):
            return None
    return "生命周期已结束（目标区兑现后大幅回吐，已归档）"


def apply_pattern_lifecycle(
    hits: List[Dict[str, Any]],
    bars: Sequence[Dict[str, Any]],
    *,
    min_bars: int = LIFECYCLE_MIN_BARS,
    min_excursion_pct: float = LIFECYCLE_MIN_EXCURSION_PCT,
    giveback_ratio: float = LIFECYCLE_GIVEBACK_RATIO,
    target_ratio: float = LIFECYCLE_TARGET_RATIO,
) -> List[Dict[str, Any]]:
    """将已走完周期的已确认反转形态标为 archived。

    优先级：
    1. 测幅目标已兑现（不依赖 45 根 / 回吐）；
    2. 后续出现反向已确认巩固突破 → 降权归档；
    3. 原条件：≥min_bars + 有利方向极值 + 回吐。
    """
    if not hits or not bars:
        return hits

    # 先用原始列表做「反向突破」对照，再逐条归档
    out: List[Dict[str, Any]] = []
    for h in hits:
        hit = dict(h)
        if str(hit.get("status") or "") != "confirmed":
            out.append(hit)
            continue
        ptype = str(hit.get("pattern_type") or "")
        if ptype not in _REVERSAL_TYPES:
            out.append(hit)
            continue

        note = _target_realized(hit, bars, target_ratio=target_ratio)
        if not note:
            note = _newer_opposite_consol_breakout(hit, hits)
        if not note:
            note = _giveback_archive_note(
                hit,
                bars,
                min_bars=min_bars,
                min_excursion_pct=min_excursion_pct,
                giveback_ratio=giveback_ratio,
            )
        if note:
            out.append(_mark_archived(hit, note))
        else:
            out.append(hit)
    return out
