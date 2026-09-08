"""
迁移：stock_realtime_quote 增加 buy_price / sell_price
（新浪 stock_zh_a_spot 的「买入」「卖出」字段）
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
                ALTER TABLE stock_realtime_quote
                ADD COLUMN IF NOT EXISTS buy_price DOUBLE PRECISION
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE stock_realtime_quote
                ADD COLUMN IF NOT EXISTS sell_price DOUBLE PRECISION
                """
            )
        )
        conn.commit()
    logger.info("stock_realtime_quote.buy_price/sell_price 迁移完成")


if __name__ == "__main__":
    upgrade()
