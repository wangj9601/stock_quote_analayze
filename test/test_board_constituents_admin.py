"""板块成分股管理单元测试"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_api.admin.board_constituents import (
    _normalize_board_code,
    _normalize_stock_code,
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
