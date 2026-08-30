"""
迁移：创建 rs_ratings 表（IBD 风格股价相对强度评级）
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
                CREATE TABLE IF NOT EXISTS rs_ratings (
                    code TEXT NOT NULL,
                    date VARCHAR(20) NOT NULL,
                    market_type VARCHAR(10) NOT NULL DEFAULT 'CN',
                    rs_raw DOUBLE PRECISION,
                    rs_rating INTEGER,
                    roc_63 DOUBLE PRECISION,
                    roc_126 DOUBLE PRECISION,
                    roc_189 DOUBLE PRECISION,
                    roc_252 DOUBLE PRECISION,
                    universe_size INTEGER,
                    coverage_ratio DOUBLE PRECISION,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (code, date, market_type)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_rs_ratings_date
                ON rs_ratings (date)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_rs_ratings_code_date
                ON rs_ratings (code, date DESC)
                """
            )
        )
    logger.info("rs_ratings 表已就绪")


if __name__ == "__main__":
    upgrade()
