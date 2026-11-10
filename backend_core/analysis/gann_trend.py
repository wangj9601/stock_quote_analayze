# -*- coding: utf-8 -*-
"""江恩趋势预测（V1）：ZigZag 锚点 + 角度线 + 时间窗 + 扇形几何。

1×1 为标的自适应「每根 K 线对应价格单位」，非屏幕 45°。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from backend_core.analysis.swing_zigzag import (
    DEFAULT_FRACTAL,
    DEFAULT_MAX_BARS,
    DEFAULT_MIN_SWING_BARS,
    PRICE_DECIMALS,
    extract_zigzag_swing,
    wilder_atr,
    _parse_bars,
)

# 角度比：price_delta_per_bar = scale * (rise / run)
ANGLE_RATIOS: Tuple[Tuple[str, float, float], ...] = (
    ("1x1", 1.0, 1.0),
    ("2x1", 2.0, 1.0),  # 更陡：两份价一份时间
    ("1x2", 1.0, 2.0),  # 更平：一份价两份时间
    ("4x1", 4.0, 1.0),
    ("1x4", 1.0, 4.0),
)

TIME_WINDOWS = (45, 90, 144, 180, 360)
FAN_HORIZON_BARS = 90
NEAR_BAND_ATR_MULT = 0.5
NEAR_BAND_MIN_PCT = 0.005
# 射线相对现价偏离超过该倍数 → 该射线失真（不画、不参与坐标）。整扇不因此作废。
ANGLE_MAX_DEV_RATIO = 3.0
# 方向结论须「相对 1×1 的位置」与「近端收盘斜率」同向；单边不给偏多/偏空。
SLOPE_LOOKBACK = 10
SLOPE_MIN_BARS = 3
SLOPE_SCALE_FRAC = 0.25


def _round_p(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return round(float(v), PRICE_DECIMALS)
    except (TypeError, ValueError):
        return None


def estimate_gann_scale(
    parsed: Sequence[Tuple[Any, float, float, float]],
    *,
    atr: Optional[float],
    last_close: float,
) -> float:
    """估计 1×1：每根交易日对应的价格单位。"""
    if atr is not None and atr > 0:
        scale = float(atr) * 0.35
    else:
        n = min(20, len(parsed))
        if n >= 2:
            ranges = [parsed[i][1] - parsed[i][2] for i in range(-n, 0)]
            avg_rng = sum(ranges) / len(ranges)
            scale = max(avg_rng * 0.5, abs(last_close) * 0.002)
        else:
            scale = abs(last_close) * 0.01 if last_close else 0.1
    floor = abs(last_close) * 0.001 if last_close else 0.01
    return max(float(scale), floor)


def angle_price(
    *,
    anchor_price: float,
    bars_from_anchor: int,
    scale: float,
    rise: float,
    run: float,
    direction: str,
) -> float:
    """direction up：价格随时间上升；down：随时间下降。"""
    slope = float(scale) * (float(rise) / max(float(run), 1e-9))
    offset = abs(int(bars_from_anchor)) * slope
    if direction == "down":
        return float(anchor_price) - offset
    return float(anchor_price) + offset


def angle_usable(price: float, last_close: float) -> Tuple[bool, Optional[str]]:
    """单条角度线在基准日是否可展示、可参与坐标。穿零或远离现价只作废该线。"""
    try:
        px = float(price)
        ref = abs(float(last_close))
    except (TypeError, ValueError):
        return False, "invalid"
    if px != px or px <= 0:
        return False, "non_positive"
    if ref > 0 and abs(px - ref) / ref > ANGLE_MAX_DEV_RATIO:
        return False, "far_from_spot"
    return True, None


def recent_close_slope(
    parsed: Sequence[Tuple[Any, float, float, float]],
    *,
    lookback: int = SLOPE_LOOKBACK,
) -> Optional[float]:
    """近端收盘的每根变化。样本不足返回 None。"""
    n = min(int(lookback), len(parsed) - 1)
    if n < SLOPE_MIN_BARS:
        return None
    c0 = float(parsed[-1 - n][3])
    c1 = float(parsed[-1][3])
    return (c1 - c0) / float(n)


def classify_gann_bias(
    *,
    last_close: float,
    one_price: Optional[float],
    one_usable: bool,
    near_band: float,
    scale: float,
    fan_dir: str,
    recent_slope: Optional[float],
    slope_bars: int,
) -> Tuple[str, str, str]:
    """位置与近端斜率同向才给偏多/偏空。下行扇里「回到不断下移的 1×1 上方」本身不够。"""
    fan_zh = "下行扇" if fan_dir == "down" else "上行扇"
    if not one_usable or one_price is None:
        return (
            "insufficient",
            "不可用",
            "1×1 理论价穿零或远离现价，本扇不作为方向结论。",
        )
    diff = float(last_close) - float(one_price)
    if abs(diff) <= float(near_band):
        return (
            "near",
            "贴近1×1",
            (
                f"{fan_zh}：收盘 {last_close:.2f} 贴近 1×1 理论价 {one_price:.2f}"
                f"（带宽 ±{near_band:.2f}），多空临界。"
            ),
        )
    above = diff > 0
    pos_zh = "上方" if above else "下方"
    if recent_slope is None:
        return (
            "neutral",
            "中性",
            (
                f"{fan_zh}：收盘 {last_close:.2f} 位于 1×1（{one_price:.2f}）{pos_zh}，"
                "近端斜率样本不足，不单独作为方向。"
            ),
        )
    eps = max(abs(float(scale)) * SLOPE_SCALE_FRAC, abs(float(last_close)) * 0.0005)
    n = max(int(slope_bars), 1)
    slope_txt = f"近{n}根斜率 {recent_slope:+.3f}/根"
    if above and recent_slope > eps:
        return (
            "bullish",
            "偏多",
            (
                f"{fan_zh}：收盘 {last_close:.2f} 位于 1×1（{one_price:.2f}）上方，"
                f"且{slope_txt}向上，几何上偏强。"
            ),
        )
    if (not above) and recent_slope < -eps:
        return (
            "bearish",
            "偏空",
            (
                f"{fan_zh}：收盘 {last_close:.2f} 位于 1×1（{one_price:.2f}）下方，"
                f"且{slope_txt}向下，几何上偏弱。"
            ),
        )
    return (
        "neutral",
        "中性",
        (
            f"{fan_zh}：收盘 {last_close:.2f} 位于 1×1（{one_price:.2f}）{pos_zh}，"
            f"但{slope_txt}与位置不一致，不单独作为方向。"
        ),
    )


def _pick_anchor(swing: Dict[str, Any]) -> Dict[str, Any]:
    """上涨波段以低点为扇起点；下跌波段以高点为起点。"""
    direction = str(swing.get("direction") or "up")
    if direction == "down":
        return {
            "kind": "high",
            "price": float(swing["swing_high"]),
            "date": swing.get("swing_high_date"),
            "index": int(swing["swing_high_index"]),
            "fan_direction": "down",
            "role": "swing_high",
        }
    return {
        "kind": "low",
        "price": float(swing["swing_low"]),
        "date": swing.get("swing_low_date"),
        "index": int(swing["swing_low_index"]),
        "fan_direction": "up",
        "role": "swing_low",
    }


def _bars_dicts_from_parsed(
    parsed: Sequence[Tuple[Any, float, float, float]],
) -> List[Dict[str, Any]]:
    return [
        {
            "date": p[0].isoformat(),
            "high": p[1],
            "low": p[2],
            "close": p[3],
        }
        for p in parsed
    ]


def _zigzag_overlay(
    zigzag: Sequence[Dict[str, Any]],
    anchor_idx: int,
    parsed: Sequence[Tuple[Any, float, float, float]],
) -> List[Dict[str, Any]]:
    """将 zigzag 转为相对锚点的 bar_offset。"""
    out: List[Dict[str, Any]] = []
    date_to_idx = {parsed[i][0].isoformat(): i for i in range(len(parsed))}
    for z in zigzag or []:
        d = str(z.get("date") or "")[:10]
        idx = date_to_idx.get(d)
        if idx is None:
            continue
        out.append(
            {
                "bar_offset": int(idx - anchor_idx),
                "price": _round_p(z.get("price")),
                "kind": z.get("kind"),
            }
        )
    return out


def analyze_gann_trend(
    bars: Sequence[Dict[str, Any]],
    *,
    max_bars: int = DEFAULT_MAX_BARS,
    fractal_left: int = DEFAULT_FRACTAL,
    fractal_right: int = DEFAULT_FRACTAL,
    min_swing_bars: int = DEFAULT_MIN_SWING_BARS,
    scale_override: Optional[float] = None,
    fan_horizon_bars: int = FAN_HORIZON_BARS,
) -> Dict[str, Any]:
    """对日线序列做江恩趋势分析。"""
    parsed_all = _parse_bars(bars)
    mb = max(20, int(max_bars or DEFAULT_MAX_BARS))
    parsed = parsed_all[-mb:] if len(parsed_all) > mb else parsed_all
    window_bars = _bars_dicts_from_parsed(parsed)

    zz_pack = extract_zigzag_swing(
        window_bars,
        max_bars=len(window_bars) or mb,
        fractal_left=fractal_left,
        fractal_right=fractal_right,
        min_swing_bars=min_swing_bars,
    )

    empty = {
        "ok": False,
        "reason": zz_pack.get("reason") or "insufficient",
        "asof": parsed[-1][0].isoformat() if parsed else None,
        "last_close": _round_p(parsed[-1][3]) if parsed else None,
        "anchor": None,
        "scale": None,
        "scale_note": "1×1=每交易日价格单位（自适应），非屏幕45°",
        "angles": [],
        "fan_geometry": None,
        "time_windows": [],
        "verdict": {
            "bias": "insufficient",
            "bias_label": "信息不足",
            "summary": "有效波段锚点不足，暂无法给出江恩趋势结论。",
        },
        "swing": zz_pack.get("swing"),
        "atr": zz_pack.get("atr"),
        "zigzag": zz_pack.get("zigzag") or [],
    }
    if not zz_pack.get("ok") or not zz_pack.get("swing") or not parsed:
        return empty

    swing = zz_pack["swing"]
    atr = zz_pack.get("atr")
    if atr is None:
        atr = wilder_atr(parsed)
    last_close = float(parsed[-1][3])
    asof = parsed[-1][0].isoformat()
    asof_index = len(parsed) - 1

    if scale_override is not None and float(scale_override) > 0:
        scale = float(scale_override)
        scale_source = "override"
    else:
        scale = estimate_gann_scale(
            parsed, atr=float(atr) if atr else None, last_close=last_close
        )
        scale_source = "atr_adaptive"

    anchor = _pick_anchor(swing)
    anchor_idx = int(anchor["index"])
    if anchor_idx < 0 or anchor_idx >= len(parsed):
        return {**empty, "reason": "anchor_out_of_range"}

    bars_from_anchor = asof_index - anchor_idx
    fan_dir = str(anchor["fan_direction"])
    atr_f = float(atr) if atr is not None else abs(last_close) * 0.02
    near_band = max(abs(last_close) * NEAR_BAND_MIN_PCT, atr_f * NEAR_BAND_ATR_MULT)

    angles: List[Dict[str, Any]] = []
    for name, rise, run in ANGLE_RATIOS:
        px = angle_price(
            anchor_price=float(anchor["price"]),
            bars_from_anchor=max(0, bars_from_anchor),
            scale=scale,
            rise=rise,
            run=run,
            direction=fan_dir,
        )
        usable, invalid_reason = angle_usable(px, last_close)
        angles.append(
            {
                "name": name,
                "rise": rise,
                "run": run,
                "price_at_asof": _round_p(px),
                "slope_per_bar": _round_p(scale * (rise / run)),
                "usable": usable,
                "invalid_reason": invalid_reason,
            }
        )

    one_one = next((a for a in angles if a["name"] == "1x1"), None)
    one_price = (
        float(one_one["price_at_asof"])
        if one_one and one_one.get("price_at_asof") is not None
        else None
    )
    one_usable = bool(one_one and one_one.get("usable"))
    slope = recent_close_slope(parsed)
    slope_bars = min(SLOPE_LOOKBACK, max(0, len(parsed) - 1))
    if one_price is None or bars_from_anchor < 0:
        bias, bias_label, summary = (
            "insufficient",
            "信息不足",
            "基准日早于锚点或缺少 1×1 价，无法判定。",
        )
    else:
        bias, bias_label, summary = classify_gann_bias(
            last_close=last_close,
            one_price=one_price,
            one_usable=one_usable,
            near_band=near_band,
            scale=scale,
            fan_dir=fan_dir,
            recent_slope=slope,
            slope_bars=slope_bars,
        )

    time_windows: List[Dict[str, Any]] = []
    for n in TIME_WINDOWS:
        target_idx = anchor_idx + int(n)
        days_to = target_idx - asof_index
        if target_idx < len(parsed):
            status = "passed"
            target_date = parsed[target_idx][0].isoformat()
            if abs(target_idx - asof_index) <= 5:
                status = "near"
        else:
            status = "upcoming"
            target_date = None
            if 0 < days_to <= 10:
                status = "near"
        time_windows.append(
            {
                "bars": int(n),
                "target_date": target_date,
                "bars_from_asof": int(days_to),
                "status": status,
                "status_label": {
                    "passed": "已过",
                    "near": "临近",
                    "upcoming": "未到",
                }.get(status, status),
            }
        )

    horizon = max(10, int(fan_horizon_bars or FAN_HORIZON_BARS))
    end_offset = max(bars_from_anchor, horizon, 1)
    rays: List[Dict[str, Any]] = []
    all_prices = [float(anchor["price"]), last_close]
    for name, rise, run in ANGLE_RATIOS:
        end_px = angle_price(
            anchor_price=float(anchor["price"]),
            bars_from_anchor=end_offset,
            scale=scale,
            rise=rise,
            run=run,
            direction=fan_dir,
        )
        asof_px = angle_price(
            anchor_price=float(anchor["price"]),
            bars_from_anchor=max(0, bars_from_anchor),
            scale=scale,
            rise=rise,
            run=run,
            direction=fan_dir,
        )
        end_ok, _end_why = angle_usable(end_px, last_close)
        asof_ok, _asof_why = angle_usable(asof_px, last_close)
        ray_ok = end_ok and asof_ok
        if ray_ok:
            all_prices.extend([end_px, asof_px])
        rays.append(
            {
                "name": name,
                "usable": ray_ok,
                "start": {"bar_offset": 0, "price": _round_p(anchor["price"])},
                "end": {"bar_offset": int(end_offset), "price": _round_p(end_px)},
                "asof_point": {
                    "bar_offset": max(0, int(bars_from_anchor)),
                    "price": _round_p(asof_px),
                },
            }
        )

    y_min = min(all_prices)
    y_max = max(all_prices)
    pad = (y_max - y_min) * 0.08 if y_max > y_min else abs(last_close) * 0.02
    fan_geometry = {
        "anchor": {
            "bar_offset": 0,
            "price": _round_p(anchor["price"]),
            "date": anchor.get("date"),
            "kind": anchor.get("kind"),
        },
        "asof_bar_offset": max(0, int(bars_from_anchor)),
        "last_close": _round_p(last_close),
        "direction": fan_dir,
        "horizon_bars": int(end_offset),
        "y_min": _round_p(y_min - pad),
        "y_max": _round_p(y_max + pad),
        "rays": rays,
        "zigzag_overlay": _zigzag_overlay(zz_pack.get("zigzag") or [], anchor_idx, parsed),
    }

    return {
        "ok": True,
        "reason": None,
        "asof": asof,
        "last_close": _round_p(last_close),
        "anchor": {
            **anchor,
            "price": _round_p(anchor["price"]),
            "bars_from_anchor": int(bars_from_anchor),
            "swing_high": _round_p(swing.get("swing_high")),
            "swing_low": _round_p(swing.get("swing_low")),
            "swing_direction": swing.get("direction"),
        },
        "scale": _round_p(scale),
        "scale_source": scale_source,
        "scale_note": "1×1=每交易日价格单位（自适应 ATR/振幅），非屏幕45°",
        "angles": angles,
        "fan_geometry": fan_geometry,
        "time_windows": time_windows,
        "verdict": {
            "bias": bias,
            "bias_label": bias_label,
            "summary": summary,
            "one_x_one_price": _round_p(one_price) if one_price is not None else None,
            "near_band": _round_p(near_band),
        },
        "swing": {
            "direction": swing.get("direction"),
            "swing_high": _round_p(swing.get("swing_high")),
            "swing_low": _round_p(swing.get("swing_low")),
            "swing_high_date": swing.get("swing_high_date"),
            "swing_low_date": swing.get("swing_low_date"),
            "bar_span": swing.get("bar_span"),
        },
        "atr": _round_p(atr) if atr is not None else None,
        "zigzag": zz_pack.get("zigzag") or [],
        "disclaimer": "几何参考，非投资建议。",
    }
