"""cn_listed_board_filter 单元测试。"""

import pytest

from backend_api.utils.cn_listed_board_filter import (
    normalize_list_board_segment,
)
from backend_core.strategies.volume_shrink_breakout.data_loader import (
    code_matches_vsb_boards,
    normalize_vsb_board_keys,
)


def test_normalize_main_expands():
    assert normalize_list_board_segment("MAIN") == ["SH_MAIN", "SZ_MAIN"]
    assert normalize_list_board_segment("main") == ["SH_MAIN", "SZ_MAIN"]


def test_normalize_single_board():
    assert normalize_list_board_segment("CYB") == ["CYB"]
    assert normalize_list_board_segment("") == []
    assert normalize_list_board_segment(None) == []


def test_main_matches_prefixes():
    keys = normalize_vsb_board_keys(["SH_MAIN", "SZ_MAIN"])
    assert code_matches_vsb_boards("000981", keys)
    assert code_matches_vsb_boards("600000", keys)
    assert not code_matches_vsb_boards("300001", keys)
    assert not code_matches_vsb_boards("688001", keys)
