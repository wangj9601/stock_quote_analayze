"""
测试一阳穿三线策略的乖离率计算功能
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend_api.stock.one_yang_three_lines_strategy import OneYangThreeLinesStrategy


def test_calculate_bias_normal():
    """测试正常情况下的乖离率计算"""
    print("\n=== 测试1: 正常情况下的乖离率计算 ===")
    
    # 准备测试数据
    current_price = 10.0
    ma_values = {
        'ma5': 9.5,
        'ma10': 9.0,
        'ma30': 8.5
    }
    
    # 调用方法
    bias_values = OneYangThreeLinesStrategy.calculate_bias(current_price, ma_values)
    
    # 验证结果
    print(f"当前价格: {current_price}")
    print(f"MA5: {ma_values['ma5']}, BIAS5: {bias_values['bias5']}")
    print(f"MA10: {ma_values['ma10']}, BIAS10: {bias_values['bias10']}")
    print(f"MA30: {ma_values['ma30']}, BIAS30: {bias_values['bias30']}")
    
    # 手动计算验证
    expected_bias5 = (10.0 - 9.5) / 9.5 * 100  # 5.26%
    expected_bias10 = (10.0 - 9.0) / 9.0 * 100  # 11.11%
    expected_bias30 = (10.0 - 8.5) / 8.5 * 100  # 17.65%
    
    print(f"\n预期 BIAS5: {expected_bias5:.2f}%, 实际: {bias_values['bias5']}%")
    print(f"预期 BIAS10: {expected_bias10:.2f}%, 实际: {bias_values['bias10']}%")
    print(f"预期 BIAS30: {expected_bias30:.2f}%, 实际: {bias_values['bias30']}%")
    
    # 断言
    assert bias_values['bias5'] == round(expected_bias5, 2), f"BIAS5计算错误"
    assert bias_values['bias10'] == round(expected_bias10, 2), f"BIAS10计算错误"
    assert bias_values['bias30'] == round(expected_bias30, 2), f"BIAS30计算错误"
    
    print("✓ 测试通过")


def test_calculate_bias_negative():
    """测试负乖离率（价格低于均线）"""
    print("\n=== 测试2: 负乖离率（价格低于均线） ===")
    
    # 准备测试数据
    current_price = 8.0
    ma_values = {
        'ma5': 9.0,
        'ma10': 9.5,
        'ma30': 10.0
    }
    
    # 调用方法
    bias_values = OneYangThreeLinesStrategy.calculate_bias(current_price, ma_values)
    
    # 验证结果
    print(f"当前价格: {current_price}")
    print(f"MA5: {ma_values['ma5']}, BIAS5: {bias_values['bias5']}")
    print(f"MA10: {ma_values['ma10']}, BIAS10: {bias_values['bias10']}")
    print(f"MA30: {ma_values['ma30']}, BIAS30: {bias_values['bias30']}")
    
    # 手动计算验证
    expected_bias5 = (8.0 - 9.0) / 9.0 * 100  # -11.11%
    expected_bias10 = (8.0 - 9.5) / 9.5 * 100  # -15.79%
    expected_bias30 = (8.0 - 10.0) / 10.0 * 100  # -20.00%
    
    print(f"\n预期 BIAS5: {expected_bias5:.2f}%, 实际: {bias_values['bias5']}%")
    print(f"预期 BIAS10: {expected_bias10:.2f}%, 实际: {bias_values['bias10']}%")
    print(f"预期 BIAS30: {expected_bias30:.2f}%, 实际: {bias_values['bias30']}%")
    
    # 断言
    assert bias_values['bias5'] == round(expected_bias5, 2), f"BIAS5计算错误"
    assert bias_values['bias10'] == round(expected_bias10, 2), f"BIAS10计算错误"
    assert bias_values['bias30'] == round(expected_bias30, 2), f"BIAS30计算错误"
    
    # 验证都是负值
    assert bias_values['bias5'] < 0, "BIAS5应该为负值"
    assert bias_values['bias10'] < 0, "BIAS10应该为负值"
    assert bias_values['bias30'] < 0, "BIAS30应该为负值"
    
    print("✓ 测试通过")


def test_calculate_bias_high_bias30():
    """测试BIAS30>10%的情况（需要风险提示）"""
    print("\n=== 测试3: BIAS30>10%的情况 ===")
    
    # 准备测试数据
    current_price = 12.0
    ma_values = {
        'ma5': 11.5,
        'ma10': 11.0,
        'ma30': 10.0  # BIAS30 = (12-10)/10*100 = 20%
    }
    
    # 调用方法
    bias_values = OneYangThreeLinesStrategy.calculate_bias(current_price, ma_values)
    
    # 验证结果
    print(f"当前价格: {current_price}")
    print(f"MA30: {ma_values['ma30']}, BIAS30: {bias_values['bias30']}")
    
    # 验证BIAS30大于10%
    assert bias_values['bias30'] > 10, f"BIAS30应该大于10%，实际为{bias_values['bias30']}%"
    
    print(f"✓ BIAS30 = {bias_values['bias30']}% > 10%，需要风险提示")
    print("✓ 测试通过")


def test_calculate_bias_invalid_price():
    """测试无效价格的处理"""
    print("\n=== 测试4: 无效价格的处理 ===")
    
    ma_values = {
        'ma5': 10.0,
        'ma10': 9.5,
        'ma30': 9.0
    }
    
    # 测试None价格
    bias_values = OneYangThreeLinesStrategy.calculate_bias(None, ma_values)
    assert bias_values['bias5'] is None, "None价格应返回None"
    assert bias_values['bias10'] is None, "None价格应返回None"
    assert bias_values['bias30'] is None, "None价格应返回None"
    print("✓ None价格处理正确")
    
    # 测试0价格
    bias_values = OneYangThreeLinesStrategy.calculate_bias(0, ma_values)
    assert bias_values['bias5'] is None, "0价格应返回None"
    assert bias_values['bias10'] is None, "0价格应返回None"
    assert bias_values['bias30'] is None, "0价格应返回None"
    print("✓ 0价格处理正确")
    
    # 测试负价格
    bias_values = OneYangThreeLinesStrategy.calculate_bias(-10.0, ma_values)
    assert bias_values['bias5'] is None, "负价格应返回None"
    assert bias_values['bias10'] is None, "负价格应返回None"
    assert bias_values['bias30'] is None, "负价格应返回None"
    print("✓ 负价格处理正确")
    
    print("✓ 测试通过")


def test_calculate_bias_invalid_ma():
    """测试无效均线值的处理"""
    print("\n=== 测试5: 无效均线值的处理 ===")
    
    current_price = 10.0
    
    # 测试None均线
    ma_values = {
        'ma5': None,
        'ma10': 9.5,
        'ma30': 9.0
    }
    bias_values = OneYangThreeLinesStrategy.calculate_bias(current_price, ma_values)
    assert bias_values['bias5'] is None, "None均线应返回None"
    assert bias_values['bias10'] is not None, "有效均线应返回计算结果"
    assert bias_values['bias30'] is not None, "有效均线应返回计算结果"
    print("✓ None均线处理正确")
    
    # 测试0均线
    ma_values = {
        'ma5': 10.0,
        'ma10': 0,
        'ma30': 9.0
    }
    bias_values = OneYangThreeLinesStrategy.calculate_bias(current_price, ma_values)
    assert bias_values['bias5'] is not None, "有效均线应返回计算结果"
    assert bias_values['bias10'] is None, "0均线应返回None"
    assert bias_values['bias30'] is not None, "有效均线应返回计算结果"
    print("✓ 0均线处理正确")
    
    # 测试负均线
    ma_values = {
        'ma5': 10.0,
        'ma10': 9.5,
        'ma30': -9.0
    }
    bias_values = OneYangThreeLinesStrategy.calculate_bias(current_price, ma_values)
    assert bias_values['bias5'] is not None, "有效均线应返回计算结果"
    assert bias_values['bias10'] is not None, "有效均线应返回计算结果"
    assert bias_values['bias30'] is None, "负均线应返回None"
    print("✓ 负均线处理正确")
    
    print("✓ 测试通过")


def test_calculate_bias_formula():
    """测试乖离率公式的正确性"""
    print("\n=== 测试6: 乖离率公式验证 ===")
    
    # 测试用例1: 价格等于均线
    current_price = 10.0
    ma_values = {
        'ma5': 10.0,
        'ma10': 10.0,
        'ma30': 10.0
    }
    bias_values = OneYangThreeLinesStrategy.calculate_bias(current_price, ma_values)
    assert bias_values['bias5'] == 0.0, "价格等于均线时，乖离率应为0"
    assert bias_values['bias10'] == 0.0, "价格等于均线时，乖离率应为0"
    assert bias_values['bias30'] == 0.0, "价格等于均线时，乖离率应为0"
    print("✓ 价格等于均线时，乖离率为0")
    
    # 测试用例2: 价格高于均线5%
    current_price = 10.5
    ma_values = {
        'ma5': 10.0,
        'ma10': 10.0,
        'ma30': 10.0
    }
    bias_values = OneYangThreeLinesStrategy.calculate_bias(current_price, ma_values)
    expected_bias = (10.5 - 10.0) / 10.0 * 100  # 5%
    assert bias_values['bias5'] == round(expected_bias, 2), f"乖离率应为{expected_bias:.2f}%"
    print(f"✓ 价格高于均线5%时，乖离率为{bias_values['bias5']}%")
    
    # 测试用例3: 价格低于均线10%
    current_price = 9.0
    ma_values = {
        'ma5': 10.0,
        'ma10': 10.0,
        'ma30': 10.0
    }
    bias_values = OneYangThreeLinesStrategy.calculate_bias(current_price, ma_values)
    expected_bias = (9.0 - 10.0) / 10.0 * 100  # -10%
    assert bias_values['bias5'] == round(expected_bias, 2), f"乖离率应为{expected_bias:.2f}%"
    print(f"✓ 价格低于均线10%时，乖离率为{bias_values['bias5']}%")
    
    print("✓ 测试通过")


if __name__ == "__main__":
    print("开始测试乖离率计算功能...")
    
    try:
        test_calculate_bias_normal()
        test_calculate_bias_negative()
        test_calculate_bias_high_bias30()
        test_calculate_bias_invalid_price()
        test_calculate_bias_invalid_ma()
        test_calculate_bias_formula()
        
        print("\n" + "="*50)
        print("所有测试通过！✓")
        print("="*50)
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
