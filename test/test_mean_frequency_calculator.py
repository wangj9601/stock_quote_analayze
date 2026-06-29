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
