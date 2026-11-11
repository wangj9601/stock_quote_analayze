"""个股资金流向趋势序列接口单测。"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from backend_api.stock import stock_fund_flow as mod


def test_get_stock_fund_flow_trend_series_day():
    db = MagicMock()

    def execute(sql, params=None):
        sql_s = str(sql)
        result = MagicMock()
        if "MAX(trade_date)" in sql_s:
            result.scalar.return_value = "2026-09-11"
            return result
        if "DISTINCT trade_date" in sql_s:
            result.fetchall.return_value = [
                ("2026-09-11",),
                ("2026-09-10",),
            ]
            return result
        if "GROUP BY trade_date" in sql_s:
            result.mappings.return_value.all.return_value = [
                {
                    "trade_date": "2026-09-10",
                    "net_amount": 1e8,
                    "inflow_amount": 3e8,
                    "outflow_amount": 2e8,
                },
                {
                    "trade_date": "2026-09-11",
                    "net_amount": 2e8,
                    "inflow_amount": 4e8,
                    "outflow_amount": 2e8,
                },
            ]
            return result
        if "GROUP BY code" in sql_s:
            result.mappings.return_value.all.return_value = [
                {"code": "600519", "name": "贵州茅台", "window_net": 2e8},
                {"code": "000001", "name": "平安银行", "window_net": 1e8},
            ]
            return result
        result.mappings.return_value.all.return_value = [
            {"code": "600519", "trade_date": "2026-09-10", "net_amount": 5e7},
            {"code": "600519", "trade_date": "2026-09-11", "net_amount": 1.5e8},
            {"code": "000001", "trade_date": "2026-09-11", "net_amount": 1e8},
        ]
        return result

    db.execute.side_effect = execute

    result = asyncio.get_event_loop().run_until_complete(
        mod.get_stock_fund_flow_trend_series(
            period="day",
            trade_date=None,
            top_n=5,
            db=db,
        )
    )
    assert result["success"] is True
    data = result["data"]
    assert data["trend_days"] == 20
    assert data["dates"] == ["2026-09-10", "2026-09-11"]
    assert data["aggregate"]["net_amount"] == [1e8, 2e8]
    assert data["top_entities"][0]["code"] == "600519"
    assert data["top_entities"][0]["net_amount"] == [5e7, 1.5e8]
    assert data["top_entities"][1]["net_amount"] == [None, 1e8]


def test_get_stock_fund_flow_trend_series_invalid_period():
    result = asyncio.get_event_loop().run_until_complete(
        mod.get_stock_fund_flow_trend_series(
            period="year",
            trade_date=None,
            top_n=5,
            db=MagicMock(),
        )
    )
    assert result.status_code == 400
