# -*- coding: utf-8 -*-
"""底部放量分型：三 K 底分型 + 底部区域 + 中 K 放量。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence


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


def detect_bottom_volume_fractal(
    bars: Sequence[Dict[str, Any]],
    *,
    pattern_cfg: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """从升序日线 bars 识别「右 K = 最后一根」的底部放量分型。

    假定传入 OHLC 已按策略要求复权；volume 为原始量。
    命中返回 dict，否则 None。
    """
    cfg = dict(pattern_cfg or {})
    lookback_bottom = max(5, int(cfg.get("lookback_bottom") or 60))
    bottom_tol = float(cfg.get("bottom_tol") if cfg.get("bottom_tol") is not None else 0.03)
    vol_ma = max(1, int(cfg.get("vol_ma") or 20))
    vol_ratio = float(cfg.get("vol_ratio") if cfg.get("vol_ratio") is not None else 2.0)

    seq: List[Dict[str, Any]] = [b for b in (bars or []) if isinstance(b, dict)]
    n = len(seq)
    # 至少：底部回看(含中) + 右 K；且中前需有 vol_ma 根
    if n < lookback_bottom + 1:
        return None
    mid_i = n - 2
    left_i = n - 3
    right_i = n - 1
    if left_i < 0:
        return None
    if mid_i < vol_ma:
        return None

    left, mid, right = seq[left_i], seq[mid_i], seq[right_i]
    lh, ll = _f(left.get("high")), _f(left.get("low"))
    mh, ml = _f(mid.get("high")), _f(mid.get("low"))
    rh, rl = _f(right.get("high")), _f(right.get("low"))
    mv = _f(mid.get("volume"))
    if None in (lh, ll, mh, ml, rh, rl, mv):
        return None
    if mh >= lh or mh >= rh:
        return None
    if ml >= ll or ml >= rl:
        return None

    win_start = mid_i + 1 - lookback_bottom
    if win_start < 0:
        return None
    window_lows: List[float] = []
    for b in seq[win_start : mid_i + 1]:
        lo = _f(b.get("low"))
        if lo is None:
            return None
        window_lows.append(lo)
    min_low = min(window_lows)
    if min_low <= 0:
        return None
    if ml > min_low * (1.0 + bottom_tol):
        return None
    bottom_dev_pct = (ml - min_low) / min_low

    prev_vols: List[float] = []
    for b in seq[mid_i - vol_ma : mid_i]:
        v = _f(b.get("volume"))
        if v is None or v < 0:
            return None
        prev_vols.append(v)
    avg_vol = sum(prev_vols) / float(vol_ma)
    if avg_vol <= 0:
        return None
    vol_ratio_actual = mv / avg_vol
    if vol_ratio_actual < vol_ratio:
        return None

    rc = _f(right.get("close"))
    mc = _f(mid.get("close"))
    return {
        "status": "hit",
        "left_date": _bar_date(left),
        "mid_date": _bar_date(mid),
        "right_date": _bar_date(right),
        "left_high": lh,
        "left_low": ll,
        "mid_high": mh,
        "mid_low": ml,
        "right_high": rh,
        "right_low": rl,
        "mid_volume": mv,
        "min_low": min_low,
        "bottom_dev_pct": round(bottom_dev_pct, 6),
        "vol_ma": vol_ma,
        "vol_ratio_threshold": vol_ratio,
        "vol_ratio_actual": round(vol_ratio_actual, 6),
        "last_close": rc,
        "mid_close": mc,
        "lookback_bottom": lookback_bottom,
        "bottom_tol": bottom_tol,
    }
