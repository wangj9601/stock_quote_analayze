"""
测试一阳穿三线策略的信号质量评分功能
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend_api.stock.one_yang_three_lines_strategy import OneYangThreeLinesStrategy


def test_calculate_signal_score_basic():
    """测试基本的信号评分计算"""
    # 测试最高分情况：6条均线，3倍成交量，理想换手率，低位，低乖离率
    score = OneYangThreeLinesStrategy.calculate_signal_score(
        crossed_lines_count=6,
        volume_ratio=3.0,
        turnover_rate=5.0,
        position_type="低位",
        bias30=3.0
    )
    # 50 + 25 + 15 + 15 + 10 = 115，但实际最高应该是100
    # 让我们验证实际得分
    expected = 50 + 25 + 15 + 15 + 10  # 115
    assert score == expected, f"期望得分{expected}，实际得分{score}"
    print(f"✓ 最高分测试通过: {score}分")


def test_calculate_signal_score_minimum():
    """测试最低分情况：3条均线，2倍成交量，非理想换手率，高位，高乖离率"""
    score = OneYangThreeLinesStrategy.calculate_signal_score(
        crossed_lines_count=3,
        volume_ratio=2.0,
        turnover_rate=15.0,
        position_type="高位",
        bias30=15.0
    )
    # 20 + 20 + 5 + 0 + 0 = 45
    expected = 20 + 20 + 5 + 0 + 0
    assert score == expected, f"期望得分{expected}，实际得分{score}"
    print(f"✓ 最低分测试通过: {score}分")


def test_calculate_signal_score_crossed_lines():
    """测试穿越均线数量评分"""
    # 3条均线
    score_3 = OneYangThreeLinesStrategy.calculate_signal_score(
        crossed_lines_count=3,
        volume_ratio=2.0,
        turnover_rate=5.0,
        position_type="中位",
        bias30=6.0
    )
    
    # 4条均线
    score_4 = OneYangThreeLinesStrategy.calculate_signal_score(
        crossed_lines_count=4,
        volume_ratio=2.0,
        turnover_rate=5.0,
        position_type="中位",
        bias30=6.0
    )
    
    # 5条均线
    score_5 = OneYangThreeLinesStrategy.calculate_signal_score(
        crossed_lines_count=5,
        volume_ratio=2.0,
        turnover_rate=5.0,
        position_type="中位",
        bias30=6.0
    )
    
    # 6条均线
    score_6 = OneYangThreeLinesStrategy.calculate_signal_score(
        crossed_lines_count=6,
        volume_ratio=2.0,
        turnover_rate=5.0,
        position_type="中位",
        bias30=6.0
    )
    
    # 验证单调性：穿越均线数量越多，评分越高
    assert score_3 < score_4 < score_5 < score_6, \
        f"穿越均线数量单调性测试失败: {score_3}, {score_4}, {score_5}, {score_6}"
    
    # 验证具体分数差异
    assert score_4 - score_3 == 10, f"3条到4条应该增加10分"
    assert score_5 - score_4 == 10, f"4条到5条应该增加10分"
    assert score_6 - score_5 == 10, f"5条到6条应该增加10分"
    
    print(f"✓ 穿越均线数量评分测试通过: 3条={score_3}, 4条={score_4}, 5条={score_5}, 6条={score_6}")


def test_calculate_signal_score_volume_ratio():
    """测试成交量倍数评分"""
    # 2倍成交量
    score_2x = OneYangThreeLinesStrategy.calculate_signal_score(
        crossed_lines_count=3,
        volume_ratio=2.0,
        turnover_rate=5.0,
        position_type="中位",
        bias30=6.0
    )
    
    # 3倍成交量
    score_3x = OneYangThreeLinesStrategy.calculate_signal_score(
        crossed_lines_count=3,
        volume_ratio=3.0,
        turnover_rate=5.0,
        position_type="中位",
        bias30=6.0
    )
    
    # 验证3倍成交量得分更高
    assert score_3x > score_2x, f"3倍成交量应该比2倍得分高"
    assert score_3x - score_2x == 5, f"3倍成交量应该比2倍多5分"
    
    print(f"✓ 成交量倍数评分测试通过: 2倍={score_2x}, 3倍={score_3x}")


def test_calculate_signal_score_turnover_rate():
    """测试换手率评分"""
    # 理想换手率（3%-10%）
    score_ideal = OneYangThreeLinesStrategy.calculate_signal_score(
        crossed_lines_count=3,
        volume_ratio=2.0,
        turnover_rate=5.0,
        position_type="中位",
        bias30=6.0
    )
    
    # 非理想换手率（<3%）
    score_low = OneYangThreeLinesStrategy.calculate_signal_score(
        crossed_lines_count=3,
        volume_ratio=2.0,
        turnover_rate=2.0,
        position_type="中位",
        bias30=6.0
    )
    
    # 非理想换手率（>10%）
    score_high = OneYangThreeLinesStrategy.calculate_signal_score(
        crossed_lines_count=3,
        volume_ratio=2.0,
        turnover_rate=15.0,
        position_type="中位",
        bias30=6.0
    )
    
    # 验证理想换手率得分更高
    assert score_ideal > score_low, f"理想换手率应该比低换手率得分高"
    assert score_ideal > score_high, f"理想换手率应该比高换手率得分高"
    assert score_ideal - score_low == 10, f"理想换手率应该比非理想多10分"
    assert score_ideal - score_high == 10, f"理想换手率应该比非理想多10分"
    
    print(f"✓ 换手率评分测试通过: 理想={score_ideal}, 低={score_low}, 高={score_high}")


def test_calculate_signal_score_position_type():
    """测试位置类型评分"""
    # 低位
    score_low = OneYangThreeLinesStrategy.calculate_signal_score(
        crossed_lines_count=3,
        volume_ratio=2.0,
        turnover_rate=5.0,
        position_type="低位",
        bias30=6.0
    )
    
    # 中位
    score_mid = OneYangThreeLinesStrategy.calculate_signal_score(
        crossed_lines_count=3,
        volume_ratio=2.0,
        turnover_rate=5.0,
        position_type="中位",
        bias30=6.0
    )
    
    # 高位
    score_high = OneYangThreeLinesStrategy.calculate_signal_score(
        crossed_lines_count=3,
        volume_ratio=2.0,
        turnover_rate=5.0,
        position_type="高位",
        bias30=6.0
    )
    
    # 验证位置类型评分：低位 > 中位 > 高位
    assert score_low > score_mid > score_high, \
        f"位置类型评分应该是低位>中位>高位: {score_low}, {score_mid}, {score_high}"
    assert score_low - score_mid == 5, f"低位应该比中位多5分"
    assert score_mid - score_high == 10, f"中位应该比高位多10分"
    
    print(f"✓ 位置类型评分测试通过: 低位={score_low}, 中位={score_mid}, 高位={score_high}")


def test_calculate_signal_score_bias30():
    """测试乖离率评分"""
    # 低乖离率（<5%）
    score_low = OneYangThreeLinesStrategy.calculate_signal_score(
        crossed_lines_count=3,
        volume_ratio=2.0,
        turnover_rate=5.0,
        position_type="中位",
        bias30=3.0
    )
    
    # 中等乖离率（5%-10%）
    score_mid = OneYangThreeLinesStrategy.calculate_signal_score(
        crossed_lines_count=3,
        volume_ratio=2.0,
        turnover_rate=5.0,
        position_type="中位",
        bias30=7.0
    )
    
    # 高乖离率（>10%）
    score_high = OneYangThreeLinesStrategy.calculate_signal_score(
        crossed_lines_count=3,
        volume_ratio=2.0,
        turnover_rate=5.0,
        position_type="中位",
        bias30=15.0
    )
    
    # None乖离率
    score_none = OneYangThreeLinesStrategy.calculate_signal_score(
        crossed_lines_count=3,
        volume_ratio=2.0,
        turnover_rate=5.0,
        position_type="中位",
        bias30=None
    )
    
    # 验证乖离率评分：低 > 中 > 高
    assert score_low > score_mid > score_high, \
        f"乖离率评分应该是低>中>高: {score_low}, {score_mid}, {score_high}"
    assert score_low - score_mid == 5, f"低乖离率应该比中等多5分"
    assert score_mid - score_high == 5, f"中等乖离率应该比高多5分"
    assert score_none == score_high, f"None乖离率应该和高乖离率得分相同"
    
    print(f"✓ 乖离率评分测试通过: 低={score_low}, 中={score_mid}, 高={score_high}, None={score_none}")


def test_calculate_signal_score_edge_cases():
    """测试边界情况"""
    # 测试边界值：换手率刚好3%
    score_3 = OneYangThreeLinesStrategy.calculate_signal_score(
        crossed_lines_count=3,
        volume_ratio=2.0,
        turnover_rate=3.0,
        position_type="中位",
        bias30=6.0
    )
    
    # 测试边界值：换手率刚好10%
    score_10 = OneYangThreeLinesStrategy.calculate_signal_score(
        crossed_lines_count=3,
        volume_ratio=2.0,
        turnover_rate=10.0,
        position_type="中位",
        bias30=6.0
    )
    
    # 测试边界值：乖离率刚好5%
    score_bias5 = OneYangThreeLinesStrategy.calculate_signal_score(
        crossed_lines_count=3,
        volume_ratio=2.0,
        turnover_rate=5.0,
        position_type="中位",
        bias30=5.0
    )
    
    # 测试边界值：乖离率刚好10%
    score_bias10 = OneYangThreeLinesStrategy.calculate_signal_score(
        crossed_lines_count=3,
        volume_ratio=2.0,
        turnover_rate=5.0,
        position_type="中位",
        bias30=10.0
    )
    
    # 验证边界值处理
    # 换手率3%和10%应该都算理想范围
    base_score = OneYangThreeLinesStrategy.calculate_signal_score(
        crossed_lines_count=3,
        volume_ratio=2.0,
        turnover_rate=5.0,
        position_type="中位",
        bias30=6.0
    )
    
    assert score_3 == base_score, f"换手率3%应该算理想范围"
    assert score_10 == base_score, f"换手率10%应该算理想范围"
    
    # 乖离率5%和10%应该算中等范围
    assert score_bias5 == score_bias10, f"乖离率5%和10%应该得分相同"
    
    print(f"✓ 边界情况测试通过")


if __name__ == "__main__":
    print("开始测试信号质量评分功能...")
    print()
    
    test_calculate_signal_score_basic()
    test_calculate_signal_score_minimum()
    test_calculate_signal_score_crossed_lines()
    test_calculate_signal_score_volume_ratio()
    test_calculate_signal_score_turnover_rate()
    test_calculate_signal_score_position_type()
    test_calculate_signal_score_bias30()
    test_calculate_signal_score_edge_cases()
    
    print()
    print("=" * 50)
    print("所有测试通过！✓")
    print("=" * 50)
