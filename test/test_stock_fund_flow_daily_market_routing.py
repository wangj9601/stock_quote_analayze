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


@pytest.mark.asyncio
async def test_daily_merges_newer_day_from_fund_flow_daily():
    """行情表滞后时，日表新交易日仍应出现在个股详情资金流。"""

    class _Db:
        def execute(self, sql, params=None):
            sql_s = str(sql)
            if "stock_fund_flow_daily" in sql_s and "stock_fund_flow_daily_hk" not in sql_s:
                return _Mappings(
                    [
                        {
                            "code": "605289",
                            "trade_date": "2026-09-10",
                            "name": "罗曼股份",
                            "inflow_amount": 1.04e8,
                            "outflow_amount": 9.05784e7,
                            "net_amount": 1.33011e7,
                            "turnover_amount": 1.94e8,
                            "change_percent": -1.61,
                            "turnover_rate": 1.29,
                            "current_price": 98.52,
                            "source": "ths",
                            "updated_at": None,
                        }
                    ]
                )
            if "historical_quotes" in sql_s and "historical_quotes_hk" not in sql_s:
                return _Mappings(
                    [
                        {
                            "code": "605289",
                            "trade_date": "2026-09-09",
                            "name": "罗曼股份",
                            "inflow_amount": 1.44e8,
                            "outflow_amount": 1.43e8,
                            "net_amount": 1e6,
                            "turnover_amount": None,
                            "change_percent": None,
                            "turnover_rate": None,
                            "current_price": None,
                        },
                        {
                            "code": "605289",
                            "trade_date": "2026-09-08",
                            "name": "罗曼股份",
                            "inflow_amount": 1.74e8,
                            "outflow_amount": 2.27e8,
                            "net_amount": -5.4e7,
                            "turnover_amount": None,
                            "change_percent": None,
                            "turnover_rate": None,
                            "current_price": None,
                        },
                    ]
                )
            return _Mappings([])

    result = await mod.get_daily_inflow_outflow(code="605289", days=2, db=_Db())
    assert result["success"] is True
    series = result["data"]["series"]
    assert [r["trade_date"] for r in series] == ["2026-09-09", "2026-09-10"]
    assert series[-1]["net_amount"] == 1.33011e7
    assert "stock_fund_flow_daily" in result["data"]["series_source"]
