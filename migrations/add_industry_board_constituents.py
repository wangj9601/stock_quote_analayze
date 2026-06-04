"""
迁移：industry_board_constituents（东财行业板块成分股 ↔ 股票代码）
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
                CREATE TABLE IF NOT EXISTS industry_board_constituents (
                    board_code VARCHAR(20) NOT NULL,
                    stock_code VARCHAR(20) NOT NULL,
                    stock_name VARCHAR(100),
                    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (board_code, stock_code)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_industry_board_constituents_stock_code
                ON industry_board_constituents (stock_code)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_industry_board_constituents_board_code
                ON industry_board_constituents (board_code)
                """
            )
        )
        conn.commit()
    logger.info("industry_board_constituents 迁移完成")


if __name__ == "__main__":
    upgrade()
