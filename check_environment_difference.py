#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
环境差异检测脚本
解释为什么本机开发环境没有报错，但生产环境报错
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend_core.database.db import SessionLocal, engine
from sqlalchemy import text, inspect
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_database_type():
    """检查数据库类型"""
    logger.info("🔍 检查数据库类型...")
    
    # 从连接URL判断数据库类型
    url = str(engine.url)
    if 'postgresql' in url:
        db_type = "PostgreSQL"
    elif 'sqlite' in url:
        db_type = "SQLite"
    else:
        db_type = "Unknown"
    
    logger.info(f"📊 当前数据库类型: {db_type}")
    logger.info(f"🔗 数据库连接URL: {url}")
    
    return db_type

def check_table_structure():
    """检查stock_basic_info表结构"""
    logger.info("🔍 检查stock_basic_info表结构...")
    
    session = SessionLocal()
    try:
        # 检查表是否存在
        result = session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'stock_basic_info'
            );
        """))
        table_exists = result.scalar()
        
        if not table_exists:
            logger.warning("⚠️  stock_basic_info表不存在！")
            return False
        
        # 检查表结构
        result = session.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default 
            FROM information_schema.columns 
            WHERE table_name = 'stock_basic_info' 
            ORDER BY ordinal_position;
        """))
        
        columns = result.fetchall()
        logger.info("📋 表结构:")
        for col in columns:
            logger.info(f"  - {col[0]}: {col[1]} (nullable: {col[2]}, default: {col[3]})")
        
        # 检查约束
        result = session.execute(text("""
            SELECT conname, contype, pg_get_constraintdef(oid) 
            FROM pg_constraint 
            WHERE conrelid = 'stock_basic_info'::regclass;
        """))
        
        constraints = result.fetchall()
        logger.info("🔒 约束:")
        for constraint in constraints:
            logger.info(f"  - {constraint[0]}: {constraint[1]} - {constraint[2]}")
        
        # 检查是否有主键约束
        has_primary_key = any(c[1] == 'p' for c in constraints)
        logger.info(f"🔑 是否有主键约束: {has_primary_key}")
        
        return has_primary_key
        
    except Exception as e:
        logger.error(f"❌ 检查表结构失败: {e}")
        return False
    finally:
        session.close()

def check_sqlite_compatibility():
    """检查SQLite兼容性"""
    logger.info("🔍 检查SQLite兼容性...")
    
    try:
        import sqlite3
        logger.info("✅ SQLite模块可用")
        
        # 检查是否有SQLite数据库文件
        sqlite_files = list(project_root.glob("**/*.db"))
        if sqlite_files:
            logger.info("📁 发现SQLite数据库文件:")
            for db_file in sqlite_files:
                logger.info(f"  - {db_file}")
        else:
            logger.info("📁 未发现SQLite数据库文件")
            
    except ImportError:
        logger.warning("⚠️  SQLite模块不可用")

def explain_difference():
    """解释环境差异"""
    logger.info("🔍 分析环境差异...")
    
    db_type = check_database_type()
    
    if db_type == "PostgreSQL":
        logger.info("""
🔍 环境差异分析:

📊 当前环境: PostgreSQL (生产环境)
📊 开发环境: 可能使用 SQLite

🔧 问题原因:
1. SQLite vs PostgreSQL 的 ON CONFLICT 语法差异:
   - SQLite: 更宽松，即使没有显式约束也能工作
   - PostgreSQL: 严格要求存在唯一约束或主键约束

2. 表结构差异:
   - 开发环境: stock_basic_info 表可能有主键约束
   - 生产环境: stock_basic_info 表缺少主键约束

3. 数据类型差异:
   - 开发环境: code 字段可能是 INTEGER 类型
   - 生产环境: code 字段是 TEXT 类型，但缺少约束

🔧 解决方案:
1. 运行修复脚本: python fix_database_schema.py
2. 或者手动执行SQL: 
   ALTER TABLE stock_basic_info ADD CONSTRAINT stock_basic_info_pkey PRIMARY KEY (code);
        """)
    else:
        logger.info("""
🔍 环境差异分析:

📊 当前环境: SQLite (开发环境)
📊 生产环境: PostgreSQL

✅ 开发环境正常的原因:
1. SQLite 对 ON CONFLICT 语法更宽松
2. 即使没有显式约束，SQLite 也能处理冲突
3. 表结构可能已经正确设置

⚠️ 生产环境报错的原因:
1. PostgreSQL 对约束要求更严格
2. 需要显式的主键或唯一约束
3. 表结构可能不完整
        """)

def main():
    """主函数"""
    logger.info("🚀 开始环境差异检测...")
    
    # 检查数据库类型
    db_type = check_database_type()
    
    # 检查表结构
    if db_type == "PostgreSQL":
        has_pk = check_table_structure()
        if not has_pk:
            logger.error("❌ 缺少主键约束，这是导致ON CONFLICT错误的原因！")
    
    # 检查SQLite兼容性
    check_sqlite_compatibility()
    
    # 解释差异
    explain_difference()
    
    logger.info("✅ 环境差异检测完成")

if __name__ == "__main__":
    main() 