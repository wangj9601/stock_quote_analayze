# -*- coding: utf-8 -*-
"""batch_ma_mavol 单元测试（不连库）。"""

from backend_core.data_collectors.batch_ma_mavol import (
    _compute_single_stock,
    _normalize_date_str,
)
from backend_core.utils.ma_calculator import MACalculator
from backend_core.utils.mavol_calculator import MAVOLCalculator
import datetime


def test_normalize_date_str_variants():
    assert _normalize_date_str("2026-07-24") == "2026-07-24"
    assert _normalize_date_str("20260724") == "2026-07-24"
    assert _normalize_date_str(datetime.date(2026, 7, 24)) == "2026-07-24"


def test_compute_single_stock_ma_mavol_target_day():
    start = datetime.date(2025, 1, 1)
    dates = [(start + datetime.timedelta(days=i)).isoformat() for i in range(220)]
    closes = [float(i) for i in range(1, 221)]
    volumes = [float(i * 10) for i in range(1, 221)]
    target = dates[-1]
    series = {"dates": dates, "closes": closes, "volumes": volumes}
    now = datetime.datetime.now()
    ma_row, mavol_row, status = _compute_single_stock(
        "600000",
        series,
        target,
        "CN",
        True,
        True,
        now,
    )
    assert status == "ok"
    assert ma_row is not None
    assert mavol_row is not None
    assert ma_row["code"] == "600000"
    assert ma_row["date"] == target
    assert ma_row["ma200"] is not None
    assert mavol_row["m20"] is not None


def test_compute_single_stock_skip_when_target_missing():
    series = {
        "dates": ["2026-07-22", "2026-07-23"],
        "closes": [10.0, 11.0],
        "volumes": [100.0, 110.0],
    }
    ma_row, mavol_row, status = _compute_single_stock(
        "600000",
        series,
        "2026-07-24",
        "CN",
        True,
        True,
        datetime.datetime.now(),
    )
    assert status == "skip"
    assert ma_row is None
    assert mavol_row is None


def test_ma_for_list_matches_last_row_of_dataframe():
    closes = [float(i) for i in range(1, 220)]
    import pandas as pd

    df = pd.DataFrame({"close": closes})
    ma_df = MACalculator.calculate_ma_for_dataframe(df)
    list_vals = MACalculator.calculate_ma_for_list(closes)
    last = ma_df.iloc[-1]
    assert list_vals["ma200"] == last["ma200"]


def test_mavol_for_list_matches_batch_last():
    volumes = [float(i) for i in range(1, 220)]
    list_vals = MAVOLCalculator.calculate_mavol_for_list(volumes)
    batch_vals = MAVOLCalculator.calculate_mavol_batch(volumes)[-1]
    assert list_vals["mavol200"] == batch_vals["mavol200"]
