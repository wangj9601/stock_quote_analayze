"""板块成分股管理单元测试"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import HTTPException

from backend_api.admin.board_constituents import (
    SaveBoardInfoBody,
    _assert_concept_board_name_unique,
    _format_bk_board_code,
    _generate_next_concept_board_code,
    _normalize_board_code,
    _normalize_stock_code,
    _sync_concept_board_basic_from_import,
    _tables,
)


class TestBoardConstituentsHelpers:
    def test_normalize_board_code(self):
        assert _normalize_board_code(" bk0479 ") == "BK0479"

    def test_normalize_stock_code(self):
        assert _normalize_stock_code("sz000001") == "000001"
        assert _normalize_stock_code("300668") == "300668"

    def test_tables_mapping(self):
        ind = _tables("industry")
        assert ind["constituents"] == "industry_board_constituents"
        con = _tables("concept")
        assert con["constituents"] == "concept_board_constituents"

    def test_save_board_body_validation(self):
        body = SaveBoardInfoBody(board_type="concept", board_code="BK0428", board_name="电力")
        assert body.board_code == "BK0428"
        empty_concept = SaveBoardInfoBody(board_type="concept", board_name="测试概念")
        assert empty_concept.board_code is None
        try:
            SaveBoardInfoBody(board_type="industry", board_name="x")
            assert False, "行业板块应要求代码"
        except ValueError:
            pass

    def test_format_bk_board_code(self):
        assert _format_bk_board_code(428) == "BK0428"
        assert _format_bk_board_code(1253) == "BK1253"
        assert _format_bk_board_code(10000) == "BK10000"

    def test_generate_next_concept_board_code(self):
        class _Q:
            def __init__(self, rows):
                self._rows = rows

            def fetchall(self):
                return self._rows

        class _DB:
            def execute(self, *args, **kwargs):
                return _Q([("BK0428",), ("BK1253",), ("BK0999",)])

        db = _DB()
        assert _generate_next_concept_board_code(db) == "BK1254"
        assert _generate_next_concept_board_code(db, after_code="BK1254") == "BK1255"
        assert _generate_next_concept_board_code(db, after_code="BK1253") == "BK1254"

    def test_concept_board_name_unique(self):
        class _DB:
            def __init__(self, row):
                self._row = row

            def execute(self, *args, **kwargs):
                outer = self

                class _R:
                    def fetchone(inner):
                        return outer._row

                return _R()

        try:
            _assert_concept_board_name_unique(
                _DB(("BK1638",)),
                "华为海思概念",
            )
            assert False, "应拒绝重复名称"
        except HTTPException as e:
            assert e.status_code == 400
            assert "已存在" in str(e.detail)

        _assert_concept_board_name_unique(
            _DB(("BK1638",)),
            "华为海思概念",
            exclude_codes=["BK1638"],
        )
        _assert_concept_board_name_unique(_DB(None), "新板块")
        _assert_concept_board_name_unique(_DB(("BK1638",)), "  ")

    def test_sync_concept_board_basic_from_import(self):
        from datetime import datetime

        executed: list[dict] = []

        class _DB:
            def execute(self, sql, params=None):
                sql_s = str(sql)
                if "board_code <> :code" in sql_s:
                    return type("R", (), {"fetchone": lambda self: None})()
                return type("R", (), {"fetchone": lambda self: None})()

            def _record(self, params):
                executed.append(params)

        class _DBWrap:
            def __init__(self):
                self.inner = _DB()

            def execute(self, sql, params=None):
                sql_s = str(sql)
                if "INSERT INTO concept_board_basic_info" in sql_s:
                    executed.append(params)
                return self.inner.execute(sql, params)

        issues: list = []
        now = datetime(2026, 6, 6, 12, 0, 0)
        count = _sync_concept_board_basic_from_import(
            _DBWrap(),
            [
                {"board_code": "BK1641", "board_name": "苹果概念", "stock_code": "000001", "stock_name": "平安银行"},
                {"board_code": "BK1641", "board_name": "苹果概念", "stock_code": "000002", "stock_name": "万科A"},
                {"board_code": "BK1642", "board_name": "", "stock_code": "600519", "stock_name": "贵州茅台"},
            ],
            now,
            issues,
        )
        assert count == 2
        assert len(issues) == 0
        assert len(executed) == 2
        assert executed[0]["board_code"] == "BK1641"
        assert executed[0]["board_name"] == "苹果概念"
        assert executed[1]["board_code"] == "BK1642"
        assert executed[1]["board_name"] is None
