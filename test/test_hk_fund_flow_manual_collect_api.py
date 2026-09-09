"""港股资金流向手动采集 API 单测（mock 采集器）。"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from backend_api.stock import data_collection_api as api


@pytest.mark.asyncio
async def test_collect_hk_fund_flow_manual_with_trade_date(monkeypatch):
    called = {}

    def _fake_collect(trade_date=None, data_dir=None):
        called["trade_date"] = trade_date
        return {
            "success": True,
            "trade_date": trade_date,
            "written": 10,
            "historical_updated": 3,
            "realtime_updated": 5,
        }

    monkeypatch.setattr(
        "backend_core.data_collectors.akshare.hk_fund_flow_from_file.collect_hk_fund_flow_from_file",
        _fake_collect,
    )

    db = MagicMock()
    result = await api.collect_hk_fund_flow_manual(trade_date="2026-09-08", db=db)
    assert result["success"] is True
    assert called["trade_date"] == "2026-09-08"
    assert result["data"]["written"] == 10


@pytest.mark.asyncio
async def test_collect_hk_fund_flow_manual_missing_file(monkeypatch):
    monkeypatch.setattr(
        "backend_core.data_collectors.akshare.hk_fund_flow_from_file.collect_hk_fund_flow_from_file",
        lambda trade_date=None, data_dir=None: {
            "success": False,
            "error": "未找到港股资金流向文件",
        },
    )
    db = MagicMock()
    with pytest.raises(HTTPException) as ei:
        await api.collect_hk_fund_flow_manual(trade_date="2026-09-08", db=db)
    assert ei.value.status_code == 400


@pytest.mark.asyncio
async def test_collect_hk_fund_flow_manual_holiday_requires_date(monkeypatch):
    monkeypatch.setattr(
        "backend_api.utils.trading_calendar_utils.is_market_session_closed",
        lambda db, market, d: True,
    )
    monkeypatch.setattr(api, "datetime", api.datetime)  # keep
    # force "today" path by omitting trade_date
    db = MagicMock()
    with pytest.raises(HTTPException) as ei:
        await api.collect_hk_fund_flow_manual(trade_date=None, db=db)
    assert ei.value.status_code == 400
    assert "休市" in str(ei.value.detail)
