# -*- coding: utf-8 -*-
"""个股日资金流合并：日表优先，行情表补齐。"""

from backend_api.stock.stock_fund_flow import _merge_fund_flow_series


def test_merge_prefers_daily_table_for_newer_day():
    """行情表只有到 09 号，日表已有 10 号时应合并出 10 号。"""
    hist = [
        {"trade_date": "2026-09-09", "net_amount": 1e6, "inflow_amount": 1.44e8, "outflow_amount": 1.43e8},
        {"trade_date": "2026-09-08", "net_amount": -5.4e7, "inflow_amount": 1.74e8, "outflow_amount": 2.27e8},
    ]
    daily = [
        {"trade_date": "2026-09-10", "net_amount": 1.33011e7, "inflow_amount": 1.04e8, "outflow_amount": 9.05784e7},
        {"trade_date": "2026-09-09", "net_amount": 2e6, "inflow_amount": 1.5e8, "outflow_amount": 1.48e8},
    ]
    series, source = _merge_fund_flow_series(
        daily,
        hist,
        days=20,
        primary_label="stock_fund_flow_daily",
        secondary_label="historical_quotes",
    )
    dates = [r["trade_date"] for r in series]
    assert dates[-1] == "2026-09-10"
    assert "2026-09-08" in dates
    # 同日优先日表
    row09 = next(r for r in series if r["trade_date"] == "2026-09-09")
    assert row09["net_amount"] == 2e6
    assert "stock_fund_flow_daily" in source
    assert "historical_quotes" in source


def test_merge_days_limit():
    daily = [{"trade_date": f"2026-09-{d:02d}", "net_amount": float(d)} for d in range(1, 11)]
    series, source = _merge_fund_flow_series(
        daily,
        [],
        days=3,
        primary_label="stock_fund_flow_daily",
        secondary_label="historical_quotes",
    )
    assert len(series) == 3
    assert [r["trade_date"] for r in series] == ["2026-09-08", "2026-09-09", "2026-09-10"]
    assert source == "stock_fund_flow_daily"
