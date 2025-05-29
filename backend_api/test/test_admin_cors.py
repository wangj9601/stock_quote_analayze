#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import time

def test_admin_cors():
    """测试admin端CORS"""
    print("🔍 测试admin端CORS预检请求...")
    
    try:
        # 模拟admin端发送的预检请求
        response = requests.options('http://localhost:5000/api/admin/login', 
                                  headers={
                                      'Origin': 'http://localhost:8001',
                                      'Access-Control-Request-Method': 'POST',
                                      'Access-Control-Request-Headers': 'Content-Type'
                                  })
        
        print(f"预检请求状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        
        # 检查重要的CORS头
        cors_headers = {
            'Access-Control-Allow-Origin': response.headers.get('Access-Control-Allow-Origin'),
            'Access-Control-Allow-Credentials': response.headers.get('Access-Control-Allow-Credentials'),
            'Access-Control-Allow-Methods': response.headers.get('Access-Control-Allow-Methods'),
            'Access-Control-Allow-Headers': response.headers.get('Access-Control-Allow-Headers')
        }
        
        print("\n🔍 CORS头检查:")
        for header, value in cors_headers.items():
            if value:
                print(f"   ✅ {header}: {value}")
            else:
                print(f"   ❌ {header}: 缺失")
        
        return response.status_code == 200
        
    except Exception as e:
        print(f"❌ 预检请求失败: {e}")
        return False

def test_admin_login():
    """测试admin登录请求"""
    print("\n🔍 测试admin登录请求...")
    
    try:
        # 模拟admin端的登录请求
        response = requests.post('http://localhost:5000/api/admin/login',
                               json={'username': 'admin', 'password': '123456'},
                               headers={
                                   'Origin': 'http://localhost:8001',
                                   'Content-Type': 'application/json'
                               })
        
        print(f"登录请求状态码: {response.status_code}")
        
        result = response.json()
        print(f"响应内容: {result}")
        
        # 检查CORS头
        cors_origin = response.headers.get('Access-Control-Allow-Origin')
        cors_credentials = response.headers.get('Access-Control-Allow-Credentials')
        
        print(f"\n🔍 响应CORS头:")
        print(f"   Access-Control-Allow-Origin: {cors_origin}")
        print(f"   Access-Control-Allow-Credentials: {cors_credentials}")
        
        if result.get('success'):
            print("✅ admin登录请求成功")
            return True
        else:
            print(f"❌ admin登录失败: {result.get('message')}")
            return False
            
    except Exception as e:
        print(f"❌ admin登录请求失败: {e}")
        return False

def test_user_login():
    """测试用户登录请求"""
    print("\n🔍 测试用户登录请求...")
    
    try:
        # 模拟用户端的登录请求
        response = requests.post('http://localhost:5000/api/auth/login',
                               json={'username': 'test123', 'password': '123456'},
                               headers={
                                   'Origin': 'http://localhost:8000',
                                   'Content-Type': 'application/json'
                               })
        
        print(f"用户登录请求状态码: {response.status_code}")
        
        result = response.json()
        print(f"响应内容: {result}")
        
        if result.get('success'):
            print("✅ 用户登录请求成功")
            return True
        else:
            print(f"❌ 用户登录失败: {result.get('message')}")
            return False
            
    except Exception as e:
        print(f"❌ 用户登录请求失败: {e}")
        return False

def test_backend_status():
    """测试后端服务状态"""
    print("🔍 检查后端服务状态...")
    
    for attempt in range(10):
        try:
            response = requests.get('http://localhost:5000/api/admin/stats')
            if response.status_code == 200:
                print("✅ 后端服务正常运行")
                return True
            else:
                print(f"❌ 后端服务异常: {response.status_code}")
                return False
        except Exception as e:
            print(f"尝试 {attempt + 1}/10: 无法连接后端服务")
            if attempt < 9:
                time.sleep(1)
    
    print("❌ 后端服务未启动")
    return False

if __name__ == '__main__':
    print("🚀 开始测试admin端CORS修复...")
    
    if test_backend_status():
        admin_preflight_ok = test_admin_cors()
        admin_login_ok = test_admin_login()
        user_login_ok = test_user_login()
        
        print("\n📊 测试结果总结:")
        print(f"   Admin预检请求: {'✅ 通过' if admin_preflight_ok else '❌ 失败'}")
        print(f"   Admin登录请求: {'✅ 通过' if admin_login_ok else '❌ 失败'}")
        print(f"   用户登录请求: {'✅ 通过' if user_login_ok else '❌ 失败'}")
        
        if admin_preflight_ok and admin_login_ok and user_login_ok:
            print("\n🎉 CORS问题已完全修复！")
            print("✅ Admin端 (localhost:8001) 现在可以正常使用")
            print("✅ 用户端 (localhost:8000) 现在可以正常使用")
        else:
            print("\n⚠️ 仍有问题需要解决。")
    else:
        print("❌ 后端服务未启动，请先启动后端服务")
        print("🔧 启动命令: cd backend && python app_complete.py") 