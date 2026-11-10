# -*- coding: utf-8 -*-
"""江恩趋势预测单测：角度价、时间窗、扇形几何与斜率一致。"""

from datetime import date, timedelta

from backend_core.analysis.gann_trend import (
    analyze_gann_trend,
    angle_price,
    angle_usable,
    classify_gann_bias,
    estimate_gann_scale,
)


def _make_uptrend_bars(n: int = 120, start: float = 10.0) -> list:
    """构造可检出上升波段的日线：先缓跌再缓升，形成低点锚。"""
    bars = []
    d0 = date(2024, 1, 2)
    # 前半：从高点回落
    for i in range(40):
        px = start + 5 - i * 0.08
        bars.append(
            {
                "date": (d0 + timedelta(days=i)).isoformat(),
                "high": px + 0.15,
                "low": px - 0.15,
                "close": px,
            }
        )
    # 后半：从低点上升（形成 up 波段）
    base = bars[-1]["close"]
    for i in range(40, n):
        px = base + (i - 40) * 0.12
        bars.append(
            {
                "date": (d0 + timedelta(days=i)).isoformat(),
                "high": px + 0.2,
                "low": px - 0.1,
                "close": px,
            }
        )
    return bars


def test_angle_price_up_and_down():
    up = angle_price(
        anchor_price=100.0,
        bars_from_anchor=10,
        scale=1.0,
        rise=1.0,
        run=1.0,
        direction="up",
    )
    assert abs(up - 110.0) < 1e-9
    steeper = angle_price(
        anchor_price=100.0,
        bars_from_anchor=10,
        scale=1.0,
        rise=2.0,
        run=1.0,
        direction="up",
    )
    assert abs(steeper - 120.0) < 1e-9
    flatter = angle_price(
        anchor_price=100.0,
        bars_from_anchor=10,
        scale=1.0,
        rise=1.0,
        run=2.0,
        direction="up",
    )
    assert abs(flatter - 105.0) < 1e-9
    down = angle_price(
        anchor_price=100.0,
        bars_from_anchor=10,
        scale=1.0,
        rise=1.0,
        run=1.0,
        direction="down",
    )
    assert abs(down - 90.0) < 1e-9


def test_estimate_scale_positive():
    bars = _make_uptrend_bars(80)
    from backend_core.analysis.swing_zigzag import _parse_bars, wilder_atr

    parsed = _parse_bars(bars)
    atr = wilder_atr(parsed)
    scale = estimate_gann_scale(parsed, atr=atr, last_close=parsed[-1][3])
    assert scale > 0


def test_analyze_gann_angles_and_fan():
    bars = _make_uptrend_bars(130)
    out = analyze_gann_trend(bars, max_bars=120, scale_override=0.5)
    assert out["ok"] is True
    assert out["scale"] == 0.5
    assert out["scale_source"] == "override"
    assert len(out["angles"]) == 5
    names = [a["name"] for a in out["angles"]]
    assert names == ["1x1", "2x1", "1x2", "4x1", "1x4"]

    anchor = out["anchor"]
    assert anchor is not None
    bars_n = max(0, int(anchor["bars_from_anchor"]))
    fan_dir = anchor["fan_direction"]
    for a in out["angles"]:
        expected = angle_price(
            anchor_price=float(anchor["price"]),
            bars_from_anchor=bars_n,
            scale=0.5,
            rise=float(a["rise"]),
            run=float(a["run"]),
            direction=fan_dir,
        )
        assert abs(float(a["price_at_asof"]) - expected) < 0.011

    fg = out["fan_geometry"]
    assert fg is not None
    assert len(fg["rays"]) == 5
    for ray in fg["rays"]:
        assert ray["start"]["bar_offset"] == 0
        assert ray["end"]["bar_offset"] > 0
        # 端点斜率与角度一致
        a = next(x for x in out["angles"] if x["name"] == ray["name"])
        end_expected = angle_price(
            anchor_price=float(anchor["price"]),
            bars_from_anchor=int(ray["end"]["bar_offset"]),
            scale=0.5,
            rise=float(a["rise"]),
            run=float(a["run"]),
            direction=fan_dir,
        )
        assert abs(float(ray["end"]["price"]) - end_expected) < 0.011

    tw = out["time_windows"]
    assert [t["bars"] for t in tw] == [45, 90, 144, 180, 360]
    # 递推：bars_from_asof 应按窗口增大（相对同一 asof）
    deltas = [t["bars_from_asof"] for t in tw]
    assert deltas == sorted(deltas)

    assert out["verdict"]["bias"] in ("bullish", "bearish", "near", "neutral", "insufficient")
    assert out["last_close"] is not None


def test_insufficient_bars():
    bars = [
        {
            "date": f"2024-01-{i+1:02d}",
            "high": 10,
            "low": 9,
            "close": 9.5,
        }
        for i in range(5)
    ]
    out = analyze_gann_trend(bars, max_bars=60)
    assert out["ok"] is False
    assert out["verdict"]["bias"] == "insufficient"


def test_angle_usable_rejects_non_positive_and_far():
    ok, why = angle_usable(-6.36, 28.0)
    assert ok is False and why == "non_positive"
    ok, why = angle_usable(200.0, 28.0)
    assert ok is False and why == "far_from_spot"
    ok, why = angle_usable(30.0, 28.0)
    assert ok is True and why is None


def test_down_fan_above_falling_1x1_is_not_bullish():
    """缓跌回到下移的 1×1 上方，斜率未向上，不得标偏多。"""
    bias, label, summary = classify_gann_bias(
        last_close=27.94,
        one_price=25.8,
        one_usable=True,
        near_band=0.4,
        scale=0.51,
        fan_dir="down",
        recent_slope=-0.05,
        slope_bars=10,
    )
    assert bias == "neutral"
    assert label == "中性"
    assert "不单独作为方向" in summary


def test_bias_needs_slope_to_agree():
    bias, label, _ = classify_gann_bias(
        last_close=30.0,
        one_price=28.0,
        one_usable=True,
        near_band=0.2,
        scale=0.2,
        fan_dir="up",
        recent_slope=0.2,
        slope_bars=10,
    )
    assert bias == "bullish"
    assert label == "偏多"
    bias, label, _ = classify_gann_bias(
        last_close=28.0,
        one_price=-6.0,
        one_usable=False,
        near_band=0.2,
        scale=2.0,
        fan_dir="down",
        recent_slope=0.1,
        slope_bars=10,
    )
    assert bias == "insufficient"
    assert label == "不可用"
