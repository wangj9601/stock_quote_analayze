"""行业板块 catalog 去重单元测试"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_api.utils.industry_board_query import dedupe_industry_board_catalog


class TestIndustryBoardCatalog:
    def test_dedupe_same_name_prefers_bk(self):
        items = [
            {"board_code": "白色家电", "board_name": "白色家电"},
            {"board_code": "BK0420", "board_name": "白色家电"},
            {"board_code": "半导体", "board_name": "半导体"},
            {"board_code": "BK0421", "board_name": "半导体"},
        ]
        out = dedupe_industry_board_catalog(items)
        codes = {x["board_code"] for x in out}
        assert codes == {"BK0420", "BK0421"}
        assert len(out) == 2

    def test_dedupe_keeps_distinct_names(self):
        items = [
            {"board_code": "白酒", "board_name": "白酒"},
            {"board_code": "BK1001", "board_name": "白酒II"},
            {"board_code": "BK1002", "board_name": "白酒III"},
        ]
        out = dedupe_industry_board_catalog(items)
        assert len(out) == 3

    def test_dedupe_uses_code_when_name_empty(self):
        items = [
            {"board_code": "BK0420", "board_name": None},
            {"board_code": "BK0421", "board_name": ""},
        ]
        out = dedupe_industry_board_catalog(items)
        assert len(out) == 2
