"""MeanFrequencyResonanceCalculator 单元测试。"""

import sys
from pathlib import Path
from types import SimpleNamespace

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend_core.utils.mean_frequency_calculator import MeanFrequencyResonanceCalculator  # noqa: E402


def _rows(n: int, *, bad_idx: int | None = None):
    out = []
    for i in range(n):
        close = None if bad_idx == i else 10.0 + i * 0.1
        volume = 1000.0 + i
        out.append(SimpleNamespace(date=f"2024-01-{i+1:02d}", close=close, volume=volume))
    return out


def test_calculate_for_dataframe_skips_none_close_volume():
    calc = MeanFrequencyResonanceCalculator()
    rows = _rows(25, bad_idx=10)
    df = calc.calculate_for_dataframe(rows)
    assert not df.empty
    assert len(df) > 0


def test_calculate_for_dataframe_returns_empty_when_too_many_invalid():
    calc = MeanFrequencyResonanceCalculator()
    rows = [SimpleNamespace(date=f"2024-01-{i+1:02d}", close=None, volume=100.0) for i in range(25)]
    df = calc.calculate_for_dataframe(rows)
    assert df.empty


def test_calculate_rising_falling_days_on_monotonic_series():
    calc = MeanFrequencyResonanceCalculator()
    closes = [10.0 + i for i in range(25)]
    volumes = [1000.0 + i for i in range(25)]
    dates = [f"2024-01-{i+1:02d}" for i in range(25)]
    results = calc.calculate(closes, volumes, dates=dates, window=20)
    assert len(results) == 25
    last = results[-1]
    assert last is not None
    # 单调上涨：窗口内 20 次比较均为涨
    assert last["rising_days_z"] == 20
    assert last["falling_days_f"] == 0


def test_calculate_for_target_day_returns_last_bar():
    calc = MeanFrequencyResonanceCalculator()
    closes = [10.0 + i * 0.1 for i in range(25)]
    volumes = [1000.0 + i for i in range(25)]
    dates = [f"2024-02-{i+1:02d}" for i in range(25)]
    res = calc.calculate_for_target_day(closes, volumes, dates, "2024-02-25", window=20)
    assert res is not None
    assert res["d20_date"] == "2024-02-25"
    assert res["rising_days_z"] + res["falling_days_f"] <= 20
