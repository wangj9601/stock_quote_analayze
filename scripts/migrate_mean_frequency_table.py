#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库迁移脚本:为 mean_frequency_resonance_indicators 表添加缺失的字段
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend_core.database.db import SessionLocal
from sqlalchemy import text
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def migrate_mean_frequency_table():
    """为 mean_frequency_resonance_indicators 表添加缺失的字段"""
    session = SessionLocal()
    
    try:
        logger.info("开始迁移 mean_frequency_resonance_indicators 表...")
        
        # 添加 d1 字段
        try:
            session.execute(text("ALTER TABLE mean_frequency_resonance_indicators ADD COLUMN IF NOT EXISTS d1 REAL"))
            logger.info("添加字段 d1 成功")
        except Exception as e:
            logger.warning(f"添加字段 d1 失败（可能已存在）: {e}")
        
        # 添加 d1_date 字段
        try:
            session.execute(text("ALTER TABLE mean_frequency_resonance_indicators ADD COLUMN IF NOT EXISTS d1_date VARCHAR(20)"))
            logger.info("添加字段 d1_date 成功")
        except Exception as e:
            logger.warning(f"添加字段 d1_date 失败（可能已存在）: {e}")
        
        # 添加 d20 字段
        try:
            session.execute(text("ALTER TABLE mean_frequency_resonance_indicators ADD COLUMN IF NOT EXISTS d20 REAL"))
            logger.info("添加字段 d20 成功")
        except Exception as e:
            logger.warning(f"添加字段 d20 失败（可能已存在）: {e}")
        
        # 添加 d20_date 字段
        try:
            session.execute(text("ALTER TABLE mean_frequency_resonance_indicators ADD COLUMN IF NOT EXISTS d20_date VARCHAR(20)"))
            logger.info("添加字段 d20_date 成功")
        except Exception as e:
            logger.warning(f"添加字段 d20_date 失败（可能已存在）: {e}")
        
        session.commit()
        logger.info("迁移完成!")
        
        # 验证字段是否存在
        result = session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'mean_frequency_resonance_indicators'
            ORDER BY ordinal_position
        """))
        
        columns = [row[0] for row in result.fetchall()]
        logger.info(f"当前表字段: {', '.join(columns)}")
        
        # 检查必需的字段是否都存在
        required_fields = ['d1', 'd1_date', 'd20', 'd20_date']
        missing_fields = [field for field in required_fields if field not in columns]
        
        if missing_fields:
            logger.error(f"以下字段仍然缺失: {', '.join(missing_fields)}")
        else:
            logger.info("所有必需字段都已存在!")
        
    except Exception as e:
        logger.error(f"迁移失败: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    migrate_mean_frequency_table()
