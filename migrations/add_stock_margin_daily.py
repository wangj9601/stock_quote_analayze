"""
迁移：创建 stock_margin_daily（融资融券个股日明细，金额单位：元）。
幂等，可重复执行。
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from backend_core.database.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


DDL = """
CREATE TABLE IF NOT EXISTS stock_margin_daily (
    code TEXT NOT NULL,
    trade_date VARCHAR(10) NOT NULL,
    name VARCHAR(64),
    rzye DOUBLE PRECISION,
    rzmre DOUBLE PRECISION,
    rzche DOUBLE PRECISION,
    rqye DOUBLE PRECISION,
    rqyl DOUBLE PRECISION,
    rqmcl DOUBLE PRECISION,
    rqchl DOUBLE PRECISION,
    rzrqye DOUBLE PRECISION,
    source VARCHAR(32) NOT NULL DEFAULT 'tushare',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (code, trade_date)
)
"""


def upgrade():
    with engine.begin() as conn:
        conn.execute(text(DDL))
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_stock_margin_daily_trade_date
                ON stock_margin_daily (trade_date)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_stock_margin_daily_code_date
                ON stock_margin_daily (code, trade_date DESC)
                """
            )
        )
    logger.info("stock_margin_daily 表已就绪")


if __name__ == "__main__":
    upgrade()
