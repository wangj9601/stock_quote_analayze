# -*- coding: utf-8 -*-
"""股本 Excel 解析单元测试（万股→股、同代码按变动日期取最新）。"""
import sys
from pathlib import Path

import pandas as pd

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from backend_core.data_collectors.akshare.stock_shares_collector import (
    normalize_excel_stock_code,
    parse_cninfo_share_change_latest,
    prepare_shares_excel_rows,
    resolve_shares_source,
    _ts_code_to_plain,
    _wan_to_shares,
)


def test_normalize_code():
    assert normalize_excel_stock_code("1") == "000001"
    assert normalize_excel_stock_code(1) == "000001"
    assert normalize_excel_stock_code(1.0) == "000001"
    assert normalize_excel_stock_code("600519") == "600519"


def test_ts_code_and_wan():
    assert _ts_code_to_plain("000001.SZ") == "000001"
    assert _ts_code_to_plain("600519.SH") == "600519"
    assert _wan_to_shares(1940591.8198) == 1940591.8198 * 10000.0


def test_resolve_shares_source(monkeypatch):
    monkeypatch.delenv("STOCK_SHARES_SOURCE", raising=False)
    monkeypatch.delenv("STOCK_SHARES_UPDATE_SOURCE", raising=False)
    assert resolve_shares_source("auto") == "auto"
    assert resolve_shares_source("tushare") == "tushare"
    assert resolve_shares_source("cninfo") == "cninfo"
    assert resolve_shares_source("em") == "akshare"
    monkeypatch.setenv("STOCK_SHARES_SOURCE", "tushare")
    assert resolve_shares_source(None) == "tushare"


def test_parse_cninfo_latest():
    df = pd.DataFrame(
        [
            {
                "变动日期": "2024-01-01",
                "总股本": 100.0,
                "已流通股份": 80.0,
            },
            {
                "变动日期": "2025-06-30",
                "总股本": 1940591.8198,
                "已流通股份": 1940561.7528,
            },
        ]
    )
    out = parse_cninfo_share_change_latest(df)
    assert abs(out["total_shares"] - 1940591.8198 * 10000.0) < 1e-3
    assert abs(out["free_float_shares"] - 1940561.7528 * 10000.0) < 1e-3


def test_prepare_dedup_by_change_date():
    df = pd.DataFrame(
        [
            {
                "证券代码": "000001",
                "变动日期": "2025-06-01",
                "总股本(万股)": 100.0,
                "已流通股份(万股)": 90.0,
            },
            {
                "证券代码": "000001",
                "变动日期": "2025-12-31",
                "总股本(万股)": 120.0,
                "已流通股份(万股)": 110.0,
            },
        ]
    )
    out = prepare_shares_excel_rows(df)
    assert len(out) == 1
    row = out.iloc[0]
    assert row["code"] == "000001"
    assert row["total_shares"] == 120.0 * 10000.0
    assert row["free_float_shares"] == 110.0 * 10000.0


def test_prepare_fallback_announce_date():
    df = pd.DataFrame(
        [
            {
                "证券代码": "000002",
                "公告日期": "2026-03-21",
                "总股本(万股)": 50.0,
                "已流通股份(万股)": 48.0,
            },
            {
                "证券代码": "000002",
                "公告日期": "2026-01-01",
                "总股本(万股)": 40.0,
                "已流通股份(万股)": 38.0,
            },
        ]
    )
    out = prepare_shares_excel_rows(df)
    assert len(out) == 1
    assert out.iloc[0]["total_shares"] == 50.0 * 10000.0
