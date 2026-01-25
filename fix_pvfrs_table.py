#!/usr/bin/env python3
"""修复PVFRS表结构，添加缺失的字段"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from backend_api.database import engine as main_engine
import logging

# 配置日志
logger = logging.getLogger(__name__)

def fix_pvfrs_results_table():
    """修复PVFRS结果表，添加缺失的字段"""
    logger.info("开始修复PVFRS结果表结构...")
    
    # 添加缺失字段的SQL
    alter_table_sql = """
    ALTER TABLE pvfrs_backtest_results_enhanced 
    ADD COLUMN IF NOT EXISTS report_id VARCHAR(50) UNIQUE,
    ADD COLUMN IF NOT EXISTS config_snapshot JSONB,
    ADD COLUMN IF NOT EXISTS summary_data JSONB;
    
    CREATE INDEX IF NOT EXISTS idx_pvfrs_results_report_id ON pvfrs_backtest_results_enhanced(report_id);
    """
    
    try:
        with main_engine.connect() as conn:
            # 执行ALTER TABLE语句
            conn.execute(text(alter_table_sql))
            conn.commit()
            logger.info("✅ PVFRS结果表修复完成")
            
    except Exception as e:
        logger.error(f"❌ 修复PVFRS结果表失败: {str(e)}")
        raise

def main():
    """主函数"""
    logger.info("开始修复PVFRS表结构...")
    
    try:
        fix_pvfrs_results_table()
        logger.info("✅ PVFRS表结构修复完成！")
        
    except Exception as e:
        logger.error(f"❌ PVFRS表结构修复失败: {str(e)}")
        raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
