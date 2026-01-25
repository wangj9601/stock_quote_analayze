#!/usr/bin/env python3
"""修复trade_date字段的NOT NULL约束"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from backend_api.database import engine as main_engine
import logging

# 配置日志
logger = logging.getLogger(__name__)

def fix_trade_date_constraint():
    """修复trade_date字段的NOT NULL约束"""
    logger.info("开始修复trade_date字段的NOT NULL约束...")
    
    # 修改字段约束的SQL
    alter_table_sql = """
    ALTER TABLE pvfrs_trade_records_enhanced 
    ALTER COLUMN trade_date DROP NOT NULL;
    """
    
    try:
        with main_engine.connect() as conn:
            # 执行ALTER TABLE语句
            conn.execute(text(alter_table_sql))
            conn.commit()
            logger.info("✅ trade_date字段约束修复完成")
            
    except Exception as e:
        logger.error(f"❌ 修复trade_date字段约束失败: {str(e)}")
        raise

def main():
    """主函数"""
    logger.info("开始修复trade_date字段约束...")
    
    try:
        fix_trade_date_constraint()
        logger.info("✅ trade_date字段约束修复完成！")
        
    except Exception as e:
        logger.error(f"❌ trade_date字段约束修复失败: {str(e)}")
        raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
