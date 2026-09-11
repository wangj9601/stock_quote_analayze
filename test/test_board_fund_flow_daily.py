# -*- coding: utf-8 -*-
"""板块资金流：金额解析、THS 映射、GMS 弱判定、API 形状。"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


def test_yi_to_yuan_and_ths_rows():
    from backend_core.data_collectors.akshare.board_fund_flow_daily import (
        BoardFundFlowDailyCollector,
        _yi_to_yuan,
    )

    assert _yi_to_yuan(1.5) == 1.5e8
    assert _yi_to_yuan("2.0亿") == 2.0e8
    assert _yi_to_yuan(None) is None

    coll = BoardFundFlowDailyCollector(trade_date="2026-03-20")
    df = pd.DataFrame(
        [
            {
                "行业": "元件",
                "行业-涨跌幅": "1.2%",
                "流入资金": 10.0,
                "流出资金": 8.0,
                "净额": 2.0,
            },
            {
                "行业": "未知板",
                "行业-涨跌幅": "-0.5",
                "流入资金": 1.0,
                "流出资金": 2.0,
                "净额": -1.0,
            },
        ]
    )
    rows, unmatched = coll.ths_fund_flow_to_rows(
        df, board_kind="industry", name_map={"元件": "881271"}
    )
    assert unmatched == 1
    assert len(rows) == 1
    assert rows[0]["board_code"] == "881271"
    assert rows[0]["main_net_inflow"] == 2.0e8
    assert rows[0]["inflow_amount"] == 1.0e9
    assert rows[0]["source"] == "ths_fund_flow"
    assert rows[0]["trade_date"] == date(2026, 3, 20)


def test_normalize_ths_keeps_net_inflow():
    from backend_core.data_collectors.akshare.industry_board_normalize import (
        normalize_ths_industry_df,
    )

    df = pd.DataFrame(
        [
            {
                "板块": "银行",
                "涨跌幅": "0.5",
                "总成交量": 100.0,
                "总成交额": 50.0,
                "净流入": 1.2,
                "上涨家数": 10,
                "下跌家数": 5,
                "领涨股": "工行",
                "领涨股-涨跌幅": "1.0",
            }
        ]
    )
    out = normalize_ths_industry_df(df)
    assert "净流入" in out.columns
    assert float(out.iloc[0]["净流入"]) == 1.2
    assert out.iloc[0]["最新价"] is None or pd.isna(out.iloc[0]["最新价"])


def test_realtime_fetch_prefers_ths():
    from backend_core.data_collectors.akshare.realtime_stock_industry_board_ak import (
        RealtimeStockIndustryBoardCollector,
    )

    coll = RealtimeStockIndustryBoardCollector.__new__(RealtimeStockIndustryBoardCollector)
    coll._last_fetch_source = "em"
    ths_df = pd.DataFrame([{"板块": "银行", "涨跌幅": "1", "总成交量": 1, "总成交额": 1, "净流入": 0.1}])

    with patch(
        "backend_core.data_collectors.akshare.realtime_stock_industry_board_ak.ak"
    ) as ak_mock:
        ak_mock.stock_board_industry_summary_ths.return_value = ths_df
        out = coll.fetch_data()
        ak_mock.stock_board_industry_summary_ths.assert_called_once()
        ak_mock.stock_board_industry_name_em.assert_not_called()
    assert coll._last_fetch_source == "ths"
    assert "板块名称" in out.columns or "板块" in ths_df.columns


def test_gms_fund_flow_weak_or():
    from backend_core.strategies.gms.board_resonance import evaluate_board_environment

    env = evaluate_board_environment(
        sector_slope_v=0.002,
        board_change_percent=1.0,
        enable_board_fund_flow=True,
        main_net_inflow=-1e8,
        fund_flow_weak_threshold=0.0,
    )
    assert env["board_weak"] is True
    assert env["board_weak_reason"] == "board_fund_flow_negative"

    env2 = evaluate_board_environment(
        sector_slope_v=0.002,
        board_change_percent=1.0,
        enable_board_fund_flow=False,
        main_net_inflow=-1e8,
        fund_flow_weak_threshold=0.0,
    )
    assert env2["board_weak"] is False


@pytest.mark.asyncio
async def test_board_fund_flow_daily_api_shape():
    from backend_api.stock import board_fund_flow as mod

    class _Row(dict):
        def __getitem__(self, k):
            return dict.get(self, k)

    mock_db = MagicMock()
    mock_db.execute.return_value.mappings.return_value.all.return_value = [
        _Row(
            trade_date=date(2026, 3, 20),
            board_name="元件",
            change_percent=1.2,
            inflow_amount=1e9,
            outflow_amount=8e8,
            main_net_inflow=2e8,
            main_net_inflow_pct=None,
            super_large_net_inflow=None,
            large_net_inflow=None,
            mid_net_inflow=None,
            small_net_inflow=None,
            source="ths_fund_flow",
            em_board_code=None,
        )
    ]
    result = await mod.get_board_fund_flow_daily(
        board_code="881271",
        board_kind="industry",
        board_code_source="tonghuashun",
        days=20,
        db=mock_db,
    )
    assert result["success"] is True
    assert result["data"]["series_source"] == "board_fund_flow_daily"
    assert len(result["data"]["series"]) == 1
    assert result["data"]["latest"]["main_net_inflow"] == 2e8
