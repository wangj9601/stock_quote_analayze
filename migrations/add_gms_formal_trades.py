"""
迁移：gms_formal_trades（GMS 正式交易记录）
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
                CREATE TABLE IF NOT EXISTS gms_formal_trades (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    market VARCHAR(10) NOT NULL DEFAULT 'CN',
                    code VARCHAR(20) NOT NULL,
                    name VARCHAR(200),
                    source_observe_id INTEGER,
                    entry_price DOUBLE PRECISION NOT NULL,
                    position_lots INTEGER NOT NULL DEFAULT 0,
                    exit_price DOUBLE PRECISION,
                    status VARCHAR(20) NOT NULL DEFAULT 'open',
                    signal_date DATE,
                    signal_snapshot_json JSONB,
                    notes TEXT,
                    entry_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                    exit_at TIMESTAMP WITHOUT TIME ZONE,
                    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_gms_formal_trades_user_status
                ON gms_formal_trades (user_id, status)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_gms_formal_trades_user_code
                ON gms_formal_trades (user_id, market, code)
                """
            )
        )
        conn.commit()
    logger.info("gms_formal_trades 迁移完成")


if __name__ == "__main__":
    upgrade()
