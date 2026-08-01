"""
迁移：新增 stock_adj_factor（每日复权因子，供查询层现算前复权）。

用法:
    python migrations/add_stock_adj_factor.py
"""

from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from backend_api.database import SessionLocal

logger = logging.getLogger(__name__)


def run() -> None:
    db = SessionLocal()
    try:
        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS stock_adj_factor (
                    code VARCHAR(32) NOT NULL,
                    trade_date DATE NOT NULL,
                    adj_factor DOUBLE PRECISION NOT NULL,
                    source VARCHAR(64),
                    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (code, trade_date)
                )
                """
            )
        )
        db.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_stock_adj_factor_trade_date
                ON stock_adj_factor (trade_date)
                """
            )
        )
        db.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_stock_adj_factor_code_updated
                ON stock_adj_factor (code, updated_at)
                """
            )
        )
        db.commit()
        logger.info("stock_adj_factor 表已就绪")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
