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


def build_channel_series(
    bars: Sequence[Dict[str, Any]],
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """一次计算 closes/mas/每日 squeeze_pct，供区间按日复用。"""
    closes = [_f(b.get("close")) or 0.0 for b in bars]
    mas = compute_mas(closes)
    squeeze_pcts: List[Optional[float]] = []
    for i, close in enumerate(closes):
        ma_point = {k: mas[k][i] for k in mas}
        ch = channel_band_at(ma_point, close)
        squeeze_pcts.append(_f(ch.get("squeeze_pct")))
    return {
        "bars": list(bars),
        "closes": closes,
        "mas": mas,
        "squeeze_pcts": squeeze_pcts,
    }


def _squeeze_days_from_series(
    squeeze_pcts: Sequence[Optional[float]],
    index: int,
    *,
    max_squeeze_pct: float,
    min_bars: int = 60,
) -> int:
    """与 count_squeeze_days(bars[:index+1]) 等价：从 index 向前连续粘合天数。"""
    if index + 1 < min_bars:
        return 0
    n = 0
    for i in range(index, -1, -1):
        sq = _f(squeeze_pcts[i] if i < len(squeeze_pcts) else None)
        if sq is None or sq > max_squeeze_pct:
            break
        n += 1
    return n


def channel_state_at(
    series: Dict[str, Any],
    index: int,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    取序列第 index 根（含）为止的通道状态，语义对齐
    ``compute_channel_state(bars[: index + 1], config)``。
    """
    ccfg = (config or {}).get("channel") or {}
    max_sq = float(ccfg.get("ma_squeeze_pct", 0.04))
    squeeze_need = int(ccfg.get("squeeze_days", 15))

    closes: List[float] = list(series.get("closes") or [])
    mas: Dict[str, List[Optional[float]]] = series.get("mas") or {}
    squeeze_pcts: List[Optional[float]] = list(series.get("squeeze_pcts") or [])
    bars: List[Dict[str, Any]] = list(series.get("bars") or [])

    if index < 0 or index >= len(closes):
        return {"ok": False, "reason": "insufficient_bars"}
    if index + 1 < 60:
        return {"ok": False, "reason": "insufficient_bars"}

    ma_point = {k: mas[k][index] for k in mas}
    ch = channel_band_at(ma_point, closes[index])
    squeeze_days = _squeeze_days_from_series(
        squeeze_pcts, index, max_squeeze_pct=max_sq, min_bars=60
    )
    prefix = bars[: index + 1] if bars else []
    hh20 = hh_n(prefix, 20, exclude_last=True) if prefix else None

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
        "resistance": _f(ch.get("upper")),
        "close": closes[index],
    }


def compute_channel_state(bars: List[Dict[str, Any]], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    计算当前（最后一根 bar）通道状态。
    bars 时间正序。
    """
    if len(bars) < 60:
        return {"ok": False, "reason": "insufficient_bars"}
    series = build_channel_series(bars, config)
    return channel_state_at(series, len(bars) - 1, config)
