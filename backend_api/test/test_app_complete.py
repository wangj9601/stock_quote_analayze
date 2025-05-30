#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest
import json
import os
import sqlite3
from datetime import datetime
import sys
import requests

# 添加父目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app_complete import app, init_db, hash_password

class TestStockAnalysisSystem(unittest.TestCase):
    """股票分析系统测试类"""
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        print("\n🚀 开始测试股票分析系统...")
        
        # 使用测试数据库
        cls.test_db_path = 'database/test_stock_analysis.db'
        if os.path.exists(cls.test_db_path):
            os.remove(cls.test_db_path)
        
        # 修改app配置使用测试数据库
        app.config['TESTING'] = True
        app.config['DATABASE'] = cls.test_db_path
        app.config['SECRET_KEY'] = 'test_secret_key'  # 添加测试密钥
        
        # 创建测试客户端
        cls.client = app.test_client()
        
        try:
            # 初始化测试数据库
            print("📊 初始化测试数据库...")
            init_db()
            
            # 创建测试用户
            print("👥 创建测试用户...")
            cls.create_test_users()
            
            # 创建测试管理员
            print("👤 创建测试管理员...")
            cls.create_test_admin()
            
        except Exception as e:
            print(f"❌ 初始化失败: {str(e)}")
            # 清理测试数据库
            if os.path.exists(cls.test_db_path):
                os.remove(cls.test_db_path)
            raise
    
    @classmethod
    def tearDownClass(cls):
        """测试类清理"""
        # 删除测试数据库
        if os.path.exists(cls.test_db_path):
            os.remove(cls.test_db_path)
        print("\n✨ 测试完成，清理测试数据...")
    
    @classmethod
    def create_test_users(cls):
        """创建测试用户"""
        try:
            conn = sqlite3.connect(cls.test_db_path)
            cursor = conn.cursor()
            
            # 检查users表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if not cursor.fetchone():
                raise Exception("users表不存在，请确保init_db()已正确执行")
            
            # 创建测试用户
            test_users = [
                ('testuser1', 'test1@example.com', hash_password('password123')),
                ('testuser2', 'test2@example.com', hash_password('password123')),
                ('testuser3', 'test3@example.com', hash_password('password123'))
            ]
            
            for username, email, password_hash in test_users:
                cursor.execute('''
                    INSERT INTO users (username, email, password_hash, status)
                    VALUES (?, ?, ?, ?)
                ''', (username, email, password_hash, 'active'))
            
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise Exception(f"创建测试用户失败: {str(e)}")
        finally:
            if conn:
                conn.close()
    
    @classmethod
    def create_test_admin(cls):
        """创建测试管理员"""
        try:
            conn = sqlite3.connect(cls.test_db_path)
            cursor = conn.cursor()
            
            # 检查admins表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='admins'")
            if not cursor.fetchone():
                raise Exception("admins表不存在，请确保init_db()已正确执行")
            
            # 创建测试管理员
            cursor.execute('''
                INSERT INTO admins (username, password_hash, role)
                VALUES (?, ?, ?)
            ''', ('testadmin', hash_password('admin123'), 'admin'))
            
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise Exception(f"创建测试管理员失败: {str(e)}")
        finally:
            if conn:
                conn.close()
    
    def setUp(self):
        """每个测试用例前执行"""
        self.test_user = {
            'username': 'testuser1',
            'password': 'password123'
        }
        self.test_admin = {
            'username': 'testadmin',
            'password': 'admin123'
        }
        # 清理session
        with self.client.session_transaction() as session:
            session.clear()
    
    def tearDown(self):
        """每个测试用例后执行"""
        # 清理session
        with self.client.session_transaction() as session:
            session.clear()
    
    def test_01_database_init(self):
        """测试数据库初始化"""
        print("\n📊 测试数据库初始化...")
        
        # 检查数据库文件是否存在
        self.assertTrue(os.path.exists(self.test_db_path))
        
        # 检查表是否创建
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        
        # 检查users表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        self.assertIsNotNone(cursor.fetchone())
        
        # 检查admins表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='admins'")
        self.assertIsNotNone(cursor.fetchone())
        
        # 检查watchlist表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='watchlist'")
        self.assertIsNotNone(cursor.fetchone())
        
        # 检查watchlist_groups表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='watchlist_groups'")
        self.assertIsNotNone(cursor.fetchone())
        
        conn.close()
        print("✅ 数据库初始化测试通过")
    
    def test_02_user_login(self):
        """测试用户登录"""
        print("\n🔐 测试用户登录...")
        
        # 测试正常登录
        response = self.client.post('/api/auth/login',
            json=self.test_user,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('token', data)
        self.assertIn('user', data)
        
        # 测试错误密码
        response = self.client.post('/api/auth/login',
            json={'username': 'testuser1', 'password': 'wrongpass'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        
        # 测试不存在的用户
        response = self.client.post('/api/auth/login',
            json={'username': 'nonexist', 'password': 'password123'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        
        print("✅ 用户登录测试通过")
    
    def test_03_admin_login(self):
        """测试管理员登录"""
        print("\n👤 测试管理员登录...")
        
        # 测试正常登录
        response = self.client.post('/api/admin/login',
            json=self.test_admin,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('token', data)
        self.assertIn('admin', data)
        
        # 测试错误密码
        response = self.client.post('/api/admin/login',
            json={'username': 'testadmin', 'password': 'wrongpass'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        
        print("✅ 管理员登录测试通过")
    
    def test_04_admin_users(self):
        """测试管理员用户管理功能"""
        print("\n👥 测试管理员用户管理...")
        
        # 先登录获取token
        response = self.client.post('/api/admin/login',
            json=self.test_admin,
            content_type='application/json'
        )
        token = json.loads(response.data)['token']
        
        # 测试获取用户列表
        response = self.client.get('/api/admin/users')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        self.assertIn('total', data)
        
        # 测试创建新用户
        new_user = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'password123'
        }
        response = self.client.post('/api/admin/users',
            json=new_user,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('user', data)
        
        # 测试更新用户
        user_id = data['user']['id']
        update_data = {
            'username': 'updateduser',
            'email': 'updated@example.com',
            'status': 'active'
        }
        response = self.client.put(f'/api/admin/users/{user_id}',
            json=update_data,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        
        # 测试删除用户
        response = self.client.delete(f'/api/admin/users/{user_id}')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        
        print("✅ 管理员用户管理测试通过")
    
    def test_05_stock_list(self):
        """测试股票列表功能"""
        print("\n📈 测试股票列表...")
        
        # 测试获取股票列表
        response = self.client.get('/api/stocks/list')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        self.assertIn('total', data)
        
        # 测试搜索股票
        response = self.client.get('/api/stocks/list?query=平安')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        
        print("✅ 股票列表测试通过")
    
    def test_06_watchlist(self):
        """测试自选股功能"""
        print("\n⭐ 测试自选股功能...")
        
        # 先登录
        response = self.client.post('/api/auth/login',
            json=self.test_user,
            content_type='application/json'
        )
        user_id = json.loads(response.data)['user']['id']
        
        # 测试添加自选股
        stock_data = {
            'user_id': user_id,
            'stock_code': '000001',
            'stock_name': '平安银行',
            'group_name': '银行股'
        }
        response = self.client.post('/api/watchlist',
            json=stock_data,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        
        # 测试获取自选股列表
        response = self.client.get('/api/watchlist')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        
        # 测试获取自选股分组
        response = self.client.get(f'/api/watchlist/groups?user_id={user_id}')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        
        print("✅ 自选股功能测试通过")
    
    def test_07_market_indices(self):
        """测试市场指数功能"""
        print("\n📊 测试市场指数...")
        
        response = self.client.get('/api/market/indices')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        
        # 验证返回的数据结构
        indices = data['data']
        self.assertGreater(len(indices), 0)
        for index in indices:
            self.assertIn('code', index)
            self.assertIn('name', index)
            self.assertIn('current', index)
            self.assertIn('change', index)
            self.assertIn('change_percent', index)
        
        print("✅ 市场指数测试通过")
    
    def test_08_news(self):
        """测试新闻功能"""
        print("\n📰 测试新闻功能...")
        
        # 测试获取新闻列表
        response = self.client.get('/api/news')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        self.assertIn('total', data)
        
        # 测试限制返回数量
        response = self.client.get('/api/news?limit=5')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertLessEqual(len(data['data']), 5)
        
        print("✅ 新闻功能测试通过")
    
    def test_09_auth_status(self):
        """测试用户认证状态"""
        print("\n🔒 测试用户认证状态...")
        
        # 确保session是空的
        with self.client.session_transaction() as session:
            session.clear()
        
        # 测试未登录状态
        response = self.client.get('/api/auth/status')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertFalse(data['logged_in'])
        
        # 登录后测试
        login_response = self.client.post('/api/auth/login',
            json=self.test_user,
            content_type='application/json'
        )
        self.assertEqual(login_response.status_code, 200)
        
        # 验证登录状态
        response = self.client.get('/api/auth/status')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertTrue(data['logged_in'])
        self.assertIn('user', data)
        
        # 测试登出
        logout_response = self.client.post('/api/auth/logout')
        self.assertEqual(logout_response.status_code, 200)
        data = json.loads(logout_response.data)
        self.assertTrue(data['success'])
        
        # 登出后再次检查状态
        response = self.client.get('/api/auth/status')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertFalse(data['logged_in'])
        
        print("✅ 用户认证状态测试通过")
    
    def test_10_admin_stats(self):
        """测试管理员统计功能"""
        print("\n📈 测试管理员统计...")
        
        # 先登录管理员
        self.client.post('/api/admin/login',
            json=self.test_admin,
            content_type='application/json'
        )
        
        # 测试获取统计信息
        response = self.client.get('/api/admin/stats')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        
        # 验证返回的数据结构
        stats = data['data']
        self.assertIn('active_users', stats)
        self.assertIn('disabled_users', stats)
        self.assertIn('total_users', stats)
        self.assertIn('today_logins', stats)
        self.assertIn('total_watchlist', stats)
        self.assertIn('system_status', stats)
        
        print("✅ 管理员统计测试通过")

if __name__ == '__main__':
    unittest.main(verbosity=2) 