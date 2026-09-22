"""
迁移：A 股集合竞价（同花顺 Fuyao）。

- stock_auction_daily：个股每日集合竞价快照（final/live）
- stock_auction_benchmark：短线风向标竞价基准
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
                CREATE TABLE IF NOT EXISTS stock_auction_daily (
                    trade_date VARCHAR(10) NOT NULL,
                    code VARCHAR(10) NOT NULL,
                    auction_phase VARCHAR(16) NOT NULL DEFAULT 'final',
                    thscode VARCHAR(16),
                    name TEXT,
                    data_status VARCHAR(32),
                    auction_price DOUBLE PRECISION,
                    auction_pct DOUBLE PRECISION,
                    auction_volume DOUBLE PRECISION,
                    auction_volume_shares DOUBLE PRECISION,
                    auction_amount DOUBLE PRECISION,
                    auction_unmatched DOUBLE PRECISION,
                    auction_unmatched_shares DOUBLE PRECISION,
                    auction_turnover_pct DOUBLE PRECISION,
                    auction_yesterday_ratio_pct DOUBLE PRECISION,
                    auction_volume_ratio DOUBLE PRECISION,
                    pre_close_price DOUBLE PRECISION,
                    open_price DOUBLE PRECISION,
                    last_price DOUBLE PRECISION,
                    float_market_cap DOUBLE PRECISION,
                    source VARCHAR(20) NOT NULL DEFAULT 'fuyao',
                    response_timestamp BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (trade_date, code, auction_phase)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_stock_auction_daily_date_pct
                ON stock_auction_daily (trade_date, auction_pct DESC NULLS LAST)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_stock_auction_daily_code_date
                ON stock_auction_daily (code, trade_date DESC)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS stock_auction_benchmark (
                    trade_date VARCHAR(10) NOT NULL,
                    seq INTEGER NOT NULL,
                    thscode VARCHAR(16),
                    code VARCHAR(10),
                    name TEXT,
                    auction_pct DOUBLE PRECISION,
                    tags JSONB,
                    source VARCHAR(20) NOT NULL DEFAULT 'fuyao',
                    response_timestamp BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (trade_date, seq)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_stock_auction_benchmark_code_date
                ON stock_auction_benchmark (code, trade_date DESC)
                """
            )
        )
    logger.info("stock_auction_daily / stock_auction_benchmark 表迁移完成")


if __name__ == "__main__":
    upgrade()
