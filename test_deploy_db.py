#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
部署测试用的PostgreSQL数据库连接测试脚本
"""

import os
import psycopg2
from pathlib import Path
import json

def load_config():
    """加载部署配置"""
    try:
        with open('deploy_config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] 无法加载配置文件: {e}")
        return None

def test_postgresql_database():
    """测试PostgreSQL数据库连接"""
    print("=== 测试PostgreSQL数据库连接 ===")
    
    config = load_config()
    if not config:
        return False
    
    db_config = config.get('database', {})
    
    try:
        # 连接参数
        host = db_config.get('host', 'localhost')
        port = db_config.get('port', 5432)
        database = db_config.get('name', 'stock_analysis')
        user = db_config.get('user', 'postgres')
        password = db_config.get('password', '')
        
        print(f"[INFO] 尝试连接到PostgreSQL: {host}:{port}/{database}")
        
        # 测试连接
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        
        cursor = conn.cursor()
        
        # 测试基本查询
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"[OK] PostgreSQL连接成功，版本: {version[0]}")
        
        # 检查数据库中的表
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        print(f"[INFO] 当前数据库中的表: {[table[0] for table in tables]}")
        
        # 检查连接池设置
        cursor.execute("SHOW max_connections;")
        max_conn = cursor.fetchone()
        print(f"[INFO] 数据库最大连接数: {max_conn[0]}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except psycopg2.OperationalError as e:
        print(f"[ERROR] PostgreSQL连接失败: {e}")
        print("[INFO] 请检查:")
        print("  1. PostgreSQL服务是否运行")
        print("  2. 数据库连接参数是否正确")
        print("  3. 网络连接是否正常")
        print("  4. 用户权限是否足够")
        return False
    except Exception as e:
        print(f"[ERROR] PostgreSQL测试失败: {e}")
        return False

def test_database_permissions():
    """测试数据库权限"""
    print("\n=== 测试数据库权限 ===")
    
    config = load_config()
    if not config:
        return False
    
    db_config = config.get('database', {})
    
    try:
        # 连接参数
        host = db_config.get('host', 'localhost')
        port = db_config.get('port', 5432)
        database = db_config.get('name', 'stock_analysis')
        user = db_config.get('user', 'postgres')
        password = db_config.get('password', '')
        
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        
        cursor = conn.cursor()
        
        # 测试创建临时表权限
        cursor.execute("CREATE TEMP TABLE test_permissions (id SERIAL PRIMARY KEY, name VARCHAR(50));")
        cursor.execute("INSERT INTO test_permissions (name) VALUES ('test');")
        cursor.execute("SELECT * FROM test_permissions;")
        result = cursor.fetchone()
        cursor.execute("DROP TABLE test_permissions;")
        
        if result and result[1] == 'test':
            print("[OK] 数据库读写权限正常")
        else:
            print("[ERROR] 数据库读写权限测试失败")
            return False
        
        # 检查用户权限
        cursor.execute("""
            SELECT privilege_type 
            FROM information_schema.role_table_grants 
            WHERE grantee = current_user 
            AND table_schema = 'public';
        """)
        privileges = cursor.fetchall()
        print(f"[INFO] 当前用户权限: {[priv[0] for priv in privileges]}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 数据库权限测试失败: {e}")
        return False

def test_database_initialization():
    """测试数据库初始化"""
    print("\n=== 测试数据库初始化 ===")
    
    try:
        # 检查迁移脚本是否存在
        if not os.path.exists("migrate_db.py"):
            print("[WARNING] migrate_db.py 不存在，跳过数据库初始化测试")
            return True
        
        print("[INFO] 运行数据库迁移脚本...")
        import subprocess
        import sys
        
        result = subprocess.run(
            [sys.executable, "migrate_db.py"], 
            capture_output=True, 
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            print("[OK] 数据库迁移成功")
            return True
        else:
            print(f"[ERROR] 数据库迁移失败: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("[ERROR] 数据库迁移超时")
        return False
    except Exception as e:
        print(f"[ERROR] 数据库初始化测试失败: {e}")
        return False

def main():
    """主函数"""
    print("开始PostgreSQL数据库部署测试...")
    
    # 测试PostgreSQL数据库连接
    if not test_postgresql_database():
        return False
    
    # 测试数据库权限
    if not test_database_permissions():
        return False
    
    # 测试数据库初始化
    if not test_database_initialization():
        return False
    
    print("\n[SUCCESS] PostgreSQL数据库部署测试通过！")
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1) 