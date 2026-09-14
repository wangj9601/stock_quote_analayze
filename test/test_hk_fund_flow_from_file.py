"""港股资金流向文件采集：1A 公式、代码归一、解析与回写单测。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from backend_core.data_collectors.akshare.hk_fund_flow_from_file import (
    HkFundFlowFromFileCollector,
    compute_flow_from_outer_inner,
    find_hk_fund_flow_file,
    normalize_hk_fund_flow_code,
    parse_numeric,
)


def test_parse_numeric_scientific_and_dash():
    assert parse_numeric("3.25E+08") == pytest.approx(3.25e8)
    assert parse_numeric("2.66E+11") == pytest.approx(2.66e11)
    assert parse_numeric("--") is None
    assert parse_numeric("-") is None
    assert parse_numeric(None) is None
    assert parse_numeric(69.35) == pytest.approx(69.35)


def test_normalize_hk_fund_flow_code():
    assert normalize_hk_fund_flow_code("HK0001") == "00001"
    assert normalize_hk_fund_flow_code("HK0700") == "00700"
    assert normalize_hk_fund_flow_code("700") == "00700"
    assert normalize_hk_fund_flow_code("00700") == "00700"
    assert normalize_hk_fund_flow_code("--") is None
    assert normalize_hk_fund_flow_code(None) is None


def test_compute_flow_1a_ratio():
    inflow, outflow, net = compute_flow_from_outer_inner(4_000_000.0, 100.0, 300.0)
    assert inflow == pytest.approx(1_000_000.0)
    assert outflow == pytest.approx(3_000_000.0)
    assert net == pytest.approx(-2_000_000.0)


def test_compute_flow_zero_or_missing_volumes():
    assert compute_flow_from_outer_inner(1e6, 0.0, 0.0) == (None, None, None)
    assert compute_flow_from_outer_inner(1e6, None, None) == (None, None, None)
    assert compute_flow_from_outer_inner(None, 10.0, 20.0) == (None, None, None)
    # 仅外盘：全部记为流入
    inflow, outflow, net = compute_flow_from_outer_inner(100.0, 50.0, None)
    assert inflow == pytest.approx(100.0)
    assert outflow == pytest.approx(0.0)
    assert net == pytest.approx(100.0)


def test_dataframe_to_rows_maps_columns(tmp_path: Path):
    df = pd.DataFrame(
        [
            {
                "代码": "HK0001",
                "名称": "长和",
                "涨幅%": 0.14,
                "现价": 69.35,
                "金额": 3.25e8,
                "外盘": 1665505,
                "内盘": 3038438,
            },
            {
                "代码": "HK0002",
                "名称": "中电控股",
                "涨幅%": "--",
                "现价": 84.0,
                "金额": 1e8,
                "外盘": "--",
                "内盘": "--",
            },
        ]
    )
    c = HkFundFlowFromFileCollector(trade_date="2026-03-09", data_dir=tmp_path)
    rows = c.dataframe_to_rows(df)
    assert len(rows) == 2
    r0 = rows[0]
    assert r0["code"] == "00001"
    assert r0["name"] == "长和"
    assert r0["trade_date"] == "2026-03-09"
    assert r0["turnover_amount"] == pytest.approx(3.25e8)
    total_vol = 1665505 + 3038438
    assert r0["inflow_amount"] == pytest.approx(3.25e8 * 1665505 / total_vol)
    assert r0["outflow_amount"] == pytest.approx(3.25e8 * 3038438 / total_vol)
    assert r0["net_amount"] == pytest.approx(r0["inflow_amount"] - r0["outflow_amount"])
    assert r0["source"] == "file"

    r1 = next(r for r in rows if r["code"] == "00002")
    assert r1["inflow_amount"] is None
    assert r1["outflow_amount"] is None
    assert r1["net_amount"] is None


def test_load_dataframe_ths_xls_as_gbk_tsv(tmp_path: Path):
    """同花顺导出常把 GBK 制表符文本存成 .xls。"""
    # 代码\t名称\t金额\t外盘\t内盘
    header = "代码\t名称\t涨幅%\t现价\t金额\t外盘\t内盘\n"
    row = "HK0001\t长和\t0.14\t69.35\t325275420\t1665505\t3038438\n"
    content = (header + row).encode("gbk")
    path = tmp_path / "hk_fund_flow_20260908.xls"
    path.write_bytes(content)

    c = HkFundFlowFromFileCollector(trade_date="2026-09-08", data_dir=tmp_path)
    df = c.load_dataframe(path)
    assert "代码" in [str(x).strip() for x in df.columns]
    rows = c.dataframe_to_rows(df)
    assert len(rows) == 1
    assert rows[0]["code"] == "00001"
    assert rows[0]["turnover_amount"] == pytest.approx(325275420.0)


def test_find_hk_fund_flow_file(tmp_path: Path):
    p = tmp_path / "hk_fund_flow_20260309.xlsx"
    p.write_bytes(b"dummy")
    found = find_hk_fund_flow_file("2026-03-09", tmp_path)
    assert found == p
    assert find_hk_fund_flow_file("2026-03-10", tmp_path) is None


def test_collect_missing_file(tmp_path: Path):
    out = HkFundFlowFromFileCollector(trade_date="2026-03-09", data_dir=tmp_path).collect()
    assert out["success"] is False
    assert "未找到" in out["error"]


def test_sync_to_quote_tables_updates_hk(monkeypatch):
    from backend_core.data_collectors.akshare import hk_fund_flow_from_file as mod

    class _Result:
        def __init__(self, n):
            self.rowcount = n

    calls = []

    class _Session:
        def execute(self, sql, params=None):
            sql_s = str(sql)
            calls.append((sql_s, params))
            if "historical_quotes_hk" in sql_s:
                return _Result(1)
            if "stock_realtime_quote_hk" in sql_s:
                return _Result(1)
            return _Result(0)

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(mod, "SessionLocal", lambda: _Session())
    c = mod.HkFundFlowFromFileCollector(trade_date="2026-03-09")
    out = c.sync_to_quote_tables(
        [
            {
                "code": "00700",
                "trade_date": "2026-03-09",
                "inflow_amount": 1.0,
                "outflow_amount": 2.0,
                "net_amount": -1.0,
            }
        ]
    )
    assert out["historical_updated"] == 1
    assert out["realtime_updated"] == 1
    assert any("historical_quotes_hk" in s for s, _ in calls)
    assert any("stock_realtime_quote_hk" in s for s, _ in calls)


def test_parse_numeric_leading_plus():
    assert parse_numeric("+1.68") == pytest.approx(1.68)
    assert parse_numeric("+1.145") == pytest.approx(1.145)


def test_dataframe_to_realtime_quote_rows():
    df = pd.DataFrame(
        [
            {
                "代码": "HK0001",
                "名称    ": "长和",
                "涨幅%": "+1.68",
                "现价": "69.250",
                "总手": "5007403",
                "昨收": "68.105",
                "开盘": "68.750",
                "最高": "69.300",
                "最低": "67.550",
                "涨跌": "+1.145",
                "金额": "344557840",
                "外盘": "2618254",
                "内盘": "2389149",
            }
        ]
    )
    c = HkFundFlowFromFileCollector(trade_date="2026-09-14", data_dir=Path("."))
    rows = c.dataframe_to_realtime_quote_rows(df)
    assert len(rows) == 1
    r = rows[0]
    assert r["code"] == "00001"
    assert r["name"] == "长和"
    assert r["current_price"] == pytest.approx(69.25)
    assert r["volume"] == pytest.approx(5007403)
    assert r["change_percent"] == pytest.approx(1.68)
    assert r["change_amount"] == pytest.approx(1.145)
    assert r["pre_close"] == pytest.approx(68.105)
    assert r["open"] == pytest.approx(68.75)
    assert r["inflow_amount"] is not None
    assert r["net_amount"] is not None


def test_collect_realtime_quotes_file_too_few_rows(tmp_path: Path):
    header = "代码\t名称\t涨幅%\t现价\t总手\t昨收\t开盘\t最高\t最低\t涨跌\t金额\t外盘\t内盘\n"
    row = "HK0001\t长和\t+1.68\t69.250\t5007403\t68.105\t68.750\t69.300\t67.550\t+1.145\t344557840\t1\t1\n"
    path = tmp_path / "hk_fund_flow_20260914.xls"
    path.write_bytes((header + row).encode("gbk"))
    c = HkFundFlowFromFileCollector(trade_date="2026-09-14", data_dir=tmp_path)
    out = c.collect_realtime_quotes(min_rows=100, allow_latest=False)
    assert out["success"] is False
    assert "少于最低要求" in out["error"]
    assert out["unique"] == 1


def test_collect_realtime_quotes_missing_file(tmp_path: Path):
    c = HkFundFlowFromFileCollector(trade_date="2026-09-14", data_dir=tmp_path)
    out = c.collect_realtime_quotes(allow_latest=False)
    assert out["success"] is False
    assert "未找到" in out["error"]


def test_find_latest_hk_fund_flow_file(tmp_path: Path):
    from backend_core.data_collectors.akshare.hk_fund_flow_from_file import (
        find_latest_hk_fund_flow_file,
        resolve_hk_fund_flow_file_for_realtime,
    )

    older = tmp_path / "hk_fund_flow_20260910.xls"
    newer = tmp_path / "hk_fund_flow_20260914.xls"
    older.write_bytes(b"x")
    newer.write_bytes(b"y")
    assert find_latest_hk_fund_flow_file(tmp_path) == newer
    path, d = resolve_hk_fund_flow_file_for_realtime("2026-09-15", tmp_path, allow_latest=True)
    assert path == newer
    assert d == "2026-09-14"


def test_real_hk_fund_flow_file_maps_enough_quote_rows():
    path = Path("backend_core/data/hk_fund_flow_20260914.xls")
    if not path.is_file():
        pytest.skip("sample hk_fund_flow file not present")
    c = HkFundFlowFromFileCollector(trade_date="2026-09-14", data_dir=path.parent)
    df = c.load_dataframe(path)
    rows = c.dataframe_to_realtime_quote_rows(df)
    assert len(rows) >= 100
    r0 = next(r for r in rows if r["code"] == "00001")
    assert r0["current_price"] == pytest.approx(69.25)
    assert r0["volume"] == pytest.approx(5007403)
