# -*- coding: utf-8 -*-
"""迁移：板日度斜率表增加 slope_source / slope_r2 / slope_n。

口径改造：官方指数优先、等权收益回退；走强用 R² 过滤。

用法:
    python migrations/alter_board_daily_metrics_slope_source_r2.py
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
                        slope_source VARCHAR(32),
                        slope_r2 DOUBLE PRECISION,
                        slope_n INTEGER,
                        updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                        PRIMARY KEY (board_code, slope_asof_date, sector_slope_window)
                    )
                    """
                )
            )
            for col, ddl in (
                ("slope_source", "VARCHAR(32)"),
                ("slope_r2", "DOUBLE PRECISION"),
                ("slope_n", "INTEGER"),
            ):
                conn.execute(
                    text(
                        f"""
                        ALTER TABLE {table}
                        ADD COLUMN IF NOT EXISTS {col} {ddl}
                        """
                    )
                )
            logger.info("%s 已确保 slope_source / slope_r2 / slope_n", table)


if __name__ == "__main__":
    run()
