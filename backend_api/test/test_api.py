#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json

def test_apis():
    """测试API接口"""
    base_url = "http://localhost:5000"
    
    print("=== 测试后端API ===")
    
    # 测试注册
    print("\n1. 测试用户注册")
    try:
        register_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpass'
        }
        r = requests.post(f'{base_url}/api/auth/register', json=register_data)
        print(f"注册状态码: {r.status_code}")
        print(f"注册响应: {r.json()}")
    except Exception as e:
        print(f"注册失败: {e}")
    
    # 测试登录
    print("\n2. 测试用户登录")
    try:
        login_data = {
            'username': 'testuser',
            'password': 'testpass'
        }
        r = requests.post(f'{base_url}/api/auth/login', json=login_data)
        print(f"登录状态码: {r.status_code}")
        print(f"登录响应: {r.json()}")
    except Exception as e:
        print(f"登录失败: {e}")
    
    # 测试指数数据
    print("\n3. 测试指数数据")
    try:
        r = requests.get(f'{base_url}/api/market/indices')
        print(f"指数数据状态码: {r.status_code}")
        data = r.json()
        if data['success']:
            print("指数数据:")
            for index in data['data']:
                print(f"  {index['name']}: {index['current']} ({index['change']:+.2f}, {index['change_percent']:+.2f}%)")
        else:
            print(f"获取指数数据失败: {data}")
    except Exception as e:
        print(f"获取指数数据失败: {e}")
    
    # 测试自选股
    print("\n4. 测试自选股数据")
    try:
        r = requests.get(f'{base_url}/api/watchlist')
        print(f"自选股状态码: {r.status_code}")
        data = r.json()
        if data['success']:
            print("自选股数据:")
            for stock in data['data']:
                print(f"  {stock['name']} ({stock['code']}): {stock['current_price']} ({stock['change_percent']:+.2f}%)")
        else:
            print(f"获取自选股数据失败: {data}")
    except Exception as e:
        print(f"获取自选股数据失败: {e}")

if __name__ == "__main__":
    test_apis() 