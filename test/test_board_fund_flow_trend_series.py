"""板块资金流向趋势序列接口单测。"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from backend_api.stock import board_fund_flow as mod


def test_get_board_fund_flow_trend_series_day():
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
            ]
            return result
        if "GROUP BY trade_date" in sql_s:
            result.mappings.return_value.all.return_value = [
                {
                    "trade_date": "2026-09-09",
                    "main_net_inflow": 1e8,
                    "inflow_amount": 3e8,
                    "outflow_amount": 2e8,
                },
                {
                    "trade_date": "2026-09-10",
                    "main_net_inflow": -5e7,
                    "inflow_amount": 2e8,
                    "outflow_amount": 2.5e8,
                },
                {
                    "trade_date": "2026-09-11",
                    "main_net_inflow": 2e8,
                    "inflow_amount": 4e8,
                    "outflow_amount": 2e8,
                },
            ]
            return result
        if "GROUP BY board_code" in sql_s:
            result.mappings.return_value.all.return_value = [
                {
                    "board_code": "881101",
                    "board_name": "银行",
                    "window_net": 3e8,
                },
                {
                    "board_code": "881271",
                    "board_name": "元件",
                    "window_net": 1e8,
                },
            ]
            return result
        # daily series for top entities
        result.mappings.return_value.all.return_value = [
            {
                "board_code": "881101",
                "trade_date": "2026-09-09",
                "main_net_inflow": 1e8,
            },
            {
                "board_code": "881101",
                "trade_date": "2026-09-11",
                "main_net_inflow": 2e8,
            },
            {
                "board_code": "881271",
                "trade_date": "2026-09-10",
                "main_net_inflow": 1e8,
            },
        ]
        return result

    db.execute.side_effect = execute

    result = asyncio.get_event_loop().run_until_complete(
        mod.get_board_fund_flow_trend_series(
            period="day",
            board_kind="industry",
            board_code_source="tonghuashun",
            trade_date=None,
            top_n=5,
            db=db,
        )
    )
    assert result["success"] is True
    data = result["data"]
    assert data["period"] == "day"
    assert data["trend_days"] == 20
    assert data["dates"] == ["2026-09-09", "2026-09-10", "2026-09-11"]
    assert data["aggregate"]["main_net_inflow"] == [1e8, -5e7, 2e8]
    assert len(data["top_entities"]) == 2
    assert data["top_entities"][0]["board_code"] == "881101"
    assert data["top_entities"][0]["main_net_inflow"] == [1e8, None, 2e8]
    assert data["top_entities"][1]["main_net_inflow"] == [None, 1e8, None]


def test_get_board_fund_flow_trend_series_invalid_period():
    result = asyncio.get_event_loop().run_until_complete(
        mod.get_board_fund_flow_trend_series(
            period="year",
            board_kind="industry",
            board_code_source="tonghuashun",
            trade_date=None,
            top_n=5,
            db=MagicMock(),
        )
    )
    assert result.status_code == 400
