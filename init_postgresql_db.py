#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PostgreSQL数据库初始化脚本
用于创建数据库、用户和基本表结构
"""

import psycopg2
import json
import sys
from pathlib import Path

def load_config():
    """加载部署配置"""
    try:
        with open('deploy_config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] 无法加载配置文件: {e}")
        return None

def create_database():
    """创建PostgreSQL数据库"""
    config = load_config()
    if not config:
        return False
    
    db_config = config.get('database', {})
    
    # 连接到PostgreSQL服务器（不指定数据库）
    try:
        conn = psycopg2.connect(
            host=db_config.get('host', 'localhost'),
            port=db_config.get('port', 5432),
            database='postgres',  # 连接到默认数据库
            user=db_config.get('user', 'postgres'),
            password=db_config.get('password', '')
        )
        
        conn.autocommit = True
        cursor = conn.cursor()
        
        # 检查数据库是否存在
        db_name = db_config.get('name', 'stock_analysis')
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        
        if not cursor.fetchone():
            print(f"[INFO] 创建数据库: {db_name}")
            cursor.execute(f"CREATE DATABASE {db_name}")
            print(f"[OK] 数据库 {db_name} 创建成功")
        else:
            print(f"[INFO] 数据库 {db_name} 已存在")
        
        cursor.close()
        conn.close()
        
        return True
        
    except psycopg2.OperationalError as e:
        print(f"[ERROR] 连接PostgreSQL服务器失败: {e}")
        print("[INFO] 请检查:")
        print("  1. PostgreSQL服务是否运行")
        print("  2. 连接参数是否正确")
        print("  3. 用户权限是否足够")
        return False
    except Exception as e:
        print(f"[ERROR] 创建数据库失败: {e}")
        return False

def create_tables():
    """创建基本表结构"""
    config = load_config()
    if not config:
        return False
    
    db_config = config.get('database', {})
    
    try:
        # 连接到目标数据库
        conn = psycopg2.connect(
            host=db_config.get('host', 'localhost'),
            port=db_config.get('port', 5432),
            database=db_config.get('name', 'stock_analysis'),
            user=db_config.get('user', 'postgres'),
            password=db_config.get('password', '')
        )
        
        cursor = conn.cursor()
        
        # 创建基本表结构
        tables_sql = [
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                status VARCHAR(20) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS admins (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(50) DEFAULT 'admin',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS watchlist (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                stock_code VARCHAR(20) NOT NULL,
                stock_name VARCHAR(100),
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS stock_basic_info (
                id SERIAL PRIMARY KEY,
                stock_code VARCHAR(20) UNIQUE NOT NULL,
                stock_name VARCHAR(100),
                industry VARCHAR(100),
                market VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS quote_data (
                id SERIAL PRIMARY KEY,
                stock_code VARCHAR(20) NOT NULL,
                trade_date DATE NOT NULL,
                open_price DECIMAL(10,2),
                high_price DECIMAL(10,2),
                low_price DECIMAL(10,2),
                close_price DECIMAL(10,2),
                volume BIGINT,
                amount DECIMAL(20,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(stock_code, trade_date)
            );
            """
        ]
        
        for sql in tables_sql:
            cursor.execute(sql)
            print(f"[OK] 执行SQL: {sql[:50]}...")
        
        conn.commit()
        print("[OK] 基本表结构创建完成")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 创建表结构失败: {e}")
        return False

def create_indexes():
    """创建索引以提高查询性能"""
    config = load_config()
    if not config:
        return False
    
    db_config = config.get('database', {})
    
    try:
        conn = psycopg2.connect(
            host=db_config.get('host', 'localhost'),
            port=db_config.get('port', 5432),
            database=db_config.get('name', 'stock_analysis'),
            user=db_config.get('user', 'postgres'),
            password=db_config.get('password', '')
        )
        
        cursor = conn.cursor()
        
        # 创建索引
        indexes_sql = [
            "CREATE INDEX IF NOT EXISTS idx_quote_data_stock_date ON quote_data(stock_code, trade_date);",
            "CREATE INDEX IF NOT EXISTS idx_quote_data_date ON quote_data(trade_date);",
            "CREATE INDEX IF NOT EXISTS idx_watchlist_user ON watchlist(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_stock_basic_code ON stock_basic_info(stock_code);"
        ]
        
        for sql in indexes_sql:
            cursor.execute(sql)
            print(f"[OK] 创建索引: {sql}")
        
        conn.commit()
        print("[OK] 索引创建完成")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 创建索引失败: {e}")
        return False

def main():
    """主函数"""
    print("开始PostgreSQL数据库初始化...")
    
    # 创建数据库
    if not create_database():
        return False
    
    # 创建表结构
    if not create_tables():
        return False
    
    # 创建索引
    if not create_indexes():
        return False
    
    print("\n[SUCCESS] PostgreSQL数据库初始化完成！")
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1) 