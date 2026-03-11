"""
数据库迁移脚本 - users 表增加 wechat_userid 字段
用于企业微信成员 UserID，通知发送时若包含微信方式则读取此字段。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from backend_core.database.db import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upgrade():
    """为 users 表添加 wechat_userid 列（若不存在）"""
    logger.info("检查并添加 users 表 wechat_userid 字段...")
    check_sql = text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'wechat_userid'
    """)
    with engine.begin() as conn:
        result = conn.execute(check_sql)
        if not result.fetchone():
            conn.execute(text("""
                ALTER TABLE users
                ADD COLUMN wechat_userid VARCHAR(100)
            """))
            conn.execute(text("""
                CREATE INDEX idx_users_wechat_userid ON users(wechat_userid)
            """))
            logger.info("✅ users.wechat_userid 添加成功")
        else:
            logger.info("✅ users.wechat_userid 已存在")


if __name__ == "__main__":
    upgrade()
