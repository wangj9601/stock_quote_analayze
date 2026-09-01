# -*- coding: utf-8 -*-
"""迁移：同花顺行业/概念板块历史 OHLC 表。

用法:
    python migrations/add_board_historical_quotes.py
"""

from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from backend_core.database.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS {table} (
    board_code VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    board_name VARCHAR(100),
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume DOUBLE PRECISION,
    amount DOUBLE PRECISION,
    collected_source VARCHAR(32) NOT NULL DEFAULT 'tonghuashun',
    update_time TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (board_code, trade_date)
)
"""

TABLES = (
    "industry_board_historical_quotes",
    "concept_board_historical_quotes",
)


def run() -> None:
    with engine.begin() as conn:
        for table in TABLES:
            conn.execute(text(_TABLE_DDL.format(table=table)))
            conn.execute(
                text(
                    f"""
                    CREATE INDEX IF NOT EXISTS ix_{table}_trade_date
                    ON {table} (trade_date DESC)
                    """
                )
            )
            conn.execute(
                text(
                    f"""
                    CREATE INDEX IF NOT EXISTS ix_{table}_board_date
                    ON {table} (board_code, trade_date DESC)
                    """
                )
            )
            logger.info("%s 已就绪", table)


if __name__ == "__main__":
    run()
