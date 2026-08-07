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


def _ols_slope(ys: List[float]) -> Optional[float]:
    """普通最小二乘斜率（x = 0..n-1）。"""
    n = len(ys)
    if n < 2:
        return None
    x_mean = (n - 1) / 2.0
    y_mean = sum(ys) / n
    num = 0.0
    den = 0.0
    for i, y in enumerate(ys):
        dx = i - x_mean
        num += dx * (y - y_mean)
        den += dx * dx
    if den <= 0:
        return None
    return num / den


def _close_drop_pct(closes: List[float]) -> Optional[float]:
    if len(closes) < 2 or closes[0] <= 0:
        return None
    return (closes[-1] - closes[0]) / closes[0]


def _norm_slope(closes: List[float]) -> Optional[float]:
    """日均相对斜率：OLS(close) / mean(close)。"""
    slope = _ols_slope(closes)
    if slope is None:
        return None
    mean_c = sum(closes) / len(closes)
    if mean_c <= 0:
        return None
    return slope / mean_c


def _half_low_drop(lows: List[float]) -> Optional[float]:
    """后半段最低相对前半段最低的跌幅；(后半低 - 前半低) / 前半低。"""
    n = len(lows)
    if n < 4:
        return None
    mid = n // 2
    first_lo = min(lows[:mid])
    second_lo = min(lows[mid:])
    if first_lo <= 0:
        return None
    return (second_lo - first_lo) / first_lo


def _high_before_low(
    highs: List[float],
    lows: List[float],
    *,
    high_early_frac: float,
    low_late_frac: float,
) -> bool:
    """窗口最高明显早于最低（高前低后）→ 倾向下跌通道。"""
    n = len(highs)
    if n < 4:
        return False
    i_hi = max(range(n), key=lambda i: highs[i])
    i_lo = min(range(n), key=lambda i: lows[i])
    last = n - 1
    if last <= 0:
        return False
    hi_pos = i_hi / last
    lo_pos = i_lo / last
    return hi_pos <= high_early_frac and lo_pos >= low_late_frac and i_hi < i_lo


def _ma_env_ok(
    closes: List[float],
    *,
    ma_period: int,
    max_discount_pct: float,
    min_slope_norm: float,
) -> Tuple[bool, Dict[str, Any]]:
    """
    均线环境：价相对 MA 不宜深度空头，且 MA 不宜明显下行。
    观察窗不足 ma_period 时跳过（不阻断）。
    """
    detail: Dict[str, Any] = {"skipped": False}
    if ma_period <= 1 or len(closes) < ma_period:
        detail["skipped"] = True
        return True, detail

    ma_series: List[float] = []
    for i in range(ma_period - 1, len(closes)):
        ma_series.append(sum(closes[i - ma_period + 1 : i + 1]) / ma_period)
    last_ma = ma_series[-1]
    last_c = closes[-1]
    detail["ma"] = last_ma
    detail["last_close"] = last_c
    if last_ma <= 0:
        detail["skipped"] = True
        return True, detail

    discount = (last_c - last_ma) / last_ma
    detail["ma_discount_pct"] = discount
    if discount < max_discount_pct:
        detail["reason"] = "deep_below_ma"
        return False, detail

    ma_slope = _norm_slope(ma_series)
    detail["ma_slope_norm"] = ma_slope
    if ma_slope is not None and ma_slope < min_slope_norm:
        detail["reason"] = "ma_sloping_down"
        return False, detail
    return True, detail


