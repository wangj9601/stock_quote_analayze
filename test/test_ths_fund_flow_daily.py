"""同花顺资金流日采：金额解析与序列分析单测。"""

import pytest

from backend_core.data_collectors.akshare.ths_fund_flow_daily import (
    analyze_fund_flow_series,
    normalize_ths_code,
    parse_ths_amount,
    parse_ths_percent,
)


def test_parse_ths_amount_units():
    assert parse_ths_amount("6.49亿") == 6.49e8
    assert parse_ths_amount("7588.54万") == 7588.54e4
    assert parse_ths_amount("1.48亿") == 1.48e8
    assert parse_ths_amount(100.0) == 100.0
    assert parse_ths_amount("-") is None
    assert parse_ths_amount(None) is None


def test_parse_ths_percent():
    assert parse_ths_percent("19.99%") == 19.99
    assert parse_ths_percent("-0.30%") == -0.30
    assert parse_ths_percent("-") is None


def test_normalize_ths_code():
    assert normalize_ths_code(509) == "000509"
    assert normalize_ths_code("600519") == "600519"
    assert normalize_ths_code("sh600519") == "600519"
    assert normalize_ths_code(None) is None


def test_analyze_fund_flow_series():
    rows = [
        {
            "trade_date": "2026-09-01",
            "inflow_amount": 100.0,
            "outflow_amount": 80.0,
            "net_amount": 20.0,
        },
        {
            "trade_date": "2026-09-02",
            "inflow_amount": 120.0,
            "outflow_amount": 90.0,
            "net_amount": 30.0,
        },
    ]
    out = analyze_fund_flow_series(rows)
    assert out["days"] == 2
    assert out["first_date"] == "2026-09-01"
    assert out["last_date"] == "2026-09-02"
    assert out["inflow_change"] == pytest.approx(20.0)
    assert out["outflow_change"] == pytest.approx(10.0)
    assert out["net_change"] == pytest.approx(10.0)
    assert out["inflow_sum"] == pytest.approx(220.0)
    assert out["outflow_sum"] == pytest.approx(170.0)
    assert out["net_sum"] == pytest.approx(50.0)


def test_sync_to_quote_tables_updates_both(monkeypatch):
    from backend_core.data_collectors.akshare import ths_fund_flow_daily as mod

    class _Result:
        def __init__(self, n):
            self.rowcount = n

    calls = []

    class _Session:
        def execute(self, sql, params=None):
            sql_s = str(sql)
            calls.append((sql_s, params))
            if "historical_quotes" in sql_s:
                return _Result(1)
            if "stock_realtime_quote" in sql_s:
                return _Result(1)
            return _Result(0)

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(mod, "SessionLocal", lambda: _Session())
    c = mod.ThsFundFlowDailyCollector(trade_date="2026-09-08")
    out = c.sync_to_quote_tables(
        [
            {
                "code": "600519",
                "trade_date": "2026-09-08",
                "inflow_amount": 1.0,
                "outflow_amount": 2.0,
                "net_amount": -1.0,
            }
        ]
    )
    assert out["historical_updated"] == 1
    assert out["realtime_updated"] == 1
    hist_sqls = [s for s, _ in calls if "historical_quotes" in s]
    assert hist_sqls
    assert "CAST" not in hist_sqls[0].upper()
    assert any("stock_realtime_quote" in s for s, _ in calls)
