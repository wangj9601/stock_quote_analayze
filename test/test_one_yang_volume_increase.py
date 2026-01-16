"""
测试一阳穿三线策略的成交量验证功能
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend_api.stock.one_yang_three_lines_strategy import OneYangThreeLinesStrategy


def test_check_volume_increase_basic():
    """测试基本的成交量放大判断"""
    # 构造测试数据：当日成交量是前5日平均值的2倍
    historical_data = [
        {'volume': 2000000, 'turnover_rate': 5.0},  # 当日，成交量2000000
        {'volume': 1000000, 'turnover_rate': 2.5},  # 前1日
        {'volume': 1000000, 'turnover_rate': 2.5},  # 前2日
        {'volume': 1000000, 'turnover_rate': 2.5},  # 前3日
        {'volume': 1000000, 'turnover_rate': 2.5},  # 前4日
        {'volume': 1000000, 'turnover_rate': 2.5},  # 前5日
    ]
    
    is_volume_increase, volume_ratio, turnover_rate = OneYangThreeLinesStrategy.check_volume_increase(
        historical_data, 0, 5
    )
    
    print(f"测试1 - 基本放量判断:")
    print(f"  是否放量: {is_volume_increase}")
    print(f"  成交量倍数: {volume_ratio}")
    print(f"  换手率: {turnover_rate}")
    print(f"  预期: 是否放量=True, 成交量倍数=2.0, 换手率=5.0")
    
    assert is_volume_increase == True, "应该判定为放量"
    assert volume_ratio == 2.0, f"成交量倍数应该是2.0，实际是{volume_ratio}"
    assert turnover_rate == 5.0, f"换手率应该是5.0，实际是{turnover_rate}"
    print("  ✓ 测试通过\n")


def test_check_volume_increase_not_enough():
    """测试成交量不足2倍的情况"""
    # 构造测试数据：当日成交量只有前5日平均值的1.5倍
    historical_data = [
        {'volume': 1500000, 'turnover_rate': 3.5},  # 当日，成交量1500000
        {'volume': 1000000, 'turnover_rate': 2.5},  # 前1日
        {'volume': 1000000, 'turnover_rate': 2.5},  # 前2日
        {'volume': 1000000, 'turnover_rate': 2.5},  # 前3日
        {'volume': 1000000, 'turnover_rate': 2.5},  # 前4日
        {'volume': 1000000, 'turnover_rate': 2.5},  # 前5日
    ]
    
    is_volume_increase, volume_ratio, turnover_rate = OneYangThreeLinesStrategy.check_volume_increase(
        historical_data, 0, 5
    )
    
    print(f"测试2 - 成交量不足2倍:")
    print(f"  是否放量: {is_volume_increase}")
    print(f"  成交量倍数: {volume_ratio}")
    print(f"  换手率: {turnover_rate}")
    print(f"  预期: 是否放量=False, 成交量倍数=1.5, 换手率=3.5")
    
    assert is_volume_increase == False, "不应该判定为放量"
    assert volume_ratio == 1.5, f"成交量倍数应该是1.5，实际是{volume_ratio}"
    assert turnover_rate == 3.5, f"换手率应该是3.5，实际是{turnover_rate}"
    print("  ✓ 测试通过\n")


def test_check_volume_increase_high_ratio():
    """测试成交量超过3倍的情况"""
    # 构造测试数据：当日成交量是前5日平均值的3.5倍
    historical_data = [
        {'volume': 3500000, 'turnover_rate': 8.0},  # 当日，成交量3500000
        {'volume': 1000000, 'turnover_rate': 2.5},  # 前1日
        {'volume': 1000000, 'turnover_rate': 2.5},  # 前2日
        {'volume': 1000000, 'turnover_rate': 2.5},  # 前3日
        {'volume': 1000000, 'turnover_rate': 2.5},  # 前4日
        {'volume': 1000000, 'turnover_rate': 2.5},  # 前5日
    ]
    
    is_volume_increase, volume_ratio, turnover_rate = OneYangThreeLinesStrategy.check_volume_increase(
        historical_data, 0, 5
    )
    
    print(f"测试3 - 成交量超过3倍:")
    print(f"  是否放量: {is_volume_increase}")
    print(f"  成交量倍数: {volume_ratio}")
    print(f"  换手率: {turnover_rate}")
    print(f"  预期: 是否放量=True, 成交量倍数=3.5, 换手率=8.0")
    
    assert is_volume_increase == True, "应该判定为放量"
    assert volume_ratio == 3.5, f"成交量倍数应该是3.5，实际是{volume_ratio}"
    assert turnover_rate == 8.0, f"换手率应该是8.0，实际是{turnover_rate}"
    print("  ✓ 测试通过\n")


def test_check_volume_increase_missing_turnover():
    """测试换手率缺失的情况"""
    # 构造测试数据：换手率为None
    historical_data = [
        {'volume': 2000000, 'turnover_rate': None},  # 当日，换手率缺失
        {'volume': 1000000, 'turnover_rate': 2.5},
        {'volume': 1000000, 'turnover_rate': 2.5},
        {'volume': 1000000, 'turnover_rate': 2.5},
        {'volume': 1000000, 'turnover_rate': 2.5},
        {'volume': 1000000, 'turnover_rate': 2.5},
    ]
    
    is_volume_increase, volume_ratio, turnover_rate = OneYangThreeLinesStrategy.check_volume_increase(
        historical_data, 0, 5
    )
    
    print(f"测试4 - 换手率缺失:")
    print(f"  是否放量: {is_volume_increase}")
    print(f"  成交量倍数: {volume_ratio}")
    print(f"  换手率: {turnover_rate}")
    print(f"  预期: 是否放量=True, 成交量倍数=2.0, 换手率=0.0")
    
    assert is_volume_increase == True, "应该判定为放量"
    assert volume_ratio == 2.0, f"成交量倍数应该是2.0，实际是{volume_ratio}"
    assert turnover_rate == 0.0, f"换手率应该是0.0（缺失时默认值），实际是{turnover_rate}"
    print("  ✓ 测试通过\n")


def test_check_volume_increase_invalid_data():
    """测试数据不足的情况"""
    # 构造测试数据：只有3天数据，不足以计算5日平均
    historical_data = [
        {'volume': 2000000, 'turnover_rate': 5.0},
        {'volume': 1000000, 'turnover_rate': 2.5},
        {'volume': 1000000, 'turnover_rate': 2.5},
    ]
    
    is_volume_increase, volume_ratio, turnover_rate = OneYangThreeLinesStrategy.check_volume_increase(
        historical_data, 0, 5
    )
    
    print(f"测试5 - 数据不足:")
    print(f"  是否放量: {is_volume_increase}")
    print(f"  成交量倍数: {volume_ratio}")
    print(f"  换手率: {turnover_rate}")
    print(f"  预期: 是否放量=False, 成交量倍数=0.0, 换手率=5.0")
    
    assert is_volume_increase == False, "数据不足时不应该判定为放量"
    assert volume_ratio == 0.0, f"成交量倍数应该是0.0，实际是{volume_ratio}"
    assert turnover_rate == 5.0, f"换手率应该是5.0，实际是{turnover_rate}"
    print("  ✓ 测试通过\n")


if __name__ == '__main__':
    print("=" * 60)
    print("测试一阳穿三线策略 - 成交量验证功能")
    print("=" * 60 + "\n")
    
    try:
        test_check_volume_increase_basic()
        test_check_volume_increase_not_enough()
        test_check_volume_increase_high_ratio()
        test_check_volume_increase_missing_turnover()
        test_check_volume_increase_invalid_data()
        
        print("=" * 60)
        print("所有测试通过！✓")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
