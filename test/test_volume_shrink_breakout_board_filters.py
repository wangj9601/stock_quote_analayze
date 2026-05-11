"""
3倍量缩量突破 — 板块/代码段过滤键与匹配逻辑（无 DB）
"""

import pytest

from backend_core.strategies.volume_shrink_breakout.data_loader import (
    code_matches_vsb_boards,
    normalize_vsb_board_keys,
)


def test_normalize_accepts_list_and_comma_string():
    assert normalize_vsb_board_keys(["cyb", "KCB"]) == ["CYB", "KCB"]
    assert normalize_vsb_board_keys(["CYB,KCB", "SH_MAIN"]) == ["CYB", "KCB", "SH_MAIN"]
    assert normalize_vsb_board_keys(["CYB", "CYB"]) == ["CYB"]
    assert normalize_vsb_board_keys(["nope", "CYB"]) == ["CYB"]
    assert normalize_vsb_board_keys(None) == []
    assert normalize_vsb_board_keys([]) == []


@pytest.mark.parametrize(
    "code,keys,expect",
    [
        ("300001", ["CYB"], True),
        ("688001", ["CYB"], False),
        ("688001", ["KCB"], True),
        ("600000", ["SH_MAIN"], True),
        ("688000", ["SH_MAIN"], False),
        ("605099", ["SH_MAIN"], True),
        ("000001", ["SZ_MAIN"], True),
        ("001979", ["SZ_MAIN"], True),
        ("002001", ["SZ_SME"], True),
        ("300001", ["SZ_SME"], False),
        ("300001", [], True),
        ("688001", ["CYB", "KCB"], True),
    ],
)
def test_code_matches_vsb_boards(code, keys, expect):
    assert code_matches_vsb_boards(code, keys) is expect
