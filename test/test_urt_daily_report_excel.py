# -*- coding: utf-8 -*-
"""URT 日报 Excel 列与收录规则单测。"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pandas as pd

from backend_api.services.report_service import ReportService


URT_EXCEL_COLUMNS = [
    "股票代码",
    "股票名称",
    "信号日",
    "收盘",
    "MA20",
    "4日阳",
    "5日阳",
    "10日阳",
    "15日阳",
    "20日阳",
    "多头",
    "量能倍数",
    "量比",
    "换手%",
    "支撑",
    "阻力",
    "结构盈亏比",
    "风险",
    "得分",
    "是否买点",
    "买点建议",
]


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
            "yang_count_10": 7,
            "yang_count_15": 9,
            "yang_count_20": 12,
            "ma_bull_ok": True,
            "volume_multiple": 8.91,
            "volume_ratio": 2.18,
            "turnover_rate": 9.19,
            "nearest_support": 7.80,
            "nearest_resistance": 8.90,
            "structure_rr": 2.35,
            "risk_tags": [{"label": "结构盈亏比偏低"}, {"label": "近期涨幅偏大"}],
            "score": 80.0,
            "buy_signal": True,
            "trade_advice": {"action": "回踩承接", "summary": "贴近支撑可关注"},
        },
        report_date="2026-07-27",
        code_to_name={},
    )
    assert list(row.keys()) == URT_EXCEL_COLUMNS
    assert row["股票代码"].endswith("000011")
    assert row["4日阳"] == 3
    assert row["10日阳"] == 7
    assert row["多头"] == "是"
    assert row["支撑"] == 7.8
    assert row["阻力"] == 8.9
    assert row["结构盈亏比"] == 2.35
    assert "结构盈亏比偏低" in row["风险"]
    assert row["是否买点"] == "是"
    assert "回踩承接" in row["买点建议"]


def test_urt_report_excel_row_reads_nested_score_detail():
    row = ReportService._urt_report_excel_row(
        {
            "code": "000001",
            "name": "平安银行",
            "signal_date": "2026-08-19",
            "close": 10.0,
            "ma20": 9.5,
            "yang_count_4": 3,
            "yang_count_5": 4,
            "volume_multiple": 3.2,
            "score": 72.0,
            "buy_signal": False,
            "score_detail": {
                "structure": {
                    "nearest_support": 9.2,
                    "nearest_resistance": 10.8,
                    "rr": 1.8,
                },
                "risk_tags": [{"label": "上行空间不足"}],
                "trade_advice": {"action": "仅观察", "summary": "未达正式买点"},
            },
        },
        report_date="2026-08-19",
        code_to_name={},
    )
    assert row["支撑"] == 9.2
    assert row["阻力"] == 10.8
    assert row["结构盈亏比"] == 1.8
    assert row["风险"] == "上行空间不足"
    assert row["是否买点"] == "否"
    assert "仅观察" in row["买点建议"]


def test_urt_report_field_legend_covers_excel_columns():
    """字段说明须覆盖信号列表全部列，并含收录规则说明。"""
    legend = ReportService._urt_report_field_legend_rows()
    assert legend
    assert list(legend[0].keys()) == ["字段名", "含义", "计算/取值规则"]
    names = [r["字段名"] for r in legend]
    assert "（列表收录）" in names
    for col in URT_EXCEL_COLUMNS:
        assert col in names
    text = "\n".join(f"{r['含义']}|{r['计算/取值规则']}" for r in legend)
    assert "close>open" in text
    assert "volume_lookback" in text
    assert "min_score" in text
    assert "结构硬闸" in text or "过热硬闸" in text
    assert "3.0" in text
    assert "4日阳≥3" in text or "4日≥3" in text


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
                "yang_count_10": 7,
                "yang_count_15": 9,
                "yang_count_20": 12,
                "ma_bull_ok": True,
                "volume_multiple": 8.91,
                "volume_ratio": 2.18,
                "turnover_rate": 9.19,
                "nearest_support": 7.8,
                "nearest_resistance": 8.9,
                "structure_rr": 2.5,
                "risk_tags": [],
                "score": 80.0,
                "buy_signal": True,
                "trade_advice": {"action": "现价附近可跟", "summary": "正式买点"},
            },
            {
                "code": "000533",
                "name": "顺呐股份",
                "signal_date": "2026-07-27",
                "close": 10.51,
                "ma20": 8.80,
                "yang_count_4": 3,
                "yang_count_5": 4,
                "yang_count_10": 6,
                "yang_count_15": 8,
                "yang_count_20": 10,
                "ma_bull_ok": True,
                "volume_multiple": 3.05,
                "volume_ratio": 7.87,
                "turnover_rate": 9.51,
                "score": 78.2,
                "buy_signal": False,  # 无买点，但满足 5日≥4阳，应收录
                "rule_a_ok": True,
                "rule_b_ok": True,
                "score_detail": {
                    "structure": {"nearest_support": 9.9, "nearest_resistance": 11.2, "rr": 1.2},
                    "risk_tags": [{"label": "结构盈亏比偏低"}],
                },
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
    assert list(df.columns) == URT_EXCEL_COLUMNS
    codes = [str(c).replace("\u2060", "").zfill(6) for c in df["股票代码"].tolist()]
    assert codes == ["000011", "000533"]
    assert df["是否买点"].tolist() == ["是", "否"]
    assert float(df.loc[0, "支撑"]) == 7.8
    assert "结构盈亏比偏低" in str(df.loc[1, "风险"])

    legend = pd.read_excel(result.file_path, sheet_name="字段说明")
    assert list(legend.columns) == ["字段名", "含义", "计算/取值规则"]
    legend_names = legend["字段名"].astype(str).tolist()
    for col in ("是否买点", "量能倍数", "得分", "支撑", "阻力", "结构盈亏比", "风险", "买点建议"):
        assert col in legend_names
    assert any("收录" in n for n in legend_names)


def test_generate_urt_report_excludes_codes_outside_watchlist(tmp_path):
    """选股接口若误返回非自选代码，日报不得写入 Excel。"""
    db = MagicMock()
    svc = ReportService(db)
    svc.report_dir = str(tmp_path)
    svc.get_user_watchlist = MagicMock(
        return_value=[
            {"stock_code": "000011", "stock_name": "深物业A", "market": "CN"},
        ]
    )
    payload = {
        "success": True,
        "search_date": "2026-07-31",
        "data": [
            {
                "code": "000011",
                "name": "深物业A",
                "signal_date": "2026-07-31",
                "close": 8.15,
                "ma20": 6.74,
                "yang_count_4": 3,
                "yang_count_5": 3,
                "volume_multiple": 3.0,
                "volume_ratio": 2.0,
                "turnover_rate": 5.0,
                "score": 80.0,
                "buy_signal": True,
            },
            {
                "code": "000981",
                "name": "山子高科",
                "signal_date": "2026-07-31",
                "close": 2.66,
                "ma20": 2.57,
                "yang_count_4": 4,
                "yang_count_5": 5,
                "volume_multiple": 1.35,
                "volume_ratio": 1.31,
                "turnover_rate": 3.27,
                "score": 66.2,
                "buy_signal": False,
                "rule_a_ok": True,
                "rule_b_ok": True,
            },
        ],
    }
    with patch("backend_core.strategies.urt.URTFrontendInterface.screen", return_value=payload):
        result = svc._generate_urt_report_for_user(9)
    assert result.success is True
    df = pd.read_excel(result.file_path, sheet_name="URT策略信号列表")
    codes = [str(c).replace("\u2060", "").zfill(6) for c in df["股票代码"].tolist()]
    assert codes == ["000011"]
    assert "000981" not in codes
    # 新文件名含生成时刻，避免与历史同日文件混淆
    assert "urt_9_20260731_" in os.path.basename(result.file_path)
    assert result.file_path.endswith(".xlsx")


def test_generate_urt_report_passes_config_stock_codes_subset(tmp_path):
    """推送任务配置的 stock_codes 子集应传给 get_user_watchlist。"""
    db = MagicMock()
    svc = ReportService(db)
    svc.report_dir = str(tmp_path)
    svc.get_user_watchlist = MagicMock(
        return_value=[
            {"stock_code": "000011", "stock_name": "深物业A", "market": "CN"},
        ]
    )
    payload = {
        "success": True,
        "search_date": "2026-07-31",
        "data": [
            {
                "code": "000011",
                "name": "深物业A",
                "signal_date": "2026-07-31",
                "close": 8.15,
                "ma20": 6.74,
                "yang_count_4": 3,
                "yang_count_5": 3,
                "volume_multiple": 3.0,
                "volume_ratio": 2.0,
                "turnover_rate": 5.0,
                "score": 80.0,
                "buy_signal": True,
            },
        ],
    }
    with patch("backend_core.strategies.urt.URTFrontendInterface.screen", return_value=payload):
        result = svc._generate_urt_report_for_user(9, stock_codes=["000011"])
    assert result.success is True
    svc.get_user_watchlist.assert_called_with(9, ["000011"])


def test_urt_screen_watchlist_scope_without_codes_returns_empty():
    """scope=watchlist 且未传 stock_codes 时不得回落全市场。"""
    from backend_core.strategies.urt.frontend_interface import URTFrontendInterface

    db = MagicMock()
    with patch.object(URTFrontendInterface, "_resolve_config_id", return_value=1), patch(
        "backend_core.strategies.urt.frontend_interface.URTConfigManager"
    ) as cm_cls, patch(
        "backend_core.strategies.urt.frontend_interface.URTDataLoader"
    ) as loader_cls:
        cm = cm_cls.return_value
        cm.get_config.return_value = {"min_score": 70}
        cm.merge_overrides.side_effect = lambda base, **kw: dict(base)
        loader_cls.resolve_effective_history_end_date.return_value = "2026-07-31"
        out = URTFrontendInterface.screen(db, scope="watchlist", stock_codes=None)
    assert out["data"] == []
    assert out["total"] == 0
    loader_cls.return_value.list_a_share_candidates.assert_not_called()


def test_generate_urt_report_excludes_hk_00981_mapped_to_a_share(tmp_path):
    """港股 00981 不得经 zfill(6) 变成 A 股 000981 写入日报。"""
    db = MagicMock()
    svc = ReportService(db)
    svc.report_dir = str(tmp_path)
    svc.get_user_watchlist = MagicMock(
        return_value=[
            {"stock_code": "000011", "stock_name": "深物业A", "market": "CN"},
            {"stock_code": "00981", "stock_name": "山子高科", "market": "HK"},
            {"stock_code": "00100", "stock_name": "MINIMAX-W", "market": "HK"},
        ]
    )
    payload = {
        "success": True,
        "search_date": "2026-07-31",
        "data": [
            {
                "code": "000011",
                "name": "深物业A",
                "signal_date": "2026-07-31",
                "close": 8.15,
                "ma20": 6.74,
                "yang_count_4": 3,
                "yang_count_5": 3,
                "volume_multiple": 3.0,
                "volume_ratio": 2.0,
                "turnover_rate": 5.0,
                "score": 80.0,
                "buy_signal": True,
            },
            {
                "code": "000981",
                "name": "山子高科",
                "signal_date": "2026-07-31",
                "close": 2.66,
                "ma20": 2.57,
                "yang_count_4": 4,
                "yang_count_5": 5,
                "volume_multiple": 1.35,
                "volume_ratio": 1.31,
                "turnover_rate": 3.27,
                "score": 66.2,
                "buy_signal": False,
                "rule_a_ok": True,
                "rule_b_ok": True,
            },
            {
                "code": "000100",
                "name": "TCL科技",
                "signal_date": "2026-07-31",
                "close": 4.0,
                "ma20": 3.9,
                "yang_count_4": 3,
                "yang_count_5": 4,
                "volume_multiple": 2.0,
                "volume_ratio": 2.0,
                "turnover_rate": 3.0,
                "score": 70.0,
                "buy_signal": True,
            },
        ],
    }
    with patch(
        "backend_core.strategies.urt.URTFrontendInterface.screen", return_value=payload
    ) as screen_mock:
        result = svc._generate_urt_report_for_user(9)
    assert result.success is True
    # screen 只应收到真正的 A 股池
    assert screen_mock.call_args.kwargs["stock_codes"] == ["000011"]
    df = pd.read_excel(result.file_path, sheet_name="URT策略信号列表")
    codes = [str(c).replace("\u2060", "").zfill(6) for c in df["股票代码"].tolist()]
    assert codes == ["000011"]
    assert "000981" not in codes
    assert "000100" not in codes


def test_urt_data_loader_rejects_five_digit_hk_codes():
    """list_a_share_candidates 不得把 00981 规范化为 000981。"""
    from backend_core.strategies.urt.data_loader import URTDataLoader

    db = MagicMock()
    loader = URTDataLoader(db, market="CN")
    out = loader.list_a_share_candidates(stock_codes=["00981", "00100"])
    assert out == []
    # 清洗后为空应提前返回，不执行 qry.all()
    order_by_mock = (
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.order_by
    )
    assert order_by_mock.return_value.all.call_count == 0
