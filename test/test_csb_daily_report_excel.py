# -*- coding: utf-8 -*-
"""CSB 通道突破日报：只收录自选 A 股买点。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from backend_api.services.report_service import ReportService


def test_csb_report_writes_buy_rows_and_skips_non_buy(tmp_path):
    db = MagicMock()
    svc = ReportService(db)
    svc.report_dir = str(tmp_path)
    svc.get_user_watchlist = MagicMock(
        return_value=[
            {"stock_code": "002709", "stock_name": "天赐材料", "market": "CN"},
            {"stock_code": "00981", "stock_name": "中芯国际", "market": "HK"},
        ]
    )
    payload = {
        "success": True,
        "search_date": "2026-10-17",
        "data": [
            {
                "code": "002709",
                "name": "天赐材料",
                "signal_date": "2026-10-17",
                "signal_type": "BREAKOUT",
                "close": 28.6,
                "score": 81.2,
                "channel_lower": 24.1,
                "channel_upper": 27.4,
                "squeeze_days": 8,
                "squeeze_pct": 0.06,
                "touch_count": 3,
                "vol_expand_mult": 1.8,
                "vol_ratio_5_20": 1.4,
                "entry_low": 26.2,
                "resistance": 29.0,
                "buy_signal": True,
            },
            {
                "code": "002709",
                "signal_type": "SCANNED",
                "buy_signal": False,
                "score": 0,
            },
        ],
    }
    with patch(
        "backend_core.strategies.csb.frontend_interface.CSBFrontendInterface.screen",
        return_value=payload,
    ) as screen:
        result = svc._generate_csb_report_for_user(3)

    assert result.success
    assert result.report_info.has_data
    assert result.report_info.stock_count == 1
    assert result.report_info.report_type == "csb_daily"
    screen.assert_called_once()
    kwargs = screen.call_args.kwargs
    assert kwargs["stock_codes"] == ["002709"]
    assert kwargs["prefer_cache"] is True
    assert kwargs["require_entry"] is True
    df = pd.read_excel(result.file_path, sheet_name="CSB通道突破信号")
    assert len(df) == 1
    assert str(df.iloc[0]["股票代码"]).endswith("002709")
    assert df.iloc[0]["是否买点"] == "是"
    assert df.iloc[0]["信号类型"] == "BREAKOUT"


def test_csb_report_empty_when_no_buy(tmp_path):
    db = MagicMock()
    svc = ReportService(db)
    svc.report_dir = str(tmp_path)
    svc.get_user_watchlist = MagicMock(
        return_value=[{"stock_code": "000001", "stock_name": "平安银行", "market": "CN"}]
    )
    with patch(
        "backend_core.strategies.csb.frontend_interface.CSBFrontendInterface.screen",
        return_value={"success": True, "search_date": "2026-10-17", "data": [], "message": "当日无买点"},
    ):
        result = svc._generate_csb_report_for_user(3)
    assert result.success
    assert result.file_path is None
    assert result.report_info.has_data is False
    assert "无买点" in (result.error_message or "")
