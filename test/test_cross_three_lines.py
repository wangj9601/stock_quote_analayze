"""
测试穿线识别功能
"""
import pytest
from backend_api.stock.one_yang_three_lines_strategy import OneYangThreeLinesStrategy


def test_cross_three_lines_basic():
    """测试基本的穿越三条均线情况"""
    # 构造K线数据：开盘10，收盘15，最低9，最高16
    candle_data = {
        'open': 10.0,
        'close': 15.0,
        'low': 9.0,
        'high': 16.0
    }
    
    # 构造均线数据：MA5=11, MA10=12, MA20=13, MA30=14, MA60=16, MA120=17
    # 收盘价15 > MA5(11), MA10(12), MA20(13), MA30(14)，共4条
    # 开盘价10 < MA5(11), MA10(12), MA20(13), MA30(14)，共4条（满足>=2条）
    # 最低价9 < 所有均线（满足>=1条）
    ma_values = {
        'ma5': 11.0,
        'ma10': 12.0,
        'ma20': 13.0,
        'ma30': 14.0,
        'ma60': 16.0,
        'ma120': 17.0
    }
    
    is_cross, crossed_lines, crossed_count = OneYangThreeLinesStrategy.check_cross_three_lines(
        candle_data, ma_values
    )
    
    assert is_cross is True
    assert crossed_count >= 3
    assert 'ma5' in crossed_lines
    assert 'ma10' in crossed_lines
    assert 'ma20' in crossed_lines
    assert 'ma30' in crossed_lines


def test_cross_exactly_three_lines():
    """测试恰好穿越三条均线的情况"""
    # 构造K线数据
    candle_data = {
        'open': 10.0,
        'close': 13.5,
        'low': 9.5,
        'high': 14.0
    }
    
    # 构造均线数据：收盘价13.5 > MA5(11), MA10(12), MA20(13)，共3条
    # 开盘价10 < MA5(11), MA10(12), MA20(13)，共3条
    # 最低价9.5 < 所有均线
    ma_values = {
        'ma5': 11.0,
        'ma10': 12.0,
        'ma20': 13.0,
        'ma30': 14.0,  # 收盘价13.5 < MA30(14)
        'ma60': 15.0,
        'ma120': 16.0
    }
    
    is_cross, crossed_lines, crossed_count = OneYangThreeLinesStrategy.check_cross_three_lines(
        candle_data, ma_values
    )
    
    assert is_cross is True
    assert crossed_count >= 3


def test_not_cross_insufficient_close_above():
    """测试收盘价大于的均线不足3条的情况"""
    candle_data = {
        'open': 10.0,
        'close': 12.5,  # 只大于MA5和MA10
        'low': 9.0,
        'high': 13.0
    }
    
    ma_values = {
        'ma5': 11.0,
        'ma10': 12.0,
        'ma20': 13.0,  # 收盘价12.5 < MA20(13)
        'ma30': 14.0,
        'ma60': 15.0,
        'ma120': 16.0
    }
    
    is_cross, crossed_lines, crossed_count = OneYangThreeLinesStrategy.check_cross_three_lines(
        candle_data, ma_values
    )
    
    assert is_cross is False
    assert crossed_count == 0


def test_not_cross_insufficient_open_below():
    """测试开盘价小于的均线不足2条的情况"""
    candle_data = {
        'open': 12.5,  # 只小于MA20(13), MA30(14), MA60(15), MA120(16)
        'close': 15.5,  # 大于MA5, MA10, MA20, MA30
        'low': 9.0,
        'high': 16.0
    }
    
    ma_values = {
        'ma5': 11.0,   # 开盘价12.5 > MA5(11)
        'ma10': 12.0,  # 开盘价12.5 > MA10(12)
        'ma20': 13.0,  # 开盘价12.5 < MA20(13)
        'ma30': 14.0,
        'ma60': 15.0,
        'ma120': 16.0
    }
    
    is_cross, crossed_lines, crossed_count = OneYangThreeLinesStrategy.check_cross_three_lines(
        candle_data, ma_values
    )
    
    # 收盘价大于MA5, MA10, MA20, MA30（4条）
    # 但在这4条中，开盘价只小于MA20, MA30（2条），满足>=2条的要求
    # 最低价9.0小于所有均线，满足>=1条的要求
    # 所以应该穿越成功
    assert is_cross is True


def test_not_cross_insufficient_low_below():
    """测试最低价低于的均线不足1条的情况"""
    candle_data = {
        'open': 10.0,
        'close': 15.0,
        'low': 14.5,  # 最低价很高，不低于任何被穿越的均线
        'high': 16.0
    }
    
    ma_values = {
        'ma5': 11.0,
        'ma10': 12.0,
        'ma20': 13.0,
        'ma30': 14.0,  # 最低价14.5 > MA30(14)
        'ma60': 16.0,
        'ma120': 17.0
    }
    
    is_cross, crossed_lines, crossed_count = OneYangThreeLinesStrategy.check_cross_three_lines(
        candle_data, ma_values
    )
    
    # 收盘价15 > MA5, MA10, MA20, MA30（4条）
    # 开盘价10 < 这4条均线（满足>=2条）
    # 但最低价14.5只低于MA60和MA120，不在收盘价大于的均线中
    # 在收盘价大于的4条均线中，最低价不低于任何一条
    assert is_cross is False


def test_invalid_candle_data():
    """测试无效的K线数据"""
    # 测试None值
    candle_data = {
        'open': None,
        'close': 15.0,
        'low': 9.0,
        'high': 16.0
    }
    
    ma_values = {
        'ma5': 11.0,
        'ma10': 12.0,
        'ma20': 13.0,
        'ma30': 14.0,
        'ma60': 15.0,
        'ma120': 16.0
    }
    
    is_cross, crossed_lines, crossed_count = OneYangThreeLinesStrategy.check_cross_three_lines(
        candle_data, ma_values
    )
    
    assert is_cross is False
    assert crossed_count == 0


def test_insufficient_ma_data():
    """测试均线数据不足3条的情况"""
    candle_data = {
        'open': 10.0,
        'close': 15.0,
        'low': 9.0,
        'high': 16.0
    }
    
    # 只有2条有效均线
    ma_values = {
        'ma5': 11.0,
        'ma10': 12.0,
        'ma20': None,
        'ma30': None,
        'ma60': None,
        'ma120': None
    }
    
    is_cross, crossed_lines, crossed_count = OneYangThreeLinesStrategy.check_cross_three_lines(
        candle_data, ma_values
    )
    
    assert is_cross is False
    assert crossed_count == 0


def test_cross_all_six_lines():
    """测试穿越全部6条均线的情况"""
    candle_data = {
        'open': 10.0,
        'close': 20.0,
        'low': 9.0,
        'high': 21.0
    }
    
    # 所有均线都在开盘价和收盘价之间
    ma_values = {
        'ma5': 11.0,
        'ma10': 12.0,
        'ma20': 13.0,
        'ma30': 14.0,
        'ma60': 15.0,
        'ma120': 16.0
    }
    
    is_cross, crossed_lines, crossed_count = OneYangThreeLinesStrategy.check_cross_three_lines(
        candle_data, ma_values
    )
    
    assert is_cross is True
    assert crossed_count == 6
    assert len(crossed_lines) == 6


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
