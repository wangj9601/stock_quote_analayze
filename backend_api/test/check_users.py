#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import os

def check_users():
    """检查数据库中的用户"""
    db_path = 'backend_api/database/stock_analysis.db'
    
    if not os.path.exists(db_path):
        print("❌ 数据库文件不存在")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查用户表
        cursor.execute('SELECT username, email, status FROM users')
        users = cursor.fetchall()
        
        print("📋 数据库中的用户列表:")
        if users:
            for user in users:
                print(f"  - 用户名: {user[0]}, 邮箱: {user[1]}, 状态: {user[2]}")
        else:
            print("  ⚠️ 数据库中没有用户")
            
        # 检查管理员表
        cursor.execute('SELECT username, role FROM admins')
        admins = cursor.fetchall()
        
        print("\n👑 数据库中的管理员列表:")
        if admins:
            for admin in admins:
                print(f"  - 用户名: {admin[0]}, 角色: {admin[1]}")
        else:
            print("  ⚠️ 数据库中没有管理员")
            
        conn.close()
        
    except Exception as e:
        print(f"❌ 检查数据库失败: {e}")

def create_test_user():
    """创建测试用户"""
    db_path = 'backend_api/database/stock_analysis.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查test123用户是否存在
        cursor.execute('SELECT id FROM users WHERE username = ?', ('test123',))
        if cursor.fetchone():
            print("✅ test123用户已存在")
        else:
            # 创建test123用户
            import hashlib
            password_hash = hashlib.sha256('123456'.encode()).hexdigest()
            
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, status)
                VALUES (?, ?, ?, ?)
            ''', ('test123', 'test123@example.com', password_hash, 'active'))
            
            conn.commit()
            print("✅ 已创建test123用户，密码：123456")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 创建用户失败: {e}")

if __name__ == '__main__':
    print("🔍 检查用户数据...")
    check_users()
    print("\n🛠️ 创建测试用户...")
    create_test_user()
    print("\n🔍 再次检查用户数据...")
    check_users() 