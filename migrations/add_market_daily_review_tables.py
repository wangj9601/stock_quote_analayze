# -*- coding: utf-8 -*-
"""迁移：涨停股池日表 + 每日复盘快照 + 主线上榜命中表。"""

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
                CREATE TABLE IF NOT EXISTS stock_zt_pool_daily (
                    code TEXT NOT NULL,
                    trade_date VARCHAR(10) NOT NULL,
                    name TEXT,
                    change_percent DOUBLE PRECISION,
                    price DOUBLE PRECISION,
                    amount DOUBLE PRECISION,
                    float_mv DOUBLE PRECISION,
                    total_mv DOUBLE PRECISION,
                    turnover_rate DOUBLE PRECISION,
                    seal_fund DOUBLE PRECISION,
                    first_seal_time VARCHAR(32),
                    last_seal_time VARCHAR(32),
                    break_count INTEGER,
                    limit_stats VARCHAR(64),
                    board_count INTEGER,
                    industry VARCHAR(100),
                    source VARCHAR(32) NOT NULL DEFAULT 'em_zt_pool',
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (code, trade_date)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_stock_zt_pool_daily_trade_date
                ON stock_zt_pool_daily (trade_date)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS market_daily_review (
                    trade_date VARCHAR(10) PRIMARY KEY,
                    vol_trillion DOUBLE PRECISION,
                    limit_up_count INTEGER,
                    cb_count INTEGER,
                    height INTEGER,
                    prev_cb_return DOUBLE PRECISION,
                    lo_value DOUBLE PRECISION,
                    hi_value DOUBLE PRECISION,
                    sp_value DOUBLE PRECISION,
                    lo_percentile DOUBLE PRECISION,
                    hi_percentile DOUBLE PRECISION,
                    sp_percentile DOUBLE PRECISION,
                    limit_source VARCHAR(32),
                    hard_gates JSONB,
                    season VARCHAR(16),
                    season_detail JSONB,
                    rules_json JSONB,
                    mainline_json JSONB,
                    viewpoint_md TEXT,
                    advice_md TEXT,
                    viewpoint_override BOOLEAN DEFAULT FALSE,
                    advice_override BOOLEAN DEFAULT FALSE,
                    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS market_daily_mainline_hits (
                    trade_date VARCHAR(10) NOT NULL,
                    board_type VARCHAR(16) NOT NULL,
                    board_code VARCHAR(32) NOT NULL,
                    board_name VARCHAR(100),
                    hit BOOLEAN NOT NULL DEFAULT TRUE,
                    hit_reasons JSONB,
                    change_percent DOUBLE PRECISION,
                    limit_up_count INTEGER,
                    net_inflow DOUBLE PRECISION,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (trade_date, board_type, board_code)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_market_daily_mainline_hits_date
                ON market_daily_mainline_hits (trade_date)
                """
            )
        )
    logger.info("market daily review / zt pool 表迁移完成")


if __name__ == "__main__":
    upgrade()
