#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的关键价位计算测试脚本
"""

import numpy as np
from datetime import datetime, timedelta

class KeyLevels:
    """关键价位分析类"""
    
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
        resistance_levels = KeyLevels._find_resistance_levels(highs, closes, volumes, current_price)
        
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
            # 从收盘价中估算高低点
            recent_high = max(closes[-20:])
            recent_low = min(closes[-20:])
            fib_levels = KeyLevels._calculate_fibonacci_levels(recent_high, recent_low, current_price, is_support=True)
            support_levels.extend(fib_levels)
        
        # 3. 添加移动平均线支撑位
        ma_levels = KeyLevels._calculate_ma_support_levels(closes, current_price)
        support_levels.extend(ma_levels)
        
        # 4. 添加心理支撑位（改进版）
        psychological_levels = KeyLevels._calculate_psychological_levels(current_price, is_support=True)
        support_levels.extend(psychological_levels)
        
        # 5. 添加布林带下轨支撑位
        bb_levels = KeyLevels._calculate_bollinger_support_levels(closes, current_price)
        support_levels.extend(bb_levels)
        
        # 去重、过滤和排序
        support_levels = KeyLevels._filter_and_sort_levels(support_levels, current_price, is_support=True)
        
        return support_levels[:3]
    
    @staticmethod
    def _find_resistance_levels(highs, closes, volumes, current_price):
        """寻找阻力位"""
        resistance_levels = []
        
        # 1. 寻找重要高点（使用改进的极值检测算法）
        significant_highs = KeyLevels._find_significant_highs(highs, volumes, current_price)
        resistance_levels.extend(significant_highs)
        
        # 2. 计算斐波那契回调位
        if len(closes) >= 20:
            # 从收盘价中估算高低点
            recent_high = max(closes[-20:])
            recent_low = min(closes[-20:])
            fib_levels = KeyLevels._calculate_fibonacci_levels(recent_high, recent_low, current_price, is_support=False)
            resistance_levels.extend(fib_levels)
        
        # 3. 添加移动平均线阻力位
        ma_levels = KeyLevels._calculate_ma_resistance_levels(closes, current_price)
        resistance_levels.extend(ma_levels)
        
        # 4. 添加心理阻力位（改进版）
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
        window_size = 5  # 滑动窗口大小
        
        for i in range(window_size, len(lows) - window_size):
            # 检查是否为局部最低点
            is_local_min = all(lows[i] <= lows[j] for j in range(i - window_size, i + window_size + 1))
            
            if is_local_min and lows[i] < current_price:
                # 计算成交量权重
                volume_weight = volumes[i] / max(volumes) if max(volumes) > 0 else 1
                
                # 只有成交量较大的低点才被认为是重要的
                if volume_weight > 0.5:  # 成交量超过平均值的50%
                    significant_lows.append(lows[i])
        
        return significant_lows
    
    @staticmethod
    def _find_significant_highs(highs, volumes, current_price):
        """寻找重要高点（考虑成交量权重）"""
        significant_highs = []
        window_size = 5  # 滑动窗口大小
        
        for i in range(window_size, len(highs) - window_size):
            # 检查是否为局部最高点
            is_local_max = all(highs[i] >= highs[j] for j in range(i - window_size, i + window_size + 1))
            
            if is_local_max and highs[i] > current_price:
                # 计算成交量权重
                volume_weight = volumes[i] / max(volumes) if max(volumes) > 0 else 1
                
                # 只有成交量较大的高点才被认为是重要的
                if volume_weight > 0.5:  # 成交量超过平均值的50%
                    significant_highs.append(highs[i])
        
        return significant_highs
    
    @staticmethod
    def _calculate_fibonacci_levels(high, low, current_price, is_support):
        """计算斐波那契回调位"""
        fib_levels = []
        diff = high - low
        
        # 斐波那契回调比例
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
        
        # 计算多个周期的移动平均线
        ma_periods = [5, 10, 20, 50]
        
        for period in ma_periods:
            if len(closes) >= period:
                ma = sum(closes[-period:]) / period
                if ma < current_price and ma > 0:
                    ma_levels.append(round(ma, 2))
        
        return ma_levels
    
    @staticmethod
    def _calculate_ma_resistance_levels(closes, current_price):
        """计算移动平均线阻力位"""
        ma_levels = []
        
        # 计算多个周期的移动平均线
        ma_periods = [5, 10, 20, 50]
        
        for period in ma_periods:
            if len(closes) >= period:
                ma = sum(closes[-period:]) / period
                if ma > current_price:
                    ma_levels.append(round(ma, 2))
        
        return ma_levels
    
    @staticmethod
    def _calculate_psychological_levels(current_price, is_support):
        """计算心理价位（改进版）"""
        psychological_levels = []
        
        # 获取价格的整数部分和小数部分
        integer_part = int(current_price)
        decimal_part = current_price - integer_part
        
        if is_support:
            # 支撑位：向下寻找心理价位
            for i in range(integer_part, max(0, integer_part - 10), -1):
                # 添加整数价位
                psychological_levels.append(float(i))
                
                # 添加半整数价位（如 10.5, 9.5）
                half_level = i - 0.5
                if half_level > 0:
                    psychological_levels.append(half_level)
        else:
            # 阻力位：向上寻找心理价位
            for i in range(integer_part + 1, integer_part + 11):
                # 添加整数价位
                psychological_levels.append(float(i))
                
                # 添加半整数价位（如 11.5, 12.5）
                half_level = i + 0.5
                psychological_levels.append(half_level)
        
        return psychological_levels
    
    @staticmethod
    def _calculate_bollinger_support_levels(closes, current_price):
        """计算布林带支撑位"""
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
        """计算布林带阻力位"""
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
        """过滤和排序价位"""
        if not levels:
            return []
        
        # 去重
        unique_levels = list(set(levels))
        
        # 过滤：支撑位必须小于当前价格，阻力位必须大于当前价格
        if is_support:
            filtered_levels = [level for level in unique_levels if level < current_price and level > 0]
            # 支撑位按降序排列（从高到低）
            filtered_levels.sort(reverse=True)
        else:
            filtered_levels = [level for level in unique_levels if level > current_price]
            # 阻力位按升序排列（从低到高）
            filtered_levels.sort()
        
        # 去除过于接近的价位（避免重复）
        final_levels = []
        min_distance = current_price * 0.01  # 最小距离为当前价格的1%
        
        for level in filtered_levels:
            if not any(abs(level - existing) < min_distance for existing in final_levels):
                final_levels.append(round(level, 2))
        
        return final_levels

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

if __name__ == "__main__":
    test_key_levels_calculation() 