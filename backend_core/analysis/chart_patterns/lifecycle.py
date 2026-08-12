# -*- coding: utf-8 -*-
"""已确认形态生命周期：目标兑现/大幅回吐后归档，避免过期主形态霸榜。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .rules import (
    LIFECYCLE_GIVEBACK_RATIO,
    LIFECYCLE_MIN_BARS,
    LIFECYCLE_MIN_EXCURSION_PCT,
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


def _bar_close(b: Dict[str, Any]) -> Optional[float]:
    try:
        c = float(b.get("close"))
        return c if c == c else None
    except (TypeError, ValueError):
        return None


def _bar_date(b: Dict[str, Any]) -> str:
    return str(b.get("date") or "")[:10]


def _index_on_or_after(bars: Sequence[Dict[str, Any]], date_s: str) -> Optional[int]:
    if not date_s:
        return None
    for i, b in enumerate(bars):
        if _bar_date(b) >= date_s:
            return i
    return None


def _is_bullish_reversal(pattern_type: str) -> bool:
    return pattern_type in ("double_bottom", "head_shoulders_bottom")


def apply_pattern_lifecycle(
    hits: List[Dict[str, Any]],
    bars: Sequence[Dict[str, Any]],
    *,
    min_bars: int = LIFECYCLE_MIN_BARS,
    min_excursion_pct: float = LIFECYCLE_MIN_EXCURSION_PCT,
    giveback_ratio: float = LIFECYCLE_GIVEBACK_RATIO,
) -> List[Dict[str, Any]]:
    """将已走完周期的已确认反转形态标为 archived。

    条件（同时满足）：
    1. status=confirmed 且为反转类；
    2. 自 formed_at 起至少 min_bars 根 K；
    3. 有利方向最大涨跌幅 ≥ min_excursion_pct；
    4. 现价相对该极值已回吐 ≥ giveback_ratio（双底：从最高回落；双顶对称）。
    """
    if not hits or not bars:
        return hits
    last_c = _bar_close(bars[-1])
    if last_c is None or last_c <= 0:
        return hits
    last_i = len(bars) - 1

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
        formed = str(hit.get("formed_at") or "")[:10]
        start_i = _index_on_or_after(bars, formed)
        if start_i is None:
            out.append(hit)
            continue
        elapsed = last_i - start_i
        if elapsed < int(min_bars):
            out.append(hit)
            continue

        window = bars[start_i:]
        closes = [c for c in (_bar_close(b) for b in window) if c is not None]
        if len(closes) < 5:
            out.append(hit)
            continue
        base = closes[0]
        if base <= 0:
            out.append(hit)
            continue

        bullish = _is_bullish_reversal(ptype)
        if bullish:
            peak = max(closes)
            excursion = (peak - base) / base
            if excursion < float(min_excursion_pct):
                out.append(hit)
                continue
            giveback = (peak - last_c) / max(peak - base, 1e-12)
            if giveback < float(giveback_ratio):
                out.append(hit)
                continue
        else:
            trough = min(closes)
            excursion = (base - trough) / base
            if excursion < float(min_excursion_pct):
                out.append(hit)
                continue
            giveback = (last_c - trough) / max(base - trough, 1e-12)
            if giveback < float(giveback_ratio):
                out.append(hit)
                continue

        hit["status"] = "archived"
        hit["lifecycle"] = "archived"
        reason = str(hit.get("reason") or "").strip()
        note = "生命周期已结束（目标区兑现后大幅回吐，已归档）"
        if note not in reason:
            hit["reason"] = f"{reason}；{note}" if reason else note
        out.append(hit)
    return out
