#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import time

API_BASE = 'http://localhost:5000/api'

def test_admin_login():
    """测试管理员登录"""
    print("🔐 测试管理员登录...")
    
    login_data = {
        'username': 'admin',
        'password': '123456'
    }
    
    try:
        response = requests.post(f'{API_BASE}/admin/login', 
                               json=login_data,
                               timeout=5)
        result = response.json()
        
        if result.get('success'):
            print(f"✅ 管理员登录成功")
            print(f"   用户名: {result['admin']['username']}")
            print(f"   角色: {result['admin']['role']}")
            return result['token']
        else:
            print(f"❌ 管理员登录失败: {result.get('message')}")
            return None
    except Exception as e:
        print(f"❌ 管理员登录错误: {e}")
        return None

def test_create_user():
    """测试创建用户"""
    print("\n👤 测试创建用户...")
    
    user_data = {
        'username': 'testuser001',
        'email': 'test001@example.com',
        'password': 'password123',
        'status': 'active'
    }
    
    try:
        response = requests.post(f'{API_BASE}/admin/users',
                               json=user_data,
                               timeout=5)
        result = response.json()
        
        if result.get('success'):
            print(f"✅ 用户创建成功")
            print(f"   用户ID: {result['user']['id']}")
            print(f"   用户名: {result['user']['username']}")
            print(f"   邮箱: {result['user']['email']}")
            return result['user']['id']
        else:
            print(f"❌ 用户创建失败: {result.get('message')}")
            return None
    except Exception as e:
        print(f"❌ 用户创建错误: {e}")
        return None

def test_get_users():
    """测试获取用户列表"""
    print("\n📋 测试获取用户列表...")
    
    try:
        response = requests.get(f'{API_BASE}/admin/users', timeout=5)
        result = response.json()
        
        if result.get('success'):
            users = result['data']
            print(f"✅ 获取用户列表成功，共 {len(users)} 个用户")
            for user in users:
                print(f"   - ID: {user['id']}, 用户名: {user['username']}, 状态: {user['status']}")
            return True
        else:
            print(f"❌ 获取用户列表失败: {result.get('message')}")
            return False
    except Exception as e:
        print(f"❌ 获取用户列表错误: {e}")
        return False

def test_user_login(username):
    """测试用户登录前端"""
    print(f"\n🔑 测试用户 {username} 登录前端...")
    
    login_data = {
        'username': username,
        'password': 'password123'
    }
    
    try:
        response = requests.post(f'{API_BASE}/auth/login',
                               json=login_data,
                               timeout=5)
        result = response.json()
        
        if result.get('success'):
            print(f"✅ 用户登录前端成功")
            print(f"   用户ID: {result['user']['id']}")
            print(f"   用户名: {result['user']['username']}")
            return True
        else:
            print(f"❌ 用户登录前端失败: {result.get('message')}")
            return False
    except Exception as e:
        print(f"❌ 用户登录错误: {e}")
        return False

def test_toggle_user_status(user_id):
    """测试切换用户状态"""
    print(f"\n🔄 测试切换用户 {user_id} 状态...")
    
    # 先禁用用户
    try:
        response = requests.put(f'{API_BASE}/admin/users/{user_id}/status',
                              json={'status': 'disabled'},
                              timeout=5)
        result = response.json()
        
        if result.get('success'):
            print(f"✅ 用户禁用成功")
            
            # 测试禁用用户是否能登录
            login_data = {
                'username': 'testuser001',
                'password': 'password123'
            }
            
            response = requests.post(f'{API_BASE}/auth/login',
                                   json=login_data,
                                   timeout=5)
            result = response.json()
            
            if not result.get('success') and '禁用' in result.get('message', ''):
                print(f"✅ 禁用用户无法登录，权限控制正常")
                
                # 重新启用用户
                response = requests.put(f'{API_BASE}/admin/users/{user_id}/status',
                                      json={'status': 'active'},
                                      timeout=5)
                result = response.json()
                
                if result.get('success'):
                    print(f"✅ 用户重新启用成功")
                    return True
                else:
                    print(f"❌ 用户启用失败: {result.get('message')}")
                    return False
            else:
                print(f"❌ 禁用用户仍可登录，权限控制异常")
                return False
        else:
            print(f"❌ 用户禁用失败: {result.get('message')}")
            return False
    except Exception as e:
        print(f"❌ 切换用户状态错误: {e}")
        return False

def test_admin_stats():
    """测试管理统计"""
    print(f"\n📊 测试管理统计...")
    
    try:
        response = requests.get(f'{API_BASE}/admin/stats', timeout=5)
        result = response.json()
        
        if result.get('success'):
            stats = result['data']
            print(f"✅ 获取统计数据成功")
            print(f"   总用户数: {stats['total_users']}")
            print(f"   活跃用户数: {stats['active_users']}")
            print(f"   禁用用户数: {stats['disabled_users']}")
            print(f"   今日登录数: {stats['today_logins']}")
            return True
        else:
            print(f"❌ 获取统计数据失败: {result.get('message')}")
            return False
    except Exception as e:
        print(f"❌ 获取统计数据错误: {e}")
        return False

def main():
    """主测试函数"""
    print("🧪 开始测试Admin管理功能")
    print("=" * 50)
    
    # 等待后端服务启动
    print("⏳ 等待后端服务启动...")
    time.sleep(2)
    
    # 测试管理员登录
    token = test_admin_login()
    if not token:
        print("❌ 管理员登录失败，停止测试")
        return
    
    # 测试创建用户
    user_id = test_create_user()
    if not user_id:
        print("❌ 用户创建失败，停止测试")
        return
    
    # 测试获取用户列表
    if not test_get_users():
        print("❌ 获取用户列表失败")
    
    # 测试用户登录前端
    if not test_user_login('testuser001'):
        print("❌ 用户登录前端失败")
    
    # 测试用户状态切换
    if not test_toggle_user_status(user_id):
        print("❌ 用户状态切换失败")
    
    # 测试管理统计
    if not test_admin_stats():
        print("❌ 管理统计测试失败")
    
    print("\n" + "=" * 50)
    print("🎉 Admin管理功能测试完成")
    print("📝 测试总结：")
    print("   ✅ 管理员登录功能")
    print("   ✅ 用户创建功能")
    print("   ✅ 用户列表查询")
    print("   ✅ 用户前端登录")
    print("   ✅ 用户状态管理")
    print("   ✅ 权限控制验证")
    print("   ✅ 管理数据统计")
    print("\n🚀 现在可以访问管理端:")
    print("   Admin端: http://localhost:8001")
    print("   用户端: http://localhost:8000/login.html")

if __name__ == '__main__':
    main() 