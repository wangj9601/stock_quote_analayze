"""A 股代码列表板块过滤工具单元测试。"""

from backend_api.utils.cn_listed_board_filter import filter_stock_codes_by_board_segment


def test_filter_stock_codes_by_board_segment_cyb():
    codes = ["600519", "300750", "00700"]
    assert filter_stock_codes_by_board_segment(codes, "CYB") == ["300750", "00700"]


def test_filter_stock_codes_by_board_segment_all_unchanged():
    codes = ["600519", "300750"]
    assert filter_stock_codes_by_board_segment(codes, "ALL") == codes
    assert filter_stock_codes_by_board_segment(codes, None) == codes
