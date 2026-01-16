"""
测试长阳线识别功能
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend_api.stock.one_yang_three_lines_strategy import OneYangThreeLinesStrategy


def test_valid_long_yang_candle():
    """测试有效的长阳线"""
    # 构造一个符合条件的长阳线
    # 开盘10元，收盘10.5元（涨幅5%），最高10.6元，最低9.95元
    # 实体长度 = 0.5，总长度 = 0.65，实体占比 = 76.9%
    candle_data = {
        'open': 10.0,
        'close': 10.5,
        'high': 10.6,
        'low': 9.95
    }
    
    is_long_yang, info = OneYangThreeLinesStrategy.check_long_yang_candle(candle_data)
    
    print(f"测试有效长阳线:")
    print(f"  是否为长阳线: {is_long_yang}")
    print(f"  是否为阳线: {info['is_yang']}")
    print(f"  实体长度: {info['body_length']}")
    print(f"  总长度: {info['total_length']}")
    print(f"  实体占比: {info['body_ratio']:.2%}")
    print(f"  涨幅: {info['change_percent']:.2%}")
    
    assert is_long_yang == True, "应该识别为长阳线"
    assert info['is_yang'] == True, "应该是阳线"
    assert info['body_ratio'] >= 0.7, "实体占比应该>=70%"
    assert info['change_percent'] >= 0.03, "涨幅应该>=3%"
    print("✓ 测试通过\n")


def test_not_yang_candle():
    """测试阴线（不是阳线）"""
    candle_data = {
        'open': 10.5,
        'close': 10.0,  # 收盘价 < 开盘价
        'high': 10.6,
        'low': 9.95
    }
    
    is_long_yang, info = OneYangThreeLinesStrategy.check_long_yang_candle(candle_data)
    
    print(f"测试阴线:")
    print(f"  是否为长阳线: {is_long_yang}")
    print(f"  是否为阳线: {info['is_yang']}")
    
    assert is_long_yang == False, "阴线不应该被识别为长阳线"
    assert info['is_yang'] == False, "应该不是阳线"
    print("✓ 测试通过\n")


def test_body_ratio_too_small():
    """测试实体占比不足70%"""
    # 开盘10元，收盘10.35元（涨幅3.5%），最高11元，最低9元
    # 实体长度 = 0.35，总长度 = 2，实体占比 = 17.5%
    candle_data = {
        'open': 10.0,
        'close': 10.35,
        'high': 11.0,
        'low': 9.0
    }
    
    is_long_yang, info = OneYangThreeLinesStrategy.check_long_yang_candle(candle_data)
    
    print(f"测试实体占比不足:")
    print(f"  是否为长阳线: {is_long_yang}")
    print(f"  实体占比: {info['body_ratio']:.2%}")
    print(f"  涨幅: {info['change_percent']:.2%}")
    
    assert is_long_yang == False, "实体占比不足70%不应该被识别为长阳线"
    assert info['body_ratio'] < 0.7, "实体占比应该<70%"
    print("✓ 测试通过\n")


def test_change_percent_too_small():
    """测试涨幅不足3%"""
    # 开盘10元，收盘10.2元（涨幅2%），最高10.25元，最低9.95元
    # 实体长度 = 0.2，总长度 = 0.3，实体占比 = 66.7%（不足70%）
    # 但即使实体占比够，涨幅也不够
    candle_data = {
        'open': 10.0,
        'close': 10.2,
        'high': 10.25,
        'low': 9.95
    }
    
    is_long_yang, info = OneYangThreeLinesStrategy.check_long_yang_candle(candle_data)
    
    print(f"测试涨幅不足:")
    print(f"  是否为长阳线: {is_long_yang}")
    print(f"  涨幅: {info['change_percent']:.2%}")
    
    assert is_long_yang == False, "涨幅不足3%不应该被识别为长阳线"
    assert info['change_percent'] < 0.03, "涨幅应该<3%"
    print("✓ 测试通过\n")


def test_boundary_case_exactly_70_percent():
    """测试边界情况：实体占比恰好70%"""
    # 开盘10元，收盘10.35元（涨幅3.5%），最高10.5元，最低9.95元
    # 实体长度 = 0.35，总长度 = 0.55，实体占比 = 63.6%（不够70%）
    # 让我重新计算：要实体占比=70%且涨幅>=3%
    # 开盘10元，收盘10.35元（涨幅3.5%），最高10.5元，最低10.0元
    # 实体长度 = 0.35，总长度 = 0.5，实体占比 = 70%
    candle_data = {
        'open': 10.0,
        'close': 10.35,
        'high': 10.5,
        'low': 10.0
    }
    
    # 手动计算验证
    expected_change = (10.35 - 10.0) / 10.0
    print(f"预期涨幅: {expected_change:.4f} = {expected_change:.2%}")
    
    is_long_yang, info = OneYangThreeLinesStrategy.check_long_yang_candle(candle_data)
    
    print(f"测试边界情况（实体占比=70%）:")
    print(f"  是否为长阳线: {is_long_yang}")
    print(f"  实体占比: {info['body_ratio']:.2%}")
    print(f"  涨幅: {info['change_percent']:.2%}")
    print(f"  详细信息: {info}")
    
    assert is_long_yang == True, "实体占比恰好70%应该被识别为长阳线"
    assert info['body_ratio'] == 0.7, "实体占比应该=70%"
    print("✓ 测试通过\n")


def test_boundary_case_exactly_3_percent():
    """测试边界情况：涨幅恰好3%"""
    # 开盘10元，收盘10.3元（涨幅3%），最高10.35元，最低9.95元
    # 实体长度 = 0.3，总长度 = 0.4，实体占比 = 75%
    candle_data = {
        'open': 10.0,
        'close': 10.3,
        'high': 10.35,
        'low': 9.95
    }
    
    is_long_yang, info = OneYangThreeLinesStrategy.check_long_yang_candle(candle_data)
    
    print(f"测试边界情况（涨幅=3%）:")
    print(f"  是否为长阳线: {is_long_yang}")
    print(f"  实体占比: {info['body_ratio']:.2%}")
    print(f"  涨幅: {info['change_percent']:.2%}")
    
    assert is_long_yang == True, "涨幅恰好3%应该被识别为长阳线"
    assert info['change_percent'] == 0.03, "涨幅应该=3%"
    print("✓ 测试通过\n")


def test_invalid_data():
    """测试无效数据"""
    # 测试缺失数据
    candle_data = {
        'open': 10.0,
        'close': None,
        'high': 10.5,
        'low': 9.5
    }
    
    is_long_yang, info = OneYangThreeLinesStrategy.check_long_yang_candle(candle_data)
    
    print(f"测试无效数据（缺失字段）:")
    print(f"  是否为长阳线: {is_long_yang}")
    
    assert is_long_yang == False, "无效数据不应该被识别为长阳线"
    print("✓ 测试通过\n")


if __name__ == '__main__':
    print("=" * 60)
    print("开始测试长阳线识别功能")
    print("=" * 60 + "\n")
    
    test_valid_long_yang_candle()
    test_not_yang_candle()
    test_body_ratio_too_small()
    test_change_percent_too_small()
    test_boundary_case_exactly_70_percent()
    test_boundary_case_exactly_3_percent()
    test_invalid_data()
    
    print("=" * 60)
    print("所有测试通过！")
    print("=" * 60)
