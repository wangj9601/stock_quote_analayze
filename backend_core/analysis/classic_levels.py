# -*- coding: utf-8 -*-
"""Fibonacci 回撤/扩展 + 经典 Pivot 价位（买卖判断参考，不作策略硬门槛）。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

FIB_RETRACEMENT_RATIOS = (0.236, 0.382, 0.5, 0.618, 0.786)
FIB_EXTENSION_RATIOS = (1.272, 1.618)
DEFAULT_LOOKBACK = 60
MIN_RANGE_PCT = 0.01  # (H-L)/L 过窄则跳过 Fib
PRICE_DECIMALS = 2  # 展示/入库口径：元，两位小数


def _f(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _as_date(v: Any) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _bar_tuple(bar: Dict[str, Any]) -> Optional[Tuple[date, float, float, float]]:
    d = _as_date(bar.get("date") or bar.get("trade_date"))
    h = _f(bar.get("high"))
    lo = _f(bar.get("low"))
    c = _f(bar.get("close"))
    if d is None or h is None or lo is None or c is None:
        return None
    if h < lo:
        h, lo = lo, h
    return d, h, lo, c


def classic_pivot_from_hlc(high: float, low: float, close: float) -> Dict[str, Any]:
    """经典 Floor Pivot：P/R1–R3/S1–S3。"""
    h, l, c = float(high), float(low), float(close)
    p = (h + l + c) / 3.0
    r1 = 2.0 * p - l
    s1 = 2.0 * p - h
    r2 = p + (h - l)
    s2 = p - (h - l)
    r3 = h + 2.0 * (p - l)
    s3 = l - 2.0 * (h - p)
    d = PRICE_DECIMALS
    return {
        "method": "classic",
        "H": round(h, d),
        "L": round(l, d),
        "C": round(c, d),
        "P": round(p, d),
        "R1": round(r1, d),
        "R2": round(r2, d),
        "R3": round(r3, d),
        "S1": round(s1, d),
        "S2": round(s2, d),
        "S3": round(s3, d),
    }


def fibonacci_from_swing(
    swing_high: float,
    swing_low: float,
    *,
    direction: str,
) -> Dict[str, Any]:
    """按摆动区间计算回撤/扩展位。

    direction:
      - up: 上升段回撤（价位 = H - ratio*range），扩展向上
      - down: 下降段反弹（价位 = L + ratio*range），扩展向下
    """
    h, lo = float(swing_high), float(swing_low)
    if h < lo:
        h, lo = lo, h
    rng = h - lo
    retracements: List[Dict[str, Any]] = []
    extensions: List[Dict[str, Any]] = []
    dirc = (direction or "up").strip().lower()
    if dirc not in ("up", "down"):
        dirc = "up"

    for ratio in FIB_RETRACEMENT_RATIOS:
        if dirc == "up":
            price = h - ratio * rng
        else:
            price = lo + ratio * rng
        retracements.append(
            {"ratio": ratio, "price": round(price, PRICE_DECIMALS), "kind": "retracement"}
        )

    for ratio in FIB_EXTENSION_RATIOS:
        if dirc == "up":
            price = h + (ratio - 1.0) * rng
        else:
            price = lo - (ratio - 1.0) * rng
        extensions.append(
            {"ratio": ratio, "price": round(price, PRICE_DECIMALS), "kind": "extension"}
        )

    return {
        "swing_high": round(h, PRICE_DECIMALS),
        "swing_low": round(lo, PRICE_DECIMALS),
        "range": round(rng, PRICE_DECIMALS),
        "direction": dirc,
        "retracements": retracements,
        "extensions": extensions,
    }


def _nearest_below(levels: Sequence[float], price: float) -> Optional[float]:
    below = [x for x in levels if x is not None and x < price]
    return max(below) if below else None


def _nearest_above(levels: Sequence[float], price: float) -> Optional[float]:
    above = [x for x in levels if x is not None and x > price]
    return min(above) if above else None


def compute_classic_levels_from_bars(
    bars: Sequence[Dict[str, Any]],
    *,
    last_close: Optional[float] = None,
    min_range_pct: float = MIN_RANGE_PCT,
) -> Dict[str, Any]:
    """从日线 bars（含 date/high/low/close）计算 Fib + 经典 Pivot 参考价。"""
    parsed: List[Tuple[date, float, float, float]] = []
    for b in bars or []:
        t = _bar_tuple(b if isinstance(b, dict) else {})
        if t:
            parsed.append(t)
    parsed.sort(key=lambda x: x[0])

    empty = {
        "fibonacci": None,
        "pivot": None,
        "nearest_fib_support": None,
        "nearest_fib_resistance": None,
        "nearest_pivot_support": None,
        "nearest_pivot_resistance": None,
        "ok": False,
        "reason": "insufficient_bars",
    }
    if len(parsed) < 2:
        return empty

    # Pivot：上一交易日（倒数第二根相对「最新一根」）
    prev = parsed[-2]
    pivot = classic_pivot_from_hlc(prev[1], prev[2], prev[3])
    pivot["trade_date"] = prev[0].isoformat()

    last_c = _f(last_close)
    if last_c is None:
        last_c = parsed[-1][3]

    # Fib：窗口摆动高低 + 时间序定方向
    i_hi = max(range(len(parsed)), key=lambda i: parsed[i][1])
    i_lo = min(range(len(parsed)), key=lambda i: parsed[i][2])
    swing_high = parsed[i_hi][1]
    swing_low = parsed[i_lo][2]
    swing_high_date = parsed[i_hi][0].isoformat()
    swing_low_date = parsed[i_lo][0].isoformat()
    direction = "up" if parsed[i_hi][0] >= parsed[i_lo][0] else "down"

    fib: Optional[Dict[str, Any]] = None
    nearest_fib_s: Optional[float] = None
    nearest_fib_r: Optional[float] = None
    if swing_low > 0 and (swing_high - swing_low) / swing_low >= float(min_range_pct):
        fib = fibonacci_from_swing(swing_high, swing_low, direction=direction)
        fib["swing_high_date"] = swing_high_date
        fib["swing_low_date"] = swing_low_date
        fib_prices = [x["price"] for x in (fib.get("retracements") or [])]
        # 扩展位只取距现价最近的一个加入候选
        ext = fib.get("extensions") or []
        if ext and last_c is not None:
            nearest_ext = min(ext, key=lambda x: abs(float(x["price"]) - last_c))
            fib["nearest_extension"] = nearest_ext
            fib_prices.append(float(nearest_ext["price"]))
        if last_c is not None:
            nearest_fib_s = _nearest_below(fib_prices, last_c)
            nearest_fib_r = _nearest_above(fib_prices, last_c)
            if nearest_fib_s is not None:
                nearest_fib_s = round(nearest_fib_s, PRICE_DECIMALS)
            if nearest_fib_r is not None:
                nearest_fib_r = round(nearest_fib_r, PRICE_DECIMALS)
    else:
        # 区间过窄跳过回撤位，仍返回锚点价与日期便于前端展示
        fib = {
            "swing_high": round(swing_high, PRICE_DECIMALS),
            "swing_low": round(swing_low, PRICE_DECIMALS),
            "swing_high_date": swing_high_date,
            "swing_low_date": swing_low_date,
            "range": round(swing_high - swing_low, PRICE_DECIMALS),
            "direction": direction,
            "retracements": [],
            "extensions": [],
        }

    pivot_levels = [
        pivot["S3"],
        pivot["S2"],
        pivot["S1"],
        pivot["P"],
        pivot["R1"],
        pivot["R2"],
        pivot["R3"],
    ]
    nearest_piv_s = None
    nearest_piv_r = None
    if last_c is not None:
        nearest_piv_s = _nearest_below(pivot_levels, last_c)
        nearest_piv_r = _nearest_above(pivot_levels, last_c)
        if nearest_piv_s is not None:
            nearest_piv_s = round(nearest_piv_s, PRICE_DECIMALS)
        if nearest_piv_r is not None:
            nearest_piv_r = round(nearest_piv_r, PRICE_DECIMALS)

    return {
        "fibonacci": fib,
        "pivot": pivot,
        "nearest_fib_support": nearest_fib_s,
        "nearest_fib_resistance": nearest_fib_r,
        "nearest_pivot_support": nearest_piv_s,
        "nearest_pivot_resistance": nearest_piv_r,
        "last_close": round(last_c, PRICE_DECIMALS) if last_c is not None else None,
        "ok": True,
        "reason": "ok" if fib is not None else "fib_skipped_narrow_range",
    }


def attach_reference_levels_batch(
    bars_by_code: Dict[str, Sequence[Dict[str, Any]]],
    *,
    last_close_by_code: Optional[Dict[str, float]] = None,
) -> Dict[str, Dict[str, Any]]:
    """批量：{code: Fib/Pivot + volume_profile 参考位}。"""
    from backend_core.analysis.volume_profile import compute_volume_profile_from_bars

    out: Dict[str, Dict[str, Any]] = {}
    closes = last_close_by_code or {}
    for code, bars in (bars_by_code or {}).items():
        c = code.strip() if isinstance(code, str) else str(code)
        lc = closes.get(c)
        ref = compute_classic_levels_from_bars(bars, last_close=lc)
        vp = compute_volume_profile_from_bars(
            bars, last_close=lc, lookback=DEFAULT_LOOKBACK
        )
        # 精简写入 reference_levels，避免把完整 bins 塞进每行
        ref["volume_profile"] = {
            "ok": bool(vp.get("ok")),
            "reason": vp.get("reason"),
            "lookback": vp.get("lookback"),
            "poc": vp.get("poc"),
            "vah": vp.get("vah"),
            "val": vp.get("val"),
            "nearest_support": vp.get("nearest_support"),
            "nearest_resistance": vp.get("nearest_resistance"),
        }
        ref["nearest_vp_support"] = vp.get("nearest_support")
        ref["nearest_vp_resistance"] = vp.get("nearest_resistance")
        out[c] = ref
    return out
