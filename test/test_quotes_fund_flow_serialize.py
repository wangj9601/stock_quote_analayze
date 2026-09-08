"""A股历史行情序列化应包含资金流向字段。"""

from types import SimpleNamespace

from backend_api.quotes_routes import _historical_quotes_cn_to_api


def test_historical_quotes_cn_to_api_includes_fund_flow():
    row = SimpleNamespace(
        code="600519",
        ts_code="600519.SH",
        name="贵州茅台",
        market="SH",
        date="2026-09-08",
        open=1.0,
        high=2.0,
        low=0.5,
        close=1.5,
        pre_close=1.2,
        volume=100,
        amount=1000.0,
        amplitude=1.0,
        change_percent=1.2,
        change=0.3,
        turnover_rate=0.5,
        inflow_amount=1e8,
        outflow_amount=4e7,
        net_amount=6e7,
        collected_source="tushare",
        collected_date=None,
    )
    out = _historical_quotes_cn_to_api(row)
    assert out["inflow_amount"] == 1e8
    assert out["outflow_amount"] == 4e7
    assert out["net_amount"] == 6e7
    assert out["code"] == "600519"
    assert out["date"] == "2026-09-08"
