"""季/半年/年线：日历期末日聚合单测。"""

import pandas as pd
import pytest

from backend_core.data_collectors.akshare.period_agg import (
    resample_ohlcv_to_period_ends,
    to_calendar_half_end,
    to_calendar_quarter_end,
    to_calendar_year_end,
)


def test_calendar_period_ends():
    assert to_calendar_quarter_end("2024-02-15") == pd.Timestamp("2024-03-31")
    assert to_calendar_quarter_end("2024-06-01") == pd.Timestamp("2024-06-30")
    assert to_calendar_half_end("2024-03-31") == pd.Timestamp("2024-06-30")
    assert to_calendar_half_end("2024-07-01") == pd.Timestamp("2024-12-31")
    assert to_calendar_year_end("2024-05-01") == pd.Timestamp("2024-12-31")


def test_semiannual_from_quarter_starts_q1_uses_jun_dec():
    """季线若从 03-31 起，半年线必须是 06-30/12-31，不能漂到 03-31/09-30。"""
    idx = pd.to_datetime(
        ["2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31"]
    )
    df = pd.DataFrame(
        {
            "open": [1, 2, 3, 4],
            "high": [1.5, 2.5, 3.5, 4.5],
            "low": [0.5, 1.5, 2.5, 3.5],
            "close": [1.2, 2.2, 3.2, 4.2],
            "volume": [10, 20, 30, 40],
            "amount": [100, 200, 300, 400],
            "name": ["X"] * 4,
        },
        index=idx,
    )
    out = resample_ohlcv_to_period_ends(df, "semiannual")
    dates = [d.strftime("%Y-%m-%d") for d in out.index]
    assert dates == ["2024-06-30", "2024-12-31"]
    assert out.loc[pd.Timestamp("2024-06-30"), "open"] == pytest.approx(1.0)
    assert out.loc[pd.Timestamp("2024-06-30"), "close"] == pytest.approx(2.2)
    assert out.loc[pd.Timestamp("2024-12-31"), "volume"] == pytest.approx(70.0)


def test_quarterly_and_annual_period_ends():
    idx = pd.to_datetime(
        [
            "2024-01-31",
            "2024-02-29",
            "2024-03-31",
            "2024-04-30",
            "2024-05-31",
            "2024-06-30",
        ]
    )
    df = pd.DataFrame(
        {
            "open": range(1, 7),
            "high": range(1, 7),
            "low": range(1, 7),
            "close": range(1, 7),
            "volume": [1] * 6,
            "amount": [1] * 6,
        },
        index=idx,
    )
    q = resample_ohlcv_to_period_ends(df, "quarterly")
    assert [d.strftime("%Y-%m-%d") for d in q.index] == ["2024-03-31", "2024-06-30"]

    half = pd.DataFrame(
        {
            "open": [1, 2],
            "high": [1, 2],
            "low": [1, 2],
            "close": [1, 2],
            "volume": [10, 20],
            "amount": [100, 200],
        },
        index=pd.to_datetime(["2024-06-30", "2024-12-31"]),
    )
    y = resample_ohlcv_to_period_ends(half, "annual")
    assert [d.strftime("%Y-%m-%d") for d in y.index] == ["2024-12-31"]
    assert y.loc[pd.Timestamp("2024-12-31"), "volume"] == pytest.approx(30.0)
