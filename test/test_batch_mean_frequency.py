# -*- coding: utf-8 -*-
"""batch_mean_frequency 单元测试（不连库）。"""

import datetime

from backend_core.data_collectors.batch_mean_frequency import _compute_single_stock
from backend_core.utils.mean_frequency_calculator import MeanFrequencyResonanceCalculator


def test_calculate_for_target_day_matches_full_calculate():
    start = datetime.date(2025, 1, 1)
    dates = [(start + datetime.timedelta(days=i)).isoformat() for i in range(40)]
    closes = [10.0 + i * 0.1 for i in range(40)]
    volumes = [1000.0 + i * 5 for i in range(40)]
    target = dates[-1]
    calc = MeanFrequencyResonanceCalculator()
    full = calc.calculate(closes, volumes, dates=dates)
    target_only = calc.calculate_for_target_day(closes, volumes, dates, target)
    assert full[-1] is not None
    assert target_only is not None
    assert target_only["ma20_d"] == full[-1]["ma20_d"]
    assert target_only["rising_days_z"] == full[-1]["rising_days_z"]


def test_compute_single_stock_pvfrs_ok():
    start = datetime.date(2025, 1, 1)
    dates = [(start + datetime.timedelta(days=i)).isoformat() for i in range(40)]
    closes = [10.0 + i * 0.1 for i in range(40)]
    volumes = [1000.0 + i * 5 for i in range(40)]
    target = dates[-1]
    series = {"dates": dates, "closes": closes, "volumes": volumes}
    row, status = _compute_single_stock(
        "600000", series, target, "CN", datetime.datetime.now()
    )
    assert status == "ok"
    assert row is not None
    assert row["code"] == "600000"
    assert row["date"] == target
    assert row["ma20"] is not None


def test_compute_single_stock_skip_insufficient_data():
    series = {
        "dates": ["2026-07-22", "2026-07-23"],
        "closes": [10.0, 11.0],
        "volumes": [100.0, 110.0],
    }
    row, status = _compute_single_stock(
        "600000", series, "2026-07-23", "CN", datetime.datetime.now()
    )
    assert status == "skip"
    assert row is None
