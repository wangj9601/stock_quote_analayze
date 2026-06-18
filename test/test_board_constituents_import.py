"""板块成分股导入解析单元测试"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_api.admin.board_constituents_import import parse_constituents_file


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
