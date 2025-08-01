#!/usr/bin/env python3
"""
PostgreSQL数据库数据导出脚本
用于导出股票分析系统的数据库数据
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

# 导出目录
EXPORT_DIR = Path(__file__).parent / "exports"
EXPORT_DIR.mkdir(exist_ok=True)

def run_command(command, description):
    """执行命令并处理错误"""
    print(f"正在执行: {description}")
    print(f"命令: {command}")
    
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} 成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} 失败")
        print(f"错误输出: {e.stderr}")
        return False

def export_schema():
    """导出数据库结构（包含索引、约束等）"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = EXPORT_DIR / f"schema_backup_{timestamp}.sql"
    
    print(f"正在导出数据库结构到: {output_file}")
    
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            database=DB_CONFIG["database"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            client_encoding='utf8'
        )
        
        cursor = conn.cursor()
        
        # 获取表结构
        cursor.execute("""
            SELECT 
                table_name,
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            ORDER BY table_name, ordinal_position;
        """)
        
        columns = cursor.fetchall()
        
        # 获取主键约束
        cursor.execute("""
            SELECT 
                tc.table_name,
                tc.constraint_name,
                kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name
            WHERE tc.constraint_type = 'PRIMARY KEY' 
                AND tc.table_schema = 'public'
            ORDER BY tc.table_name, kcu.ordinal_position;
        """)
        
        primary_keys = cursor.fetchall()
        
        # 获取外键约束
        cursor.execute("""
            SELECT 
                tc.table_name,
                tc.constraint_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu 
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY' 
                AND tc.table_schema = 'public'
            ORDER BY tc.table_name, kcu.ordinal_position;
        """)
        
        foreign_keys = cursor.fetchall()
        
        # 获取唯一约束
        cursor.execute("""
            SELECT 
                tc.table_name,
                tc.constraint_name,
                kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name
            WHERE tc.constraint_type = 'UNIQUE' 
                AND tc.table_schema = 'public'
            ORDER BY tc.table_name, kcu.ordinal_position;
        """)
        
        unique_constraints = cursor.fetchall()
        
        # 获取索引
        cursor.execute("""
            SELECT 
                schemaname,
                tablename,
                indexname,
                indexdef
            FROM pg_indexes 
            WHERE schemaname = 'public'
            ORDER BY tablename, indexname;
        """)
        
        indexes = cursor.fetchall()
        
        # 获取序列
        cursor.execute("""
            SELECT 
                sequence_name,
                data_type,
                start_value,
                minimum_value,
                maximum_value,
                increment
            FROM information_schema.sequences 
            WHERE sequence_schema = 'public'
            ORDER BY sequence_name;
        """)
        
        sequences = cursor.fetchall()
        
        # 写入SQL文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("-- PostgreSQL 数据库结构导出（包含索引、约束等）\n")
            f.write(f"-- 导出时间: {datetime.datetime.now()}\n")
            f.write("-- 数据库: stock_analysis\n\n")
            
            # 1. 创建序列
            if sequences:
                f.write("-- ==========================================\n")
                f.write("-- 序列 (Sequences)\n")
                f.write("-- ==========================================\n\n")
                
                for sequence in sequences:
                    sequence_name, data_type, start_value, min_value, max_value, increment = sequence
                    f.write(f"CREATE SEQUENCE {sequence_name}\n")
                    f.write(f"    AS {data_type}\n")
                    f.write(f"    START WITH {start_value}\n")
                    f.write(f"    INCREMENT BY {increment}\n")
                    f.write(f"    MINVALUE {min_value}\n")
                    f.write(f"    MAXVALUE {max_value}\n")
                    f.write("    CACHE 1;\n\n")
            
            # 2. 创建表结构
            f.write("-- ==========================================\n")
            f.write("-- 表结构 (Tables)\n")
            f.write("-- ==========================================\n\n")
            
            current_table = None
            table_columns = {}
            
            # 按表分组列信息
            for column in columns:
                table_name, column_name, data_type, is_nullable, column_default = column
                if table_name not in table_columns:
                    table_columns[table_name] = []
                table_columns[table_name].append((column_name, data_type, is_nullable, column_default))
            
            # 写入每个表的CREATE语句
            for table_name, table_cols in table_columns.items():
                f.write(f"CREATE TABLE {table_name} (\n")
                
                for i, (column_name, data_type, is_nullable, column_default) in enumerate(table_cols):
                    nullable = "" if is_nullable == "YES" else " NOT NULL"
                    default = f" DEFAULT {column_default}" if column_default else ""
                    f.write(f"    {column_name} {data_type}{nullable}{default}")
                    
                    if i < len(table_cols) - 1:
                        f.write(",")
                    f.write("\n")
                
                f.write(");\n\n")
            
            # 3. 创建主键约束
            if primary_keys:
                f.write("-- ==========================================\n")
                f.write("-- 主键约束 (Primary Keys)\n")
                f.write("-- ==========================================\n\n")
                
                current_table = None
                current_columns = []
                
                for pk in primary_keys:
                    table_name, constraint_name, column_name = pk
                    
                    if table_name != current_table:
                        if current_table and current_columns:
                            f.write(f"ALTER TABLE {current_table} ADD CONSTRAINT {constraint_name} PRIMARY KEY ({', '.join(current_columns)});\n")
                        current_table = table_name
                        current_columns = [column_name]
                    else:
                        current_columns.append(column_name)
                
                if current_table and current_columns:
                    f.write(f"ALTER TABLE {current_table} ADD CONSTRAINT {constraint_name} PRIMARY KEY ({', '.join(current_columns)});\n")
                
                f.write("\n")
            
            # 4. 创建外键约束
            if foreign_keys:
                f.write("-- ==========================================\n")
                f.write("-- 外键约束 (Foreign Keys)\n")
                f.write("-- ==========================================\n\n")
                
                for fk in foreign_keys:
                    table_name, constraint_name, column_name, foreign_table, foreign_column = fk
                    f.write(f"ALTER TABLE {table_name} ADD CONSTRAINT {constraint_name} ")
                    f.write(f"FOREIGN KEY ({column_name}) REFERENCES {foreign_table}({foreign_column});\n")
                
                f.write("\n")
            
            # 5. 创建唯一约束
            if unique_constraints:
                f.write("-- ==========================================\n")
                f.write("-- 唯一约束 (Unique Constraints)\n")
                f.write("-- ==========================================\n\n")
                
                current_table = None
                current_constraint = None
                current_columns = []
                
                for uc in unique_constraints:
                    table_name, constraint_name, column_name = uc
                    
                    if table_name != current_table or constraint_name != current_constraint:
                        if current_table and current_constraint and current_columns:
                            f.write(f"ALTER TABLE {current_table} ADD CONSTRAINT {current_constraint} UNIQUE ({', '.join(current_columns)});\n")
                        current_table = table_name
                        current_constraint = constraint_name
                        current_columns = [column_name]
                    else:
                        current_columns.append(column_name)
                
                if current_table and current_constraint and current_columns:
                    f.write(f"ALTER TABLE {current_table} ADD CONSTRAINT {current_constraint} UNIQUE ({', '.join(current_columns)});\n")
                
                f.write("\n")
            
            # 6. 创建索引
            if indexes:
                f.write("-- ==========================================\n")
                f.write("-- 索引 (Indexes)\n")
                f.write("-- ==========================================\n\n")
                
                for index in indexes:
                    schema_name, table_name, index_name, index_def = index
                    # 跳过主键和唯一约束的索引（已经通过约束创建）
                    if not any(pk[1] == index_name for pk in primary_keys) and \
                       not any(uc[1] == index_name for uc in unique_constraints):
                        f.write(f"{index_def};\n\n")
        
        cursor.close()
        conn.close()
        
        print(f"✅ 数据库结构导出成功: {output_file}")
        return output_file
    except Exception as e:
        print(f"❌ 数据库结构导出失败: {e}")
        return None

