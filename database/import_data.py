#!/usr/bin/env python3
"""
PostgreSQL数据库数据导入脚本
用于导入股票分析系统的数据库数据
"""

import os
import sys
import subprocess
import datetime
from pathlib import Path

# 数据库配置
DB_CONFIG = {
    "host": "192.168.31.237",
    "port": "5446",
    "user": "postgres",
    "password": "qidianspacetime",
    "database": "stock_analysis"
}

# 导入目录
IMPORT_DIR = Path(__file__).parent / "exports"

def test_connection():
    """测试数据库连接"""
    command = f'psql -h {DB_CONFIG["host"]} -p {DB_CONFIG["port"]} -U {DB_CONFIG["user"]} -d {DB_CONFIG["database"]} -c "SELECT version();"'
    
    env = os.environ.copy()
    env['PGPASSWORD'] = DB_CONFIG['password']
    
    print("正在测试数据库连接...")
    
    try:
        result = subprocess.run(command, shell=True, check=True, env=env, capture_output=True, text=True)
        print("✅ 数据库连接成功")
        print(f"PostgreSQL版本: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 数据库连接失败: {e.stderr}")
        return False

def list_backup_files():
    """列出可用的备份文件"""
    if not IMPORT_DIR.exists():
        print(f"❌ 导入目录不存在: {IMPORT_DIR}")
        return []
    
    backup_files = []
    for file_path in IMPORT_DIR.glob("*.sql"):
        backup_files.append(file_path)
    
    return sorted(backup_files, key=lambda x: x.stat().st_mtime, reverse=True)

def import_sql_file(file_path):
    """导入SQL文件"""
    if not file_path.exists():
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    command = f'psql -h {DB_CONFIG["host"]} -p {DB_CONFIG["port"]} -U {DB_CONFIG["user"]} -d {DB_CONFIG["database"]} < "{file_path}"'
    
    env = os.environ.copy()
    env['PGPASSWORD'] = DB_CONFIG['password']
    
    print(f"正在导入文件: {file_path}")
    print(f"文件大小: {file_path.stat().st_size / 1024 / 1024:.2f} MB")
    
    try:
        result = subprocess.run(command, shell=True, check=True, env=env, capture_output=True, text=True)
        print(f"✅ 文件导入成功: {file_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 文件导入失败: {file_path}")
        print(f"错误输出: {e.stderr}")
        return False

def import_schema_only(file_path):
    """仅导入表结构"""
    if not file_path.exists():
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    # 先删除现有表（如果存在）
    print("正在清理现有表结构...")
    cleanup_command = f'psql -h {DB_CONFIG["host"]} -p {DB_CONFIG["port"]} -U {DB_CONFIG["user"]} -d {DB_CONFIG["database"]} -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"'
    
    env = os.environ.copy()
    env['PGPASSWORD'] = DB_CONFIG['password']
    
    try:
        subprocess.run(cleanup_command, shell=True, check=True, env=env, capture_output=True, text=True)
        print("✅ 现有表结构清理完成")
    except subprocess.CalledProcessError as e:
        print(f"⚠️ 清理现有表结构时出现警告: {e.stderr}")
    
    # 导入新的表结构
    return import_sql_file(file_path)

def import_data_only(file_path):
    """仅导入数据"""
    return import_sql_file(file_path)

def backup_current_database():
    """备份当前数据库"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = IMPORT_DIR / f"pre_import_backup_{timestamp}.sql"
    
    command = f'pg_dump -h {DB_CONFIG["host"]} -p {DB_CONFIG["port"]} -U {DB_CONFIG["user"]} -d {DB_CONFIG["database"]} > "{backup_file}"'
    
    env = os.environ.copy()
    env['PGPASSWORD'] = DB_CONFIG['password']
    
    print(f"正在备份当前数据库到: {backup_file}")
    
    try:
        result = subprocess.run(command, shell=True, check=True, env=env, capture_output=True, text=True)
        print(f"✅ 当前数据库备份成功: {backup_file}")
        return backup_file
    except subprocess.CalledProcessError as e:
        print(f"❌ 当前数据库备份失败: {e.stderr}")
        return None

def select_backup_file():
    """选择备份文件"""
    backup_files = list_backup_files()
    
    if not backup_files:
        print("❌ 没有找到可用的备份文件")
        return None
    
    print("\n可用的备份文件:")
    for i, file_path in enumerate(backup_files, 1):
        file_size = file_path.stat().st_size / 1024 / 1024
        file_time = datetime.datetime.fromtimestamp(file_path.stat().st_mtime)
        print(f"{i}. {file_path.name} ({file_size:.2f} MB, {file_time.strftime('%Y-%m-%d %H:%M:%S')})")
    
    while True:
        try:
            choice = input(f"\n请选择文件 (1-{len(backup_files)}): ").strip()
            index = int(choice) - 1
            if 0 <= index < len(backup_files):
                return backup_files[index]
            else:
                print("无效选择，请重新输入")
        except ValueError:
            print("请输入有效的数字")

def main():
    """主函数"""
    print("=" * 60)
    print("PostgreSQL数据库数据导入工具")
    print("=" * 60)
    
    # 测试连接
    if not test_connection():
        print("无法连接到数据库，请检查配置")
        return
    
    print(f"\n导入目录: {IMPORT_DIR}")
    
    # 显示菜单
    while True:
        print("\n请选择操作:")
        print("1. 导入完整数据库备份")
        print("2. 仅导入表结构")
        print("3. 仅导入数据")
        print("4. 备份当前数据库")
        print("5. 退出")
        
        choice = input("\n请输入选择 (1-5): ").strip()
        
        if choice == "1":
            print("\n⚠️ 警告: 这将覆盖现有数据库!")
            confirm = input("确认继续? (y/N): ").strip().lower()
            if confirm == 'y':
                # 先备份当前数据库
                backup_file = backup_current_database()
                if backup_file:
                    print(f"当前数据库已备份到: {backup_file}")
                
                # 选择要导入的文件
                file_path = select_backup_file()
                if file_path:
                    import_sql_file(file_path)
        elif choice == "2":
            print("\n⚠️ 警告: 这将删除现有表结构!")
            confirm = input("确认继续? (y/N): ").strip().lower()
            if confirm == 'y':
                file_path = select_backup_file()
                if file_path:
                    import_schema_only(file_path)
        elif choice == "3":
            file_path = select_backup_file()
            if file_path:
                import_data_only(file_path)
        elif choice == "4":
            backup_current_database()
        elif choice == "5":
            print("退出程序")
            break
        else:
            print("无效选择，请重新输入")

if __name__ == "__main__":
    main() 