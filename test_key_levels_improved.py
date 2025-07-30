#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
改进后的关键价位计算测试脚本
验证支撑位严格小于当前价格，阻力位严格大于当前价格
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend_api'))

from stock.stock_analysis import KeyLevels
import random
from datetime import datetime, timedelta

def generate_mock_data(current_price=43.30, days=60):
    """生成模拟历史数据"""
    data = []
    base_price = current_price
    
    for i in range(days):
        # 生成合理的价格波动
        change_percent = random.uniform(-0.05, 0.05)  # ±5%的波动
        close_price = base_price * (1 + change_percent)
        
        # 生成高低开收价格
        high = close_price * random.uniform(1.0, 1.03)
        low = close_price * random.uniform(0.97, 1.0)
        open_price = close_price * random.uniform(0.98, 1.02)
        
        # 确保高低开收的逻辑关系
        high = max(high, open_price, close_price)
        low = min(low, open_price, close_price)
        
        # 生成成交量
        volume = random.randint(1000000, 10000000)
        
        data.append({
            'date': (datetime.now() - timedelta(days=days-i-1)).strftime('%Y-%m-%d'),
            'open': round(open_price, 2),
            'high': round(high, 2),
            'low': round(low, 2),
            'close': round(close_price, 2),
            'volume': volume,
            'amount': round(volume * close_price, 2)
        })
        
        base_price = close_price
    
    return data

def test_key_levels_calculation():
    """测试关键价位计算"""
    print("=== 改进后的关键价位计算测试 ===\n")
    
    # 测试用例1：正常价格
    current_price = 43.30
    print(f"测试用例1 - 当前价格: {current_price}")
    historical_data = generate_mock_data(current_price, 60)
    
    result = KeyLevels.calculate_key_levels(historical_data, current_price)
    
    print(f"当前价格: {result['current_price']}")
    print(f"支撑位: {result['support_levels']}")
    print(f"阻力位: {result['resistance_levels']}")
    
    # 验证支撑位严格小于当前价格
    support_valid = all(level < current_price for level in result['support_levels'])
    print(f"支撑位验证: {'✓ 通过' if support_valid else '✗ 失败'}")
    
    # 验证阻力位严格大于当前价格
    resistance_valid = all(level > current_price for level in result['resistance_levels'])
    print(f"阻力位验证: {'✓ 通过' if resistance_valid else '✗ 失败'}")
    
    print("\n" + "="*50 + "\n")
    
    # 测试用例2：低价股票
    current_price = 8.75
    print(f"测试用例2 - 当前价格: {current_price}")
    historical_data = generate_mock_data(current_price, 60)
    
    result = KeyLevels.calculate_key_levels(historical_data, current_price)
    
    print(f"当前价格: {result['current_price']}")
    print(f"支撑位: {result['support_levels']}")
    print(f"阻力位: {result['resistance_levels']}")
    
    # 验证支撑位严格小于当前价格
    support_valid = all(level < current_price for level in result['support_levels'])
    print(f"支撑位验证: {'✓ 通过' if support_valid else '✗ 失败'}")
    
    # 验证阻力位严格大于当前价格
    resistance_valid = all(level > current_price for level in result['resistance_levels'])
    print(f"阻力位验证: {'✓ 通过' if resistance_valid else '✗ 失败'}")
    
    print("\n" + "="*50 + "\n")
    
    # 测试用例3：高价股票
    current_price = 156.80
    print(f"测试用例3 - 当前价格: {current_price}")
    historical_data = generate_mock_data(current_price, 60)
    
    result = KeyLevels.calculate_key_levels(historical_data, current_price)
    
    print(f"当前价格: {result['current_price']}")
    print(f"支撑位: {result['support_levels']}")
    print(f"阻力位: {result['resistance_levels']}")
    
    # 验证支撑位严格小于当前价格
    support_valid = all(level < current_price for level in result['support_levels'])
    print(f"支撑位验证: {'✓ 通过' if support_valid else '✗ 失败'}")
    
    # 验证阻力位严格大于当前价格
    resistance_valid = all(level > current_price for level in result['resistance_levels'])
    print(f"阻力位验证: {'✓ 通过' if resistance_valid else '✗ 失败'}")
    
    print("\n=== 测试完成 ===")

def test_edge_cases():
    """测试边界情况"""
    print("\n=== 边界情况测试 ===\n")
    
    # 测试用例：价格接近0
    current_price = 0.85
    print(f"边界测试 - 当前价格: {current_price}")
    historical_data = generate_mock_data(current_price, 60)
    
    result = KeyLevels.calculate_key_levels(historical_data, current_price)
    
    print(f"当前价格: {result['current_price']}")
    print(f"支撑位: {result['support_levels']}")
    print(f"阻力位: {result['resistance_levels']}")
    
    # 验证支撑位严格小于当前价格
    support_valid = all(level < current_price for level in result['support_levels'])
    print(f"支撑位验证: {'✓ 通过' if support_valid else '✗ 失败'}")
    
    # 验证阻力位严格大于当前价格
    resistance_valid = all(level > current_price for level in result['resistance_levels'])
    print(f"阻力位验证: {'✓ 通过' if resistance_valid else '✗ 失败'}")
    
    print("\n=== 边界测试完成 ===")

if __name__ == "__main__":
    test_key_levels_calculation()
    test_edge_cases() 