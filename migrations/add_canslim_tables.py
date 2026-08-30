"""
迁移：CAN SLIM 一期所需表
- stock_fina_indicator：A 股财务指标（C/A）
- index_historical_quotes：A 股指数日线（M）
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
                CREATE TABLE IF NOT EXISTS stock_fina_indicator (
                    code TEXT NOT NULL,
                    end_date VARCHAR(8) NOT NULL,
                    ann_date VARCHAR(8),
                    ts_code VARCHAR(16),
                    eps DOUBLE PRECISION,
                    q_eps DOUBLE PRECISION,
                    basic_eps_yoy DOUBLE PRECISION,
                    dt_eps_yoy DOUBLE PRECISION,
                    q_eps_yoy DOUBLE PRECISION,
                    q_profit_yoy DOUBLE PRECISION,
                    q_netprofit_yoy DOUBLE PRECISION,
                    q_sales_yoy DOUBLE PRECISION,
                    roe DOUBLE PRECISION,
                    roe_waa DOUBLE PRECISION,
                    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (code, end_date)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_stock_fina_ann_date
                ON stock_fina_indicator (ann_date)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_stock_fina_code_end
                ON stock_fina_indicator (code, end_date DESC)
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS index_historical_quotes (
                    ts_code VARCHAR(16) NOT NULL,
                    trade_date DATE NOT NULL,
                    code VARCHAR(16),
                    name VARCHAR(64),
                    open DOUBLE PRECISION,
                    high DOUBLE PRECISION,
                    low DOUBLE PRECISION,
                    close DOUBLE PRECISION,
                    pre_close DOUBLE PRECISION,
                    change DOUBLE PRECISION,
                    pct_chg DOUBLE PRECISION,
                    vol DOUBLE PRECISION,
                    amount DOUBLE PRECISION,
                    collected_source VARCHAR(32) DEFAULT 'tushare',
                    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (ts_code, trade_date)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_index_hist_trade_date
                ON index_historical_quotes (trade_date)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_index_hist_code_date
                ON index_historical_quotes (code, trade_date DESC)
                """
            )
        )
    logger.info("stock_fina_indicator / index_historical_quotes 表已就绪")


if __name__ == "__main__":
    upgrade()
