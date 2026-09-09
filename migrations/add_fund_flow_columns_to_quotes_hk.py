"""
迁移：historical_quotes_hk / stock_realtime_quote_hk 增加资金流向字段
（与 stock_fund_flow_daily_hk 对齐）
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from backend_core.database.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_COLUMNS = (
    ("inflow_amount", "DOUBLE PRECISION"),
    ("outflow_amount", "DOUBLE PRECISION"),
    ("net_amount", "DOUBLE PRECISION"),
)


def _add_cols(conn, table: str) -> None:
    for col, typ in _COLUMNS:
        conn.execute(
            text(
                f"""
                ALTER TABLE {table}
                ADD COLUMN IF NOT EXISTS {col} {typ}
                """
            )
        )
    logger.info("%s 资金流字段就绪: inflow/outflow/net_amount", table)


def upgrade():
    with engine.begin() as conn:
        _add_cols(conn, "historical_quotes_hk")
        _add_cols(conn, "stock_realtime_quote_hk")
    logger.info("港股行情表资金流字段迁移完成")


if __name__ == "__main__":
    upgrade()
