"""迁移：创建 SBBR（做小做底）相关表。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from backend_core.database.db import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


DDL = [
    """
    CREATE TABLE IF NOT EXISTS sbbr_strategy_configs (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL UNIQUE,
        description TEXT,
        config_params JSONB NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        is_default BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sbbr_signal_trace (
        id SERIAL PRIMARY KEY,
        code VARCHAR(20) NOT NULL,
        trade_date DATE NOT NULL,
        config_id INTEGER NOT NULL REFERENCES sbbr_strategy_configs(id) ON DELETE CASCADE,
        name VARCHAR(200),
        market_type VARCHAR(10) NOT NULL DEFAULT 'CN',
        total_mv DOUBLE PRECISION,
        circ_mv DOUBLE PRECISION,
        size_ok BOOLEAN,
        bottom_mode VARCHAR(40),
        bottom_matched BOOLEAN,
        entry_signal BOOLEAN,
        entry_low DOUBLE PRECISION,
        defense_low DOUBLE PRECISION,
        defense_high DOUBLE PRECISION,
        defense_buffer_pct DOUBLE PRECISION,
        close_price DOUBLE PRECISION,
        ma20 DOUBLE PRECISION,
        volume_ratio DOUBLE PRECISION,
        exit_flags JSONB,
        position_advice JSONB,
        detail JSONB,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_sbbr_signal_trace_code_date_cfg UNIQUE (code, trade_date, config_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_sbbr_signal_trace_date_cfg
    ON sbbr_signal_trace (trade_date, config_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS sbbr_reserve_box (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        stock_code VARCHAR(20) NOT NULL,
        stock_name VARCHAR(200),
        industry_note TEXT,
        status VARCHAR(20) NOT NULL DEFAULT 'watching',
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_sbbr_reserve_user_code UNIQUE (user_id, stock_code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sbbr_trade_observe_stocks (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        market VARCHAR(10) NOT NULL DEFAULT 'CN',
        code VARCHAR(20) NOT NULL,
        name VARCHAR(200),
        signal_snapshot_json JSONB,
        signal_date DATE,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_sbbr_trade_observe_user_market_code UNIQUE (user_id, market, code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sbbr_formal_trades (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        market VARCHAR(10) NOT NULL DEFAULT 'CN',
        code VARCHAR(20) NOT NULL,
        name VARCHAR(200),
        source_observe_id INTEGER,
        entry_price DOUBLE PRECISION NOT NULL,
        exit_price DOUBLE PRECISION,
        status VARCHAR(20) NOT NULL DEFAULT 'open',
        signal_date DATE,
        signal_snapshot_json JSONB,
        notes TEXT,
        stage VARCHAR(20) NOT NULL DEFAULT 'probe',
        budget_total DOUBLE PRECISION,
        allocated_pct DOUBLE PRECISION NOT NULL DEFAULT 50,
        defense_anchor_low DOUBLE PRECISION,
        defense_buffer_pct DOUBLE PRECISION,
        exit_reason VARCHAR(100),
        last_eval_json JSONB,
        pnl_amount DOUBLE PRECISION,
        pnl_percent DOUBLE PRECISION,
        entry_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        exit_at TIMESTAMP WITHOUT TIME ZONE,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_sbbr_formal_trades_user_status
    ON sbbr_formal_trades (user_id, status)
    """,
    """
    CREATE TABLE IF NOT EXISTS sbbr_backtest_tasks (
        id SERIAL PRIMARY KEY,
        task_id VARCHAR(64) NOT NULL UNIQUE,
        name VARCHAR(200),
        config JSONB,
        status VARCHAR(20) NOT NULL DEFAULT 'pending',
        progress INTEGER NOT NULL DEFAULT 0,
        message TEXT,
        summary JSONB,
        error TEXT,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        started_at TIMESTAMP WITHOUT TIME ZONE,
        completed_at TIMESTAMP WITHOUT TIME ZONE,
        updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
    )
    """,
]


def upgrade():
    with engine.connect() as conn:
        for ddl in DDL:
            conn.execute(text(ddl))
        # seed default config if empty
        row = conn.execute(text("SELECT id FROM sbbr_strategy_configs WHERE is_default = TRUE LIMIT 1")).fetchone()
        if not row:
            from backend_core.strategies.sbbr.config import get_default_sbbr_config
            import json

            params = json.dumps(get_default_sbbr_config())
            conn.execute(
                text(
                    """
                    INSERT INTO sbbr_strategy_configs (name, description, config_params, is_active, is_default)
                    VALUES ('default', 'SBBR 默认参数', CAST(:p AS jsonb), TRUE, TRUE)
                    """
                ),
                {"p": params},
            )
        conn.commit()
    logger.info("SBBR tables migration completed")


if __name__ == "__main__":
    upgrade()
