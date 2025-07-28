#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append('backend_api')

from stock.stock_analysis import KeyLevels
import random

def generate_mock_data(current_price=43.30, days=60):
    """生成模拟历史数据"""
    data = []
    base_price = current_price
    
    for i in range(days):
        # 生成合理的价格波动
        change = random.uniform(-0.05, 0.05) * base_price
        open_price = base_price + change
        high_price = open_price + random.uniform(0, 0.03) * open_price
        low_price = open_price - random.uniform(0, 0.03) * open_price
        close_price = random.uniform(low_price, high_price)
        volume = random.uniform(1000000, 5000000)
        
        data.append({
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': volume
        })
        
        base_price = close_price
    
    return data

def test_key_levels_calculation():
    """测试关键价位计算"""
    print("=" * 60)
    print("关键价位计算调试测试")
    print("=" * 60)
    
    current_price = 43.30
    print(f"当前价格: {current_price}")
    
    # 生成模拟数据
    historical_data = generate_mock_data(current_price)
    print(f"历史数据天数: {len(historical_data)}")
    
    # 提取数据
    highs = [float(data['high']) for data in historical_data]
    lows = [float(data['low']) for data in historical_data]
    closes = [float(data['close']) for data in historical_data]
    volumes = [float(data['volume']) for data in historical_data]
    
    print(f"\n数据范围:")
    print(f"最高价: {max(highs):.2f}")
    print(f"最低价: {min(lows):.2f}")
    print(f"收盘价范围: {min(closes):.2f} - {max(closes):.2f}")
    
    # 测试各个计算方法
    print(f"\n" + "=" * 40)
    print("测试各个计算方法:")
    print("=" * 40)
    
    # 1. 测试重要高点
    significant_highs = KeyLevels._find_significant_highs(highs, volumes, current_price)
    print(f"重要高点: {significant_highs}")
    
    # 2. 测试重要低点
    significant_lows = KeyLevels._find_significant_lows(lows, volumes, current_price)
    print(f"重要低点: {significant_lows}")
    
    # 3. 测试斐波那契计算
    if len(closes) >= 20:
        recent_high = max(highs[-20:])
        recent_low = min(lows[-20:])
        print(f"斐波那契计算范围: 低点={recent_low:.2f}, 高点={recent_high:.2f}")
        
        fib_resistance = KeyLevels._calculate_fibonacci_levels(recent_high, recent_low, current_price, is_support=False)
        fib_support = KeyLevels._calculate_fibonacci_levels(recent_high, recent_low, current_price, is_support=True)
        print(f"斐波那契阻力位: {fib_resistance}")
        print(f"斐波那契支撑位: {fib_support}")
    
    # 4. 测试移动平均线
    ma_resistance = KeyLevels._calculate_ma_resistance_levels(closes, current_price)
    ma_support = KeyLevels._calculate_ma_support_levels(closes, current_price)
    print(f"移动平均线阻力位: {ma_resistance}")
    print(f"移动平均线支撑位: {ma_support}")
    
    # 5. 测试心理价位
    psych_resistance = KeyLevels._calculate_psychological_levels(current_price, is_support=False)
    psych_support = KeyLevels._calculate_psychological_levels(current_price, is_support=True)
    print(f"心理阻力位: {psych_resistance}")
    print(f"心理支撑位: {psych_support}")
    
    # 6. 测试布林带
    bb_resistance = KeyLevels._calculate_bollinger_resistance_levels(closes, current_price)
    bb_support = KeyLevels._calculate_bollinger_support_levels(closes, current_price)
    print(f"布林带阻力位: {bb_resistance}")
    print(f"布林带支撑位: {bb_support}")
    
    # 7. 测试完整计算
    print(f"\n" + "=" * 40)
    print("完整计算结果:")
    print("=" * 40)
    
    result = KeyLevels.calculate_key_levels(historical_data, current_price)
    
    print(f"阻力位: {result['resistance_levels']}")
    print(f"支撑位: {result['support_levels']}")
    print(f"当前价格: {result['current_price']}")
    
    # 验证结果
    print(f"\n" + "=" * 40)
    print("验证结果:")
    print("=" * 40)
    
    resistance_levels = result['resistance_levels']
    support_levels = result['support_levels']
    
    # 验证阻力位
    resistance_valid = all(level > current_price for level in resistance_levels)
    print(f"阻力位验证: {'✓' if resistance_valid else '✗'} (所有阻力位应大于当前价格)")
    if not resistance_valid:
        print(f"  问题阻力位: {[level for level in resistance_levels if level <= current_price]}")
    
    # 验证支撑位
    support_valid = all(level < current_price for level in support_levels)
    print(f"支撑位验证: {'✓' if support_valid else '✗'} (所有支撑位应小于当前价格)")
    if not support_valid:
        print(f"  问题支撑位: {[level for level in support_levels if level >= current_price]}")
    
    # 验证排序
    resistance_sorted = resistance_levels == sorted(resistance_levels)
    support_sorted = support_levels == sorted(support_levels, reverse=True)
    print(f"阻力位排序: {'✓' if resistance_sorted else '✗'} (阻力位应按升序排列)")
    print(f"支撑位排序: {'✓' if support_sorted else '✗'} (支撑位应按降序排列)")
    
    # 验证数量
    count_valid = len(resistance_levels) <= 3 and len(support_levels) <= 3
    print(f"价位数量: {'✓' if count_valid else '✗'} (最多3个价位)")
    
    print(f"\n测试完成!")

if __name__ == "__main__":
    test_key_levels_calculation() 