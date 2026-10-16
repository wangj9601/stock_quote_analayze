"""同花顺资金流日采：金额解析与序列分析单测。"""

import pytest

from backend_core.data_collectors.akshare.ths_fund_flow_daily import (
    analyze_fund_flow_series,
    normalize_ths_code,
    parse_ths_amount,
    parse_ths_percent,
    sina_records_to_frame,
    ths_html_to_frame,
    ths_page_count,
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


def test_analyze_fund_flow_series_signed_net():
    """正负净流入：合计为代数和，变化为末日相对首日。"""
    rows = [
        {
            "trade_date": "2026-09-07",
            "inflow_amount": 100.0,
            "outflow_amount": 286.0,
            "net_amount": -186_000_000.0,
        },
        {
            "trade_date": "2026-09-08",
            "inflow_amount": 50.0,
            "outflow_amount": 31.0,
            "net_amount": 19_000_000.0,
        },
    ]
    out = analyze_fund_flow_series(rows)
    # 合计：+0.19亿 + (-1.86亿) = -1.67亿
    assert out["net_sum"] == pytest.approx(-167_000_000.0)
    # 变化：末日 − 首日 = 0.19 − (-1.86) = +2.05亿
    assert out["net_change"] == pytest.approx(205_000_000.0)
    assert out["latest_net"] == pytest.approx(19_000_000.0)


_EMPTY_SHELL = """
<table class="m-table"><thead><tr><th>序号</th></tr></thead><tbody></tbody></table>
<div class="m-page"></div>
"""

_ONE_PAGE = """
<span class="page_info">1/1</span>
<table>
<tr><th>序号</th><th>股票代码</th><th>股票简称</th><th>最新价</th><th>涨跌幅</th><th>换手率</th><th>流入资金</th><th>流出资金</th><th>净额</th><th>成交额</th></tr>
<tr><td>1</td><td>600519</td><td>贵州茅台</td><td>1400</td><td>1.20%</td><td>0.30%</td><td>1.20亿</td><td>0.80亿</td><td>0.40亿</td><td>2.00亿</td></tr>
</table>
"""


def test_ths_page_count_missing_node():
    assert ths_page_count(_EMPTY_SHELL) is None
    assert ths_html_to_frame(_EMPTY_SHELL).empty
    assert ths_page_count(_ONE_PAGE) == 1
    frame = ths_html_to_frame(_ONE_PAGE)
    assert list(frame["股票代码"]) == [600519] or list(frame["股票代码"].astype(str)) == ["600519"]


def test_sina_records_keep_a_shares_only():
    frame = sina_records_to_frame(
        [
            {
                "symbol": "sh510300",
                "name": "沪深300ETF",
                "trade": "4.2",
                "changeratio": "0.01",
                "inamount": "10",
                "outamount": "8",
                "netamount": "2",
                "amount": "18",
            },
            {
                "symbol": "sz002815",
                "name": "崇达技术",
                "trade": "23.47",
                "changeratio": "0.00946237",
                "inamount": "3238197799.12",
                "outamount": "2121663783.99",
                "netamount": "1116534015.13",
                "amount": "5539031681",
            },
        ]
    )
    assert list(frame["股票代码"]) == ["002815"]
    assert frame.iloc[0]["涨跌幅"] == pytest.approx(0.946237)
    assert float(frame.iloc[0]["净额"]) == pytest.approx(1116534015.13)


def test_fetch_dataframe_falls_back_to_sina(monkeypatch):
    from backend_core.data_collectors.akshare import ths_fund_flow_daily as mod

    def _boom():
        raise RuntimeError("同花顺个股资金流免费接口返回空表，缺少 page_info")

    monkeypatch.setattr(mod, "fetch_ths_instant_dataframe", _boom)
    monkeypatch.setattr(
        mod,
        "fetch_sina_instant_dataframe",
        lambda: mod.sina_records_to_frame(
            [
                {
                    "symbol": "sh600519",
                    "name": "贵州茅台",
                    "trade": "1400",
                    "changeratio": "0.012",
                    "inamount": "100",
                    "outamount": "40",
                    "netamount": "60",
                    "amount": "140",
                }
            ]
        ),
    )
    collector = mod.ThsFundFlowDailyCollector(trade_date="2026-10-16")
    df = collector.fetch_dataframe()
    assert collector.source == "sina"
    assert not df.empty
    rows = collector.dataframe_to_rows(df)
    assert rows[0]["code"] == "600519"
    assert rows[0]["source"] == "sina"
    assert rows[0]["net_amount"] == pytest.approx(60.0)


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
