"""
迁移：为 historical_quotes / historical_quotes_hk 增加 (code, date DESC) 复合索引，
加速按股票取最新收盘价的查询。
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
                CREATE INDEX IF NOT EXISTS idx_historical_quotes_code_date
                ON historical_quotes (code, date DESC)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_historical_quotes_hk_code_date
                ON historical_quotes_hk (code, date DESC)
                """
            )
        )
        conn.commit()
    logger.info("historical_quotes (code, date) 索引迁移完成")


if __name__ == "__main__":
    upgrade()
