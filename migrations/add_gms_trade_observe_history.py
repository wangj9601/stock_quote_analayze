"""
迁移：gms_trade_observe_history（用户 GMS 交易观察股移除归档）
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
                CREATE TABLE IF NOT EXISTS gms_trade_observe_history (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    market VARCHAR(10) NOT NULL DEFAULT 'CN',
                    code VARCHAR(20) NOT NULL,
                    name VARCHAR(200),
                    signal_snapshot_json JSONB,
                    signal_date DATE,
                    observe_created_at TIMESTAMP WITHOUT TIME ZONE,
                    observe_updated_at TIMESTAMP WITHOUT TIME ZONE,
                    source_observe_id INTEGER,
                    removed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_gms_trade_observe_hist_user_removed
                ON gms_trade_observe_history (user_id, removed_at DESC)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_gms_trade_observe_hist_user_code
                ON gms_trade_observe_history (user_id, market, code)
                """
            )
        )
        conn.commit()
    logger.info("gms_trade_observe_history 迁移完成")


if __name__ == "__main__":
    upgrade()
