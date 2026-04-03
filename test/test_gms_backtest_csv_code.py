"""GMS 回测明细 CSV 中 code 列规范化（港股补零、Excel 文本）"""

import os
import sys
import tempfile

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend_core.strategies.gms.backtest_storage import (
    normalize_gms_stock_code,
    format_code_for_csv_cell,
    save_details_csv,
)


def test_normalize_hk_short_code():
    assert normalize_gms_stock_code(981, "HK") == "00981"
    assert normalize_gms_stock_code("981", "HK") == "00981"
    assert normalize_gms_stock_code(981.0, "HK") == "00981"
    assert normalize_gms_stock_code("00981", "HK") == "00981"


def test_normalize_cn_short_code():
    assert normalize_gms_stock_code(1, "CN") == "000001"
    assert normalize_gms_stock_code("000001", "CN") == "000001"


def test_format_code_for_csv_excel_tab():
    assert format_code_for_csv_cell(981, "HK") == "\t00981"
    assert format_code_for_csv_cell("000001", "CN").startswith("\t")


def test_save_details_csv_code_column(monkeypatch):
    from backend_core.strategies.gms import backtest_storage as bs

    d = tempfile.mkdtemp(prefix="gms_csv_")
    try:
        monkeypatch.setattr(bs, "_DETAILS_DIR", d)
        tid = "test-task-csv-1"
        details = [
            {
                "code": 981,
                "date": "2024-01-02",
                "market": "HK",
                "buy_type": "左侧",
                "score_total": 80.0,
                "entry_close": 10.0,
                "max_high_20d": 11.0,
                "max_gain_20d": 0.1,
                "hit": True,
            }
        ]
        fname = save_details_csv(tid, details)
        path = os.path.join(d, fname)
        with open(path, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()
        assert len(lines) >= 2
        assert "\t00981" in lines[1]
    finally:
        try:
            os.remove(os.path.join(d, f"{tid}.csv"))
        except OSError:
            pass
        try:
            os.rmdir(d)
        except OSError:
            pass
