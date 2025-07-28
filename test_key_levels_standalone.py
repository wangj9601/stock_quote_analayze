#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import random
import numpy as np

class KeyLevels:
    """关键价位计算类"""
    
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
        """寻找支撑位"""
        support_levels = []
        
        # 1. 寻找重要低点（使用改进的极值检测算法）
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
        """寻找阻力位"""
        resistance_levels = []
        
        # 1. 寻找重要高点（使用改进的极值检测算法）
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
        """寻找重要低点（考虑成交量权重）"""
        significant_lows = []
        window_size = 5
        
        for i in range(window_size, len(lows) - window_size):
            is_local_min = all(lows[i] <= lows[j] for j in range(i - window_size, i + window_size + 1))
            
            if is_local_min and lows[i] < current_price:
                volume_weight = volumes[i] / max(volumes) if max(volumes) > 0 else 1
                if volume_weight > 0.5:
                    significant_lows.append(lows[i])
        
        return significant_lows
    
    @staticmethod
    def _find_significant_highs(highs, volumes, current_price):
        """寻找重要高点（考虑成交量权重）"""
        significant_highs = []
        window_size = 5
        
        for i in range(window_size, len(highs) - window_size):
            is_local_max = all(highs[i] >= highs[j] for j in range(i - window_size, i + window_size + 1))
            
            if is_local_max and highs[i] > current_price:
                volume_weight = volumes[i] / max(volumes) if max(volumes) > 0 else 1
                if volume_weight > 0.5:
                    significant_highs.append(highs[i])
        
        return significant_highs
    
    @staticmethod
    def _calculate_fibonacci_levels(high, low, current_price, is_support):
        """计算斐波那契回调位"""
        fib_levels = []
        diff = high - low
        fib_ratios = [0.236, 0.382, 0.5, 0.618, 0.786]
        
        for ratio in fib_ratios:
            if is_support:
                level = high - (diff * ratio)
                if low < level < current_price:
                    fib_levels.append(round(level, 2))
            else:
                level = low + (diff * ratio)
                if current_price < level < high:
                    fib_levels.append(round(level, 2))
        
        return fib_levels
    
    @staticmethod
    def _calculate_ma_support_levels(closes, current_price):
        """计算移动平均线支撑位"""
        ma_levels = []
        periods = [5, 10, 20, 50]
        
        for period in periods:
            if len(closes) >= period:
                ma = sum(closes[-period:]) / period
                if ma < current_price:
                    ma_levels.append(round(ma, 2))
        
        return ma_levels
    
    @staticmethod
    def _calculate_ma_resistance_levels(closes, current_price):
        """计算移动平均线阻力位"""
        ma_levels = []
        periods = [5, 10, 20, 50]
        
        for period in periods:
            if len(closes) >= period:
                ma = sum(closes[-period:]) / period
                if ma > current_price:
                    ma_levels.append(round(ma, 2))
        
        return ma_levels
    
    @staticmethod
    def _calculate_psychological_levels(current_price, is_support):
        """计算心理价位"""
        levels = []
        base = int(current_price)
        
        if is_support:
            # 支撑位：向下取整到整数和半整数
            for i in range(1, 6):
                level = base - i
                if level > 0:
                    levels.append(level)
                level = base - i + 0.5
                if level > 0:
                    levels.append(level)
        else:
            # 阻力位：向上取整到整数和半整数
            for i in range(1, 6):
                level = base + i
                levels.append(level)
                level = base + i - 0.5
                levels.append(level)
        
        return levels
    
    @staticmethod
    def _calculate_bollinger_support_levels(closes, current_price):
        """计算布林带下轨支撑位"""
        if len(closes) < 20:
            return []
        
        period = 20
        prices = closes[-period:]
        sma = sum(prices) / period
        
        # 计算标准差
        variance = sum((price - sma) ** 2 for price in prices) / period
        std_dev = variance ** 0.5
        
        lower_band = sma - (2 * std_dev)
        if lower_band < current_price:
            return [round(lower_band, 2)]
        
        return []
    
    @staticmethod
    def _calculate_bollinger_resistance_levels(closes, current_price):
        """计算布林带上轨阻力位"""
        if len(closes) < 20:
            return []
        
        period = 20
        prices = closes[-period:]
        sma = sum(prices) / period
        
        # 计算标准差
        variance = sum((price - sma) ** 2 for price in prices) / period
        std_dev = variance ** 0.5
        
        upper_band = sma + (2 * std_dev)
        if upper_band > current_price:
            return [round(upper_band, 2)]
        
        return []
    
    @staticmethod
    def _filter_and_sort_levels(levels, current_price, is_support):
        """过滤和排序价位"""
        if not levels:
            return []
        
        # 去重
        unique_levels = list(set(levels))
        
        # 过滤：支撑位必须小于当前价格，阻力位必须大于当前价格
        if is_support:
            filtered_levels = [level for level in unique_levels if level < current_price and level > 0]
            filtered_levels.sort(reverse=True)
        else:
            filtered_levels = [level for level in unique_levels if level > current_price]
            filtered_levels.sort()
        
        # 去除过于接近的价位
        final_levels = []
        min_distance = current_price * 0.01
        
        for level in filtered_levels:
            if not any(abs(level - existing) < min_distance for existing in final_levels):
                final_levels.append(round(level, 2))
        
        return final_levels

def generate_mock_data(current_price=43.30, days=60):
    """生成模拟历史数据"""
    data = []
    base_price = current_price
    
    for i in range(days):
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