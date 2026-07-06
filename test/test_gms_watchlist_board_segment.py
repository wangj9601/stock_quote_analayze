"""GMS 观察股数据来源：cn_board_segment 板块过滤"""

from backend_api.stock.stock_screening_routes import _gms_filter_stock_pool_by_board_segment


def test_gms_filter_watchlist_pool_by_cyb():
    pool = ["300001", "688001", "000001", "430047", "00700"]
    out = _gms_filter_stock_pool_by_board_segment(pool, "CYB")
    assert out == ["300001"]


def test_gms_filter_watchlist_pool_by_kcb():
    pool = ["300001", "688001", "000001"]
    out = _gms_filter_stock_pool_by_board_segment(pool, "KCB")
    assert out == ["688001"]


def test_gms_filter_watchlist_pool_all_returns_unchanged():
    pool = ["300001", "688001"]
    assert _gms_filter_stock_pool_by_board_segment(pool, "ALL") == pool
    assert _gms_filter_stock_pool_by_board_segment(pool, "") == pool
