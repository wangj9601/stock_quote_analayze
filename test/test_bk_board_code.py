"""BK 板块编码工具单元测试"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_api.utils.bk_board_code import (
    format_bk_board_code,
    generate_next_bk_board_code,
    is_valid_bk_board_code,
    is_valid_industry_board_code,
    normalize_bk_board_code,
    normalize_industry_board_code,
)


class TestBkBoardCode:
    def test_format_bk_board_code(self):
        assert format_bk_board_code(428) == "BK0428"
        assert format_bk_board_code(1253) == "BK1253"
        assert format_bk_board_code(10000) == "BK10000"

    def test_normalize_and_validate(self):
        assert normalize_bk_board_code(" bk0479 ") == "BK0479"
        assert normalize_bk_board_code("玻璃") == ""
        assert is_valid_bk_board_code("BK0428") is True
        assert is_valid_bk_board_code("玻璃") is False

    def test_normalize_industry_board_code(self):
        assert normalize_industry_board_code("BK0428") == "BK0428"
        assert normalize_industry_board_code("医疗服务") == "医疗服务"
        assert normalize_industry_board_code("IT服务") == "IT服务"
        assert normalize_industry_board_code("123") == ""
        assert is_valid_industry_board_code("贵金属") is True

    def test_generate_next_bk_board_code(self):
        class _Q:
            def __init__(self, rows):
                self._rows = rows

            def fetchall(self):
                return self._rows

        class _DB:
            def execute(self, *args, **kwargs):
                return _Q([("BK0428",), ("BK1253",)])

        db = _DB()
        assert generate_next_bk_board_code(db) == "BK1254"
        assert generate_next_bk_board_code(db, after_code="BK1253") == "BK1254"
