"""个股资金流向日/周/月排名接口单测。"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from backend_api.stock import stock_fund_flow as mod


def test_pick_rank_sides_takes_weak_and_strong():
    rows = [{"code": str(i), "net_amount": float(i)} for i in range(10)]
    out = mod._pick_rank_sides(rows, sides=2)
    codes = [r["code"] for r in out]
    assert codes == ["0", "1", "8", "9"]
    assert [r["net_amount"] for r in out] == [0.0, 1.0, 8.0, 9.0]


def test_pick_rank_sides_small_universe_returns_all_sorted():
    rows = [
        {"code": "b", "net_amount": 3},
        {"code": "a", "net_amount": -1},
        {"code": "c", "net_amount": 1},
    ]
    out = mod._pick_rank_sides(rows, sides=40)
    assert [r["code"] for r in out] == ["a", "c", "b"]


def test_get_stock_fund_flow_rank_day():
    db = MagicMock()

    def execute(sql, params=None):
        sql_s = str(sql)
        result = MagicMock()
        if "MAX(trade_date)" in sql_s:
            result.scalar.return_value = "2026-09-11"
            return result
        if "DISTINCT trade_date" in sql_s:
            result.fetchall.return_value = [("2026-09-11",)]
            return result
        result.mappings.return_value.all.return_value = [
            {
                "code": "600519",
                "name": "贵州茅台",
                "net_amount": 1e8,
                "inflow_amount": 2e8,
                "outflow_amount": 1e8,
                "turnover_amount": 5e8,
                "days_count": 1,
            },
            {
                "code": "000001",
                "name": "平安银行",
                "net_amount": -5e7,
                "inflow_amount": 1e7,
                "outflow_amount": 6e7,
                "turnover_amount": 2e8,
                "days_count": 1,
            },
        ]
        return result

    db.execute.side_effect = execute

    result = asyncio.get_event_loop().run_until_complete(
        mod.get_stock_fund_flow_rank(
            period="day",
            sides=40,
            trade_date=None,
            db=db,
        )
    )
    assert result["success"] is True
    data = result["data"]
    assert data["period"] == "day"
    assert data["period_label"] == "日"
    assert data["end_date"] == "2026-09-11"
    assert data["count"] == 2
    assert data["items"][0]["code"] == "000001"
    assert data["items"][-1]["code"] == "600519"


def test_get_stock_fund_flow_rank_invalid_period():
    result = asyncio.get_event_loop().run_until_complete(
        mod.get_stock_fund_flow_rank(
            period="year",
            sides=40,
            trade_date=None,
            db=MagicMock(),
        )
    )
    assert result.status_code == 400
