"""板块代码来源枚举与校验测试"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_api.utils.board_code_source import (
    board_code_source_label,
    normalize_board_code_source,
    resolve_board_code_source,
)


class TestBoardCodeSource:
    def test_normalize_aliases(self):
        assert normalize_board_code_source("东方财富") == "eastmoney"
        assert normalize_board_code_source("同花顺") == "tonghuashun"
        assert normalize_board_code_source("华泰") == "huatai"
        assert normalize_board_code_source("eastmoney") == "eastmoney"

    def test_normalize_invalid(self):
        assert normalize_board_code_source("unknown") is None
        assert normalize_board_code_source("") is None

    def test_resolve_fallback(self):
        assert resolve_board_code_source(None) == "eastmoney"
        assert resolve_board_code_source("manual", fallback="manual") == "manual"

    def test_label(self):
        assert board_code_source_label("tonghuashun") == "同花顺"
        assert board_code_source_label("huatai") == "华泰"
