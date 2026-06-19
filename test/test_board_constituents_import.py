"""板块成分股导入：东财 Table.xls 与名称反查代码"""

import os
import sys
from unittest.mock import MagicMock

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_api.admin.board_constituents_import import (
    _normalize_eastmoney_stock_name,
    _pick_best_code,
    parse_all_constituents_file,
    parse_constituents_file,
    resolve_rows_stock_codes,
)

TABLE_XLS_PATH = r"e:\temp\Table.xls"


class TestBoardConstituentsImport:
    def test_parse_csv_with_chinese_headers(self):
        csv_text = "股票代码,股票名称\n000001,平安银行\n600519,贵州茅台\n"
        rows, issues = parse_constituents_file("a.csv", csv_text.encode("utf-8-sig"))
        assert len(rows) == 2
        assert rows[0]["stock_code"] == "000001"
        assert rows[0]["stock_name"] == "平安银行"
        assert not issues or all("重复" not in i.get("message", "") for i in issues)

    def test_parse_xlsx_english_headers(self):
        import io

        df = pd.DataFrame([{"stock_code": "300750", "stock_name": "宁德时代"}])
        bio = io.BytesIO()
        with pd.ExcelWriter(bio, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        rows, issues = parse_constituents_file("b.xlsx", bio.getvalue())
        assert len(rows) == 1
        assert rows[0]["stock_code"] == "300750"

    def test_duplicate_skipped(self):
        csv_text = "code,name\n000001,A\n000001,B\n"
        rows, issues = parse_constituents_file("c.csv", csv_text.encode("utf-8"))
        assert len(rows) == 1
        assert any("重复" in i.get("message", "") for i in issues)

    def test_parse_eastmoney_table_xls_name_only(self):
        if not os.path.isfile(TABLE_XLS_PATH):
            pytest.skip("样例文件不存在: e:\\temp\\Table.xls")
        content = open(TABLE_XLS_PATH, "rb").read()
        rows, issues = parse_constituents_file("Table.xls", content)
        assert len(rows) >= 100
        assert all((r.get("stock_name") or "").strip() for r in rows)
        assert all(not (r.get("stock_code") or "").strip() for r in rows)
        assert not any(i.get("row_no") == 0 for i in issues)

    def test_resolve_rows_stock_codes_by_name(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [
            ("300018", "中元股份"),
            ("000001", "平安银行"),
        ]
        rows = [{"stock_code": "", "stock_name": "中元股份"}, {"stock_code": "", "stock_name": "未知股"}]
        resolved, issues = resolve_rows_stock_codes(db, rows)
        assert len(resolved) == 1
        assert resolved[0]["stock_code"] == "300018"
        assert resolved[0]["stock_name"] == "中元股份"
        assert any("未知股" in i.get("message", "") for i in issues)

    def test_resolve_keeps_existing_code(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        rows = [{"stock_code": "600519", "stock_name": "贵州茅台"}]
        resolved, issues = resolve_rows_stock_codes(db, rows)
        assert len(resolved) == 1
        assert resolved[0]["stock_code"] == "600519"
        assert not issues

    def test_normalize_eastmoney_name_suffix(self):
        assert _normalize_eastmoney_stock_name("优刻得-W") == "优刻得"
        assert _normalize_eastmoney_stock_name("云从科技-UW") == "云从科技"
        assert _normalize_eastmoney_stock_name("云天励飞-U") == "云天励飞"

    def test_pick_best_code_prefers_bse_over_neeq(self):
        picked, all_codes = _pick_best_code(["430564", "920564"])
        assert picked == "920564"
        assert set(all_codes) == {"430564", "920564"}

    def test_resolve_eastmoney_suffix_names(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [
            ("688158", "优刻得"),
            ("688327", "云从科技"),
        ]
        rows = [
            {"stock_code": "", "stock_name": "优刻得-W"},
            {"stock_code": "", "stock_name": "云从科技-UW"},
        ]
        resolved, issues = resolve_rows_stock_codes(db, rows)
        assert len(resolved) == 2
        assert resolved[0]["stock_code"] == "688158"
        assert resolved[1]["stock_code"] == "688327"
        assert not issues

    def test_resolve_duplicate_name_picks_higher_priority(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [
            ("920564", "天润科技"),
            ("430564", "天润科技"),
        ]
        rows = [{"stock_code": "", "stock_name": "天润科技"}]
        resolved, issues = resolve_rows_stock_codes(db, rows)
        assert len(resolved) == 1
        assert resolved[0]["stock_code"] == "920564"
        assert not issues

    def test_parse_all_constituents_file(self):
        csv_text = (
            "board_code,board_name,stock_code,stock_name\n"
            "IT服务,IT服务,000001,平安银行\n"
            "IT服务,IT服务,,神州数码\n"
            "半导体,半导体,688981,中芯国际\n"
        )
        rows, issues = parse_all_constituents_file("all.csv", csv_text.encode("utf-8-sig"))
        assert len(rows) == 3
        assert rows[0]["board_code"] == "IT服务"
        assert rows[1]["stock_name"] == "神州数码"
        assert rows[2]["board_code"] == "半导体"
        assert not issues

    def test_parse_all_constituents_missing_board_col(self):
        csv_text = "stock_code,stock_name\n000001,平安银行\n"
        rows, issues = parse_all_constituents_file("bad.csv", csv_text.encode("utf-8"))
        assert not rows
        assert any("板块代码" in i.get("message", "") for i in issues)
