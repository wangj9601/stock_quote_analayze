#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json

def test_api_call():
    """测试API调用"""
    print("=" * 60)
    print("API调用调试测试")
    print("=" * 60)
    
    # 测试股票代码（使用一个常见的股票代码）
    stock_code = "000001"  # 平安银行
    
    try:
        # 调用智能分析API
        url = f"http://localhost:8000/api/stock/analysis/{stock_code}"
        print(f"调用API: {url}")
        
        response = requests.get(url, timeout=10)
        print(f"响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"响应数据:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # 检查关键价位数据
            if 'data' in data and 'key_levels' in data['data']:
                key_levels = data['data']['key_levels']
                current_price = data['data'].get('current_price', 0)
                
                print(f"\n" + "=" * 40)
                print("关键价位分析:")
                print("=" * 40)
                print(f"当前价格: {current_price}")
                print(f"阻力位: {key_levels.get('resistance_levels', [])}")
                print(f"支撑位: {key_levels.get('support_levels', [])}")
                
                # 验证结果
                resistance_levels = key_levels.get('resistance_levels', [])
                support_levels = key_levels.get('support_levels', [])
                
                print(f"\n验证结果:")
                resistance_valid = all(level > current_price for level in resistance_levels)
                support_valid = all(level < current_price for level in support_levels)
                
                print(f"阻力位验证: {'✓' if resistance_valid else '✗'}")
                if not resistance_valid:
                    print(f"  问题阻力位: {[level for level in resistance_levels if level <= current_price]}")
                
                print(f"支撑位验证: {'✓' if support_valid else '✗'}")
                if not support_valid:
                    print(f"  问题支撑位: {[level for level in support_levels if level >= current_price]}")
            else:
                print("响应中没有找到key_levels数据")
        else:
            print(f"API调用失败: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"请求异常: {e}")
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
    except Exception as e:
        print(f"其他错误: {e}")

if __name__ == "__main__":
    test_api_call() 