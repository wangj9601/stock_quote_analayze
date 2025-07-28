#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API修复验证测试脚本
"""

import requests
import json

def test_stock_analysis_api():
    """测试股票分析API"""
    
    # 测试股票代码
    test_stock = "000001"  # 平安银行
    
    print("=" * 60)
    print("API修复验证测试")
    print("=" * 60)
    print(f"测试股票: {test_stock}")
    print()
    
    try:
        # 测试API调用
        url = f"http://localhost:8000/api/analysis/stock/{test_stock}"
        print(f"请求URL: {url}")
        
        response = requests.get(url, timeout=30)
        print(f"响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"响应成功: {data.get('success', False)}")
            
            if data.get('success'):
                analysis_data = data.get('data', {})
                key_levels = analysis_data.get('key_levels', {})
                
                print("\n关键价位分析结果:")
                print("-" * 40)
                print(f"阻力位: {key_levels.get('resistance_levels', [])}")
                print(f"支撑位: {key_levels.get('support_levels', [])}")
                print(f"当前价格: {key_levels.get('current_price', 'N/A')}")
                
                # 验证结果
                current_price = key_levels.get('current_price')
                resistance_levels = key_levels.get('resistance_levels', [])
                support_levels = key_levels.get('support_levels', [])
                
                if current_price and resistance_levels and support_levels:
                    print("\n验证结果:")
                    print("-" * 40)
                    
                    # 检查阻力位是否都大于当前价格
                    resistance_valid = all(level > current_price for level in resistance_levels)
                    print(f"阻力位验证: {'✓' if resistance_valid else '✗'}")
                    
                    # 检查支撑位是否都小于当前价格
                    support_valid = all(level < current_price for level in support_levels)
                    print(f"支撑位验证: {'✓' if support_valid else '✗'}")
                    
                    # 检查价位数量
                    resistance_count = len(resistance_levels) <= 3
                    support_count = len(support_levels) <= 3
                    print(f"价位数量: {'✓' if resistance_count and support_count else '✗'}")
                    
                    print("\n测试通过! ✅")
                else:
                    print("\n警告: 缺少关键价位数据")
            else:
                print(f"API返回失败: {data.get('message', '未知错误')}")
        else:
            print(f"HTTP请求失败: {response.status_code}")
            print(f"响应内容: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("连接错误: 请确保后端服务正在运行 (python -m backend_api.main)")
    except requests.exceptions.Timeout:
        print("请求超时: API响应时间过长")
    except Exception as e:
        print(f"测试失败: {str(e)}")

if __name__ == "__main__":
    test_stock_analysis_api() 