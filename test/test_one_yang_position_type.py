"""
测试一阳穿三线策略的位置判别功能
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend_api.stock.one_yang_three_lines_strategy import OneYangThreeLinesStrategy


def test_check_position_type_low():
    """测试低位判断（回撤 >= 30%）"""
    # 构造测试数据：当前价格为7元，60日最高价为10元
    # 回撤幅度 = (10 - 7) / 10 * 100 = 30%
    historical_data = []
    
    # 当前日期数据（索引0）
    historical_data.append({
        'close': 7.0,
        'high': 7.5
    })
    
    # 后续59天的数据，最高价为10元
    for i in range(59):
        historical_data.append({
            'close': 8.0 + i * 0.01,
            'high': 10.0 if i == 0 else 9.0  # 第一天最高价为10元
        })
    
    position_type, retracement = OneYangThreeLinesStrategy.check_position_type(
        historical_data, 0
    )
    
    print(f"测试低位判断:")
    print(f"  位置类型: {position_type}")
    print(f"  回撤幅度: {retracement}%")
    print(f"  预期: 低位, 30.0%")
    
    assert position_type == "低位", f"预期位置类型为'低位'，实际为'{position_type}'"
    assert retracement == 30.0, f"预期回撤幅度为30.0%，实际为{retracement}%"
    print("✓ 低位判断测试通过\n")


def test_check_position_type_mid():
    """测试中位判断（回撤在10%-30%之间）"""
    # 构造测试数据：当前价格为8元，60日最高价为10元
    # 回撤幅度 = (10 - 8) / 10 * 100 = 20%
    historical_data = []
    
    # 当前日期数据（索引0）
    historical_data.append({
        'close': 8.0,
        'high': 8.5
    })
    
    # 后续59天的数据，最高价为10元
    for i in range(59):
        historical_data.append({
            'close': 8.0 + i * 0.01,
            'high': 10.0 if i == 0 else 9.0  # 第一天最高价为10元
        })
    
    position_type, retracement = OneYangThreeLinesStrategy.check_position_type(
        historical_data, 0
    )
    
    print(f"测试中位判断:")
    print(f"  位置类型: {position_type}")
    print(f"  回撤幅度: {retracement}%")
    print(f"  预期: 中位, 20.0%")
    
    assert position_type == "中位", f"预期位置类型为'中位'，实际为'{position_type}'"
    assert retracement == 20.0, f"预期回撤幅度为20.0%，实际为{retracement}%"
    print("✓ 中位判断测试通过\n")


def test_check_position_type_high():
    """测试高位判断（回撤 < 10%）"""
    # 构造测试数据：当前价格为9.5元，60日最高价为10元
    # 回撤幅度 = (10 - 9.5) / 10 * 100 = 5%
    historical_data = []
    
    # 当前日期数据（索引0）
    historical_data.append({
        'close': 9.5,
        'high': 9.8
    })
    
    # 后续59天的数据，最高价为10元
    for i in range(59):
        historical_data.append({
            'close': 9.0 + i * 0.01,
            'high': 10.0 if i == 0 else 9.5  # 第一天最高价为10元
        })
    
    position_type, retracement = OneYangThreeLinesStrategy.check_position_type(
        historical_data, 0
    )
    
    print(f"测试高位判断:")
    print(f"  位置类型: {position_type}")
    print(f"  回撤幅度: {retracement}%")
    print(f"  预期: 高位, 5.0%")
    
    assert position_type == "高位", f"预期位置类型为'高位'，实际为'{position_type}'"
    assert retracement == 5.0, f"预期回撤幅度为5.0%，实际为{retracement}%"
    print("✓ 高位判断测试通过\n")


def test_check_position_type_boundary_30():
    """测试边界值：回撤正好30%"""
    # 构造测试数据：当前价格为7元，60日最高价为10元
    # 回撤幅度 = (10 - 7) / 10 * 100 = 30%
    historical_data = []
    
    # 当前日期数据（索引0）
    historical_data.append({
        'close': 7.0,
        'high': 7.5
    })
    
    # 后续59天的数据，最高价为10元
    for i in range(59):
        historical_data.append({
            'close': 8.0,
            'high': 10.0 if i == 0 else 9.0
        })
    
    position_type, retracement = OneYangThreeLinesStrategy.check_position_type(
        historical_data, 0
    )
    
    print(f"测试边界值30%:")
    print(f"  位置类型: {position_type}")
    print(f"  回撤幅度: {retracement}%")
    print(f"  预期: 低位（>= 30%）")
    
    assert position_type == "低位", f"预期位置类型为'低位'，实际为'{position_type}'"
    assert retracement == 30.0, f"预期回撤幅度为30.0%，实际为{retracement}%"
    print("✓ 边界值30%测试通过\n")


def test_check_position_type_boundary_10():
    """测试边界值：回撤正好10%"""
    # 构造测试数据：当前价格为9元，60日最高价为10元
    # 回撤幅度 = (10 - 9) / 10 * 100 = 10%
    historical_data = []
    
    # 当前日期数据（索引0）
    historical_data.append({
        'close': 9.0,
        'high': 9.5
    })
    
    # 后续59天的数据，最高价为10元
    for i in range(59):
        historical_data.append({
            'close': 9.0,
            'high': 10.0 if i == 0 else 9.5
        })
    
    position_type, retracement = OneYangThreeLinesStrategy.check_position_type(
        historical_data, 0
    )
    
    print(f"测试边界值10%:")
    print(f"  位置类型: {position_type}")
    print(f"  回撤幅度: {retracement}%")
    print(f"  预期: 中位（>= 10%）")
    
    assert position_type == "中位", f"预期位置类型为'中位'，实际为'{position_type}'"
    assert retracement == 10.0, f"预期回撤幅度为10.0%，实际为{retracement}%"
    print("✓ 边界值10%测试通过\n")


def test_check_position_type_insufficient_data():
    """测试数据不足的情况"""
    # 只提供30天的数据，不足60天
    historical_data = []
    
    for i in range(30):
        historical_data.append({
            'close': 9.0 + i * 0.01,
            'high': 10.0
        })
    
    position_type, retracement = OneYangThreeLinesStrategy.check_position_type(
        historical_data, 0
    )
    
    print(f"测试数据不足:")
    print(f"  位置类型: {position_type}")
    print(f"  回撤幅度: {retracement}%")
    print(f"  预期: 未知, 0.0%")
    
    assert position_type == "未知", f"预期位置类型为'未知'，实际为'{position_type}'"
    assert retracement == 0.0, f"预期回撤幅度为0.0%，实际为{retracement}%"
    print("✓ 数据不足测试通过\n")


def test_check_position_type_current_is_highest():
    """测试当前价格就是60日最高价的情况"""
    # 当前价格为10元，也是60日最高价
    # 回撤幅度 = (10 - 10) / 10 * 100 = 0%
    historical_data = []
    
    # 当前日期数据（索引0）
    historical_data.append({
        'close': 10.0,
        'high': 10.0
    })
    
    # 后续59天的数据，最高价都低于10元
    for i in range(59):
        historical_data.append({
            'close': 9.0,
            'high': 9.5
        })
    
    position_type, retracement = OneYangThreeLinesStrategy.check_position_type(
        historical_data, 0
    )
    
    print(f"测试当前价格为最高价:")
    print(f"  位置类型: {position_type}")
    print(f"  回撤幅度: {retracement}%")
    print(f"  预期: 高位, 0.0%")
    
    assert position_type == "高位", f"预期位置类型为'高位'，实际为'{position_type}'"
    assert retracement == 0.0, f"预期回撤幅度为0.0%，实际为{retracement}%"
    print("✓ 当前价格为最高价测试通过\n")


if __name__ == "__main__":
    print("=" * 60)
    print("开始测试位置判别功能")
    print("=" * 60 + "\n")
    
    try:
        test_check_position_type_low()
        test_check_position_type_mid()
        test_check_position_type_high()
        test_check_position_type_boundary_30()
        test_check_position_type_boundary_10()
        test_check_position_type_insufficient_data()
        test_check_position_type_current_is_highest()
        
        print("=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
