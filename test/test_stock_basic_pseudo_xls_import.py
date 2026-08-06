"""股本导入：东财伪 Table.xls（GBK 制表符文本）解析。"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend_core.utils.stock_basic_importer import _to_float, parse_import_file

REAL_TABLE_XLS = Path(r"c:\htzqzyb3\Table.xls")


def _build_pseudo_xls_bytes() -> bytes:
    """构造与东财 Table.xls 同结构的 GBK TSV（伪 xls）。"""
    # 东财 Table.xls 实际表头为「总股数」（非「总股本」）、「流通比例%」等
    header = "\t".join(
        [
            "代码",
            "名称",
            ".",
            "流通股",
            "总股数",
            "流通比例%",
            "股东总数",
            "人均持股数",
            "B股",
            "H股",
            "国家股",
        ]
    )
    row1 = "\t".join(
        [
            "SH600000",
            "浦发银行",
            "--",
            "33,305,838,300",
            "33,305,838,300",
            "100",
            "100000",
            "333058",
            "--",
            "--",
            "--",
        ]
    )
    row2 = "\t".join(
        [
            "SZ000001",
            "平安银行",
            "--",
            "19,405,618,000",
            "--",
            "100",
            "--",
            "--",
            "--",
            "--",
            "--",
        ]
    )
    # 东财导出常见仅用 \\r 换行
    text = "\r".join([header, row1, row2]) + "\r"
    return text.encode("gbk")


def test_parse_pseudo_xls_table_strips_prefix_and_reads_shares() -> None:
    content = _build_pseudo_xls_bytes()
    rows, issues = parse_import_file("Table.xls", content)

    assert not issues
    assert len(rows) == 2

    r0 = rows[0]
    assert r0["code"] == "600000"
    assert r0["name"] == "浦发银行"
    assert r0["total_shares"] == 33305838300.0
    assert r0["free_float_shares"] == 33305838300.0
    assert r0["market"] == "CN"

    r1 = rows[1]
    assert r1["code"] == "000001"
    assert r1["free_float_shares"] == 19405618000.0
    assert r1["total_shares"] is None  # 总股本为 --


def test_parse_pseudo_xls_also_accepts_total_shares_alias() -> None:
    """列名「总股本」仍应匹配（非东财「总股数」场景）。"""
    header = "代码\t名称\t流通股\t总股本"
    row = "BJ430047\t某某\t1,000\t2,000"
    content = (header + "\r" + row + "\r").encode("gbk")
    rows, issues = parse_import_file("Table.xls", content)
    assert not issues
    assert rows[0]["code"] == "430047"
    assert rows[0]["free_float_shares"] == 1000.0
    assert rows[0]["total_shares"] == 2000.0


def test_to_float_treats_double_dash_as_empty() -> None:
    assert _to_float("--") is None
    assert _to_float("-") is None
    assert _to_float("1,234") == 1234.0


@pytest.mark.skipif(not REAL_TABLE_XLS.exists(), reason="本机无 c:\\htzqzyb3\\Table.xls")
def test_optional_real_table_xls_smoke() -> None:
    rows, issues = parse_import_file("Table.xls", REAL_TABLE_XLS.read_bytes())
    assert len(rows) > 1000
    assert rows[0]["code"].isdigit()
    assert rows[0].get("total_shares") is not None or rows[0].get("free_float_shares") is not None
    # issues 允许存在，但不应对整文件失败
    assert len(issues) < len(rows)
