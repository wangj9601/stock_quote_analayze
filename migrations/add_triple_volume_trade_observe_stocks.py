"""
迁移：triple_volume_trade_observe_stocks（用户 3倍量策略交易观察股）
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from backend_core.database.db import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upgrade():
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS triple_volume_trade_observe_stocks (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    market VARCHAR(10) NOT NULL DEFAULT 'CN',
                    code VARCHAR(20) NOT NULL,
                    name VARCHAR(200),
                    observe_trade_date DATE,
                    observe_snapshot_json JSONB,
                    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_tvo_trade_observe_user_market_code UNIQUE (user_id, market, code)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_tvo_trade_observe_user_id
                ON triple_volume_trade_observe_stocks (user_id)
                """
            )
        )
        conn.commit()
    logger.info("triple_volume_trade_observe_stocks 迁移完成")


if __name__ == "__main__":
    upgrade()
