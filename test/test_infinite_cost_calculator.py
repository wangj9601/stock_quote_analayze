"""无穷成本均线：累计成交额/成交量递推。"""

import os
import sys

import pandas as pd

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend_core.utils.infinite_cost_calculator import calculate_infinite_cost_for_dataframe, icost_rows_for_db


def test_cumulative_vwap_simple():
    df = pd.DataFrame(
        [
            {"date": "2024-01-02", "open": 10, "high": 10, "low": 10, "close": 10, "volume": 100, "amount": 1000.0},
            {"date": "2024-01-03", "open": 12, "high": 12, "low": 12, "close": 12, "volume": 100, "amount": 1200.0},
        ]
    )
    out = calculate_infinite_cost_for_dataframe(df, volume_in_lots=False)
    assert len(out) == 2
    assert abs(out.iloc[0]["ic_price"] - 10.0) < 1e-9
    assert abs(out.iloc[1]["ic_price"] - 11.0) < 1e-9
    assert abs(out.iloc[1]["cum_amount"] - 2200.0) < 1e-6
    assert abs(out.iloc[1]["cum_volume"] - 200.0) < 1e-6


def test_fallback_typical_price_when_no_amount():
    df = pd.DataFrame(
        [
            {"date": "2024-01-02", "open": 10, "high": 12, "low": 8, "close": 10, "volume": 100, "amount": None},
        ]
    )
    out = calculate_infinite_cost_for_dataframe(df, volume_in_lots=False)
    tp = (12 + 8 + 10) / 3.0
    assert abs(out.iloc[0]["ic_price"] - tp) < 1e-9


def test_cyc_infinity_with_turnover_rate():
    """CYC∞：P_t = (1-HSL)*P_{t-1} + HSL*P_t，P_t 为 amount/volume(股)。"""
    df = pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "open": 10,
                "high": 10,
                "low": 10,
                "close": 10,
                "volume": 100,
                "amount": 1000.0,
                "turnover_rate": 0.1,
            },
            {
                "date": "2024-01-03",
                "open": 12,
                "high": 12,
                "low": 12,
                "close": 12,
                "volume": 100,
                "amount": 1200.0,
                "turnover_rate": 0.1,
            },
        ]
    )
    out = calculate_infinite_cost_for_dataframe(df, volume_in_lots=False)
    assert abs(out.iloc[0]["ic_price"] - 10.0) < 1e-9
    assert abs(out.iloc[1]["ic_price"] - (0.9 * 10.0 + 0.1 * 12.0)) < 1e-9


def test_hsl_percent_column_normalized():
    """换手率列若为百分数（如 10 表示 10%），单行 >1 时按 /100 处理。"""
    df = pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "open": 10,
                "high": 10,
                "low": 10,
                "close": 10,
                "volume": 100,
                "amount": 1000.0,
                "turnover_rate": 10.0,
            },
        ]
    )
    out = calculate_infinite_cost_for_dataframe(df, volume_in_lots=False)
    assert abs(out.iloc[0]["ic_price"] - 10.0) < 1e-9


def test_volume_in_lots_default_100_shares_per_lot():
    """库表 volume 为手：默认换算为股后再算 VWAP。"""
    df = pd.DataFrame(
        [
            {"date": "2024-01-02", "open": 10, "high": 10, "low": 10, "close": 10, "volume": 1, "amount": 1000.0},
            {"date": "2024-01-03", "open": 12, "high": 12, "low": 12, "close": 12, "volume": 1, "amount": 1200.0},
        ]
    )
    out = calculate_infinite_cost_for_dataframe(df)  # volume_in_lots=True
    assert abs(out.iloc[0]["ic_price"] - 10.0) < 1e-9
    assert abs(out.iloc[1]["ic_price"] - 11.0) < 1e-9
    assert abs(out.iloc[1]["cum_volume"] - 200.0) < 1e-6


def test_icost_rows_for_db_dates():
    df = pd.DataFrame(
        [{"date": "2024-01-02", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1, "amount": 10.0}]
    )
    out = calculate_infinite_cost_for_dataframe(df, volume_in_lots=False)
    rows = icost_rows_for_db(out)
    assert rows[0]["date"] == "2024-01-02"
