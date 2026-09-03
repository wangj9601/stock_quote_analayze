# -*- coding: utf-8 -*-
"""ln(I_t) 斜率与走强档展示口径。"""
import math

from backend_core.strategies.gms.board_resonance import (
    DEFAULT_SLOPE_STRONG_THRESHOLD,
    evaluate_board_environment,
)
from backend_core.strategies.rpe.sector_benchmark import sector_slope


def test_sector_slope_log_transform_positive_trend():
    # 指数日增约 0.2% → ln 序列近似线性，斜率接近 ln(1.002)
    it = [100.0 * (1.002**i) for i in range(60)]
    bench = [{"date": f"d{i}", "i_t": v, "volume_sum": 1.0} for i, v in enumerate(it)]
    slope = sector_slope(bench, 60, transform="log")
    assert slope is not None
    assert abs(slope - math.log(1.002)) < 1e-6
    assert slope >= DEFAULT_SLOPE_STRONG_THRESHOLD
    env = evaluate_board_environment(sector_slope_v=slope, board_change_percent=None)
    assert env["board_env"] == "strong"
    assert env["board_strong"] is True


def test_sector_slope_none_keeps_absolute_price_scale():
    """transform=none 仍为绝对价位斜率；默认/log 为更小量级的对数斜率。"""
    it = [100.0 + i for i in range(30)]
    bench = [{"date": f"d{i}", "i_t": v, "volume_sum": 1.0} for i, v in enumerate(it)]
    abs_slope = sector_slope(bench, 30, transform="none")
    log_slope = sector_slope(bench, 30, transform="log")
    default_slope = sector_slope(bench, 30)  # 默认 log，与行情/RPE 一致
    assert abs_slope is not None and abs(abs_slope - 1.0) < 1e-9
    assert log_slope is not None
    assert abs(log_slope) < 0.05  # 绝对斜率≈1，对数斜率远更小
    assert default_slope is not None
    assert abs(default_slope - log_slope) < 1e-12
