# -*- coding: utf-8 -*-
"""Fibonacci（ZigZag 锚定）+ 经典/Camarilla/ATR Pivot + 共振带（参考用，不作策略硬门槛）。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

FIB_RETRACEMENT_RATIOS = (0.236, 0.382, 0.5, 0.618, 0.786)
FIB_EXTENSION_RATIOS = (1.272, 1.618)
DEFAULT_LOOKBACK = 60
OHLC_LOOKBACK = 180  # ZigZag / 批量日线回看
MIN_RANGE_PCT = 0.01  # (H-L)/L 过窄则跳过 Fib
PRICE_DECIMALS = 2  # 展示/入库口径：元，两位小数
# 现价相对确认波段极值：越过则按运行高/低重算 Fib（保留确认锚点元数据）
ANCHOR_EXCEED_UP_MULT = 1.005
ANCHOR_EXCEED_DOWN_MULT = 0.995


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
    """从日线 bars 计算 ZigZag Fib + 经典/Camarilla/ATR Pivot 参考价。"""
    from backend_core.analysis.pivot_variants import compute_vol_pivots_from_parsed
    from backend_core.analysis.swing_zigzag import extract_zigzag_swing

    parsed: List[Tuple[date, float, float, float]] = []
    for b in bars or []:
        t = _bar_tuple(b if isinstance(b, dict) else {})
        if t:
            parsed.append(t)
    parsed.sort(key=lambda x: x[0])

    empty = {
        "fibonacci": None,
        "pivot": None,
        "camarilla": None,
        "atr_pivot": None,
        "atr": None,
        "nearest_fib_support": None,
        "nearest_fib_resistance": None,
        "nearest_pivot_support": None,
        "nearest_pivot_resistance": None,
        "nearest_cam_support": None,
        "nearest_cam_resistance": None,
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

    vol = compute_vol_pivots_from_parsed(
        parsed, last_close=last_c, classic_p=pivot.get("P")
    )
    camarilla = vol.get("camarilla")
    atr_pivot = vol.get("atr_pivot")
    atr = vol.get("atr")

    # Fib：ZigZag 波段高低（未确认腿不参与）
    zz = extract_zigzag_swing(bars, max_bars=OHLC_LOOKBACK)
    swing = zz.get("swing") if zz.get("ok") else None
    fib: Optional[Dict[str, Any]] = None
    nearest_fib_s: Optional[float] = None
    nearest_fib_r: Optional[float] = None
    fib_reason = "ok"

    def _fib_zz_meta(target: Dict[str, Any], sw: Optional[Dict[str, Any]] = None) -> None:
        target["depth_pct"] = zz.get("depth_pct")
        target["depth"] = zz.get("depth")
        target["atr"] = zz.get("atr") or atr
        target["min_swing_bars"] = zz.get("min_swing_bars")
        target["zigzag"] = zz.get("zigzag") or []
        if sw:
            target["bar_span"] = sw.get("bar_span")
            target["skipped_short_leg"] = sw.get("skipped_short_leg")
            target["fallback_longest"] = sw.get("fallback_longest")

    if swing is None:
        fib = {
            "anchor_method": "zigzag_fractal",
            "ok": False,
            "reason": zz.get("reason") or "no_confirmed_swing",
            "retracements": [],
            "extensions": [],
        }
        _fib_zz_meta(fib)
        fib_reason = str(fib["reason"])
    else:
        swing_high = float(swing["swing_high"])
        swing_low = float(swing["swing_low"])
        direction = swing["direction"]
        swing_high_date = swing["swing_high_date"]
        swing_low_date = swing["swing_low_date"]
        if swing_low > 0 and (swing_high - swing_low) / swing_low >= float(min_range_pct):
            anchor_high = swing_high
            anchor_low = swing_low
            anchor_high_date = swing_high_date
            anchor_low_date = swing_low_date
            fib_direction = direction
            exceeded = False
            running_extreme = None

            if last_c is not None:
                # 无论原波段方向：现价有效越过确认高点 → 按运行高点重算上升段 Fib
                if last_c > swing_high * ANCHOR_EXCEED_UP_MULT:
                    run_hi = swing_high
                    hi_d = str(swing_high_date or "")[:10]
                    for d, h, _lo, _c in parsed:
                        ds = d.isoformat()[:10]
                        if hi_d and ds < hi_d:
                            continue
                        run_hi = max(run_hi, float(h))
                    run_hi = max(run_hi, float(last_c))
                    if run_hi > swing_high:
                        anchor_high = run_hi
                        anchor_high_date = parsed[-1][0].isoformat()
                        # 低点：原上升段保留 swing_low；原下降段则用确认低点
                        anchor_low = swing_low
                        anchor_low_date = swing_low_date
                        fib_direction = "up"
                        exceeded = True
                        running_extreme = run_hi
                elif last_c < swing_low * ANCHOR_EXCEED_DOWN_MULT:
                    run_lo = swing_low
                    lo_d = str(swing_low_date or "")[:10]
                    for d, _h, lo, _c in parsed:
                        ds = d.isoformat()[:10]
                        if lo_d and ds < lo_d:
                            continue
                        run_lo = min(run_lo, float(lo))
                    run_lo = min(run_lo, float(last_c))
                    if run_lo < swing_low:
                        anchor_low = run_lo
                        anchor_low_date = parsed[-1][0].isoformat()
                        anchor_high = swing_high
                        anchor_high_date = swing_high_date
                        fib_direction = "down"
                        exceeded = True
                        running_extreme = run_lo

            fib = fibonacci_from_swing(anchor_high, anchor_low, direction=fib_direction)
            fib["anchor_method"] = (
                "zigzag_fractal_running" if exceeded else "zigzag_fractal"
            )
            fib["ok"] = True
            fib["reason"] = "anchor_exceeded_running_extreme" if exceeded else "ok"
            fib["swing_high_date"] = anchor_high_date
            fib["swing_low_date"] = anchor_low_date
            fib["confirmed_swing_high"] = round(swing_high, PRICE_DECIMALS)
            fib["confirmed_swing_low"] = round(swing_low, PRICE_DECIMALS)
            fib["confirmed_swing_high_date"] = swing_high_date
            fib["confirmed_swing_low_date"] = swing_low_date
            fib["confirmed_direction"] = direction
            if exceeded:
                fib["anchor_exceeded"] = True
                fib["running_extreme"] = round(float(running_extreme), PRICE_DECIMALS)
            _fib_zz_meta(fib, swing)
            # 越过锚点后：回撤 + 全部扩展一并参与最近支撑/压力
            fib_prices = [x["price"] for x in (fib.get("retracements") or [])]
            ext = fib.get("extensions") or []
            for e in ext:
                try:
                    fib_prices.append(float(e["price"]))
                except (TypeError, ValueError, KeyError):
                    continue
            if ext and last_c is not None:
                nearest_ext = min(ext, key=lambda x: abs(float(x["price"]) - last_c))
                fib["nearest_extension"] = nearest_ext
            if last_c is not None:
                nearest_fib_s = _nearest_below(fib_prices, last_c)
                nearest_fib_r = _nearest_above(fib_prices, last_c)
                if nearest_fib_s is not None:
                    nearest_fib_s = round(nearest_fib_s, PRICE_DECIMALS)
                if nearest_fib_r is not None:
                    nearest_fib_r = round(nearest_fib_r, PRICE_DECIMALS)
            if exceeded:
                fib_reason = "anchor_exceeded_running_extreme"
        else:
            fib = {
                "anchor_method": "zigzag_fractal",
                "ok": False,
                "reason": "fib_skipped_narrow_range",
                "swing_high": round(swing_high, PRICE_DECIMALS),
                "swing_low": round(swing_low, PRICE_DECIMALS),
                "swing_high_date": swing_high_date,
                "swing_low_date": swing_low_date,
                "range": round(swing_high - swing_low, PRICE_DECIMALS),
                "direction": direction,
                "retracements": [],
                "extensions": [],
            }
            _fib_zz_meta(fib, swing)
            fib_reason = "fib_skipped_narrow_range"

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

    nearest_cam_s = (camarilla or {}).get("nearest_support") if camarilla else None
    nearest_cam_r = (camarilla or {}).get("nearest_resistance") if camarilla else None

    fib_s_note = None
    fib_r_note = None
    if last_c is not None and fib and fib.get("ok"):
        d = PRICE_DECIMALS
        fib_prices_all = [x["price"] for x in (fib.get("retracements") or [])]
        for e in fib.get("extensions") or []:
            try:
                fib_prices_all.append(float(e["price"]))
            except (TypeError, ValueError, KeyError):
                continue
        if nearest_fib_r is None and fib_prices_all:
            top = max(fib_prices_all)
            if last_c > top:
                fib_r_note = f"已突破Fib最高档({top:.{d}f})，上方暂无同窗压力"
                fib["resistance_note"] = fib_r_note
        if nearest_fib_s is None and fib_prices_all:
            bot = min(fib_prices_all)
            if last_c < bot:
                fib_s_note = f"已跌破Fib最低档({bot:.{d}f})，下方暂无同窗支撑"
                fib["support_note"] = fib_s_note

    piv_s_note = None
    piv_r_note = None
    if last_c is not None:
        d = PRICE_DECIMALS
        if nearest_piv_r is None:
            top = max(pivot_levels)
            if last_c > top:
                piv_r_note = f"已突破Pivot最高档R3({top:.{d}f})，上方暂无同窗压力"
        if nearest_piv_s is None:
            bot = min(pivot_levels)
            if last_c < bot:
                piv_s_note = f"已跌破Pivot最低档S3({bot:.{d}f})，下方暂无同窗支撑"

    return {
        "fibonacci": fib,
        "pivot": pivot,
        "camarilla": camarilla,
        "atr_pivot": atr_pivot,
        "atr": atr,
        "nearest_fib_support": nearest_fib_s,
        "nearest_fib_resistance": nearest_fib_r,
        "fib_support_note": fib_s_note,
        "fib_resistance_note": fib_r_note,
        "nearest_pivot_support": nearest_piv_s,
        "nearest_pivot_resistance": nearest_piv_r,
        "pivot_support_note": piv_s_note,
        "pivot_resistance_note": piv_r_note,
        "nearest_cam_support": nearest_cam_s,
        "nearest_cam_resistance": nearest_cam_r,
        "cam_support_note": (camarilla or {}).get("support_note") if camarilla else None,
        "cam_resistance_note": (camarilla or {}).get("resistance_note") if camarilla else None,
        "last_close": round(last_c, PRICE_DECIMALS) if last_c is not None else None,
        "ok": True,
        "reason": fib_reason,
    }


def attach_reference_levels_batch(
    bars_by_code: Dict[str, Sequence[Dict[str, Any]]],
    *,
    last_close_by_code: Optional[Dict[str, float]] = None,
    kde_by_code: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Dict[str, Any]]:
    """批量：{code: Fib/Pivot/Cam/ATR + VP + confluence 参考位}。"""
    from backend_core.analysis.confluence_zones import compute_confluence_from_reference
    from backend_core.analysis.volume_profile import compute_volume_profile_from_bars

    out: Dict[str, Dict[str, Any]] = {}
    closes = last_close_by_code or {}
    kde_map = kde_by_code or {}
    for code, bars in (bars_by_code or {}).items():
        c = code.strip() if isinstance(code, str) else str(code)
        lc = closes.get(c)
        ref = compute_classic_levels_from_bars(bars, last_close=lc)
        vp = compute_volume_profile_from_bars(
            bars, last_close=lc, lookback=DEFAULT_LOOKBACK
        )
        ref["volume_profile"] = {
            "ok": bool(vp.get("ok")),
            "reason": vp.get("reason"),
            "lookback": vp.get("lookback"),
            "bars_used": vp.get("bars_used"),
            "poc": vp.get("poc"),
            "vah": vp.get("vah"),
            "val": vp.get("val"),
            "nearest_support": vp.get("nearest_support"),
            "nearest_resistance": vp.get("nearest_resistance"),
            "support_note": vp.get("support_note"),
            "resistance_note": vp.get("resistance_note"),
        }
        ref["nearest_vp_support"] = vp.get("nearest_support")
        ref["nearest_vp_resistance"] = vp.get("nearest_resistance")
        ref["vp_support_note"] = vp.get("support_note")
        ref["vp_resistance_note"] = vp.get("resistance_note")

        kde = kde_map.get(c) or {}
        conf = compute_confluence_from_reference(
            ref,
            kde_support=kde.get("support") or kde.get("nearest_support"),
            kde_resistance=kde.get("resistance") or kde.get("nearest_resistance"),
            kde_supports=kde.get("supports") or kde.get("support_levels"),
            kde_resistances=kde.get("resistances") or kde.get("resistance_levels"),
            kde_multi_windows=kde.get("kde_multi_windows") or kde.get("multi_windows"),
            last_close=lc if lc is not None else ref.get("last_close"),
            atr=ref.get("atr"),
        )
        ref["confluence_zones"] = conf
        nz_s = conf.get("nearest_support_zone") if conf.get("ok") else None
        nz_r = conf.get("nearest_resistance_zone") if conf.get("ok") else None
        ref["nearest_confluence_support"] = (
            nz_s.get("center") if isinstance(nz_s, dict) else None
        )
        ref["nearest_confluence_resistance"] = (
            nz_r.get("center") if isinstance(nz_r, dict) else None
        )
        out[c] = ref
    return out
