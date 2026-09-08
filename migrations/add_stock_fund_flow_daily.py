"""
迁移：创建 stock_fund_flow_daily（同花顺即时流入/流出日快照）
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from backend_core.database.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upgrade():
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS stock_fund_flow_daily (
                    code TEXT NOT NULL,
                    trade_date VARCHAR(10) NOT NULL,
                    name TEXT,
                    inflow_amount DOUBLE PRECISION,
                    outflow_amount DOUBLE PRECISION,
                    net_amount DOUBLE PRECISION,
                    turnover_amount DOUBLE PRECISION,
                    change_percent DOUBLE PRECISION,
                    turnover_rate DOUBLE PRECISION,
                    current_price DOUBLE PRECISION,
                    source VARCHAR(20) NOT NULL DEFAULT 'ths',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (code, trade_date)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_stock_fund_flow_daily_trade_date
                ON stock_fund_flow_daily (trade_date)
                """
            )
        )
    logger.info("stock_fund_flow_daily 表迁移完成")


if __name__ == "__main__":
    upgrade()
