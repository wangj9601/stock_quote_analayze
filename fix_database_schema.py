#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库表结构修复脚本
解决 stock_basic_info 表的 ON CONFLICT 错误
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend_core.database.db import SessionLocal
from sqlalchemy import text
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_table_structure():
    """检查表结构"""
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
            logger.info("stock_basic_info 表不存在，将创建新表")
            return False
            
        # 检查列结构
        result = session.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default 
            FROM information_schema.columns 
            WHERE table_name = 'stock_basic_info' 
            ORDER BY ordinal_position;
        """))
        columns = result.fetchall()
        
        logger.info("当前表结构:")
        for col in columns:
            logger.info(f"  {col[0]}: {col[1]} (nullable: {col[2]}, default: {col[3]})")
            
        # 检查约束
        result = session.execute(text("""
            SELECT conname, contype, pg_get_constraintdef(oid) 
            FROM pg_constraint 
            WHERE conrelid = 'stock_basic_info'::regclass;
        """))
        constraints = result.fetchall()
        
        logger.info("当前约束:")
        for constraint in constraints:
            logger.info(f"  {constraint[0]}: {constraint[1]} - {constraint[2]}")
            
        return True
        
    except Exception as e:
        logger.error(f"检查表结构时出错: {e}")
        return False
    finally:
        session.close()

def fix_table_structure():
    """修复表结构"""
    session = SessionLocal()
    try:
        # 1. 删除重复数据
        logger.info("删除重复数据...")
        session.execute(text("""
            DELETE FROM stock_basic_info a USING stock_basic_info b 
            WHERE a.ctid < b.ctid AND a.code = b.code;
        """))
        
        # 2. 检查并添加主键约束
        logger.info("检查主键约束...")
        result = session.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_constraint 
                WHERE conname = 'stock_basic_info_pkey' 
                AND conrelid = 'stock_basic_info'::regclass
            );
        """))
        has_pk = result.scalar()
        
        if not has_pk:
            logger.info("添加主键约束...")
            session.execute(text("""
                ALTER TABLE stock_basic_info ADD CONSTRAINT stock_basic_info_pkey PRIMARY KEY (code);
            """))
        else:
            logger.info("主键约束已存在")
            
        # 3. 创建索引
        logger.info("创建索引...")
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_stock_basic_info_code ON stock_basic_info(code);"))
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_stock_basic_info_name ON stock_basic_info(name);"))
        
        # 4. 提交更改
        session.commit()
        logger.info("表结构修复完成")
        
        return True
        
    except Exception as e:
        logger.error(f"修复表结构时出错: {e}")
        session.rollback()
        return False
    finally:
        session.close()

def create_table_if_not_exists():
    """如果表不存在，创建表"""
    session = SessionLocal()
    try:
        logger.info("创建 stock_basic_info 表...")
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS stock_basic_info (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                create_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        
        # 创建索引
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_stock_basic_info_code ON stock_basic_info(code);"))
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_stock_basic_info_name ON stock_basic_info(name);"))
        
        session.commit()
        logger.info("表创建完成")
        return True
        
    except Exception as e:
        logger.error(f"创建表时出错: {e}")
        session.rollback()
        return False
    finally:
        session.close()

def test_insert():
    """测试插入操作"""
    session = SessionLocal()
    try:
        logger.info("测试插入操作...")
        
        # 测试数据
        test_data = {
            'code': '833266',
            'name': '生物谷',
            'create_date': '2025-08-01 16:30:07'
        }
        
        # 执行插入
        session.execute(text("""
            INSERT INTO stock_basic_info (code, name, create_date)
            VALUES (:code, :name, :create_date)
            ON CONFLICT (code) DO UPDATE SET
                name = EXCLUDED.name,
                create_date = EXCLUDED.create_date
        """), test_data)
        
        session.commit()
        logger.info("测试插入成功")
        
        # 验证数据
        result = session.execute(text("SELECT * FROM stock_basic_info WHERE code = :code"), {'code': '833266'})
        row = result.fetchone()
        if row:
            logger.info(f"验证成功: {row}")
        else:
            logger.warning("验证失败: 未找到插入的数据")
            
        return True
        
    except Exception as e:
        logger.error(f"测试插入时出错: {e}")
        session.rollback()
        return False
    finally:
        session.close()

def main():
    """主函数"""
    logger.info("开始修复数据库表结构...")
    
    # 1. 检查表结构
    if not check_table_structure():
        # 表不存在，创建表
        if not create_table_if_not_exists():
            logger.error("创建表失败")
            return False
    else:
        # 表存在，修复结构
        if not fix_table_structure():
            logger.error("修复表结构失败")
            return False
    
    # 2. 测试插入
    if not test_insert():
        logger.error("测试插入失败")
        return False
    
    logger.info("数据库表结构修复完成！")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 