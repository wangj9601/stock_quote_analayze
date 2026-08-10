# -*- coding: utf-8 -*-
"""双顶 / 双底检测（双底复用 DBLB，双顶为镜像）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from backend_core.strategies.double_bottom.detector import detect_double_bottom

from .schema import make_hit


def _f(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def _bar_date(bar: Dict[str, Any]) -> str:
    raw = bar.get("date") if bar.get("date") is not None else bar.get("trade_date")
    return str(raw or "")[:10]


def _local_peaks(highs: Sequence[float], *, left: int, right: int) -> List[int]:
    n = len(highs)
    L, R = max(1, int(left)), max(1, int(right))
    out: List[int] = []
    for i in range(L, n - R):
        hi = highs[i]
        if any(highs[j] > hi for j in range(i - L, i)):
            continue
        if any(highs[j] > hi for j in range(i + 1, i + R + 1)):
            continue
        out.append(i)
    return out


def detect_double_bottom_hit(
    bars: Sequence[Dict[str, Any]],
    *,
    pattern_cfg: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    raw = detect_double_bottom(bars, pattern_cfg=pattern_cfg)
    if not raw:
        return None
    conf = 0.72 if raw.get("status") == "confirmed" else 0.55
    return make_hit(
        pattern_family="double_extremes",
        pattern_type="double_bottom",
        status=str(raw.get("status") or "forming"),
        confidence=conf,
        reason=f"W双底 L1={raw.get('l1_price')} L2={raw.get('l2_price')} 颈线={raw.get('neckline')}",
        key_levels={
            "l1": raw.get("l1_price"),
            "l2": raw.get("l2_price"),
            "neckline": raw.get("neckline"),
            "last_close": raw.get("last_close"),
        },
        pivots=[
            {"role": "L1", "date": raw.get("l1_date"), "price": raw.get("l1_price")},
            {"role": "neck", "date": raw.get("neck_date"), "price": raw.get("neckline")},
            {"role": "L2", "date": raw.get("l2_date"), "price": raw.get("l2_price")},
        ],
        extra={"source": "dblb", "confirm_date": raw.get("confirm_date")},
    )


def detect_double_top_hit(
    bars: Sequence[Dict[str, Any]],
    *,
    pattern_cfg: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """镜像双底规则：两峰近似等高 + 中间谷为颈线，收盘跌破确认。"""
    cfg = dict(pattern_cfg or {})
    lookback = max(30, int(cfg.get("lookback_days") or 120))
    swing_left = int(cfg.get("swing_left") or 3)
    swing_right = int(cfg.get("swing_right") or 3)
    min_gap = max(2, int(cfg.get("min_trough_gap_bars") or 8))
    max_gap = max(min_gap, int(cfg.get("max_trough_gap_bars") or 60))
    tol = float(cfg.get("trough_tol_pct") or 0.03)
    min_drop = float(cfg.get("min_rise_to_neck_pct") or 0.05)
    buffer_pct = float(cfg.get("confirm_buffer_pct") or 0.0)

    seq = [b for b in (bars or []) if isinstance(b, dict)]
    if len(seq) > lookback:
        seq = list(seq[-lookback:])
    if len(seq) < min_gap + swing_left + swing_right + 5:
        return None

    highs: List[float] = []
    lows: List[float] = []
    closes: List[float] = []
    for b in seq:
        h, lo, c = _f(b.get("high")), _f(b.get("low")), _f(b.get("close"))
        if h is None or lo is None or c is None:
            return None
        if h < lo:
            h, lo = lo, h
        highs.append(h)
        lows.append(lo)
        closes.append(c)

    peaks = _local_peaks(highs, left=swing_left, right=swing_right)
    if len(peaks) < 2:
        return None

    best = None
    for j in range(len(peaks) - 1, 0, -1):
        i2 = peaks[j]
        for i in range(j - 1, -1, -1):
            i1 = peaks[i]
            gap = i2 - i1
            if gap < min_gap or gap > max_gap:
                continue
            p1, p2 = highs[i1], highs[i2]
            mid = (p1 + p2) / 2.0
            if mid <= 0 or abs(p1 - p2) / mid > tol:
                continue
            if i2 - i1 < 2:
                continue
            neck_slice = lows[i1 + 1 : i2]
            if not neck_slice:
                continue
            neck = min(neck_slice)
            neck_rel = i1 + 1 + neck_slice.index(neck)
            top = max(p1, p2)
            if top <= 0 or (top - neck) / top < min_drop:
                continue
            after_highs = highs[i2 + 1 :]
            if after_highs and max(after_highs) > top * (1.0 + tol):
                continue
            best = (i1, i2, neck, neck_rel)
            break
        if best:
            break

    if not best:
        return None

    i1, i2, neck, neck_rel = best
    p1, p2 = highs[i1], highs[i2]
    last_close = closes[-1]
    threshold = neck * (1.0 - buffer_pct)
    confirmed = False
    confirm_date = None
    for k in range(i2 + 1, len(closes)):
        if closes[k] < threshold:
            confirmed = True
            confirm_date = _bar_date(seq[k])
            break

    status = "confirmed" if confirmed else "forming"
    conf = 0.72 if confirmed else 0.55
    return make_hit(
        pattern_family="double_extremes",
        pattern_type="double_top",
        status=status,
        confidence=conf,
        reason=f"M双顶 H1={round(p1,4)} H2={round(p2,4)} 颈线={round(neck,4)}",
        key_levels={
            "h1": round(p1, 4),
            "h2": round(p2, 4),
            "neckline": round(neck, 4),
            "last_close": round(last_close, 4),
        },
        pivots=[
            {"role": "H1", "date": _bar_date(seq[i1]), "price": round(p1, 4)},
            {"role": "neck", "date": _bar_date(seq[neck_rel]), "price": round(neck, 4)},
            {"role": "H2", "date": _bar_date(seq[i2]), "price": round(p2, 4)},
        ],
        extra={"confirm_date": confirm_date},
    )


def detect_double_extremes(
    bars: Sequence[Dict[str, Any]],
    *,
    pattern_cfg: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    hits: List[Dict[str, Any]] = []
    db = detect_double_bottom_hit(bars, pattern_cfg=pattern_cfg)
    if db:
        hits.append(db)
    dt = detect_double_top_hit(bars, pattern_cfg=pattern_cfg)
    if dt:
        hits.append(dt)
    return hits
