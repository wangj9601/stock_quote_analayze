# -*- coding: utf-8 -*-
"""板块斜率新口径：等权收益链、官方指数选源、R² 走强过滤。"""
import math

from backend_core.board_metrics.sector_slope_store import (
    SLOPE_SOURCE_EQUAL_WEIGHT,
    SLOPE_SOURCE_THS_INDEX,
    min_points_for_slope_window,
    slope_r2_min_for_window,
)
from backend_core.strategies.gms.board_resonance import (
    DEFAULT_SLOPE_STRONG_THRESHOLD,
    evaluate_board_environment,
)
from backend_core.strategies.rpe.sector_benchmark import (
    compute_equal_weight_return_benchmark,
    compute_vwap_benchmark,
    index_closes_to_benchmark,
    linear_slope_fit,
    sector_slope,
    sector_slope_fit,
)


def test_vwap_jumps_on_volume_shift_but_equal_weight_stable():
    """价不变、量在高低价间搬家：VWAP 跳，等权收益链不跳。"""
    # Day1: A=100×100, B=10×100 → VWAP=55
    # Day2: A=100×200, B=10×100 → VWAP≈70
    dm = {
        "2024-01-01": [(100.0, 100.0), (10.0, 100.0)],
        "2024-01-02": [(100.0, 200.0), (10.0, 100.0)],
    }
    vwap = compute_vwap_benchmark(dm)
    assert abs(vwap[0]["i_t"] - 55.0) < 1e-6
    assert abs(vwap[1]["i_t"] - 70.0) < 1e-6

    panel = {
        "A": [
            {"date": "2024-01-01", "close": 100.0},
            {"date": "2024-01-02", "close": 100.0},
        ],
        "B": [
            {"date": "2024-01-01", "close": 10.0},
            {"date": "2024-01-02", "close": 10.0},
        ],
    }
    ew = compute_equal_weight_return_benchmark(panel, min_members=2)
    assert len(ew) == 1
    assert abs(ew[0]["i_t"] - 1000.0) < 1e-9  # R_t=0 → 水平不变


def test_equal_weight_chain_rises_with_uniform_returns():
    panel = {}
    for code in ("A", "B", "C", "D", "E"):
        panel[code] = [
            {"date": f"2024-01-{i+1:02d}", "close": 10.0 * (1.01**i)}
            for i in range(10)
        ]
    ew = compute_equal_weight_return_benchmark(panel, min_members=5)
    assert len(ew) == 9
    assert ew[-1]["i_t"] > 1000.0
    fit = sector_slope_fit(ew, 9, transform="log")
    assert fit is not None
    assert fit["sector_slope"] > 0
    assert fit["slope_r2"] > 0.99


def test_linear_slope_fit_returns_r2():
    vals = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    fit = linear_slope_fit(vals)
    assert fit is not None
    b, r2, n = fit
    assert abs(b - 1.0) < 1e-9
    assert r2 > 0.999
    assert n == 8


def test_index_closes_to_benchmark_and_min_points():
    rows = [
        {"date": "2024-01-01", "close": 100},
        {"trade_date": "2024-01-02", "close": 101},
        {"date": "2024-01-03", "close": 0},  # skip
    ]
    bm = index_closes_to_benchmark(rows)
    assert len(bm) == 2
    assert bm[0]["i_t"] == 100
    assert min_points_for_slope_window(60) == 30
    assert min_points_for_slope_window(5) == 5
    assert abs(slope_r2_min_for_window(60) - 0.30) < 1e-9


def test_board_env_strong_requires_r2():
    slope = 0.0015
    # 无 R²：不标走强
    env0 = evaluate_board_environment(
        sector_slope_v=slope, board_change_percent=None, slope_r2=None
    )
    assert env0["board_env"] == "neutral"
    assert env0["board_strong"] is False
    assert env0["board_weak_reason"] == "sector_slope_strong_low_r2"

    # R² 不足
    env1 = evaluate_board_environment(
        sector_slope_v=slope,
        board_change_percent=None,
        slope_r2=0.1,
        sector_slope_window=60,
    )
    assert env1["board_env"] == "neutral"
    assert env1["board_strong"] is False

    # R² 达标
    env2 = evaluate_board_environment(
        sector_slope_v=slope,
        board_change_percent=None,
        slope_r2=0.9,
        sector_slope_window=60,
    )
    assert env2["board_env"] == "strong"
    assert env2["board_strong"] is True
    assert slope >= DEFAULT_SLOPE_STRONG_THRESHOLD


def test_board_env_weak_ignores_r2_by_default():
    env = evaluate_board_environment(
        sector_slope_v=-0.01,
        board_change_percent=None,
        slope_r2=0.05,
        sector_slope_window=60,
    )
    assert env["board_env"] == "weak"
    assert env["board_weak"] is True


def test_sector_slope_log_still_works():
    it = [100.0 * (1.002**i) for i in range(60)]
    bench = [{"date": f"d{i}", "i_t": v} for i, v in enumerate(it)]
    slope = sector_slope(bench, 60, transform="log")
    assert slope is not None
    assert abs(slope - math.log(1.002)) < 1e-6
    fit = sector_slope_fit(bench, 60, transform="log")
    assert fit is not None and fit["slope_r2"] > 0.99


def test_source_constants():
    assert SLOPE_SOURCE_THS_INDEX == "ths_index"
    assert SLOPE_SOURCE_EQUAL_WEIGHT == "equal_weight_return"
