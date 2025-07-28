#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
关键价位计算测试脚本
"""

import sys
import os
import numpy as np
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_key_levels_calculation():
    """测试关键价位计算"""
    
    # 模拟历史数据
    historical_data = []
    base_price = 30.0
    
    # 生成60天的模拟数据
    for i in range(60):
        date = datetime.now() - timedelta(days=60-i)
        
        # 模拟价格波动
        noise = np.random.normal(0, 0.5)
        trend = 0.1 * np.sin(i * 0.1)  # 添加一些趋势
        
        close_price = base_price + noise + trend
        high_price = close_price + abs(np.random.normal(0, 0.3))
        low_price = close_price - abs(np.random.normal(0, 0.3))
        open_price = close_price + np.random.normal(0, 0.2)
        volume = np.random.uniform(1000000, 5000000)
        
        historical_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'open': round(open_price, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'close': round(close_price, 2),
            'volume': round(volume, 0)
        })
    
    # 当前价格
    current_price = 30.15
    
    print("=" * 60)
    print("关键价位计算测试")
    print("=" * 60)
    print(f"当前价格: {current_price}")
    print(f"历史数据天数: {len(historical_data)}")
    print()
    
    try:
        # 导入KeyLevels类
        import sys
        sys.path.append('..')
        from stock.stock_analysis import KeyLevels
        
        # 计算关键价位
        result = KeyLevels.calculate_key_levels(historical_data, current_price)
        
        print("计算结果:")
        print("-" * 40)
        print(f"阻力位: {result['resistance_levels']}")
        print(f"支撑位: {result['support_levels']}")
        print(f"当前价格: {result['current_price']}")
        print()
        
        # 验证结果
        print("验证结果:")
        print("-" * 40)
        
        # 检查阻力位是否都大于当前价格
        resistance_valid = all(level > current_price for level in result['resistance_levels'])
        print(f"阻力位验证: {'✓' if resistance_valid else '✗'} (所有阻力位应大于当前价格)")
        
        # 检查支撑位是否都小于当前价格
        support_valid = all(level < current_price for level in result['support_levels'])
        print(f"支撑位验证: {'✓' if support_valid else '✗'} (所有支撑位应小于当前价格)")
        
        # 检查价位是否按正确顺序排列
        resistance_sorted = result['resistance_levels'] == sorted(result['resistance_levels'])
        print(f"阻力位排序: {'✓' if resistance_sorted else '✗'} (阻力位应按升序排列)")
        
        support_sorted = result['support_levels'] == sorted(result['support_levels'], reverse=True)
        print(f"支撑位排序: {'✓' if support_sorted else '✗'} (支撑位应按降序排列)")
        
        # 检查价位数量
        resistance_count = len(result['resistance_levels']) <= 3
        support_count = len(result['support_levels']) <= 3
        print(f"价位数量: {'✓' if resistance_count and support_count else '✗'} (最多3个价位)")
        
        print()
        print("测试完成!")
        
    except Exception as e:
        print(f"测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

def test_individual_methods():
    """测试各个计算方法"""
    
    print("=" * 60)
    print("各方法测试")
    print("=" * 60)
    
    try:
        import sys
        sys.path.append('..')
        from stock.stock_analysis import KeyLevels
        
        # 测试数据
        highs = [32.5, 31.8, 33.2, 30.9, 32.1, 31.5, 33.8, 32.3, 31.9, 33.5]
        lows = [30.2, 29.8, 30.5, 29.2, 30.8, 29.9, 31.2, 30.1, 29.5, 31.8]
        closes = [31.2, 30.5, 32.1, 30.1, 31.8, 30.8, 32.5, 31.2, 30.8, 32.2]
        volumes = [1000000, 1200000, 800000, 1500000, 900000, 1100000, 1300000, 950000, 1400000, 1000000]
        current_price = 31.5
        
        print(f"测试数据:")
        print(f"当前价格: {current_price}")
        print(f"最高价范围: {min(highs)} - {max(highs)}")
        print(f"最低价范围: {min(lows)} - {max(lows)}")
        print()
        
        # 测试重要低点检测
        significant_lows = KeyLevels._find_significant_lows(lows, volumes, current_price)
        print(f"重要低点: {significant_lows}")
        
        # 测试重要高点检测
        significant_highs = KeyLevels._find_significant_highs(highs, volumes, current_price)
        print(f"重要高点: {significant_highs}")
        
        # 测试斐波那契回调位
        recent_high = max(highs)
        recent_low = min(lows)
        fib_support = KeyLevels._calculate_fibonacci_levels(recent_high, recent_low, current_price, is_support=True)
        fib_resistance = KeyLevels._calculate_fibonacci_levels(recent_high, recent_low, current_price, is_support=False)
        print(f"斐波那契支撑位: {fib_support}")
        print(f"斐波那契阻力位: {fib_resistance}")
        
        # 测试移动平均线
        ma_support = KeyLevels._calculate_ma_support_levels(closes, current_price)
        ma_resistance = KeyLevels._calculate_ma_resistance_levels(closes, current_price)
        print(f"移动平均线支撑位: {ma_support}")
        print(f"移动平均线阻力位: {ma_resistance}")
        
        # 测试心理价位
        psych_support = KeyLevels._calculate_psychological_levels(current_price, is_support=True)
        psych_resistance = KeyLevels._calculate_psychological_levels(current_price, is_support=False)
        print(f"心理支撑位: {psych_support[:5]}...")  # 只显示前5个
        print(f"心理阻力位: {psych_resistance[:5]}...")  # 只显示前5个
        
        # 测试布林带
        bb_support = KeyLevels._calculate_bollinger_support_levels(closes, current_price)
        bb_resistance = KeyLevels._calculate_bollinger_resistance_levels(closes, current_price)
        print(f"布林带支撑位: {bb_support}")
        print(f"布林带阻力位: {bb_resistance}")
        
        print()
        print("各方法测试完成!")
        
    except Exception as e:
        print(f"方法测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_key_levels_calculation()
    print()
    test_individual_methods() 