# -*- coding: utf-8 -*-
from backend_core.analysis.classic_levels import (
    attach_reference_levels_batch,
    classic_pivot_from_hlc,
    compute_classic_levels_from_bars,
    fibonacci_from_swing,
)


def test_classic_pivot_formula():
    p = classic_pivot_from_hlc(12.0, 10.0, 11.0)
    assert abs(p["P"] - (12 + 10 + 11) / 3) < 1e-6
    assert abs(p["R1"] - (2 * p["P"] - 10)) < 1e-6
    assert abs(p["S1"] - (2 * p["P"] - 12)) < 1e-6


def test_fib_up_retracement_0382_0618():
    fib = fibonacci_from_swing(10.0, 0.0, direction="up")
    r382 = next(x for x in fib["retracements"] if abs(x["ratio"] - 0.382) < 1e-9)
    r618 = next(x for x in fib["retracements"] if abs(x["ratio"] - 0.618) < 1e-9)
    assert abs(r382["price"] - 6.18) < 1e-6  # 10 - 0.382*10
    assert abs(r618["price"] - 3.82) < 1e-6  # 10 - 0.618*10


def test_fib_down_retracement_0618():
    fib = fibonacci_from_swing(10.0, 0.0, direction="down")
    r618 = next(x for x in fib["retracements"] if abs(x["ratio"] - 0.618) < 1e-9)
    assert abs(r618["price"] - 6.18) < 1e-6  # 0 + 0.618*10


def test_compute_from_bars_nearest():
    bars = []
    for i in range(10):
        bars.append(
            {
                "date": f"2026-01-{i+1:02d}",
                "high": 10.0 + i * 0.1,
                "low": 9.0,
                "close": 9.5 + i * 0.05,
            }
        )
    # last close mid-range
    out = compute_classic_levels_from_bars(bars, last_close=9.8)
    assert out["ok"] is True
    assert out["pivot"] is not None
    assert out["pivot"].get("trade_date") == "2026-01-09"
    assert out["fibonacci"] is not None
    assert 0.236 in [x["ratio"] for x in out["fibonacci"]["retracements"]]
    # 窗口最高在最后一天，最低多日同低取最早一根（min 稳定）
    assert out["fibonacci"]["swing_high"] == 10.9
    assert out["fibonacci"]["swing_high_date"] == "2026-01-10"
    assert out["fibonacci"]["swing_low"] == 9.0
    assert out["fibonacci"]["swing_low_date"] == "2026-01-01"


def test_attach_reference_includes_volume_profile():
    bars = []
    for i in range(30):
        bars.append(
            {
                "date": f"2026-02-{i+1:02d}" if i < 28 else f"2026-03-{i-27:02d}",
                "high": 15.5,
                "low": 14.5,
                "close": 15.0,
                "volume": 1_000_000 + i * 1000,
            }
        )
    out = attach_reference_levels_batch({"000001": bars}, last_close_by_code={"000001": 15.0})
    ref = out["000001"]
    assert ref.get("volume_profile", {}).get("ok") is True
    assert ref["volume_profile"]["poc"] is not None
    assert "nearest_vp_support" in ref or "nearest_vp_resistance" in ref
