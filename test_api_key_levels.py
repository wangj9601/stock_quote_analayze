#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试后端API关键价位计算
验证支撑位严格小于当前价格，阻力位严格大于当前价格
"""

import requests
import json
import sys
import os

# 添加后端API路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend_api'))

def test_api_key_levels():
    """测试API关键价位计算"""
    print("=== 测试后端API关键价位计算 ===\n")
    
    # API基础URL
    base_url = "http://localhost:8000"
    
    # 测试股票代码
    test_stocks = [
        "000001",  # 平安银行
        "000002",  # 万科A
        "600000",  # 浦发银行
    ]
    
    for stock_code in test_stocks:
        print(f"测试股票: {stock_code}")
        
        try:
            # 调用智能分析API
            url = f"{base_url}/api/analysis/stock/{stock_code}"
            print(f"请求URL: {url}")
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('success'):
                    key_levels = data['data']['key_levels']
                    current_price = data['data']['current_price']
                    
                    print(f"当前价格: {current_price}")
                    print(f"支撑位: {key_levels['support_levels']}")
                    print(f"阻力位: {key_levels['resistance_levels']}")
                    
                    # 验证支撑位严格小于当前价格
                    support_valid = all(level < current_price for level in key_levels['support_levels'])
                    print(f"支撑位验证: {'✓ 通过' if support_valid else '✗ 失败'}")
                    
                    # 验证阻力位严格大于当前价格
                    resistance_valid = all(level > current_price for level in key_levels['resistance_levels'])
                    print(f"阻力位验证: {'✓ 通过' if resistance_valid else '✗ 失败'}")
                    
                    if not support_valid or not resistance_valid:
                        print("❌ 发现问题！")
                        if not support_valid:
                            invalid_supports = [level for level in key_levels['support_levels'] if level >= current_price]
                            print(f"  无效支撑位: {invalid_supports}")
                        if not resistance_valid:
                            invalid_resistances = [level for level in key_levels['resistance_levels'] if level <= current_price]
                            print(f"  无效阻力位: {invalid_resistances}")
                    else:
                        print("✅ 验证通过！")
                        
                else:
                    print(f"API返回失败: {data.get('message', '未知错误')}")
                    
            else:
                print(f"HTTP请求失败: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"请求异常: {e}")
        except Exception as e:
            print(f"其他异常: {e}")
            
        print("\n" + "-"*50 + "\n")

def test_standalone_key_levels():
    """测试独立的关键价位计算"""
    print("=== 测试独立的关键价位计算 ===\n")
    
    try:
        # 导入改进后的计算模块
        from stock.stock_analysis import KeyLevels
        import random
        from datetime import datetime, timedelta
        
        def generate_test_data(current_price=6.80, days=60):
            """生成测试数据"""
            data = []
            base_price = current_price
            
            for i in range(days):
                change_percent = random.uniform(-0.05, 0.05)
                close_price = base_price * (1 + change_percent)
                
                high = close_price * random.uniform(1.0, 1.03)
                low = close_price * random.uniform(0.97, 1.0)
                open_price = close_price * random.uniform(0.98, 1.02)
                
                high = max(high, open_price, close_price)
                low = min(low, open_price, close_price)
                
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
        
        # 测试多个价格点
        test_prices = [6.80, 12.34, 25.67, 156.80]
        
        for current_price in test_prices:
            print(f"测试当前价格: {current_price}")
            
            historical_data = generate_test_data(current_price, 60)
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
            
            if not support_valid or not resistance_valid:
                print("❌ 发现问题！")
            else:
                print("✅ 验证通过！")
                
            print("\n" + "-"*30 + "\n")
            
    except ImportError as e:
        print(f"导入模块失败: {e}")
        print("请确保在正确的目录下运行此脚本")
    except Exception as e:
        print(f"测试异常: {e}")

if __name__ == "__main__":
    print("开始测试关键价位计算...\n")
    
    # 测试独立计算
    test_standalone_key_levels()
    
    # 测试API（如果后端服务运行中）
    print("是否要测试API？(y/n): ", end="")
    try:
        choice = input().strip().lower()
        if choice == 'y':
            test_api_key_levels()
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    
    print("测试完成！") 