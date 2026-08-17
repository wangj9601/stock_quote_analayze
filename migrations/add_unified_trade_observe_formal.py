# -*- coding: utf-8 -*-
"""迁移：创建统一交易观察 / 正式交易表（PostgreSQL）。

表：trade_observe_stocks、trade_observe_history、formal_trades
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from backend_core.database.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


DDL = [
    """
    CREATE TABLE IF NOT EXISTS trade_observe_stocks (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        market VARCHAR(10) NOT NULL DEFAULT 'CN',
        code VARCHAR(20) NOT NULL,
        name VARCHAR(200),
        source VARCHAR(32) NOT NULL,
        signal_date DATE,
        signal_snapshot_json JSONB,
        extra_json JSONB,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_trade_observe_user_market_code_source
            UNIQUE (user_id, market, code, source)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_trade_observe_stocks_user_id
    ON trade_observe_stocks (user_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_trade_observe_stocks_source
    ON trade_observe_stocks (source)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_trade_observe_stocks_user_source
    ON trade_observe_stocks (user_id, source)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_trade_observe_stocks_code
    ON trade_observe_stocks (code)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_trade_observe_stocks_signal_date
    ON trade_observe_stocks (signal_date)
    """,
    """
    CREATE TABLE IF NOT EXISTS trade_observe_history (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        market VARCHAR(10) NOT NULL DEFAULT 'CN',
        code VARCHAR(20) NOT NULL,
        name VARCHAR(200),
        source VARCHAR(32) NOT NULL,
        signal_date DATE,
        signal_snapshot_json JSONB,
        extra_json JSONB,
        observe_created_at TIMESTAMP WITHOUT TIME ZONE,
        observe_updated_at TIMESTAMP WITHOUT TIME ZONE,
        source_observe_id INTEGER,
        removed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_trade_observe_history_user_id
    ON trade_observe_history (user_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_trade_observe_history_source
    ON trade_observe_history (source)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_trade_observe_history_removed_at
    ON trade_observe_history (removed_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_trade_observe_history_user_source
    ON trade_observe_history (user_id, source)
    """,
    """
    CREATE TABLE IF NOT EXISTS formal_trades (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        market VARCHAR(10) NOT NULL DEFAULT 'CN',
        code VARCHAR(20) NOT NULL,
        name VARCHAR(200),
        source VARCHAR(32) NOT NULL,
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
        extra_json JSONB,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_formal_trades_user_id
    ON formal_trades (user_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_formal_trades_source
    ON formal_trades (source)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_formal_trades_user_status
    ON formal_trades (user_id, status)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_formal_trades_user_source_status
    ON formal_trades (user_id, source, status)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_formal_trades_user_code
    ON formal_trades (user_id, market, code)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_formal_trades_source_observe_id
    ON formal_trades (source_observe_id)
    """,
    # 同 user+market+code+source 至多一条 open
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_formal_trades_open_user_market_code_source
    ON formal_trades (user_id, market, code, source)
    WHERE status = 'open'
    """,
]


def upgrade():
    with engine.connect() as conn:
        for sql in DDL:
            conn.execute(text(sql))
        conn.commit()
    logger.info("统一交易观察/正式交易表迁移完成")


if __name__ == "__main__":
    upgrade()
