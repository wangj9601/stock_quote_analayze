"""
迁移：创建 board_fund_flow_daily（行业/概念板块资金流日快照）
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
                CREATE TABLE IF NOT EXISTS board_fund_flow_daily (
                    board_kind VARCHAR(16) NOT NULL,
                    board_code_source VARCHAR(32) NOT NULL DEFAULT 'tonghuashun',
                    board_code VARCHAR(32) NOT NULL,
                    trade_date DATE NOT NULL,
                    board_name VARCHAR(100),
                    change_percent DOUBLE PRECISION,
                    inflow_amount DOUBLE PRECISION,
                    outflow_amount DOUBLE PRECISION,
                    main_net_inflow DOUBLE PRECISION,
                    main_net_inflow_pct DOUBLE PRECISION,
                    super_large_net_inflow DOUBLE PRECISION,
                    large_net_inflow DOUBLE PRECISION,
                    mid_net_inflow DOUBLE PRECISION,
                    small_net_inflow DOUBLE PRECISION,
                    source VARCHAR(32) NOT NULL DEFAULT 'ths_fund_flow',
                    em_board_code VARCHAR(32),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (board_kind, board_code_source, board_code, trade_date)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_board_fund_flow_daily_trade_date
                ON board_fund_flow_daily (trade_date)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_board_fund_flow_daily_kind_date
                ON board_fund_flow_daily (board_kind, trade_date)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_board_fund_flow_daily_code_date
                ON board_fund_flow_daily (board_code, trade_date)
                """
            )
        )
    logger.info("board_fund_flow_daily 表迁移完成")


if __name__ == "__main__":
    upgrade()
