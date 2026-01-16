"""
测试一阳穿三线策略的移动平均线计算功能
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend_api.stock.one_yang_three_lines_strategy import OneYangThreeLinesStrategy


def test_calculate_moving_averages_basic():
    """测试基本的移动平均线计算"""
    # 创建测试数据：10个交易日的收盘价
    historical_data = [
        {'date': '2025-01-16', 'close': 10.0},  # 最新
        {'date': '2025-01-15', 'close': 9.5},
        {'date': '2025-01-14', 'close': 9.0},
        {'date': '2025-01-13', 'close': 8.5},
        {'date': '2025-01-10', 'close': 8.0},
        {'date': '2025-01-09', 'close': 7.5},
        {'date': '2025-01-08', 'close': 7.0},
        {'date': '2025-01-07', 'close': 6.5},
        {'date': '2025-01-06', 'close': 6.0},
        {'date': '2025-01-03', 'close': 5.5},
    ]
    
    # 计算移动平均线
    ma_values = OneYangThreeLinesStrategy.calculate_moving_averages(historical_data, current_index=0)
    
    # 验证MA5：(10.0 + 9.5 + 9.0 + 8.5 + 8.0) / 5 = 9.0
    expected_ma5 = (10.0 + 9.5 + 9.0 + 8.5 + 8.0) / 5
    assert ma_values['ma5'] is not None, "MA5不应为None"
    assert abs(ma_values['ma5'] - expected_ma5) < 0.01, f"MA5计算错误，期望{expected_ma5}，实际{ma_values['ma5']}"
    
    # 验证MA10：所有10个价格的平均值
    expected_ma10 = sum([d['close'] for d in historical_data]) / 10
    assert ma_values['ma10'] is not None, "MA10不应为None"
    assert abs(ma_values['ma10'] - expected_ma10) < 0.01, f"MA10计算错误，期望{expected_ma10}，实际{ma_values['ma10']}"
    
    # MA20应该为None（数据不足）
    assert ma_values['ma20'] is None, "MA20应该为None（数据不足）"
    assert ma_values['ma30'] is None, "MA30应该为None（数据不足）"
    assert ma_values['ma60'] is None, "MA60应该为None（数据不足）"
    assert ma_values['ma120'] is None, "MA120应该为None（数据不足）"
    
    print("✓ 基本移动平均线计算测试通过")


def test_calculate_moving_averages_with_sufficient_data():
    """测试有足够数据时的移动平均线计算"""
    # 创建130个交易日的测试数据
    historical_data = []
    for i in range(130):
        historical_data.append({
            'date': f'2025-01-{i:02d}',
            'close': 10.0 + i * 0.1  # 递增的价格
        })
    
    # 计算移动平均线
    ma_values = OneYangThreeLinesStrategy.calculate_moving_averages(historical_data, current_index=0)
    
    # 所有均线都应该有值
    assert ma_values['ma5'] is not None, "MA5不应为None"
    assert ma_values['ma10'] is not None, "MA10不应为None"
    assert ma_values['ma20'] is not None, "MA20不应为None"
    assert ma_values['ma30'] is not None, "MA30不应为None"
    assert ma_values['ma60'] is not None, "MA60不应为None"
    assert ma_values['ma120'] is not None, "MA120不应为None"
    
    # 验证MA5的计算
    expected_ma5 = sum([10.0 + i * 0.1 for i in range(5)]) / 5
    assert abs(ma_values['ma5'] - expected_ma5) < 0.01, f"MA5计算错误"
    
    print("✓ 充足数据的移动平均线计算测试通过")


def test_calculate_moving_averages_with_different_index():
    """测试使用不同索引位置计算移动平均线"""
    # 创建20个交易日的测试数据
    historical_data = []
    for i in range(20):
        historical_data.append({
            'date': f'2025-01-{i:02d}',
            'close': 10.0 + i
        })
    
    # 从索引5开始计算（即第6个交易日）
    ma_values = OneYangThreeLinesStrategy.calculate_moving_averages(historical_data, current_index=5)
    
    # 验证MA5：从索引5开始的5个价格
    expected_ma5 = sum([10.0 + i for i in range(5, 10)]) / 5
    assert ma_values['ma5'] is not None, "MA5不应为None"
    assert abs(ma_values['ma5'] - expected_ma5) < 0.01, f"MA5计算错误，期望{expected_ma5}，实际{ma_values['ma5']}"
    
    print("✓ 不同索引位置的移动平均线计算测试通过")


def test_calculate_moving_averages_with_invalid_data():
    """测试包含无效数据的情况"""
    historical_data = [
        {'date': '2025-01-16', 'close': 10.0},
        {'date': '2025-01-15', 'close': None},  # 无效数据
        {'date': '2025-01-14', 'close': 9.0},
        {'date': '2025-01-13', 'close': 8.5},
        {'date': '2025-01-10', 'close': 8.0},
    ]
    
    # 计算移动平均线
    ma_values = OneYangThreeLinesStrategy.calculate_moving_averages(historical_data, current_index=0)
    
    # 由于有无效数据，MA5应该为None
    assert ma_values['ma5'] is None, "MA5应该为None（包含无效数据）"
    
    print("✓ 无效数据处理测试通过")


if __name__ == '__main__':
    print("开始测试移动平均线计算功能...")
    print()
    
    test_calculate_moving_averages_basic()
    test_calculate_moving_averages_with_sufficient_data()
    test_calculate_moving_averages_with_different_index()
    test_calculate_moving_averages_with_invalid_data()
    
    print()
    print("=" * 50)
    print("所有测试通过！✓")
    print("=" * 50)
