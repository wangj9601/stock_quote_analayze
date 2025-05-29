#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import time

def test_frontend_backend():
    """测试前后端连接"""
    print("=== 全面系统检查 ===")
    
    # 1. 测试后端API
    print("\n1. 检查后端API (5000端口)")
    try:
        r = requests.get('http://localhost:5000/api/auth/status', timeout=5)
        print(f"  ✅ 后端状态码: {r.status_code}")
        print(f"  ✅ 后端响应: {r.json()}")
    except Exception as e:
        print(f"  ❌ 后端连接失败: {e}")
        return
    
    # 2. 测试前端服务 (8000端口)
    print("\n2. 检查前端服务 (8000端口)")
    try:
        r = requests.get('http://localhost:8000/login.html', timeout=5)
        print(f"  ✅ 前端状态码: {r.status_code}")
        print(f"  ✅ Content-Type: {r.headers.get('Content-Type', 'N/A')}")
        if r.status_code == 200:
            if 'html' in r.headers.get('Content-Type', '').lower():
                print("  ✅ 前端HTML正常返回")
            else:
                print("  ⚠️ 返回的不是HTML内容")
    except Exception as e:
        print(f"  ❌ 前端连接失败: {e}")
        
    # 3. 测试前端服务 (8001端口，如果存在)
    print("\n3. 检查前端服务 (8001端口)")
    try:
        r = requests.get('http://localhost:8001/login.html', timeout=5)
        print(f"  ✅ 前端8001状态码: {r.status_code}")
    except Exception as e:
        print(f"  ❌ 前端8001连接失败: {e}")
    
    # 4. 测试CORS - 模拟浏览器登录请求
    print("\n4. 测试CORS和登录API")
    try:
        # 模拟浏览器请求头
        headers = {
            'Origin': 'http://localhost:8000',
            'Content-Type': 'application/json',
            'Referer': 'http://localhost:8000/login.html'
        }
        login_data = {
            'username': 'testuser',
            'password': 'testpass'
        }
        r = requests.post('http://localhost:5000/api/auth/login', 
                         json=login_data, headers=headers, timeout=5)
        print(f"  ✅ 跨域登录状态码: {r.status_code}")
        print(f"  ✅ CORS头: {r.headers.get('Access-Control-Allow-Origin', 'N/A')}")
        print(f"  ✅ 登录响应: {r.json()}")
    except Exception as e:
        print(f"  ❌ 跨域登录失败: {e}")
    
    # 5. 检查静态文件
    print("\n5. 检查关键静态文件")
    static_files = [
        '/js/login.js',
        '/css/login.css',
        '/css/common.css'
    ]
    
    for file_path in static_files:
        try:
            r = requests.get(f'http://localhost:8000{file_path}', timeout=5)
            if r.status_code == 200:
                print(f"  ✅ {file_path}: OK")
            else:
                print(f"  ❌ {file_path}: {r.status_code}")
        except Exception as e:
            print(f"  ❌ {file_path}: {e}")
    
    print("\n=== 检查完成 ===")
    print("如果前后端都正常，请在浏览器访问：")
    print("  登录页面: http://localhost:8000/login.html")
    print("  首页: http://localhost:8000/index.html")

if __name__ == "__main__":
    test_frontend_backend() 