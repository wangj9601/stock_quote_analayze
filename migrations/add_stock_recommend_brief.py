"""
迁移：个股推荐简报表 stock_recommend_brief
统一存放日/周/月简报快照（asof 冻结）。
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
                CREATE TABLE IF NOT EXISTS stock_recommend_brief (
                    id SERIAL PRIMARY KEY,
                    horizon VARCHAR(16) NOT NULL,
                    asof_date DATE NOT NULL,
                    plan_for VARCHAR(64),
                    late_run BOOLEAN NOT NULL DEFAULT FALSE,
                    market_stance VARCHAR(16),
                    summary_json JSONB,
                    items_json JSONB NOT NULL DEFAULT '[]'::jsonb,
                    risk_observe_json JSONB,
                    kpi_json JSONB,
                    generated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_stock_recommend_brief_horizon_asof
                        UNIQUE (horizon, asof_date)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_stock_recommend_brief_asof
                ON stock_recommend_brief (asof_date DESC)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_stock_recommend_brief_horizon_asof
                ON stock_recommend_brief (horizon, asof_date DESC)
                """
            )
        )
    logger.info("stock_recommend_brief 表已就绪")


if __name__ == "__main__":
    upgrade()
