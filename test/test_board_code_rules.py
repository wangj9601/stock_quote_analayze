"""板块代码 BK 前缀规则单元测试"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_core.data_collectors.akshare.board_code_rules import (
    is_concept_board_code,
    is_industry_board_code,
)


class TestBoardCodeRules:
    def test_concept_bk_prefix(self):
        assert is_concept_board_code("BK0479") is True
        assert is_concept_board_code("bk1623") is True

    def test_industry_bk_format(self):
        assert is_industry_board_code("BK0479") is True
        assert is_industry_board_code("贵金属") is False
        assert is_concept_board_code("贵金属") is False
