# -*- coding: utf-8 -*-
"""楔形 + 简化旗形。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .pivots import extract_pivot_sequence, linreg_slope
from .schema import fmt_px, make_hit


def _closes(bars: Sequence[Dict[str, Any]]) -> List[float]:
    out: List[float] = []
    for b in bars:
        try:
            c = float(b.get("close"))
            if c == c:
                out.append(c)
        except (TypeError, ValueError):
            continue
    return out


def detect_wedges(
    bars: Sequence[Dict[str, Any]],
    pivots: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    piv = pivots if pivots is not None else extract_pivot_sequence(bars)
    highs = [p for p in piv if p["kind"] == "high"]
    lows = [p for p in piv if p["kind"] == "low"]
    if len(highs) < 3 or len(lows) < 3:
        return []

    hi, lo = highs[-4:], lows[-4:]
    hs = linreg_slope([float(p["index"]) for p in hi], [float(p["price"]) for p in hi])
    ls = linreg_slope([float(p["index"]) for p in lo], [float(p["price"]) for p in lo])
    if hs is None or ls is None:
        return []

    first_w = abs(hi[0]["price"] - lo[0]["price"])
    last_w = abs(hi[-1]["price"] - lo[-1]["price"])
    if first_w <= 0 or last_w >= first_w * 0.95:
        return []

    # 同向收敛
    same_up = hs > 0 and ls > 0
    same_down = hs < 0 and ls < 0
    if not (same_up or same_down):
        return []

    closes = _closes(bars)
    if not closes:
        return []
    last_c = closes[-1]
    upper, lower = hi[-1]["price"], lo[-1]["price"]

    if same_up:
        pattern_type = "rising_wedge"
        label = "上升楔形"
        confirmed = last_c < lower
    else:
        pattern_type = "falling_wedge"
        label = "下降楔形"
        confirmed = last_c > upper

    status = "confirmed" if confirmed else "forming"
    conf = 0.62 if confirmed else 0.45
    return [
        make_hit(
            pattern_family="wedge_flag",
            pattern_type=pattern_type,
            status=status,
            confidence=conf,
            reason=(
                f"{label} {fmt_px('上沿', round(upper, 4), hi[-1].get('date'))} "
                f"{fmt_px('下沿', round(lower, 4), lo[-1].get('date'))} "
                f"上沿斜率={round(hs, 6)} 下沿斜率={round(ls, 6)}"
            ),
            key_levels={
                "upper": round(upper, 4),
                "lower": round(lower, 4),
                "last_close": round(last_c, 4),
            },
            pivots=[
                *[{"role": "high", "date": p.get("date"), "price": p["price"]} for p in hi[-3:]],
                *[{"role": "low", "date": p.get("date"), "price": p["price"]} for p in lo[-3:]],
            ],
        )
    ]


def detect_flags(
    bars: Sequence[Dict[str, Any]],
    pivots: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """简化旗形：先有一段强趋势旗杆，随后短轴通道整理，再同向突破。"""
    piv = pivots if pivots is not None else extract_pivot_sequence(bars)
    if len(piv) < 4:
        return []
    closes = _closes(bars)
    if len(closes) < 30:
        return []

    # 旗杆：识别前段最大单向波动
    look = closes[-60:] if len(closes) >= 60 else closes
    pole_up = False
    pole_down = False
    for i in range(10, len(look) - 8):
        seg = look[i - 10 : i]
        if not seg:
            continue
        chg = (seg[-1] - seg[0]) / max(abs(seg[0]), 1e-9)
        if chg >= 0.08:
            pole_up = True
            pole_end = len(closes) - len(look) + i
            break
        if chg <= -0.08:
            pole_down = True
            pole_end = len(closes) - len(look) + i
            break
    else:
        return []

    # 旗面：旗杆后短轴枢轴通道（近 3 高 3 低近似平行）
    after = [p for p in piv if int(p["index"]) >= pole_end]
    highs = [p for p in after if p["kind"] == "high"][-3:]
    lows = [p for p in after if p["kind"] == "low"][-3:]
    if len(highs) < 2 or len(lows) < 2:
        return []
    hs = linreg_slope([float(p["index"]) for p in highs], [float(p["price"]) for p in highs])
    ls = linreg_slope([float(p["index"]) for p in lows], [float(p["price"]) for p in lows])
    if hs is None or ls is None:
        return []
    # 近似平行（斜率同号且接近）
    if hs * ls < 0:
        return []
    if abs(hs - ls) > abs(hs) * 2.5 + 1e-6:
        return []

    last_c = closes[-1]
    upper, lower = highs[-1]["price"], lows[-1]["price"]
    if pole_up:
        pattern_type = "bull_flag"
        label = "上升旗形"
        confirmed = last_c > upper
    else:
        pattern_type = "bear_flag"
        label = "下降旗形"
        confirmed = last_c < lower

    status = "confirmed" if confirmed else "forming"
    conf = 0.58 if confirmed else 0.42
    return [
        make_hit(
            pattern_family="wedge_flag",
            pattern_type=pattern_type,
            status=status,
            confidence=conf,
            reason=(
                f"{label}（简化规则）"
                f" {fmt_px('通道上沿', round(upper, 4), highs[-1].get('date'))}"
                f" {fmt_px('下沿', round(lower, 4), lows[-1].get('date'))}"
            ),
            key_levels={
                "upper": round(upper, 4),
                "lower": round(lower, 4),
                "last_close": round(last_c, 4),
            },
            pivots=[
                *[{"role": "high", "date": p.get("date"), "price": p["price"]} for p in highs],
                *[{"role": "low", "date": p.get("date"), "price": p["price"]} for p in lows],
            ],
            extra={"simplified": True},
        )
    ]


def detect_wedges_flags(
    bars: Sequence[Dict[str, Any]],
    pivots: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    piv = pivots if pivots is not None else extract_pivot_sequence(bars)
    hits: List[Dict[str, Any]] = []
    hits.extend(detect_wedges(bars, piv))
    hits.extend(detect_flags(bars, piv))
    return hits