def detect_range_bottom(
    bars: List[Dict[str, Any]],
    *,
    lookback: int,
    max_range_pct: float,
    touch_tol_pct: float,
    min_touches: int,
    max_touches: int,
    require_up_vol_gt_down: bool,
    max_close_drop_pct: float = -0.12,
    min_close_slope_norm: float = -0.002,
    reject_new_low_seq: bool = True,
    half_low_drop_pct: float = 0.05,
    reject_high_before_low: bool = True,
    high_early_frac: float = 0.40,
    low_late_frac: float = 0.60,
    require_ma_env: bool = True,
    ma_env_period: int = 60,
    ma_env_max_discount_pct: float = -0.12,
    ma_env_min_slope_norm: float = -0.0015,
) -> Dict[str, Any]:
    """
    bars: 时间正序（旧→新）。
    横盘：观察窗振幅 ≤ max_range_pct；上涨日均量 > 下跌日均量；
    收盘贴近区间下沿的次数落在 [min_touches, max_touches]；
    并排除明显下跌通道（趋势跌幅/斜率、新低序列、高前低后、均线空头环境）。
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

    hi_vals: List[float] = highs  # type: ignore
    lo_vals: List[float] = lows  # type: ignore
    cl_vals: List[float] = closes  # type: ignore

    hi = max(hi_vals)
    lo = min(lo_vals)
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

    # P0：趋势过滤 — 近窗收盘跌幅 / 线性斜率过负
    close_drop = _close_drop_pct(cl_vals)
    if close_drop is not None and close_drop <= max_close_drop_pct:
        return {
            "matched": False,
            "mode": None,
            "detail": {
                "reason": "close_drop_too_steep",
                "close_drop_pct": close_drop,
                "max_close_drop_pct": max_close_drop_pct,
                "range_pct": range_pct,
            },
        }

    slope_norm = _norm_slope(cl_vals)
    if slope_norm is not None and slope_norm < min_close_slope_norm:
        return {
            "matched": False,
            "mode": None,
            "detail": {
                "reason": "close_slope_too_negative",
                "close_slope_norm": slope_norm,
                "min_close_slope_norm": min_close_slope_norm,
                "range_pct": range_pct,
            },
        }

    # P0：新低序列 — 后半段低点明显低于前半
    if reject_new_low_seq:
        half_drop = _half_low_drop(lo_vals)
        if half_drop is not None and half_drop <= -abs(half_low_drop_pct):
            return {
                "matched": False,
                "mode": None,
                "detail": {
                    "reason": "new_low_sequence",
                    "half_low_drop_pct": half_drop,
                    "threshold": -abs(half_low_drop_pct),
                    "range_pct": range_pct,
                },
            }

    # P1：高低点时间序 — 高前低后倾向趋势而非箱体
    if reject_high_before_low and _high_before_low(
        hi_vals,
        lo_vals,
        high_early_frac=high_early_frac,
        low_late_frac=low_late_frac,
    ):
        i_hi = max(range(len(hi_vals)), key=lambda i: hi_vals[i])
        i_lo = min(range(len(lo_vals)), key=lambda i: lo_vals[i])
        return {
            "matched": False,
            "mode": None,
            "detail": {
                "reason": "high_before_low",
                "high_idx": i_hi,
                "low_idx": i_lo,
                "range_pct": range_pct,
            },
        }

    # P2：均线环境（深度空头 / MA 明显下行则拒绝横盘底）
    if require_ma_env:
        ma_ok, ma_detail = _ma_env_ok(
            cl_vals,
            ma_period=ma_env_period,
            max_discount_pct=ma_env_max_discount_pct,
            min_slope_norm=ma_env_min_slope_norm,
        )
        if not ma_ok:
            return {
                "matched": False,
                "mode": None,
                "detail": {
                    "reason": "ma_env_reject",
                    "ma_env": ma_detail,
                    "range_pct": range_pct,
                },
            }

    up_vols: List[float] = []
    down_vols: List[float] = []
    for i in range(1, len(window)):
        c0 = cl_vals[i - 1]
        c1 = cl_vals[i]
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
    for b, c in zip(window, cl_vals):
        if support <= 0:
            continue
        if abs(c - support) / support <= touch_tol_pct or (_f(b.get("low")) or 0) <= support * (
            1 + touch_tol_pct
        ):
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
            "close_drop_pct": close_drop,
            "close_slope_norm": slope_norm,
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
        max_range_pct=float(bcfg.get("max_range_pct", 0.35)),
        touch_tol_pct=float(bcfg.get("touch_tol_pct", 0.02)),
        min_touches=int(bcfg.get("min_touches", 3)),
        max_touches=int(bcfg.get("max_touches", 4)),
        require_up_vol_gt_down=bool(bcfg.get("up_volume_gt_down", True)),
        max_close_drop_pct=float(bcfg.get("max_close_drop_pct", -0.12)),
        min_close_slope_norm=float(bcfg.get("min_close_slope_norm", -0.002)),
        reject_new_low_seq=bool(bcfg.get("reject_new_low_seq", True)),
        half_low_drop_pct=float(bcfg.get("half_low_drop_pct", 0.05)),
        reject_high_before_low=bool(bcfg.get("reject_high_before_low", True)),
        high_early_frac=float(bcfg.get("high_early_frac", 0.40)),
        low_late_frac=float(bcfg.get("low_late_frac", 0.60)),
        require_ma_env=bool(bcfg.get("require_ma_env", True)),
        ma_env_period=int(bcfg.get("ma_env_period", 60)),
        ma_env_max_discount_pct=float(bcfg.get("ma_env_max_discount_pct", -0.12)),
        ma_env_min_slope_norm=float(bcfg.get("ma_env_min_slope_norm", -0.0015)),
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
