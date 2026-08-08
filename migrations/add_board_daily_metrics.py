# -*- coding: utf-8 -*-
"""迁移：行业/概念板日度指标表（sector_slope 等）。

业务写入侧仅同花顺行业板会刷新 industry 表；概念表预留对称结构。

用法:
    python migrations/add_board_daily_metrics.py
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

TABLES = ("industry_board_daily_metrics", "concept_board_daily_metrics")


def run() -> None:
    with engine.begin() as conn:
        for table in TABLES:
            conn.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS {table} (
                        board_code VARCHAR(20) NOT NULL,
                        slope_asof_date DATE NOT NULL,
                        sector_slope DOUBLE PRECISION,
                        sector_slope_window INTEGER NOT NULL DEFAULT 60,
                        member_count_used INTEGER,
                        updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                        PRIMARY KEY (board_code, slope_asof_date)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    f"""
                    CREATE INDEX IF NOT EXISTS ix_{table}_asof
                    ON {table} (slope_asof_date DESC)
                    """
                )
            )
            logger.info("%s 已就绪", table)


if __name__ == "__main__":
    run()
