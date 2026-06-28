"""K 线 MA 查询 market_type 与 ma_indicators 表一致（CN/HK，兼容历史 A股/港股）。"""

from backend_api.stock.stock_manage import MA_MARKET_TYPES_CN, _normalize_indicator_date
from backend_api.stock.hk_stock_manage import MA_MARKET_TYPES_HK


def test_cn_market_type_includes_cn():
    assert 'CN' in MA_MARKET_TYPES_CN
    assert 'A股' in MA_MARKET_TYPES_CN


def test_hk_market_type_includes_hk():
    assert 'HK' in MA_MARKET_TYPES_HK
    assert '港股' in MA_MARKET_TYPES_HK


def test_normalize_indicator_date():
    assert _normalize_indicator_date('2026-06-26') == '2026-06-26'
    assert _normalize_indicator_date('2026-06-26 00:00:00') == '2026-06-26'
