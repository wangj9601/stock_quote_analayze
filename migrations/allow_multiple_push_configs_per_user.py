"""
数据库迁移 - 允许同一用户配置多条推送任务
移除 user_push_configs.user_id 的 UNIQUE 约束，使同一 user_id 可对应多行（不同 report_type/push_times 等）。
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
    """移除 user_id 唯一约束"""
    logger.info("移除 user_push_configs.user_id 唯一约束...")
    with engine.connect() as conn:
        # PostgreSQL 默认唯一约束名为 <table>_<column>_key
        conn.execute(text("""
            ALTER TABLE user_push_configs
            DROP CONSTRAINT IF EXISTS user_push_configs_user_id_key
        """))
        conn.commit()
    logger.info("✅ user_push_configs 现支持同一用户多条推送任务")


def downgrade():
    """恢复 user_id 唯一约束（仅当每用户仅一条配置时可执行）"""
    logger.info("恢复 user_push_configs.user_id 唯一约束...")
    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE user_push_configs
            ADD CONSTRAINT user_push_configs_user_id_key UNIQUE (user_id)
        """))
        conn.commit()
    logger.info("✅ 已恢复 user_id 唯一约束")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        downgrade()
    else:
        upgrade()
