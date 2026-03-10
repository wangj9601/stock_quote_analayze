#!/usr/bin/env python3
"""创建PVFRS告警表"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from backend_api.database import engine as main_engine
import logging

# 配置日志
logger = logging.getLogger(__name__)

def create_alerts_table():
    """创建PVFRS告警表"""
    logger.info("开始创建PVFRS告警表...")
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS pvfrs_alerts (
        id SERIAL PRIMARY KEY,
        level VARCHAR(20) NOT NULL,
        type VARCHAR(50) NOT NULL,
        title VARCHAR(200) NOT NULL,
        message TEXT NOT NULL,
        timestamp TIMESTAMP NOT NULL,
        severity VARCHAR(20) DEFAULT 'medium',
        acknowledged BOOLEAN DEFAULT FALSE,
        acknowledged_at TIMESTAMP,
        source VARCHAR(100),
        details JSONB,
        created_at TIMESTAMP DEFAULT NOW()
    );
    
    CREATE INDEX IF NOT EXISTS idx_pvfrs_alerts_timestamp ON pvfrs_alerts(timestamp);
    CREATE INDEX IF NOT EXISTS idx_pvfrs_alerts_level ON pvfrs_alerts(level);
    CREATE INDEX IF NOT EXISTS idx_pvfrs_alerts_type ON pvfrs_alerts(type);
    CREATE INDEX IF NOT EXISTS idx_pvfrs_alerts_acknowledged ON pvfrs_alerts(acknowledged);
    CREATE INDEX IF NOT EXISTS idx_pvfrs_alerts_severity ON pvfrs_alerts(severity);
    CREATE INDEX IF NOT EXISTS idx_pvfrs_alerts_created_at ON pvfrs_alerts(created_at);
    """
    
    try:
        with main_engine.connect() as conn:
            # 创建表
            conn.execute(text(create_table_sql))
            conn.commit()
            logger.info("✅ PVFRS告警表创建完成")
            
    except Exception as e:
        logger.error(f"❌ 创建PVFRS告警表失败: {str(e)}")
        raise

def main():
    """主函数"""
    logger.info("开始创建PVFRS告警表...")
    
    try:
        create_alerts_table()
        logger.info("✅ PVFRS告警表创建完成！")
        
    except Exception as e:
        logger.error(f"❌ PVFRS告警表创建失败: {str(e)}")
        raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
