#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
独立的关键价位计算测试脚本
验证支撑位严格小于当前价格，阻力位严格大于当前价格
"""

import random
import numpy as np
from datetime import datetime, timedelta

class KeyLevels:
    """关键价位计算类（改进版）"""
    
    @staticmethod
    def calculate_key_levels(historical_data, current_price):
        """计算关键支撑阻力位"""
        if len(historical_data) < 20:
            return {
                "resistance_levels": [],
                "support_levels": [],
                "current_price": current_price
            }
        
        # 提取数据
        highs = [float(data['high']) for data in historical_data]
        lows = [float(data['low']) for data in historical_data]
        closes = [float(data['close']) for data in historical_data]
        volumes = [float(data.get('volume', 0)) for data in historical_data]
        
        # 计算支撑位（基于近期低点和重要价位）
        support_levels = KeyLevels._find_support_levels(lows, closes, volumes, current_price)
        
        # 计算阻力位（基于近期高点和重要价位）
        resistance_levels = KeyLevels._find_resistance_levels(highs, lows, closes, volumes, current_price)
        
        return {
            "resistance_levels": resistance_levels,
            "support_levels": support_levels,
            "current_price": current_price
        }
    
    @staticmethod
    def _find_support_levels(lows, closes, volumes, current_price):
        """寻找支撑位（改进版）"""
        support_levels = []
        
        # 1. 寻找重要低点
        significant_lows = KeyLevels._find_significant_lows(lows, volumes, current_price)
        support_levels.extend(significant_lows)
        
        # 2. 计算斐波那契回调位
        if len(closes) >= 20:
            recent_high = max(closes[-20:])
            recent_low = min(lows[-20:])
            fib_levels = KeyLevels._calculate_fibonacci_levels(recent_high, recent_low, current_price, is_support=True)
            support_levels.extend(fib_levels)
        
        # 3. 添加移动平均线支撑位
        ma_levels = KeyLevels._calculate_ma_support_levels(closes, current_price)
        support_levels.extend(ma_levels)
        
        # 4. 添加心理支撑位
        psychological_levels = KeyLevels._calculate_psychological_levels(current_price, is_support=True)
        support_levels.extend(psychological_levels)
        
        # 5. 添加布林带下轨支撑位
        bb_levels = KeyLevels._calculate_bollinger_support_levels(closes, current_price)
        support_levels.extend(bb_levels)
        
        # 去重、过滤和排序
        support_levels = KeyLevels._filter_and_sort_levels(support_levels, current_price, is_support=True)
        
        return support_levels[:3]
    
    @staticmethod
    def _find_resistance_levels(highs, lows, closes, volumes, current_price):
        """寻找阻力位（改进版）"""
        resistance_levels = []
        
        # 1. 寻找重要高点
        significant_highs = KeyLevels._find_significant_highs(highs, volumes, current_price)
        resistance_levels.extend(significant_highs)
        
        # 2. 计算斐波那契回调位
        if len(closes) >= 20:
            recent_high = max(highs[-20:])
            recent_low = min(lows[-20:])
            fib_levels = KeyLevels._calculate_fibonacci_levels(recent_high, recent_low, current_price, is_support=False)
            resistance_levels.extend(fib_levels)
        
        # 3. 添加移动平均线阻力位
        ma_levels = KeyLevels._calculate_ma_resistance_levels(closes, current_price)
        resistance_levels.extend(ma_levels)
        
        # 4. 添加心理阻力位
        psychological_levels = KeyLevels._calculate_psychological_levels(current_price, is_support=False)
        resistance_levels.extend(psychological_levels)
        
        # 5. 添加布林带上轨阻力位
        bb_levels = KeyLevels._calculate_bollinger_resistance_levels(closes, current_price)
        resistance_levels.extend(bb_levels)
        
        # 去重、过滤和排序
        resistance_levels = KeyLevels._filter_and_sort_levels(resistance_levels, current_price, is_support=False)
        
        return resistance_levels[:3]
    
    @staticmethod
    def _find_significant_lows(lows, volumes, current_price):
        """寻找重要低点（改进版）"""
        significant_lows = []
        window_size = 3
        
        for i in range(window_size, len(lows) - window_size):
            # 检查是否为局部最低点
            is_local_min = all(lows[i] <= lows[j] for j in range(i - window_size, i + window_size + 1))
            
            # 支撑位必须严格小于当前价格
            if is_local_min and lows[i] < current_price and lows[i] > 0:
                # 计算成交量权重
                avg_volume = sum(volumes) / len(volumes) if volumes else 0
                volume_weight = volumes[i] / avg_volume if avg_volume > 0 else 1
                
                # 只有成交量较大的低点才被认为是重要的
                if volume_weight > 0.8:
                    # 避免过于接近的低点
                    if not any(abs(lows[i] - existing) < current_price * 0.02 for existing in significant_lows):
                        significant_lows.append(round(lows[i], 2))
        
        return significant_lows
    
    @staticmethod
    def _find_significant_highs(highs, volumes, current_price):
        """寻找重要高点（改进版）"""
        significant_highs = []
        window_size = 3
        
        for i in range(window_size, len(highs) - window_size):
            # 检查是否为局部最高点
            is_local_max = all(highs[i] >= highs[j] for j in range(i - window_size, i + window_size + 1))
            
            # 阻力位必须严格大于当前价格
            if is_local_max and highs[i] > current_price:
                # 计算成交量权重
                avg_volume = sum(volumes) / len(volumes) if volumes else 0
                volume_weight = volumes[i] / avg_volume if avg_volume > 0 else 1
                
                # 只有成交量较大的高点才被认为是重要的
                if volume_weight > 0.8:
                    # 避免过于接近的高点
                    if not any(abs(highs[i] - existing) < current_price * 0.02 for existing in significant_highs):
                        significant_highs.append(round(highs[i], 2))
        
        return significant_highs
    
    @staticmethod
    def _calculate_fibonacci_levels(high, low, current_price, is_support):
        """计算斐波那契回调位（改进版）"""
        fib_levels = []
        diff = high - low
        
        # 如果高低点差距太小，不计算斐波那契位
        if diff < current_price * 0.05:
            return fib_levels
        
        # 斐波那契回调比例
        fib_ratios = [0.236, 0.382, 0.5, 0.618, 0.786]
        
        for ratio in fib_ratios:
            if is_support:
                level = high - (diff * ratio)
                # 支撑位必须严格小于当前价格，且大于最低点
                if low < level < current_price:
                    fib_levels.append(round(level, 2))
            else:
                level = low + (diff * ratio)
                # 阻力位必须严格大于当前价格，且小于最高点
                if current_price < level < high:
                    fib_levels.append(round(level, 2))
        
        return fib_levels
    
    @staticmethod
    def _calculate_ma_support_levels(closes, current_price):
        """计算移动平均线支撑位（改进版）"""
        ma_levels = []
        
        # 计算多个周期的移动平均线
        ma_periods = [5, 10, 20, 30, 60]
        
        for period in ma_periods:
            if len(closes) >= period:
                ma = sum(closes[-period:]) / period
                # 支撑位必须严格小于当前价格，且为正数
                if ma < current_price and ma > 0:
                    # 只添加距离当前价格不太远的移动平均线
                    if current_price - ma <= current_price * 0.15:
                        ma_levels.append(round(ma, 2))
        
        return ma_levels
    
    @staticmethod
    def _calculate_ma_resistance_levels(closes, current_price):
        """计算移动平均线阻力位（改进版）"""
        ma_levels = []
        
        # 计算多个周期的移动平均线
        ma_periods = [5, 10, 20, 30, 60]
        
        for period in ma_periods:
            if len(closes) >= period:
                ma = sum(closes[-period:]) / period
                # 阻力位必须严格大于当前价格
                if ma > current_price:
                    # 只添加距离当前价格不太远的移动平均线
                    if ma - current_price <= current_price * 0.15:
                        ma_levels.append(round(ma, 2))
        
        return ma_levels
    
    @staticmethod
    def _calculate_psychological_levels(current_price, is_support):
        """计算心理价位（改进版）"""
        psychological_levels = []
        
        # 获取价格的整数部分
        integer_part = int(current_price)
        
        if is_support:
            # 支撑位：严格小于当前价格的心理价位
            # 从当前价格整数部分减1开始，向下寻找
            for i in range(integer_part - 1, max(0, integer_part - 15), -1):
                # 添加整数价位
                if i > 0:
                    psychological_levels.append(float(i))
                
                # 添加半整数价位
                half_level = i + 0.5
                if half_level > 0 and half_level < current_price:
                    psychological_levels.append(half_level)
        else:
            # 阻力位：严格大于当前价格的心理价位
            # 从当前价格整数部分加1开始，向上寻找
            for i in range(integer_part + 1, integer_part + 15):
                # 添加整数价位
                psychological_levels.append(float(i))
                
                # 添加半整数价位
                half_level = i - 0.5
                if half_level > current_price:
                    psychological_levels.append(half_level)
        
        return psychological_levels
    
    @staticmethod
    def _calculate_bollinger_support_levels(closes, current_price):
        """计算布林带支撑位（改进版）"""
        if len(closes) < 20:
            return []
        
        # 计算20日移动平均线
        ma20 = sum(closes[-20:]) / 20
        
        # 计算标准差
        variance = sum((price - ma20) ** 2 for price in closes[-20:]) / 20
        std = variance ** 0.5
        
        # 布林带下轨
        lower_band = ma20 - (2 * std)
        
        if lower_band < current_price and lower_band > 0:
            return [round(lower_band, 2)]
        
        return []
    
    @staticmethod
    def _calculate_bollinger_resistance_levels(closes, current_price):
        """计算布林带阻力位（改进版）"""
        if len(closes) < 20:
            return []
        
        # 计算20日移动平均线
        ma20 = sum(closes[-20:]) / 20
        
        # 计算标准差
        variance = sum((price - ma20) ** 2 for price in closes[-20:]) / 20
        std = variance ** 0.5
        
        # 布林带上轨
        upper_band = ma20 + (2 * std)
        
        if upper_band > current_price:
            return [round(upper_band, 2)]
        
        return []
    
    @staticmethod
    def _filter_and_sort_levels(levels, current_price, is_support):
        """过滤和排序价位（改进版）"""
        if not levels:
            return []
        
        # 去重
        unique_levels = list(set(levels))
        
        # 过滤：支撑位必须严格小于当前价格，阻力位必须严格大于当前价格
        if is_support:
            filtered_levels = [level for level in unique_levels if level < current_price and level > 0]
            # 支撑位按降序排列（从高到低，最接近当前价格的在前）
            filtered_levels.sort(reverse=True)
        else:
            filtered_levels = [level for level in unique_levels if level > current_price]
            # 阻力位按升序排列（从低到高，最接近当前价格的在前）
            filtered_levels.sort()
        
        # 去除过于接近的价位
        final_levels = []
        min_distance = current_price * 0.015  # 最小距离为当前价格的1.5%
        
        for level in filtered_levels:
            if not any(abs(level - existing) < min_distance for existing in final_levels):
                final_levels.append(round(level, 2))
        
        # 限制返回的价位数量
        max_levels = 5
        return final_levels[:max_levels]

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