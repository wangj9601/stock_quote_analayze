# -*- coding: utf-8 -*-
"""自选股导入：华泰 Table.xls（GBK+Tab 伪 xls）与代码归一化。"""

from pathlib import Path

from backend_api.watchlist_manage import (
    normalize_import_stock_code,
    parse_watchlist_upload,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "htzq_table_sample.xls"


def _ensure_fixture() -> Path:
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    if FIXTURE.exists():
        return FIXTURE
    # 精简样本：表头 + 3 只股票 + 2 只指数（应被过滤）
    text = (
        "代码\t    名称\t涨幅%\t现价\n"
        "SH601811\t新华文轩\t--\t--\n"
        "SZ002815\t崇达技术\t--\t--\n"
        "BJ920527\t夜光明\t--\t--\n"
        "SZ399001\t深证成指\t--\t--\n"
        "SH000001\t上证指数\t--\t--\n"
    )
    FIXTURE.write_bytes(text.encode("gbk"))
    return FIXTURE


def test_normalize_import_stock_code_broker_prefix():
    assert normalize_import_stock_code("SH601811") == "601811"
    assert normalize_import_stock_code("SZ002815") == "002815"
    assert normalize_import_stock_code("BJ920527") == "920527"
    assert normalize_import_stock_code("600519.SH") == "600519"
    assert normalize_import_stock_code("00700") == "00700"
    assert normalize_import_stock_code("HK00700") == "00700"


def test_normalize_import_stock_code_skips_indices():
    assert normalize_import_stock_code("SH000001") is None
    assert normalize_import_stock_code("SZ399001") is None


def test_parse_htzq_table_xls():
    path = _ensure_fixture()
    rows = parse_watchlist_upload("Table.xls", path.read_bytes())
    assert len(rows) >= 3
    assert "代码" in rows[0]
    assert "名称" in rows[0]  # 表头空格已剥离
    codes = [normalize_import_stock_code(r.get("代码")) for r in rows]
    assert "601811" in codes
    assert "002815" in codes
    assert "920527" in codes
    # 指数行仍在原始 records 中，但归一化后为 None
    assert None in codes


def test_parse_real_user_table_xls_if_present():
    src = Path(r"c:\htzqzyb3\Table.xls")
    if not src.exists():
        return
    rows = parse_watchlist_upload("Table.xls", src.read_bytes())
    assert len(rows) > 10
    codes = [
        normalize_import_stock_code(r.get("代码"))
        for r in rows
        if normalize_import_stock_code(r.get("代码"))
    ]
    assert "601811" in codes
    assert "000001" not in codes or any(
        str(r.get("代码") or "").upper().startswith("SZ000001") for r in rows
    )


if __name__ == "__main__":
    test_normalize_import_stock_code_broker_prefix()
    test_normalize_import_stock_code_skips_indices()
    test_parse_htzq_table_xls()
    test_parse_real_user_table_xls_if_present()
    print("test_watchlist_htzq_table_import.py: all passed")
