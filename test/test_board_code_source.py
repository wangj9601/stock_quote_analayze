"""板块代码来源枚举与校验测试"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_api.utils.board_code_source import (
    DEFAULT_BOARD_CODE_SOURCE,
    LEGACY_DEFAULT_BOARD_CODE_SOURCE,
    SYNC_BOARD_CODE_SOURCE,
    board_code_source_label,
    merge_board_code_source_on_sync,
    normalize_board_code_source,
    resolve_board_code_source,
    sql_board_code_source_preserve_on_conflict,
)


class TestBoardCodeSource:
    def test_defaults_split_by_use_case(self):
        """新增/导入默认同花顺；东财同步与存量空值展示仍为东方财富。"""
        assert DEFAULT_BOARD_CODE_SOURCE == "tonghuashun"
        assert SYNC_BOARD_CODE_SOURCE == "eastmoney"
        assert LEGACY_DEFAULT_BOARD_CODE_SOURCE == "eastmoney"

    def test_normalize_aliases(self):
        assert normalize_board_code_source("东方财富") == "eastmoney"
        assert normalize_board_code_source("同花顺") == "tonghuashun"
        assert normalize_board_code_source("华泰") == "huatai"
        assert normalize_board_code_source("eastmoney") == "eastmoney"

    def test_normalize_invalid(self):
        assert normalize_board_code_source("unknown") is None
        assert normalize_board_code_source("") is None

    def test_resolve_fallback(self):
        # 未显式传 fallback 时走 LEGACY（存量空值展示）
        assert resolve_board_code_source(None) == "eastmoney"
        assert resolve_board_code_source("manual", fallback="manual") == "manual"
        assert resolve_board_code_source(None, fallback=DEFAULT_BOARD_CODE_SOURCE) == "tonghuashun"

    def test_label(self):
        assert board_code_source_label("tonghuashun") == "同花顺"
        assert board_code_source_label("huatai") == "华泰"
        assert board_code_source_label(None) == "东方财富"

    def test_merge_on_sync_preserves_tonghuashun(self):
        """已有同花顺板同步后不得改成东财。"""
        assert merge_board_code_source_on_sync("tonghuashun") == "tonghuashun"
        assert merge_board_code_source_on_sync("同花顺", "eastmoney") == "tonghuashun"
        assert merge_board_code_source_on_sync("manual") == "manual"
        assert merge_board_code_source_on_sync(None) == "eastmoney"
        assert merge_board_code_source_on_sync("") == "eastmoney"
        assert merge_board_code_source_on_sync(None, "tonghuashun") == "tonghuashun"

    def test_sql_preserve_fragment(self):
        frag = sql_board_code_source_preserve_on_conflict("concept_board_basic_info")
        assert "concept_board_basic_info.board_code_source" in frag
        assert "EXCLUDED.board_code_source" in frag
        assert "COALESCE" in frag
