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


def latest_confirmed_swing(
    zz: Sequence[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """最近一对已确认的 high+low（至少两点，且种类不同）。"""
    if len(zz) < 2:
        return None
    # 从末尾找最近的 high 与 low
    last_high = None
    last_low = None
    for p in reversed(zz):
        if p.get("kind") == "high" and last_high is None:
            last_high = p
        if p.get("kind") == "low" and last_low is None:
            last_low = p
        if last_high is not None and last_low is not None:
            break
    if last_high is None or last_low is None:
        return None
    direction = "up" if last_high["index"] >= last_low["index"] else "down"
    return {
        "swing_high": round(float(last_high["price"]), PRICE_DECIMALS),
        "swing_low": round(float(last_low["price"]), PRICE_DECIMALS),
        "swing_high_date": last_high["date"],
        "swing_low_date": last_low["date"],
        "swing_high_index": last_high["index"],
        "swing_low_index": last_low["index"],
        "direction": direction,
        "confirmed": True,
    }


def extract_zigzag_swing(
    bars: Sequence[Dict[str, Any]],
    *,
    max_bars: int = DEFAULT_MAX_BARS,
    fractal_left: int = DEFAULT_FRACTAL,
    fractal_right: int = DEFAULT_FRACTAL,
) -> Dict[str, Any]:
    """从日线提取 ZigZag 波段锚点。"""
    parsed = _parse_bars(bars)
    mb = max(20, int(max_bars or DEFAULT_MAX_BARS))
    if len(parsed) > mb:
        parsed = parsed[-mb:]
    empty = {
        "ok": False,
        "reason": "insufficient_bars",
        "anchor_method": "zigzag_fractal",
        "swing": None,
        "atr": None,
        "depth_pct": None,
        "depth": None,
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
    swing = latest_confirmed_swing(zz)
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
