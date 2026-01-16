"""
一阳穿三线策略的属性测试
使用hypothesis框架进行基于属性的测试

Feature: one-yang-three-lines-strategy
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from hypothesis import given, strategies as st, settings
from backend_api.stock.one_yang_three_lines_strategy import OneYangThreeLinesStrategy


# 属性1: 移动平均线计算正确性
# Feature: one-yang-three-lines-strategy, Property 1: 对于任意股票的历史价格数据和任意周期N(5,10,20,30,60,120),计算的N日移动平均线应该等于最近N个交易日收盘价的算术平均值
# 验证: 需求 2.1-2.7
@settings(max_examples=100)
@given(
    # 生成130-200个交易日的价格数据（确保能计算所有周期的MA）
    prices=st.lists(
        st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        min_size=130,
        max_size=200
    ),
    # 选择一个周期进行测试
    period=st.sampled_from([5, 10, 20, 30, 60, 120])
)
def test_property_ma_calculation_correctness(prices, period):
    """
    属性1: 移动平均线计算正确性
    
    对于任意股票的历史价格数据和任意周期N(5,10,20,30,60,120),
    计算的N日移动平均线应该等于最近N个交易日收盘价的算术平均值
    
    验证: 需求 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7
    """
    # 构造历史数据（倒序，最新在前）
    historical_data = [
        {'date': f'2025-01-{i:02d}', 'close': price}
        for i, price in enumerate(prices)
    ]
    
    # 计算移动平均线
    ma_values = OneYangThreeLinesStrategy.calculate_moving_averages(
        historical_data, 
        current_index=0
    )
    
    # 获取对应周期的MA值
    ma_key = f'ma{period}'
    calculated_ma = ma_values[ma_key]
    
    # MA值不应该为None（因为我们提供了足够的数据）
    assert calculated_ma is not None, f"MA{period}不应为None，数据量为{len(prices)}"
    
    # 手动计算期望的MA值：最近N个交易日收盘价的算术平均值
    # historical_data是倒序的，所以取前period个
    expected_ma = sum(prices[:period]) / period
    
    # 验证计算结果（允许小的浮点误差）
    assert abs(calculated_ma - expected_ma) < 0.01, \
        f"MA{period}计算错误: 期望{expected_ma:.4f}, 实际{calculated_ma:.4f}, 差异{abs(calculated_ma - expected_ma):.6f}"


if __name__ == '__main__':
    print("开始运行属性测试...")
    print("=" * 60)
    print("属性1: 移动平均线计算正确性")
    print("验证: 需求 2.1-2.7")
    print("=" * 60)
    print()
    
    # 运行属性测试
    test_property_ma_calculation_correctness()
    
    print()
    print("=" * 60)
    print("✓ 属性测试通过！")
    print("=" * 60)
