#!/usr/bin/env python3
"""修复PVFRS任务表，添加缺失的字段"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from backend_api.database import engine as main_engine
import logging

# 配置日志
logger = logging.getLogger(__name__)

def fix_pvfrs_tasks_table():
    """修复PVFRS任务表，添加缺失的字段"""
    logger.info("开始修复PVFRS任务表结构...")
    
    # 添加缺失字段的SQL
    alter_table_sql = """
    ALTER TABLE pvfrs_backtest_tasks_enhanced 
    ADD COLUMN IF NOT EXISTS task_name VARCHAR(200),
    ADD COLUMN IF NOT EXISTS total_stocks INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS processed_stocks INTEGER DEFAULT 0;
    
    CREATE INDEX IF NOT EXISTS idx_pvfrs_tasks_task_name ON pvfrs_backtest_tasks_enhanced(task_name);
    CREATE INDEX IF NOT EXISTS idx_pvfrs_tasks_total_stocks ON pvfrs_backtest_tasks_enhanced(total_stocks);
    CREATE INDEX IF NOT EXISTS idx_pvfrs_tasks_processed_stocks ON pvfrs_backtest_tasks_enhanced(processed_stocks);
    """
    
    try:
        with main_engine.connect() as conn:
            # 执行ALTER TABLE语句
            conn.execute(text(alter_table_sql))
            conn.commit()
            logger.info("✅ PVFRS任务表修复完成")
            
    except Exception as e:
        logger.error(f"❌ 修复PVFRS任务表失败: {str(e)}")
        raise

def main():
    """主函数"""
    logger.info("开始修复PVFRS任务表结构...")
    
    try:
        fix_pvfrs_tasks_table()
        logger.info("✅ PVFRS任务表结构修复完成！")
        
    except Exception as e:
        logger.error(f"❌ PVFRS任务表结构修复失败: {str(e)}")
        raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
