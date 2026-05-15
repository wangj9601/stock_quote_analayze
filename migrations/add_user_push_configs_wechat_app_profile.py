"""
迁移：user_push_configs.wechat_app_profile
按推送任务选择不同企业微信主体：非空时读取 WECHAT_<PROFILE>_CORP_ID / _CORP_SECRET / _AGENT_ID。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from backend_core.database.db import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upgrade():
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                ALTER TABLE user_push_configs
                ADD COLUMN IF NOT EXISTS wechat_app_profile VARCHAR(32)
                """
            )
        )
        conn.commit()
    logger.info("user_push_configs.wechat_app_profile 迁移完成")


def downgrade():
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                ALTER TABLE user_push_configs
                DROP COLUMN IF EXISTS wechat_app_profile
                """
            )
        )
        conn.commit()
    logger.info("已回滚 wechat_app_profile")


if __name__ == "__main__":
    upgrade()
