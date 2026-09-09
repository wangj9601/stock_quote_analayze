"""个股资金流向 daily API：按代码位数分流 A/港股表。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend_api.stock import stock_fund_flow as mod


class _Mappings:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


@pytest.mark.asyncio
async def test_daily_inflow_outflow_hk_uses_hk_tables(monkeypatch):
    calls = []

    class _Db:
        def execute(self, sql, params=None):
            sql_s = str(sql)
            calls.append((sql_s, params))
            if "stock_fund_flow_daily_hk" in sql_s:
                return _Mappings(
                    [
                        {
                            "code": "00700",
                            "trade_date": "2026-09-08",
                            "name": "腾讯控股",
                            "inflow_amount": 1e8,
                            "outflow_amount": 4e7,
                            "net_amount": 6e7,
                            "turnover_amount": 2e8,
                            "change_percent": 1.2,
                            "turnover_rate": None,
                            "current_price": 400.0,
                            "source": "file",
                            "updated_at": None,
                        }
                    ]
                )
            # historical_quotes_hk 先返回空，触发回退日表
            return _Mappings([])

    result = await mod.get_daily_inflow_outflow(code="HK0700", days=20, db=_Db())
    assert result["success"] is True
    assert result["data"]["market"] == "HK"
    assert result["data"]["code"] == "00700"
    assert result["data"]["series_source"] == "stock_fund_flow_daily_hk"
    assert result["data"]["series"][0]["net_amount"] == 6e7
    assert any("stock_fund_flow_daily_hk" in s for s, _ in calls)
    assert any("historical_quotes_hk" in s for s, _ in calls)


@pytest.mark.asyncio
async def test_daily_inflow_outflow_cn_keeps_cn_tables(monkeypatch):
    class _Db:
        def execute(self, sql, params=None):
            sql_s = str(sql)
            if "historical_quotes" in sql_s and "historical_quotes_hk" not in sql_s:
                return _Mappings(
                    [
                        {
                            "code": "600519",
                            "trade_date": "2026-09-08",
                            "name": "贵州茅台",
                            "inflow_amount": 2e8,
                            "outflow_amount": 1e8,
                            "net_amount": 1e8,
                            "turnover_amount": 5e8,
                            "change_percent": 0.5,
                            "turnover_rate": 0.2,
                            "current_price": 1700.0,
                        }
                    ]
                )
            return _Mappings([])

    result = await mod.get_daily_inflow_outflow(code="600519", days=10, db=_Db())
    assert result["success"] is True
    assert result["data"]["market"] == "CN"
    assert result["data"]["series_source"] == "historical_quotes"
    assert len(result["data"]["series"]) == 1
