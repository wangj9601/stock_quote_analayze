"""
迁移：gms_trade_observe_stocks 增加 key_focus_flag（交易观察列表重点关注标记）
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from sqlalchemy import text

from backend_core.database.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upgrade():
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                ALTER TABLE gms_trade_observe_stocks
                ADD COLUMN IF NOT EXISTS key_focus_flag BOOLEAN NOT NULL DEFAULT FALSE
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_gms_trade_observe_key_focus_flag
                ON gms_trade_observe_stocks (user_id, key_focus_flag)
                """
            )
        )
        conn.commit()
    logger.info("gms_trade_observe_stocks.key_focus_flag 迁移完成")


if __name__ == "__main__":
    upgrade()
