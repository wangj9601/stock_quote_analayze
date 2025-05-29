#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json

def test_login():
    """测试用户登录功能"""
    api_url = 'http://localhost:5000/api/auth/login'
    
    # 测试用例
    test_cases = [
        {'username': 'test123', 'password': '123456', 'expected': True},
        {'username': 'testuser', 'password': 'password123', 'expected': False},  # 密码可能不对
        {'username': 'nonexist', 'password': '123456', 'expected': False},  # 用户不存在
    ]
    
    print("🔍 测试用户登录API...")
    
    for i, test in enumerate(test_cases, 1):
        try:
            response = requests.post(api_url, json={
                'username': test['username'],
                'password': test['password']
            })
            
            result = response.json()
            
            print(f"\n📝 测试用例 {i}:")
            print(f"   用户名: {test['username']}")
            print(f"   密码: {test['password']}")
            print(f"   响应状态: {response.status_code}")
            print(f"   响应内容: {result}")
            
            if result.get('success'):
                print(f"   ✅ 登录成功")
            else:
                print(f"   ❌ 登录失败: {result.get('message', '未知错误')}")
                
        except Exception as e:
            print(f"   ❌ 请求失败: {e}")

def test_backend_status():
    """测试后端服务状态"""
    try:
        response = requests.get('http://localhost:5000/api/admin/stats')
        if response.status_code == 200:
            print("✅ 后端服务正常运行")
            return True
        else:
            print(f"❌ 后端服务异常: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 无法连接后端服务: {e}")
        return False

if __name__ == '__main__':
    print("🚀 开始测试登录修复...")
    
    if test_backend_status():
        test_login()
    else:
        print("❌ 后端服务未启动，请先启动后端服务")
        print("🔧 启动命令: cd backend && python app_fixed.py") 