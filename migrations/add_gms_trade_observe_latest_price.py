"""
迁移：gms_trade_observe_stocks 增加 latest_close_price / latest_close_date（按需查询后持久化）
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
                ADD COLUMN IF NOT EXISTS latest_close_price DOUBLE PRECISION
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE gms_trade_observe_stocks
                ADD COLUMN IF NOT EXISTS latest_close_date DATE
                """
            )
        )
        conn.commit()
    logger.info("gms_trade_observe_stocks.latest_close_price/date 迁移完成")


if __name__ == "__main__":
    upgrade()
