"""
迁移：板日度斜率表主键纳入 sector_slope_window，支持中线(60)与短线(10)并存。

用法:
    python migrations/alter_board_daily_metrics_slope_window_pk.py
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


def _pk_columns(conn, table: str) -> list[str]:
    rows = conn.execute(
        text(
            """
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a
              ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = to_regclass(:tbl)
              AND i.indisprimary
            ORDER BY array_position(i.indkey, a.attnum)
            """
        ),
        {"tbl": table},
    ).fetchall()
    return [str(r[0]) for r in rows]


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
                        PRIMARY KEY (board_code, slope_asof_date, sector_slope_window)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    f"""
                    ALTER TABLE {table}
                    ADD COLUMN IF NOT EXISTS sector_slope_window INTEGER NOT NULL DEFAULT 60
                    """
                )
            )
            pk = _pk_columns(conn, table)
            wanted = ["board_code", "slope_asof_date", "sector_slope_window"]
            if pk != wanted:
                conn.execute(
                    text(
                        f"""
                        DELETE FROM {table} a
                        USING {table} b
                        WHERE a.board_code = b.board_code
                          AND a.slope_asof_date = b.slope_asof_date
                          AND a.sector_slope_window = b.sector_slope_window
                          AND a.ctid < b.ctid
                        """
                    )
                )
                conn.execute(text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_pkey"))
                conn.execute(
                    text(
                        f"""
                        ALTER TABLE {table}
                        ADD PRIMARY KEY (board_code, slope_asof_date, sector_slope_window)
                        """
                    )
                )
                logger.info("%s 主键已改为 (board_code, slope_asof_date, sector_slope_window)", table)
            else:
                logger.info("%s 主键已是三列，跳过", table)
            conn.execute(
                text(
                    f"""
                    CREATE INDEX IF NOT EXISTS ix_{table}_asof
                    ON {table} (slope_asof_date DESC)
                    """
                )
            )
            conn.execute(
                text(
                    f"""
                    CREATE INDEX IF NOT EXISTS ix_{table}_window_asof
                    ON {table} (sector_slope_window, slope_asof_date DESC)
                    """
                )
            )


if __name__ == "__main__":
    run()
