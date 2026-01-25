#!/usr/bin/env python3
"""创建PVFRS监控指标表"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from backend_api.database import engine as main_engine
import logging

# 配置日志
logger = logging.getLogger(__name__)

def create_monitor_metrics_table():
    """创建PVFRS监控指标表"""
    logger.info("开始创建PVFRS监控指标表...")
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS pvfrs_monitor_metrics (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMP NOT NULL,
        metric_name VARCHAR(100) NOT NULL,
        metric_value DECIMAL(15,6) NOT NULL,
        tags JSONB,
        created_at TIMESTAMP DEFAULT NOW()
    );
    
    CREATE INDEX IF NOT EXISTS idx_pvfrs_monitor_metrics_timestamp ON pvfrs_monitor_metrics(timestamp);
    CREATE INDEX IF NOT EXISTS idx_pvfrs_monitor_metrics_metric_name ON pvfrs_monitor_metrics(metric_name);
    CREATE INDEX IF NOT EXISTS idx_pvfrs_monitor_metrics_created_at ON pvfrs_monitor_metrics(created_at);
    """
    
    try:
        with main_engine.connect() as conn:
            # 创建表
            conn.execute(text(create_table_sql))
            conn.commit()
            logger.info("✅ PVFRS监控指标表创建完成")
            
    except Exception as e:
        logger.error(f"❌ 创建PVFRS监控指标表失败: {str(e)}")
        raise

def main():
    """主函数"""
    logger.info("开始创建PVFRS监控指标表...")
    
    try:
        create_monitor_metrics_table()
        logger.info("✅ PVFRS监控指标表创建完成！")
        
    except Exception as e:
        logger.error(f"❌ PVFRS监控指标表创建失败: {str(e)}")
        raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
