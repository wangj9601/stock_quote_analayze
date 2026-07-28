# -*- coding: utf-8 -*-
"""URT 日报 Excel 列与收录规则单测。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from backend_api.services.report_service import ReportService


def test_urt_row_meets_report_filter_buy_or_yang():
    assert ReportService._urt_row_meets_report_filter({"buy_signal": True, "yang_count_4": 0, "yang_count_5": 0})
    assert ReportService._urt_row_meets_report_filter({"buy_signal": False, "yang_count_4": 3, "yang_count_5": 1})
    assert ReportService._urt_row_meets_report_filter({"buy_signal": False, "yang_count_4": 2, "yang_count_5": 4})
    assert not ReportService._urt_row_meets_report_filter({"buy_signal": False, "yang_count_4": 2, "yang_count_5": 3})
    assert ReportService._urt_row_meets_report_filter({"buy_signal": False, "rule_a_ok": True, "rule_b_ok": False})
    assert not ReportService._urt_row_meets_report_filter({"buy_signal": False, "rule_a_ok": False, "rule_b_ok": False})


def test_urt_report_excel_row_columns_match_screening():
    row = ReportService._urt_report_excel_row(
        {
            "code": "11",
            "name": "深物业A",
            "signal_date": "2026-07-27",
            "close": 8.15,
            "ma20": 6.74,
            "yang_count_4": 3,
            "yang_count_5": 3,
            "volume_multiple": 8.91,
            "volume_ratio": 2.18,
            "turnover_rate": 9.19,
            "score": 80.0,
            "buy_signal": True,
        },
        report_date="2026-07-27",
        code_to_name={},
    )
    assert list(row.keys()) == [
        "股票代码",
        "股票名称",
        "信号日",
        "收盘",
        "MA20",
        "4日阳",
        "5日阳",
        "量能倍数",
        "量比",
        "换手%",
        "得分",
        "是否买点",
    ]
    assert row["股票代码"].endswith("000011")
    assert row["4日阳"] == 3
    assert row["是否买点"] == "是"


def test_generate_urt_report_includes_non_buy_yang_watchlist(tmp_path):
    db = MagicMock()
    svc = ReportService(db)
    svc.report_dir = str(tmp_path)
    svc.get_user_watchlist = MagicMock(
        return_value=[
            {"stock_code": "000011", "stock_name": "深物业A", "market": "CN"},
            {"stock_code": "000533", "stock_name": "顺呐股份", "market": "CN"},
            {"stock_code": "000001", "stock_name": "平安银行", "market": "CN"},
        ]
    )

    payload = {
        "success": True,
        "search_date": "2026-07-27",
        "data": [
            {
                "code": "000011",
                "name": "深物业A",
                "signal_date": "2026-07-27",
                "close": 8.15,
                "ma20": 6.74,
                "yang_count_4": 3,
                "yang_count_5": 3,
                "volume_multiple": 8.91,
                "volume_ratio": 2.18,
                "turnover_rate": 9.19,
                "score": 80.0,
                "buy_signal": True,
            },
            {
                "code": "000533",
                "name": "顺呐股份",
                "signal_date": "2026-07-27",
                "close": 10.51,
                "ma20": 8.80,
                "yang_count_4": 3,
                "yang_count_5": 4,
                "volume_multiple": 3.05,
                "volume_ratio": 7.87,
                "turnover_rate": 9.51,
                "score": 78.2,
                "buy_signal": False,  # 无买点，但满足 5日≥4阳，应收录
                "rule_a_ok": True,
                "rule_b_ok": True,
            },
            {
                "code": "000001",
                "name": "平安银行",
                "signal_date": "2026-07-27",
                "close": 10.0,
                "ma20": 10.1,
                "yang_count_4": 2,
                "yang_count_5": 3,
                "volume_multiple": 1.0,
                "volume_ratio": 1.0,
                "turnover_rate": 1.0,
                "score": 40.0,
                "buy_signal": False,  # 4日<3 且 5日<4，不收录
                "rule_a_ok": False,
                "rule_b_ok": False,
            },
        ],
    }

    with patch("backend_core.strategies.urt.URTFrontendInterface.screen", return_value=payload):
        result = svc._generate_urt_report_for_user(7)

    assert result.success is True
    assert result.file_path
    assert result.report_info and result.report_info.stock_count == 2
    df = pd.read_excel(result.file_path, sheet_name="URT策略信号列表")
    assert list(df.columns)[:11] == [
        "股票代码",
        "股票名称",
        "信号日",
        "收盘",
        "MA20",
        "4日阳",
        "5日阳",
        "量能倍数",
        "量比",
        "换手%",
        "得分",
    ]
    assert "是否买点" in df.columns
    codes = [str(c).replace("\u2060", "").zfill(6) for c in df["股票代码"].tolist()]
    assert codes == ["000011", "000533"]
    assert df["是否买点"].tolist() == ["是", "否"]
