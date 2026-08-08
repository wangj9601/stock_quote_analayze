# -*- coding: utf-8 -*-
"""分形预选 + ZigZag 过滤：为 Fibonacci 提供波段高低锚点。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

PRICE_DECIMALS = 2
DEFAULT_FRACTAL = 2
DEFAULT_MAX_BARS = 180
MIN_DEPTH_PCT = 0.025
ATR_DEPTH_MULT = 1.5
ATR_PERIOD = 14
# 高低点 index 间距下限（交易日根数）；过短的急跌/急拉跳过，改取上一完整波段
# 短线 Fib 参考默认 8 根（≈1.5 周）：滤 1～数日异动，又不过于陈旧
DEFAULT_MIN_SWING_BARS = 8


def _f(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        x = float(v)
        return x if x == x else None
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


def _parse_bars(
    bars: Sequence[Dict[str, Any]],
) -> List[Tuple[date, float, float, float]]:
    out: List[Tuple[date, float, float, float]] = []
    for b in bars or []:
        if not isinstance(b, dict):
            continue
        d = _as_date(b.get("date") or b.get("trade_date"))
        h = _f(b.get("high"))
        lo = _f(b.get("low"))
        c = _f(b.get("close"))
        if d is None or h is None or lo is None or c is None:
            continue
        if h < lo:
            h, lo = lo, h
        out.append((d, h, lo, c))
    out.sort(key=lambda x: x[0])
    return out


def wilder_atr(
    parsed: Sequence[Tuple[date, float, float, float]],
    *,
    period: int = ATR_PERIOD,
) -> Optional[float]:
    """Wilder ATR；不足 period+1 根时用简单均值 TR。"""
    if len(parsed) < 2:
        return None
    trs: List[float] = []
    for i in range(1, len(parsed)):
        h, lo, c = parsed[i][1], parsed[i][2], parsed[i][3]
        prev_c = parsed[i - 1][3]
        tr = max(h - lo, abs(h - prev_c), abs(lo - prev_c))
        trs.append(tr)
    if not trs:
        return None
    p = max(1, int(period))
    if len(trs) < p:
        return sum(trs) / len(trs)
    atr = sum(trs[:p]) / p
    for tr in trs[p:]:
        atr = (atr * (p - 1) + tr) / p
    return atr


def find_fractal_pivots(
    parsed: Sequence[Tuple[date, float, float, float]],
    *,
    left: int = DEFAULT_FRACTAL,
    right: int = DEFAULT_FRACTAL,
) -> List[Dict[str, Any]]:
    """Williams 分形：左右各 L/R 根确认的局部高/低。"""
    L, R = max(1, int(left)), max(1, int(right))
    n = len(parsed)
    pivots: List[Dict[str, Any]] = []
    for i in range(L, n - R):
        h = parsed[i][1]
        lo = parsed[i][2]
        is_high = all(h >= parsed[j][1] for j in range(i - L, i)) and all(
            h > parsed[j][1] for j in range(i + 1, i + R + 1)
        )
        is_low = all(lo <= parsed[j][2] for j in range(i - L, i)) and all(
            lo < parsed[j][2] for j in range(i + 1, i + R + 1)
        )
        if is_high:
            pivots.append(
                {
                    "index": i,
                    "kind": "high",
                    "price": h,
                    "date": parsed[i][0].isoformat(),
                }
            )
        if is_low:
            pivots.append(
                {
                    "index": i,
                    "kind": "low",
                    "price": lo,
                    "date": parsed[i][0].isoformat(),
                }
            )
    pivots.sort(key=lambda x: x["index"])
    return pivots


def _depth_threshold(close: float, atr: Optional[float]) -> float:
    base = abs(close) * MIN_DEPTH_PCT
    if atr is not None and close > 0:
        base = max(base, float(atr) * ATR_DEPTH_MULT)
    return base


def _augment_with_window_extremes(
    parsed: Sequence[Tuple[date, float, float, float]],
    pivots: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """分形不足时，补入窗口最高/最低，避免单调趋势无 Fib 锚点。"""
    if not parsed:
        return list(pivots or [])
    i_hi = max(range(len(parsed)), key=lambda i: parsed[i][1])
    i_lo = min(range(len(parsed)), key=lambda i: parsed[i][2])
    existing = {(p["index"], p["kind"]) for p in pivots}
    out = list(pivots)
    if (i_hi, "high") not in existing:
        out.append(
            {
                "index": i_hi,
                "kind": "high",
                "price": parsed[i_hi][1],
                "date": parsed[i_hi][0].isoformat(),
            }
        )
    if (i_lo, "low") not in existing:
        out.append(
            {
                "index": i_lo,
                "kind": "low",
                "price": parsed[i_lo][2],
                "date": parsed[i_lo][0].isoformat(),
            }
        )
    out.sort(key=lambda x: x["index"])
    return out


def zigzag_from_fractals(
    pivots: Sequence[Dict[str, Any]],
    *,
    depth: float,
) -> List[Dict[str, Any]]:
    """在分形点上交替确认峰/谷，幅度不足则忽略。"""
    if not pivots:
        return []
    zz: List[Dict[str, Any]] = []
    # 取第一个分形为起点
    first = dict(pivots[0])
    first["confirmed"] = True
    zz.append(first)
    for p in pivots[1:]:
        last = zz[-1]
        if p["kind"] == last["kind"]:
            # 同向取更极端
            if p["kind"] == "high" and p["price"] >= last["price"]:
                zz[-1] = dict(p)
                zz[-1]["confirmed"] = True
            elif p["kind"] == "low" and p["price"] <= last["price"]:
                zz[-1] = dict(p)
                zz[-1]["confirmed"] = True
            continue
        move = abs(float(p["price"]) - float(last["price"]))
        if move < float(depth):
            continue
        np_ = dict(p)
        np_["confirmed"] = True
        zz.append(np_)
    return zz


def _swing_from_leg(
    a: Dict[str, Any],
    b: Dict[str, Any],
    *,
    skipped_short: bool = False,
    fallback_longest: bool = False,
) -> Dict[str, Any]:
    """由 ZigZag 相邻两点构成完整波段（一峰一谷）。"""
    if a["kind"] == b["kind"]:
        raise ValueError("zigzag leg must alternate high/low")
    if a["kind"] == "high":
        hi, lo = a, b
    else:
        hi, lo = b, a
    # 方向按时间序：后出现的点决定上升段/下降段
    if int(a["index"]) <= int(b["index"]):
        direction = "down" if a["kind"] == "high" else "up"
    else:
        direction = "up" if a["kind"] == "high" else "down"
    bar_span = abs(int(a["index"]) - int(b["index"]))
    return {
        "swing_high": round(float(hi["price"]), PRICE_DECIMALS),
        "swing_low": round(float(lo["price"]), PRICE_DECIMALS),
        "swing_high_date": hi["date"],
        "swing_low_date": lo["date"],
        "swing_high_index": hi["index"],
        "swing_low_index": lo["index"],
        "direction": direction,
        "bar_span": bar_span,
        "confirmed": True,
        "skipped_short_leg": bool(skipped_short),
        "fallback_longest": bool(fallback_longest),
    }


def select_swing_from_zigzag(
    zz: Sequence[Dict[str, Any]],
    *,
    min_swing_bars: int = DEFAULT_MIN_SWING_BARS,
) -> Optional[Dict[str, Any]]:
    """优先取最近「完整波段」且高低点至少隔 min_swing_bars 根 K。

    完整波段 = ZigZag 链上相邻两点（交替峰/谷）。
    若最近一腿过短（如一日暴跌），回退到更早的完整波段；
    若全部过短，则取跨度最大的一腿（并标记 fallback_longest）。
    """
    if len(zz) < 2:
        return None
    min_n = max(1, int(min_swing_bars or DEFAULT_MIN_SWING_BARS))
    legs: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for i in range(len(zz) - 1):
        a, b = zz[i], zz[i + 1]
        if a.get("kind") == b.get("kind"):
            continue
        legs.append((a, b))
    if not legs:
        return None

    # 从最近一腿往前找满足跨度的
    skipped = False
    for a, b in reversed(legs):
        span = abs(int(a["index"]) - int(b["index"]))
        if span >= min_n:
            return _swing_from_leg(a, b, skipped_short=skipped)
        skipped = True

    # 全部过短：取跨度最大者
    a, b = max(legs, key=lambda ab: abs(int(ab[0]["index"]) - int(ab[1]["index"])))
    return _swing_from_leg(a, b, skipped_short=True, fallback_longest=True)


def latest_confirmed_swing(
    zz: Sequence[Dict[str, Any]],
    *,
    min_swing_bars: int = DEFAULT_MIN_SWING_BARS,
) -> Optional[Dict[str, Any]]:
    """兼容入口：等价于 select_swing_from_zigzag。"""
    return select_swing_from_zigzag(zz, min_swing_bars=min_swing_bars)


def extract_zigzag_swing(
    bars: Sequence[Dict[str, Any]],
    *,
    max_bars: int = DEFAULT_MAX_BARS,
    fractal_left: int = DEFAULT_FRACTAL,
    fractal_right: int = DEFAULT_FRACTAL,
    min_swing_bars: int = DEFAULT_MIN_SWING_BARS,
) -> Dict[str, Any]:
    """从日线提取 ZigZag 波段锚点。"""
    parsed = _parse_bars(bars)
    mb = max(20, int(max_bars or DEFAULT_MAX_BARS))
    if len(parsed) > mb:
        parsed = parsed[-mb:]
    min_n = max(1, int(min_swing_bars or DEFAULT_MIN_SWING_BARS))
    empty = {
        "ok": False,
        "reason": "insufficient_bars",
        "anchor_method": "zigzag_fractal",
        "swing": None,
        "atr": None,
        "depth_pct": None,
        "depth": None,
        "min_swing_bars": min_n,
        "zigzag": [],
    }
    if len(parsed) < fractal_left + fractal_right + 3:
        return empty

    atr = wilder_atr(parsed)
    last_close = parsed[-1][3]
    depth = _depth_threshold(last_close, atr)
    depth_pct = depth / last_close if last_close > 0 else MIN_DEPTH_PCT

    pivots = find_fractal_pivots(
        parsed, left=fractal_left, right=fractal_right
    )
    # 单调段常缺分形：补窗口绝对高/低作锚点候选（仍经 ZigZag 深度过滤）
    pivots = _augment_with_window_extremes(parsed, pivots)
    zz = zigzag_from_fractals(pivots, depth=depth)
    swing = select_swing_from_zigzag(zz, min_swing_bars=min_n)
    if swing is None:
        return {
            **empty,
            "reason": "no_confirmed_swing",
            "atr": round(atr, PRICE_DECIMALS) if atr is not None else None,
            "depth": round(depth, PRICE_DECIMALS),
            "depth_pct": round(depth_pct, 4),
            "zigzag": [
                {
                    "kind": z["kind"],
                    "price": round(float(z["price"]), PRICE_DECIMALS),
                    "date": z["date"],
                }
                for z in zz[-8:]
            ],
        }

    return {
        "ok": True,
        "reason": "ok",
        "anchor_method": "zigzag_fractal",
        "swing": swing,
        "atr": round(atr, PRICE_DECIMALS) if atr is not None else None,
        "depth": round(depth, PRICE_DECIMALS),
        "depth_pct": round(depth_pct, 4),
        "fractal_left": fractal_left,
        "fractal_right": fractal_right,
        "min_swing_bars": min_n,
        "max_bars": mb,
        "zigzag": [
            {
                "kind": z["kind"],
                "price": round(float(z["price"]), PRICE_DECIMALS),
                "date": z["date"],
            }
            for z in zz[-8:]
        ],
    }
