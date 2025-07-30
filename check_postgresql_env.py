#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PostgreSQL环境检查脚本
检查PostgreSQL是否正确安装和配置
"""

import subprocess
import sys
import json
import os

def check_postgresql_installation():
    """检查PostgreSQL是否安装"""
    print("=== 检查PostgreSQL安装 ===")
    
    try:
        # 检查psql命令
        result = subprocess.run(['psql', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[OK] PostgreSQL客户端已安装: {result.stdout.strip()}")
            return True
        else:
            print("[ERROR] PostgreSQL客户端未安装")
            return False
    except FileNotFoundError:
        print("[ERROR] PostgreSQL客户端未安装或不在PATH中")
        print("[INFO] 请安装PostgreSQL客户端:")
        print("  Ubuntu/Debian: sudo apt-get install postgresql-client")
        print("  CentOS/RHEL: sudo yum install postgresql")
        print("  Windows: 下载PostgreSQL安装包")
        print("  macOS: brew install postgresql")
        return False

def check_postgresql_service():
    """检查PostgreSQL服务状态"""
    print("\n=== 检查PostgreSQL服务 ===")
    
    try:
        # 尝试连接PostgreSQL服务器
        result = subprocess.run([
            'psql', '-h', 'localhost', '-U', 'postgres', 
            '-c', 'SELECT version();'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("[OK] PostgreSQL服务正在运行")
            return True
        else:
            print(f"[ERROR] PostgreSQL服务连接失败: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("[ERROR] PostgreSQL服务连接超时")
        return False
    except Exception as e:
        print(f"[ERROR] 检查PostgreSQL服务失败: {e}")
        return False

def check_python_dependencies():
    """检查Python PostgreSQL依赖"""
    print("\n=== 检查Python PostgreSQL依赖 ===")
    
    try:
        import psycopg2
        print(f"[OK] psycopg2已安装: {psycopg2.__version__}")
        return True
    except ImportError:
        print("[ERROR] psycopg2未安装")
        print("[INFO] 请安装psycopg2:")
        print("  pip install psycopg2-binary")
        return False

def check_database_config():
    """检查数据库配置"""
    print("\n=== 检查数据库配置 ===")
    
    try:
        with open('deploy_config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        db_config = config.get('database', {})
        db_type = db_config.get('type', 'postgresql')
        
        if db_type == 'postgresql':
            print("[OK] 配置为PostgreSQL数据库")
            
            # 检查配置参数
            required_fields = ['host', 'port', 'name', 'user', 'password']
            for field in required_fields:
                if field in db_config:
                    value = db_config[field]
                    if field == 'password':
                        print(f"[INFO] {field}: {'*' * len(str(value))}")
                    else:
                        print(f"[INFO] {field}: {value}")
                else:
                    print(f"[ERROR] 缺少配置字段: {field}")
                    return False
            
            return True
        else:
            print(f"[WARNING] 数据库类型为: {db_type}")
            return False
            
    except FileNotFoundError:
        print("[ERROR] deploy_config.json文件不存在")
        return False
    except json.JSONDecodeError as e:
        print(f"[ERROR] deploy_config.json格式错误: {e}")
        return False

def test_database_connection():
    """测试数据库连接"""
    print("\n=== 测试数据库连接 ===")
    
    try:
        with open('deploy_config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        db_config = config.get('database', {})
        
        # 构建连接字符串
        host = db_config.get('host', 'localhost')
        port = db_config.get('port', 5432)
        database = db_config.get('name', 'stock_analysis')
        user = db_config.get('user', 'postgres')
        password = db_config.get('password', '')
        
        # 测试连接
        import psycopg2
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"[OK] 数据库连接成功: {version[0]}")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"[ERROR] 数据库连接失败: {e}")
        return False

def main():
    """主函数"""
    print("开始PostgreSQL环境检查...\n")
    
    checks = [
        check_postgresql_installation,
        check_postgresql_service,
        check_python_dependencies,
        check_database_config,
        test_database_connection
    ]
    
    passed = 0
    total = len(checks)
    
    for check in checks:
        if check():
            passed += 1
        print()
    
    print(f"=== 检查结果 ===")
    print(f"通过: {passed}/{total}")
    
    if passed == total:
        print("[SUCCESS] PostgreSQL环境检查全部通过！")
        return True
    else:
        print("[ERROR] PostgreSQL环境检查未通过，请解决上述问题后重试。")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1) 