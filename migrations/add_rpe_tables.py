"""迁移：创建 RPE（比价效应）相关表。"""

import json
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
    CREATE TABLE IF NOT EXISTS rpe_strategy_configs (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL UNIQUE,
        description TEXT,
        config_params JSONB NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        is_default BOOLEAN NOT NULL DEFAULT FALSE,
        precompute_enabled BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rpe_signal_trace (
        id SERIAL PRIMARY KEY,
        code VARCHAR(20) NOT NULL,
        trade_date DATE NOT NULL,
        market_type VARCHAR(10) NOT NULL DEFAULT 'CN',
        config_id INTEGER NOT NULL REFERENCES rpe_strategy_configs(id) ON DELETE CASCADE,
        name VARCHAR(200),
        sector_id VARCHAR(40),
        sector_name VARCHAR(100),
        z_score DOUBLE PRECISION,
        ratio DOUBLE PRECISION,
        signal_type VARCHAR(20),
        entry_signal BOOLEAN,
        watch_only BOOLEAN,
        trend_veto BOOLEAN,
        sector_slope DOUBLE PRECISION,
        support_levels JSONB,
        resistance_levels JSONB,
        nearest_support DOUBLE PRECISION,
        nearest_resistance DOUBLE PRECISION,
        structure_valid BOOLEAN,
        liquidity_ok BOOLEAN,
        close_price DOUBLE PRECISION,
        detail JSONB,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_rpe_signal_trace_code_date_mkt_cfg UNIQUE (code, trade_date, market_type, config_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_rpe_signal_trace_date_cfg
    ON rpe_signal_trace (trade_date, config_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS rpe_trade_observe_stocks (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        market VARCHAR(10) NOT NULL DEFAULT 'CN',
        code VARCHAR(20) NOT NULL,
        name VARCHAR(200),
        signal_snapshot_json JSONB,
        signal_date DATE,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_rpe_trade_observe_user_market_code UNIQUE (user_id, market, code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rpe_trade_observe_history (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        market VARCHAR(10) NOT NULL DEFAULT 'CN',
        code VARCHAR(20) NOT NULL,
        name VARCHAR(200),
        signal_snapshot_json JSONB,
        signal_date DATE,
        source_observe_id INTEGER,
        removed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rpe_formal_trades (
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
        structure_support DOUBLE PRECISION,
        structure_resistance DOUBLE PRECISION,
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
    CREATE INDEX IF NOT EXISTS ix_rpe_formal_trades_user_status
    ON rpe_formal_trades (user_id, status)
    """,
    """
    CREATE TABLE IF NOT EXISTS rpe_backtest_tasks (
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
    """
    CREATE TABLE IF NOT EXISTS rpe_precompute_runs (
        id SERIAL PRIMARY KEY,
        config_id INTEGER NOT NULL,
        trade_date DATE,
        market VARCHAR(10) NOT NULL DEFAULT 'CN',
        status VARCHAR(20) NOT NULL DEFAULT 'completed',
        stock_count INTEGER,
        message TEXT,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
    )
    """,
]


def upgrade():
    with engine.connect() as conn:
        for ddl in DDL:
            conn.execute(text(ddl))
        row = conn.execute(
            text("SELECT id FROM rpe_strategy_configs WHERE is_default = TRUE LIMIT 1")
        ).fetchone()
        if not row:
            from backend_core.strategies.rpe.config import get_default_rpe_config

            params = json.dumps(get_default_rpe_config())
            conn.execute(
                text(
                    """
                    INSERT INTO rpe_strategy_configs
                    (name, description, config_params, is_active, is_default, precompute_enabled)
                    VALUES ('default', 'RPE 默认参数', CAST(:p AS jsonb), TRUE, TRUE, TRUE)
                    """
                ),
                {"p": params},
            )
        conn.commit()
    logger.info("RPE tables migration completed")


if __name__ == "__main__":
    upgrade()
