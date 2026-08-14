# -*- coding: utf-8 -*-
"""上升 / 下降 / 对称三角形。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .pivots import extract_pivot_sequence, linreg_slope
from .rules import SLOPE_UNIT_NOTE, consolidation_status
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


def detect_triangles(
    bars: Sequence[Dict[str, Any]],
    pivots: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    piv = pivots if pivots is not None else extract_pivot_sequence(bars)
    highs = [p for p in piv if p["kind"] == "high"]
    lows = [p for p in piv if p["kind"] == "low"]
    if len(highs) < 3 or len(lows) < 3:
        return []

    # 最近若干枢轴
    hi = highs[-4:]
    lo = lows[-4:]
    hx = [float(p["index"]) for p in hi]
    hy = [float(p["price"]) for p in hi]
    lx = [float(p["index"]) for p in lo]
    ly = [float(p["price"]) for p in lo]
    hs = linreg_slope(hx, hy)
    ls = linreg_slope(lx, ly)
    if hs is None or ls is None:
        return []

    first_span = max(hy[0], ly[0], 1e-9)
    last_hi, last_lo = hy[-1], ly[-1]
    first_width = abs(hy[0] - ly[0])
    last_width = abs(last_hi - last_lo)
    if first_width <= 0:
        return []
    # 必须收敛
    if last_width >= first_width * 0.92:
        return []

    closes = _closes(bars)
    if not closes:
        return []
    last_c = closes[-1]
    mid = (last_hi + last_lo) / 2.0

    # 分类
    flat_thr = abs(first_span) * 0.0008  # 近似走平
    pattern_type = None
    if abs(hs) < flat_thr and ls > flat_thr:
        pattern_type = "ascending_triangle"
        label = "上升三角"
    elif abs(ls) < flat_thr and hs < -flat_thr:
        pattern_type = "descending_triangle"
        label = "下降三角"
    elif hs < -flat_thr and ls > flat_thr:
        pattern_type = "symmetrical_triangle"
        label = "对称三角"
    else:
        return []

    # 突破确认：预期方向 → confirmed；反向脱离 → invalidated
    if pattern_type == "ascending_triangle":
        status, st_note = consolidation_status(
            last_c, last_hi, last_lo, expect_up=True
        )
    elif pattern_type == "descending_triangle":
        status, st_note = consolidation_status(
            last_c, last_hi, last_lo, expect_down=True
        )
    else:
        status, st_note = consolidation_status(
            last_c, last_hi, last_lo, expect_up=True, expect_down=True
        )

    if status == "confirmed":
        conf = 0.65
    elif status == "invalidated":
        conf = 0.2
    else:
        conf = 0.48
    shrink = 1.0 - (last_width / first_width)
    conf = min(1.0, conf + max(0.0, shrink) * 0.15)

    # Time-to-apex：用高低回归线交点相对当前末根的剩余 K 线数（轻量估计，不作硬门槛）
    bars_to_apex: Optional[float] = None
    apex_window: Optional[str] = None
    n_bars = len(bars)
    if n_bars > 0 and hs != ls:
        hmx = sum(hx) / len(hx)
        hmy = sum(hy) / len(hy)
        lmx = sum(lx) / len(lx)
        lmy = sum(ly) / len(ly)
        denom = hs - ls
        if abs(denom) > 1e-12:
            apex_x = (lmy - ls * lmx - hmy + hs * hmx) / denom
            remaining = apex_x - float(n_bars - 1)
            # 仅收敛指向未来的交点有意义
            if remaining > 0 and remaining < 500:
                bars_to_apex = round(remaining, 1)
                lo_w = max(1, int(remaining) - 2)
                hi_w = int(remaining) + 3
                apex_window = f"{lo_w}-{hi_w}根K线"

    reason = (
        f"{label} 收敛约{round(shrink * 100, 1)}%"
        f" {fmt_px('上沿', round(last_hi, 4), hi[-1].get('date'))}"
        f" {fmt_px('下沿', round(last_lo, 4), lo[-1].get('date'))}"
        f" 上沿斜率={round(hs, 6)}{SLOPE_UNIT_NOTE}"
        f" 下沿斜率={round(ls, 6)}{SLOPE_UNIT_NOTE}"
    )
    if bars_to_apex is not None:
        reason = f"{reason} 预计约{bars_to_apex}根至顶点"
        if apex_window:
            reason = f"{reason}（拐点窗口约{apex_window}）"
    if st_note:
        reason = f"{reason} {st_note}"

    key_levels: Dict[str, Any] = {
        "upper": round(last_hi, 4),
        "lower": round(last_lo, 4),
        "mid": round(mid, 4),
        "last_close": round(last_c, 4),
        "upper_slope": round(hs, 8),
        "lower_slope": round(ls, 8),
        "slope_unit": SLOPE_UNIT_NOTE,
        "shrink_pct": round(shrink * 100.0, 1),
    }
    if bars_to_apex is not None:
        key_levels["bars_to_apex"] = bars_to_apex
    if apex_window is not None:
        key_levels["apex_window"] = apex_window

    return [
        make_hit(
            pattern_family="triangle",
            pattern_type=pattern_type,
            status=status,
            confidence=conf,
            reason=reason,
            key_levels=key_levels,
            pivots=[
                *[{"role": "high", "date": p.get("date"), "price": p["price"]} for p in hi[-3:]],
                *[{"role": "low", "date": p.get("date"), "price": p["price"]} for p in lo[-3:]],
            ],
        )
    ]
