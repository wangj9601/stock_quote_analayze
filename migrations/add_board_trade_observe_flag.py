"""
迁移：行业/概念板块基础信息表增加 trade_observe_flag（交易观察标志）
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from backend_core.database.db import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_TABLES = ("industry_board_basic_info", "concept_board_basic_info")


def upgrade():
    with engine.connect() as conn:
        for table in _TABLES:
            conn.execute(
                text(
                    f"""
                    ALTER TABLE {table}
                    ADD COLUMN IF NOT EXISTS trade_observe_flag BOOLEAN NOT NULL DEFAULT FALSE
                    """
                )
            )
            conn.execute(
                text(
                    f"""
                    COMMENT ON COLUMN {table}.trade_observe_flag IS '交易观察标志：管理端标记需重点关注的板块'
                    """
                )
            )
        conn.commit()
    logger.info("board trade_observe_flag 迁移完成")


if __name__ == "__main__":
    upgrade()
