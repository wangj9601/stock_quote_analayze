# -*- coding: utf-8 -*-
from backend_core.analysis.classic_levels import (
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
    assert out["fibonacci"] is not None
    assert 0.236 in [x["ratio"] for x in out["fibonacci"]["retracements"]]
