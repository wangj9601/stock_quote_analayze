"""
迁移：创建 stock_fund_flow_em_daily（东财个股主力/分档资金流日序列）

已弃用（schema 入口已切 Alembic）：请使用
  alembic/versions/0002_em_fund_flow_daily.py
  python scripts/db_migrate.py upgrade --yes
本脚本仅作空库历史引导 / 兼容保留，内容与 0002 幂等一致。
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
                CREATE TABLE IF NOT EXISTS stock_fund_flow_em_daily (
                    code TEXT NOT NULL,
                    trade_date VARCHAR(10) NOT NULL,
                    main_net_inflow DOUBLE PRECISION,
                    main_net_inflow_pct DOUBLE PRECISION,
                    super_large_net_inflow DOUBLE PRECISION,
                    super_large_net_inflow_pct DOUBLE PRECISION,
                    large_net_inflow DOUBLE PRECISION,
                    large_net_inflow_pct DOUBLE PRECISION,
                    mid_net_inflow DOUBLE PRECISION,
                    mid_net_inflow_pct DOUBLE PRECISION,
                    small_net_inflow DOUBLE PRECISION,
                    small_net_inflow_pct DOUBLE PRECISION,
                    close_price DOUBLE PRECISION,
                    change_percent DOUBLE PRECISION,
                    source VARCHAR(20) NOT NULL DEFAULT 'em',
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
                CREATE INDEX IF NOT EXISTS idx_stock_fund_flow_em_daily_trade_date
                ON stock_fund_flow_em_daily (trade_date)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_stock_fund_flow_em_daily_code_date
                ON stock_fund_flow_em_daily (code, trade_date DESC)
                """
            )
        )
    logger.info("stock_fund_flow_em_daily 表迁移完成")


if __name__ == "__main__":
    upgrade()
