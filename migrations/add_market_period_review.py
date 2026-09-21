# -*- coding: utf-8 -*-
"""迁移：周报 / 月报复盘快照。"""

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
                CREATE TABLE IF NOT EXISTS market_period_review (
                    period_type VARCHAR(8) NOT NULL,
                    period_key VARCHAR(16) NOT NULL,
                    start_date VARCHAR(10),
                    end_date VARCHAR(10),
                    snapshot_json JSONB,
                    viewpoint_md TEXT,
                    advice_md TEXT,
                    viewpoint_override BOOLEAN DEFAULT FALSE,
                    advice_override BOOLEAN DEFAULT FALSE,
                    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (period_type, period_key)
                )
                """
            )
        )
    logger.info("market_period_review 表迁移完成")


if __name__ == "__main__":
    upgrade()
