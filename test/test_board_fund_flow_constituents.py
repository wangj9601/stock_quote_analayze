"""板块成分股资金流向接口单测。"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from backend_api.stock import board_fund_flow as mod


def test_get_board_constituent_fund_flow_day():
    db = MagicMock()
    call_n = {"i": 0}

    def execute(sql, params=None):
        sql_s = str(sql)
        result = MagicMock()
        call_n["i"] += 1
        if "FROM industry_board_basic_info" in sql_s:
            result.fetchone.return_value = ("银行",)
            return result
        if "FROM board_fund_flow_daily" in sql_s and "board_name" in sql_s:
            result.scalar.return_value = None
            return result
        if "FROM industry_board_constituents" in sql_s and "SELECT 1" in sql_s:
            result.fetchone.return_value = (1,)
            return result
        if "SELECT COUNT(*)" in sql_s:
            result.scalar.return_value = 2
            return result
        if "MAX(trade_date)" in sql_s:
            result.scalar.return_value = "2026-09-11"
            return result
        if "DISTINCT trade_date" in sql_s:
            result.fetchall.return_value = [("2026-09-11",)]
            return result
        if "LEFT JOIN stock_fund_flow_daily" in sql_s:
            result.mappings.return_value.all.return_value = [
                {
                    "code": "601398",
                    "name": "工商银行",
                    "net_amount": -5e7,
                    "inflow_amount": 1e8,
                    "outflow_amount": 1.5e8,
                    "turnover_amount": 3e8,
                    "days_count": 1,
                    "change_percent": -0.5,
                },
                {
                    "code": "600036",
                    "name": "招商银行",
                    "net_amount": 2e8,
                    "inflow_amount": 4e8,
                    "outflow_amount": 2e8,
                    "turnover_amount": 8e8,
                    "days_count": 1,
                    "change_percent": 1.2,
                },
            ]
            return result
        result.fetchone.return_value = None
        result.scalar.return_value = None
        result.fetchall.return_value = []
        result.mappings.return_value.all.return_value = []
        return result

    db.execute.side_effect = execute

    result = asyncio.get_event_loop().run_until_complete(
        mod.get_board_constituent_fund_flow(
            board_code="881101",
            board_kind="industry",
            period="day",
            board_code_source="tonghuashun",
            trade_date=None,
            db=db,
        )
    )
    assert result["success"] is True
    data = result["data"]
    assert data["period"] == "day"
    assert data["board_code"] == "881101"
    assert data["board_name"] == "银行"
    assert data["cons_board_code"] == "881101"
    assert data["member_count"] == 2
    assert data["count"] == 2
    assert data["items"][0]["code"] == "601398"
    assert data["items"][0]["net_amount"] == -5e7
    assert data["items"][1]["code"] == "600036"
    assert data["source"] == "ths"


def test_get_board_constituent_fund_flow_invalid_kind():
    result = asyncio.get_event_loop().run_until_complete(
        mod.get_board_constituent_fund_flow(
            board_code="881101",
            board_kind="sector",
            period="day",
            board_code_source="tonghuashun",
            trade_date=None,
            db=MagicMock(),
        )
    )
    assert result.status_code == 400
