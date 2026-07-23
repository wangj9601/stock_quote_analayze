"""
迁移：URT 交易观察 / 正式交易独立表（urt_trade_observe_stocks、urt_trade_observe_history、urt_formal_trades）
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
                CREATE TABLE IF NOT EXISTS urt_trade_observe_stocks (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    market VARCHAR(10) NOT NULL DEFAULT 'CN',
                    code VARCHAR(20) NOT NULL,
                    name VARCHAR(200),
                    signal_snapshot_json JSONB,
                    signal_date DATE,
                    config_id INTEGER,
                    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_urt_trade_observe_user_market_code UNIQUE (user_id, market, code)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_urt_trade_observe_user_id
                ON urt_trade_observe_stocks (user_id)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_urt_trade_observe_config_id
                ON urt_trade_observe_stocks (config_id)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS urt_trade_observe_history (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    market VARCHAR(10) NOT NULL DEFAULT 'CN',
                    code VARCHAR(20) NOT NULL,
                    name VARCHAR(200),
                    signal_snapshot_json JSONB,
                    signal_date DATE,
                    config_id INTEGER,
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
                CREATE INDEX IF NOT EXISTS ix_urt_trade_observe_history_user_id
                ON urt_trade_observe_history (user_id)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_urt_trade_observe_history_removed_at
                ON urt_trade_observe_history (removed_at)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS urt_formal_trades (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
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
                    pnl_amount DOUBLE PRECISION,
                    pnl_percent DOUBLE PRECISION,
                    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_urt_formal_trades_user_status
                ON urt_formal_trades (user_id, status)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_urt_formal_trades_user_code
                ON urt_formal_trades (user_id, market, code)
                """
            )
        )
        conn.commit()
    logger.info("URT 交易观察/正式交易表迁移完成")


if __name__ == "__main__":
    upgrade()
