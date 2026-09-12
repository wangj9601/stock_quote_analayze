"""板块资金流向日/周/月排名接口单测。"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from backend_api.stock import board_fund_flow as mod


def test_get_board_fund_flow_rank_week():
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
                ("2026-09-09",),
                ("2026-09-08",),
                ("2026-09-05",),
            ]
            return result
        result.mappings.return_value.all.return_value = [
            {
                "board_kind": "industry",
                "board_code": "881271",
                "board_name": "元件",
                "main_net_inflow": -1e8,
                "inflow_amount": 2e8,
                "outflow_amount": 3e8,
                "days_count": 5,
            },
            {
                "board_kind": "industry",
                "board_code": "881101",
                "board_name": "银行",
                "main_net_inflow": 2e8,
                "inflow_amount": 5e8,
                "outflow_amount": 3e8,
                "days_count": 5,
            },
        ]
        return result

    db.execute.side_effect = execute

    result = asyncio.get_event_loop().run_until_complete(
        mod.get_board_fund_flow_rank(
            period="week",
            board_kind="industry",
            board_code_source="tonghuashun",
            trade_date=None,
            db=db,
        )
    )
    assert result["success"] is True
    data = result["data"]
    assert data["period"] == "week"
    assert data["period_label"] == "周"
    assert data["trade_days"] == 5
    assert data["start_date"] == "2026-09-05"
    assert data["end_date"] == "2026-09-11"
    assert data["count"] == 2
    assert data["items"][0]["board_code"] == "881271"
    assert data["items"][0]["main_net_inflow"] == -1e8
    assert data["items"][1]["board_code"] == "881101"


def test_get_board_fund_flow_rank_invalid_period():
    result = asyncio.get_event_loop().run_until_complete(
        mod.get_board_fund_flow_rank(
            period="year",
            board_kind="industry",
            board_code_source="tonghuashun",
            trade_date=None,
            db=MagicMock(),
        )
    )
    assert result.status_code == 400
