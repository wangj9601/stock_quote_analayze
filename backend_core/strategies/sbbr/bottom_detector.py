"""筑底识别：横盘收集 / 打压恐慌（黄金坑）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def _f(v) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def detect_range_bottom(
    bars: List[Dict[str, Any]],
    *,
    lookback: int,
    max_range_pct: float,
    touch_tol_pct: float,
    min_touches: int,
    max_touches: int,
    require_up_vol_gt_down: bool,
) -> Dict[str, Any]:
    """
    bars: 时间正序（旧→新）。
    横盘：观察窗振幅 ≤ max_range_pct；上涨日均量 > 下跌日均量；
    收盘贴近区间下沿的次数落在 [min_touches, max_touches]。
    """
    if len(bars) < max(lookback, 10):
        return {"matched": False, "mode": None, "detail": {"reason": "insufficient_bars"}}

    window = bars[-lookback:]
    highs = [_f(b.get("high")) for b in window]
    lows = [_f(b.get("low")) for b in window]
    closes = [_f(b.get("close")) for b in window]
    volumes = [_f(b.get("volume")) or 0.0 for b in window]
    if any(x is None or x <= 0 for x in highs + lows + closes):
        return {"matched": False, "mode": None, "detail": {"reason": "bad_ohlc"}}

    hi = max(highs)  # type: ignore
    lo = min(lows)  # type: ignore
    mid = (hi + lo) / 2.0
    if mid <= 0:
        return {"matched": False, "mode": None, "detail": {"reason": "bad_mid"}}
    range_pct = (hi - lo) / mid
    if range_pct > max_range_pct:
        return {
            "matched": False,
            "mode": None,
            "detail": {"reason": "range_too_wide", "range_pct": range_pct},
        }

    up_vols: List[float] = []
    down_vols: List[float] = []
    for i in range(1, len(window)):
        c0 = closes[i - 1]
        c1 = closes[i]
        if c0 is None or c1 is None:
            continue
        if c1 > c0:
            up_vols.append(volumes[i])
        elif c1 < c0:
            down_vols.append(volumes[i])

    up_avg = sum(up_vols) / len(up_vols) if up_vols else 0.0
    down_avg = sum(down_vols) / len(down_vols) if down_vols else 0.0
    vol_ok = (not require_up_vol_gt_down) or (up_avg > down_avg and down_avg >= 0)

    touches = 0
    touch_dates: List[str] = []
    support = lo
    for b, c in zip(window, closes):
        if c is None or support <= 0:
            continue
        if abs(c - support) / support <= touch_tol_pct or (_f(b.get("low")) or 0) <= support * (1 + touch_tol_pct):
            touches += 1
            touch_dates.append(str(b.get("date") or "")[:10])

    touch_ok = min_touches <= touches <= max_touches
    matched = bool(vol_ok and touch_ok)
    return {
        "matched": matched,
        "mode": "range_accumulation" if matched else None,
        "support": support,
        "resistance": hi,
        "range_pct": range_pct,
        "touches": touches,
        "detail": {
            "up_vol_avg": up_avg,
            "down_vol_avg": down_avg,
            "touch_dates": touch_dates[-8:],
            "vol_ok": vol_ok,
            "touch_ok": touch_ok,
        },
    }


def detect_panic_bottom(
    bars: List[Dict[str, Any]],
    market_returns: List[float],
    *,
    panic_market_drop_pct: float,
    panic_stock_drop_pct: float,
    reclaim_ma20: bool,
) -> Dict[str, Any]:
    """
    打压恐慌：近几日个股急跌且大盘同步走弱，之后收盘回到/上穿 MA20。
    bars/market_returns 时间正序；market_returns 与 bars 对齐（同长度或更短取尾部）。
    """
    n = len(bars)
    if n < 25:
        return {"matched": False, "mode": None, "detail": {"reason": "insufficient_bars"}}

    closes = [_f(b.get("close")) for b in bars]
    if any(c is None or c <= 0 for c in closes[-25:]):
        return {"matched": False, "mode": None, "detail": {"reason": "bad_close"}}

    # MA20 at last bar
    ma20 = sum(closes[-20:]) / 20.0  # type: ignore
    last = closes[-1]
    prev = closes[-2]
    if last is None or prev is None:
        return {"matched": False, "mode": None, "detail": {"reason": "bad_last"}}

    # find recent panic day in last 10 bars (exclude today)
    panic_idx = None
    for i in range(n - 2, max(n - 12, 0), -1):
        c = closes[i]
        c_prev = closes[i - 1] if i > 0 else None
        if c is None or c_prev is None or c_prev <= 0:
            continue
        stock_ret = (c - c_prev) / c_prev
        mkt_ret = 0.0
        if market_returns:
            # align from end
            off = (n - 1) - i
            mi = len(market_returns) - 1 - off
            if 0 <= mi < len(market_returns):
                mkt_ret = float(market_returns[mi])
        if stock_ret <= panic_stock_drop_pct and mkt_ret <= panic_market_drop_pct:
            panic_idx = i
            break

    if panic_idx is None:
        return {"matched": False, "mode": None, "detail": {"reason": "no_panic"}}

    reclaim = True
    if reclaim_ma20:
        # previously below ma, now above or cross
        ma20_prev = sum(closes[panic_idx - 19 : panic_idx + 1]) / 20.0 if panic_idx >= 19 else ma20
        reclaim = last >= ma20 and (prev < ma20_prev or closes[panic_idx] < ma20_prev)

    low_panic = _f(bars[panic_idx].get("low")) or closes[panic_idx]
    matched = bool(reclaim)
    return {
        "matched": matched,
        "mode": "panic_accumulation" if matched else None,
        "support": low_panic,
        "detail": {
            "panic_date": str(bars[panic_idx].get("date") or "")[:10],
            "ma20": ma20,
            "last_close": last,
            "reclaim": reclaim,
        },
    }


def detect_bottom(
    bars: List[Dict[str, Any]],
    market_returns: List[float],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    bcfg = (config or {}).get("bottom") or {}
    range_res = detect_range_bottom(
        bars,
        lookback=int(bcfg.get("lookback_days", 60)),
        max_range_pct=float(bcfg.get("max_range_pct", 0.60)),
        touch_tol_pct=float(bcfg.get("touch_tol_pct", 0.02)),
        min_touches=int(bcfg.get("min_touches", 3)),
        max_touches=int(bcfg.get("max_touches", 4)),
        require_up_vol_gt_down=bool(bcfg.get("up_volume_gt_down", True)),
    )
    if range_res.get("matched"):
        return range_res

    panic_res = detect_panic_bottom(
        bars,
        market_returns,
        panic_market_drop_pct=float(bcfg.get("panic_market_drop_pct", -0.02)),
        panic_stock_drop_pct=float(bcfg.get("panic_stock_drop_pct", -0.05)),
        reclaim_ma20=bool(bcfg.get("panic_reclaim_ma20", True)),
    )
    if panic_res.get("matched"):
        return panic_res

    # return richer of the two for debugging
    return {
        "matched": False,
        "mode": None,
        "detail": {"range": range_res.get("detail"), "panic": panic_res.get("detail")},
    }
