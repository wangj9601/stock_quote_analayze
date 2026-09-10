# -*- coding: utf-8 -*-
"""CSB 通道：MA 粘合、上下轨、HH20。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .indicators import _f, sma, sma_series


MA_PERIODS = (5, 10, 20, 60, 250)


def compute_mas(closes: Sequence[float]) -> Dict[str, List[Optional[float]]]:
    return {f"ma{p}": sma_series(list(closes), p) for p in MA_PERIODS}


def channel_band_at(
    ma_vals: Dict[str, Optional[float]],
    close: float,
) -> Dict[str, Optional[float]]:
    """单点通道上下轨与粘合带宽。"""
    keys = [f"ma{p}" for p in (5, 10, 20, 60)]
    vals = [_f(ma_vals.get(k)) for k in keys]
    vals = [v for v in vals if v is not None]
    if not vals or close <= 0:
        return {
            "lower": None,
            "upper": None,
            "squeeze_pct": None,
            "ma5": ma_vals.get("ma5"),
            "ma10": ma_vals.get("ma10"),
            "ma20": ma_vals.get("ma20"),
            "ma60": ma_vals.get("ma60"),
            "ma250": ma_vals.get("ma250"),
        }
    lo = min(vals)
    hi = max(vals)
    squeeze = (hi - lo) / close if close > 0 else None
    return {
        "lower": lo,
        "upper": hi,
        "squeeze_pct": squeeze,
        "ma5": ma_vals.get("ma5"),
        "ma10": ma_vals.get("ma10"),
        "ma20": ma_vals.get("ma20"),
        "ma60": ma_vals.get("ma60"),
        "ma250": ma_vals.get("ma250"),
    }


def count_squeeze_days(
    bars: Sequence[Dict[str, Any]],
    *,
    max_squeeze_pct: float,
    min_bars: int = 60,
) -> int:
    """从尾部向前连续粘合天数。"""
    if len(bars) < min_bars:
        return 0
    closes = [_f(b.get("close")) or 0.0 for b in bars]
    mas = compute_mas(closes)
    n = 0
    for i in range(len(bars) - 1, -1, -1):
        ma_point = {k: mas[k][i] for k in mas}
        ch = channel_band_at(ma_point, closes[i])
        sq = _f(ch.get("squeeze_pct"))
        if sq is None or sq > max_squeeze_pct:
            break
        n += 1
    return n


def hh_n(bars: Sequence[Dict[str, Any]], n: int = 20, exclude_last: bool = True) -> Optional[float]:
    """近 n 日最高价（默认不含当日）。"""
    if len(bars) < n + (1 if exclude_last else 0):
        return None
    window = bars[-(n + 1) : -1] if exclude_last else bars[-n:]
    highs = [_f(b.get("high")) for b in window]
    highs = [h for h in highs if h is not None]
    return max(highs) if highs else None


def compute_channel_state(bars: List[Dict[str, Any]], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    计算当前（最后一根 bar）通道状态。
    bars 时间正序。
    """
    ccfg = (config or {}).get("channel") or {}
    max_sq = float(ccfg.get("ma_squeeze_pct", 0.04))
    squeeze_need = int(ccfg.get("squeeze_days", 15))

    if len(bars) < 60:
        return {"ok": False, "reason": "insufficient_bars"}

    closes = [_f(b.get("close")) or 0.0 for b in bars]
    mas = compute_mas(closes)
    i = len(bars) - 1
    ma_point = {k: mas[k][i] for k in mas}
    ch = channel_band_at(ma_point, closes[i])
    squeeze_days = count_squeeze_days(bars, max_squeeze_pct=max_sq)
    hh20 = hh_n(bars, 20, exclude_last=True)

    squeeze_ok = (
        ch.get("squeeze_pct") is not None
        and float(ch["squeeze_pct"]) <= max_sq
        and squeeze_days >= squeeze_need
    )

    return {
        "ok": True,
        "lower": ch.get("lower"),
        "upper": ch.get("upper"),
        "squeeze_pct": ch.get("squeeze_pct"),
        "squeeze_days": squeeze_days,
        "squeeze_ok": squeeze_ok,
        "ma5": ch.get("ma5"),
        "ma10": ch.get("ma10"),
        "ma20": ch.get("ma20"),
        "ma60": ch.get("ma60"),
        "ma250": ch.get("ma250"),
        "hh20": hh20,
        "resistance": max(_f(ch.get("upper")) or 0.0, _f(hh20) or 0.0) or None,
        "close": closes[i],
    }
