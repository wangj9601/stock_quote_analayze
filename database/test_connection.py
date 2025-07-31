#!/usr/bin/env python3
"""
测试PostgreSQL数据库连接
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
        print("✅ psycopg2 连接成功")
        
        # 测试查询
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"PostgreSQL 版本: {version[0]}")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ psycopg2 连接失败: {e}")
        return False

def test_sqlalchemy_connection():
    """测试使用 SQLAlchemy 连接"""
    print("\n=== 测试 SQLAlchemy 连接 ===")
    try:
        DATABASE_URL = "postgresql+psycopg2://postgres:qidianspacetime@192.168.31.237:5446/stock_analysis"
        engine = create_engine(DATABASE_URL, echo=False)
        
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version();"))
            version = result.fetchone()
            print(f"✅ SQLAlchemy 连接成功")
            print(f"PostgreSQL 版本: {version[0]}")
        
        return True
    except Exception as e:
        print(f"❌ SQLAlchemy 连接失败: {e}")
        return False

def test_database_tables():
    """测试数据库表是否存在"""
    print("\n=== 测试数据库表 ===")
    try:
        conn = psycopg2.connect(
            host="192.168.31.237",
            port=5446,
            database="stock_analysis",
            user="postgres",
            password="qidianspacetime",
            client_encoding='utf8'
        )
        
        cursor = conn.cursor()
        
        # 查询所有表
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """)
        
        tables = cursor.fetchall()
        print(f"✅ 数据库连接成功，找到 {len(tables)} 个表:")
        
        for table in tables:
            print(f"  - {table[0]}")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ 查询表失败: {e}")
        return False

def test_table_data():
    """测试表数据"""
    print("\n=== 测试表数据 ===")
    try:
        conn = psycopg2.connect(
            host="192.168.31.237",
            port=5446,
            database="stock_analysis",
            user="postgres",
            password="qidianspacetime",
            client_encoding='utf8'
        )
        
        cursor = conn.cursor()
        
        # 测试主要表的数据量
        tables_to_check = [
            "users",
            "stock_basic_info", 
            "stock_realtime_quote",
            "historical_quotes",
            "watchlist",
            "stock_news"
        ]
        
        for table in tables_to_check:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table};")
                count = cursor.fetchone()[0]
                print(f"  {table}: {count} 条记录")
            except Exception as e:
                print(f"  {table}: 查询失败 - {e}")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ 查询数据失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("PostgreSQL数据库连接测试")
    print("=" * 60)
    
    # 测试连接
    psycopg2_ok = test_psycopg2_connection()
    sqlalchemy_ok = test_sqlalchemy_connection()
    
    if psycopg2_ok and sqlalchemy_ok:
        print("\n✅ 数据库连接测试通过")
        
        # 测试表结构
        test_database_tables()
        
        # 测试数据
        test_table_data()
        
        print("\n🎉 所有测试通过！数据库可以正常使用。")
    else:
        print("\n❌ 数据库连接测试失败")
        print("请检查:")
        print("1. 数据库服务是否运行")
        print("2. 网络连接是否正常")
        print("3. 数据库配置是否正确")
        print("4. 用户权限是否足够")
        sys.exit(1)

if __name__ == "__main__":
    main() 