def export_data():
    """导出所有数据"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = EXPORT_DIR / f"data_backup_{timestamp}.sql"
    
    print(f"正在导出数据库数据到: {output_file}")
    
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            database=DB_CONFIG["database"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            client_encoding='utf8'
        )
        
        cursor = conn.cursor()
        
        # 获取所有表
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """)
        
        tables = cursor.fetchall()
        
        # 写入SQL文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("-- PostgreSQL 数据库数据导出\n")
            f.write(f"-- 导出时间: {datetime.datetime.now()}\n")
            f.write("-- 数据库: stock_analysis\n\n")
            
            for table in tables:
                table_name = table[0]
                print(f"  正在导出表: {table_name}")
                
                # 获取表数据
                cursor.execute(f"SELECT * FROM {table_name}")
                rows = cursor.fetchall()
                
                if rows:
                    # 获取列名
                    cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}' AND table_schema = 'public' ORDER BY ordinal_position")
                    columns = [col[0] for col in cursor.fetchall()]
                    
                    f.write(f"\n-- 表 {table_name} 的数据\n")
                    f.write(f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES\n")
                    
                    for i, row in enumerate(rows):
                        values = []
                        for value in row:
                            if value is None:
                                values.append("NULL")
                            elif isinstance(value, str):
                                # 转义单引号
                                escaped_value = value.replace("'", "''")
                                values.append(f"'{escaped_value}'")
                            elif isinstance(value, datetime.date) or isinstance(value, datetime.datetime):
                                # 日期和日期时间类型，格式化为字符串并加单引号
                                if isinstance(value, datetime.datetime):
                                    formatted_date = value.strftime("%Y-%m-%d %H:%M:%S")
                                else:
                                    formatted_date = value.strftime("%Y-%m-%d")
                                values.append(f"'{formatted_date}'")
                            else:
                                values.append(str(value))
                        
                        f.write(f"({', '.join(values)})")
                        if i < len(rows) - 1:
                            f.write(",")
                        f.write("\n")
                    
                    f.write(";\n")
        
        cursor.close()
        conn.close()
        
        print(f"✅ 数据库数据导出成功: {output_file}")
        return output_file
    except Exception as e:
        print(f"❌ 数据库数据导出失败: {e}")
        return None

def export_full_backup():
    """导出完整数据库备份"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = EXPORT_DIR / f"full_backup_{timestamp}.sql"
    
    command = f'pg_dump -h {DB_CONFIG["host"]} -p {DB_CONFIG["port"]} -U {DB_CONFIG["user"]} -d {DB_CONFIG["database"]} > "{output_file}"'
    
    env = os.environ.copy()
    env['PGPASSWORD'] = DB_CONFIG['password']
    
    print(f"正在导出完整数据库备份到: {output_file}")
    
    try:
        result = subprocess.run(command, shell=True, check=True, env=env, capture_output=True, text=True)
        print(f"✅ 完整数据库备份导出成功: {output_file}")
        return output_file
    except subprocess.CalledProcessError as e:
        print(f"❌ 完整数据库备份导出失败: {e.stderr}")
        return None

def export_table_data(table_name):
    """导出特定表的数据"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = EXPORT_DIR / f"{table_name}_data_{timestamp}.sql"
    
    print(f"正在导出表 {table_name} 的数据到: {output_file}")
    
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            database=DB_CONFIG["database"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            client_encoding='utf8'
        )
        
        cursor = conn.cursor()
        
        # 获取表数据
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        
        if rows:
            # 获取列名
            cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}' AND table_schema = 'public' ORDER BY ordinal_position")
            columns = [col[0] for col in cursor.fetchall()]
            
            # 写入SQL文件
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"-- 表 {table_name} 的数据导出\n")
                f.write(f"-- 导出时间: {datetime.datetime.now()}\n\n")
                f.write(f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES\n")
                
                for i, row in enumerate(rows):
                    values = []
                    for value in row:
                        if value is None:
                            values.append("NULL")
                        elif isinstance(value, str):
                            # 转义单引号
                            escaped_value = value.replace("'", "''")
                            values.append(f"'{escaped_value}'")
                        elif isinstance(value, datetime.date) or isinstance(value, datetime.datetime):
                            # 日期和日期时间类型，格式化为字符串并加单引号
                            if isinstance(value, datetime.datetime):
                                formatted_date = value.strftime("%Y-%m-%d %H:%M:%S")
                            else:
                                formatted_date = value.strftime("%Y-%m-%d")
                            values.append(f"'{formatted_date}'")
                        else:
                            values.append(str(value))
                    
                    f.write(f"({', '.join(values)})")
                    if i < len(rows) - 1:
                        f.write(",")
                    f.write("\n")
                
                f.write(";\n")
        
        cursor.close()
        conn.close()
        
        print(f"✅ 表 {table_name} 数据导出成功: {output_file}")
        return output_file
    except Exception as e:
        print(f"❌ 表 {table_name} 数据导出失败: {e}")
        return None

def export_all_tables():
    """导出所有主要表的数据"""
    tables = [
        "users",
        "admins", 
        "stock_basic_info",
        "stock_realtime_quote",
        "historical_quotes",
        "watchlist",
        "watchlist_groups",
        "watchlist_history_collection_logs",
        "stock_news",
        "stock_notice_report",
        "stock_research_report",
        "quote_data",
        "quote_sync_tasks"
    ]
    
    results = {}
    for table in tables:
        result_file = export_table_data(table)
        results[table] = result_file
    
    return results

def test_connection():
    """测试数据库连接"""
    print("正在测试数据库连接...")
    
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            database=DB_CONFIG["database"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            client_encoding='utf8'
        )
        print("✅ 数据库连接成功")
        
        # 测试查询
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"PostgreSQL版本: {version[0]}")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("PostgreSQL数据库数据导出工具")
    print("=" * 60)
    
    # 测试连接
    if not test_connection():
        print("无法连接到数据库，请检查配置")
        return
    
    print(f"\n导出目录: {EXPORT_DIR}")
    
    # 显示菜单
    while True:
        print("\n请选择操作:")
        print("1. 导出数据库结构")
        print("2. 导出所有数据")
        print("3. 导出完整数据库备份")
        print("4. 导出特定表数据")
        print("5. 导出所有主要表数据")
        print("6. 退出")
        
        choice = input("\n请输入选择 (1-6): ").strip()
        
        if choice == "1":
            export_schema()
        elif choice == "2":
            export_data()
        elif choice == "3":
            export_full_backup()
        elif choice == "4":
            table_name = input("请输入表名: ").strip()
            if table_name:
                export_table_data(table_name)
            else:
                print("表名不能为空")
        elif choice == "5":
            print("正在导出所有主要表数据...")
            results = export_all_tables()
            print("\n导出结果:")
            for table, file_path in results.items():
                status = "✅ 成功" if file_path else "❌ 失败"
                print(f"  {table}: {status}")
        elif choice == "6":
            print("退出程序")
            break
        else:
            print("无效选择，请重新输入")

if __name__ == "__main__":
    main() 