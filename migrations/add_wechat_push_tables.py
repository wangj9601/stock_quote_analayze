"""
数据库迁移脚本 - 添加微信推送相关表
创建 user_push_configs 和 push_records 表
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from backend_core.database.db import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upgrade():
    """创建推送相关表"""
    
    # 1. 为 users 表添加微信相关字段（如果不存在）
    logger.info("检查并添加 users 表的微信字段...")
    
    # 检查字段是否存在
    check_wechat_openid = text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='users' AND column_name='wechat_openid'
    """)
    
    with engine.connect() as conn:
        result = conn.execute(check_wechat_openid)
        if not result.fetchone():
            logger.info("添加 wechat_openid 字段...")
            conn.execute(text("""
                ALTER TABLE users 
                ADD COLUMN wechat_openid VARCHAR(100),
                ADD COLUMN wechat_type VARCHAR(20)
            """))
            conn.execute(text("""
                CREATE INDEX idx_users_wechat_openid ON users(wechat_openid)
            """))
            conn.commit()
            logger.info("✅ users 表字段添加成功")
        else:
            logger.info("✅ users 表字段已存在")
    
    # 2. 创建 user_push_configs 表
    logger.info("创建 user_push_configs 表...")
    
    create_user_push_configs = text("""
        CREATE TABLE IF NOT EXISTS user_push_configs (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            channels JSON NOT NULL DEFAULT '["wechat"]'::json,
            push_times JSON NOT NULL DEFAULT '["09:30", "15:30"]'::json,
            report_type VARCHAR(20) NOT NULL DEFAULT 'summary',
            stock_codes JSON,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    with engine.connect() as conn:
        conn.execute(create_user_push_configs)
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_user_push_configs_user_id ON user_push_configs(user_id)"))
        conn.commit()
        logger.info("✅ user_push_configs 表创建成功")
    
    # 3. 创建 push_records 表
    logger.info("创建 push_records 表...")
    
    create_push_records = text("""
        CREATE TABLE IF NOT EXISTS push_records (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            push_date DATE NOT NULL,
            push_time VARCHAR(10) NOT NULL,
            report_type VARCHAR(20) NOT NULL,
            channel_status JSON NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            report_file_path VARCHAR(500),
            error_messages JSON,
            retry_count INTEGER NOT NULL DEFAULT 0,
            max_retries INTEGER NOT NULL DEFAULT 3,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)
    
    with engine.connect() as conn:
        conn.execute(create_push_records)
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_push_records_user_id ON push_records(user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_push_records_push_date ON push_records(push_date)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_push_records_status ON push_records(status)"))
        conn.commit()
        logger.info("✅ push_records 表创建成功")
    
    logger.info("=" * 60)
    logger.info("✅ 所有表创建成功！")
    logger.info("=" * 60)


def downgrade():
    """删除推送相关表"""
    logger.info("删除推送相关表...")
    
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS push_records CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS user_push_configs CASCADE"))
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS wechat_openid"))
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS wechat_type"))
        conn.commit()
    
    logger.info("✅ 表删除成功")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        downgrade()
    else:
        upgrade()
