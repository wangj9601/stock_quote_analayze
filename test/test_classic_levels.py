# -*- coding: utf-8 -*-
from datetime import date, timedelta

from backend_core.analysis.classic_levels import (
    attach_reference_levels_batch,
    classic_pivot_from_hlc,
    compute_classic_levels_from_bars,
    fibonacci_from_swing,
)


def _v_shape_bars(n=60):
    bars = []
    base = date(2025, 1, 2)
    mid = n // 2
    for i in range(n):
        if i <= mid:
            c = 20.0 - (i / mid) * 8.0
        else:
            c = 12.0 + ((i - mid) / max(1, n - 1 - mid)) * 10.0
        bars.append(
            {
                "date": (base + timedelta(days=i)).isoformat(),
                "high": round(c + 0.4, 2),
                "low": round(c - 0.4, 2),
                "close": round(c, 2),
                "volume": 1_000_000 + i * 1000,
            }
        )
    return bars


def test_classic_pivot_formula():
    p = classic_pivot_from_hlc(12.0, 10.0, 11.0)
    assert abs(p["P"] - (12 + 10 + 11) / 3) < 1e-6
    assert abs(p["R1"] - (2 * p["P"] - 10)) < 1e-6
    assert abs(p["S1"] - (2 * p["P"] - 12)) < 1e-6


def test_fib_up_retracement_0382_0618():
    fib = fibonacci_from_swing(10.0, 0.0, direction="up")
    r382 = next(x for x in fib["retracements"] if abs(x["ratio"] - 0.382) < 1e-9)
    r618 = next(x for x in fib["retracements"] if abs(x["ratio"] - 0.618) < 1e-9)
    assert abs(r382["price"] - 6.18) < 1e-6
    assert abs(r618["price"] - 3.82) < 1e-6


def test_fib_down_retracement_0618():
    fib = fibonacci_from_swing(10.0, 0.0, direction="down")
    r618 = next(x for x in fib["retracements"] if abs(x["ratio"] - 0.618) < 1e-9)
    assert abs(r618["price"] - 6.18) < 1e-6


def test_compute_from_bars_zigzag_fib_and_cam():
    bars = _v_shape_bars(60)
    out = compute_classic_levels_from_bars(bars, last_close=bars[-1]["close"])
    assert out["ok"] is True
    assert out["pivot"] is not None
    assert out["camarilla"] is not None
    assert out["atr_pivot"] is not None
    fib = out["fibonacci"]
    assert fib is not None
    assert fib.get("anchor_method") == "zigzag_fractal"
    assert fib.get("ok") is True
    assert 0.236 in [x["ratio"] for x in fib["retracements"]]
    assert fib["swing_low"] < fib["swing_high"]
    assert fib["direction"] == "up"
    assert out["nearest_cam_support"] is not None or out["nearest_cam_resistance"] is not None


def test_attach_reference_includes_vp_and_confluence():
    bars = _v_shape_bars(60)
    out = attach_reference_levels_batch(
        {"000001": bars},
        last_close_by_code={"000001": bars[-1]["close"]},
        kde_by_code={
            "000001": {
                "support": 12.5,
                "resistance": 20.0,
                "supports": [12.4, 12.6],
                "resistances": [19.8, 20.2],
            }
        },
    )
    ref = out["000001"]
    assert ref.get("volume_profile", {}).get("ok") is True
    assert ref["volume_profile"]["poc"] is not None
    assert "confluence_zones" in ref
    assert ref["camarilla"] is not None
