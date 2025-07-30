#!/usr/bin/env python3
"""
测试数据库连接
"""

import psycopg2
from sqlalchemy import create_engine, text
import sys

def test_psycopg2_connection():
    """测试直接使用 psycopg2 连接"""
    print("=== 测试 psycopg2 直接连接 ===")
    try:
        conn = psycopg2.connect(
            host="192.168.31.237",
            port=5446,
            database="stock_analysis",
            user="postgres",
            password="qidianspacetime",
            client_encoding='utf8'
        )
        print("[OK] psycopg2 连接成功")
        
        # 测试查询
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"PostgreSQL 版本: {version[0]}")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[ERROR] psycopg2 连接失败: {e}")
        return False

def test_sqlalchemy_connection():
    """测试使用 SQLAlchemy 连接"""
    print("\n=== 测试 SQLAlchemy 连接 ===")
    try:
        DATABASE_URL = "postgresql+psycopg2://postgres:qidianspacetime@192.168.31.237:5446/stock_analysis"
        engine = create_engine(DATABASE_URL, echo=True)
        
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version();"))
            version = result.fetchone()
            print(f"[OK] SQLAlchemy 连接成功")
            print(f"PostgreSQL 版本: {version[0]}")
        
        return True
    except Exception as e:
        print(f"[ERROR] SQLAlchemy 连接失败: {e}")
        return False

def test_database_exists():
    """测试数据库是否存在"""
    print("\n=== 测试数据库是否存在 ===")
    try:
        # 连接到默认的 postgres 数据库
        conn = psycopg2.connect(
            host="192.168.31.237",
            port=5446,
            database="postgres",
            user="postgres",
            password="qidianspacetime",
            client_encoding='utf8'
        )
        
        cursor = conn.cursor()
        cursor.execute("SELECT datname FROM pg_database WHERE datname = 'stock_analysis';")
        result = cursor.fetchone()
        
        if result:
            print("[OK] stock_analysis 数据库存在")
        else:
            print("[ERROR] stock_analysis 数据库不存在")
            print("需要创建数据库...")
            
            # 创建数据库
            cursor.execute("CREATE DATABASE stock_analysis;")
            conn.commit()
            print("[OK] stock_analysis 数据库已创建")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[ERROR] 检查数据库失败: {e}")
        return False

if __name__ == "__main__":
    print("开始测试数据库连接...")
    
    # 测试数据库是否存在
    if not test_database_exists():
        sys.exit(1)
    
    # 测试 psycopg2 连接
    if not test_psycopg2_connection():
        sys.exit(1)
    
    # 测试 SQLAlchemy 连接
    if not test_sqlalchemy_connection():
        sys.exit(1)
    
    print("\n[SUCCESS] 所有数据库连接测试通过！") 