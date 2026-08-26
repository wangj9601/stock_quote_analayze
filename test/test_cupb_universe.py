# -*- coding: utf-8 -*-
"""CUPB 股票池过滤单测。"""

from backend_core.strategies.cup_bottom.universe import (
    filter_cupb_cn_codes,
    is_valid_cupb_cn_code,
    normalize_cn_board_segments,
    normalize_market_scopes,
)


def test_normalize_market_scopes_defaults_cn():
    assert normalize_market_scopes(None) == ["CN"]
    assert normalize_market_scopes(["CN", "HK"]) == ["CN", "HK"]


def test_filter_invalid_4_8_prefix_by_default():
    codes = ["600519", "873593", "430425", "300750", "00700"]
    out = filter_cupb_cn_codes(codes)
    assert "600519" in out
    assert "300750" in out
    assert "873593" not in out
    assert "430425" not in out
    assert "00700" not in out


def test_bj_segment_allows_bj_codes():
    codes = ["873593", "430425", "600519"]
    out = filter_cupb_cn_codes(codes, board_segments=["BJ"])
    assert "873593" in out
    assert "430425" in out
    assert "600519" not in out


def test_cyb_segment_only():
    codes = ["600519", "300750", "688981"]
    out = filter_cupb_cn_codes(codes, board_segments=["CYB"])
    assert out == ["300750"]


def test_is_valid_cupb_cn_code():
    assert is_valid_cupb_cn_code("600519")
    assert not is_valid_cupb_cn_code("873593")
    assert is_valid_cupb_cn_code("873593", board_segments=["BJ"])


def test_normalize_cn_board_segments_multi():
    segs = normalize_cn_board_segments(["MAIN", "CYB", "KCB"])
    assert "MAIN" in segs
    assert "CYB" in segs
    assert "KCB" in segs
