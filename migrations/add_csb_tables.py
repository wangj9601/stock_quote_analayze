"""
迁移：CSB 核心表（csb_strategy_configs、csb_signal_trace、csb_backtest_tasks）
对齐 backend_api/models.py 中 CSBStrategyConfig / CSBSignalTrace / CSBBacktestTask。
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
                CREATE TABLE IF NOT EXISTS csb_strategy_configs (
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
                """
            )
        )
        for idx in (
            "CREATE INDEX IF NOT EXISTS ix_csb_strategy_configs_name ON csb_strategy_configs (name)",
            "CREATE INDEX IF NOT EXISTS ix_csb_strategy_configs_is_active ON csb_strategy_configs (is_active)",
            "CREATE INDEX IF NOT EXISTS ix_csb_strategy_configs_is_default ON csb_strategy_configs (is_default)",
            "CREATE INDEX IF NOT EXISTS ix_csb_strategy_configs_precompute_enabled ON csb_strategy_configs (precompute_enabled)",
        ):
            conn.execute(text(idx))

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS csb_signal_trace (
                    id SERIAL PRIMARY KEY,
                    code VARCHAR(20) NOT NULL,
                    trade_date DATE NOT NULL,
                    config_id INTEGER NOT NULL REFERENCES csb_strategy_configs(id) ON DELETE CASCADE,
                    signal_type VARCHAR(32) NOT NULL,
                    name VARCHAR(200),
                    setup_ok BOOLEAN,
                    entry_signal BOOLEAN,
                    score DOUBLE PRECISION,
                    close_price DOUBLE PRECISION,
                    channel_lower DOUBLE PRECISION,
                    channel_upper DOUBLE PRECISION,
                    squeeze_days INTEGER,
                    entry_low DOUBLE PRECISION,
                    detail JSONB,
                    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_csb_signal_trace_code_date_cfg_type
                        UNIQUE (code, trade_date, config_id, signal_type)
                )
                """
            )
        )
        for idx in (
            "CREATE INDEX IF NOT EXISTS ix_csb_signal_trace_code ON csb_signal_trace (code)",
            "CREATE INDEX IF NOT EXISTS ix_csb_signal_trace_trade_date ON csb_signal_trace (trade_date)",
            "CREATE INDEX IF NOT EXISTS ix_csb_signal_trace_config_id ON csb_signal_trace (config_id)",
            "CREATE INDEX IF NOT EXISTS ix_csb_signal_trace_signal_type ON csb_signal_trace (signal_type)",
            "CREATE INDEX IF NOT EXISTS ix_csb_signal_trace_cfg_date ON csb_signal_trace (config_id, trade_date)",
        ):
            conn.execute(text(idx))

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS csb_backtest_tasks (
                    task_id VARCHAR(64) PRIMARY KEY,
                    name VARCHAR(500),
                    status VARCHAR(20) NOT NULL,
                    progress INTEGER NOT NULL DEFAULT 0,
                    message TEXT,
                    config JSONB NOT NULL,
                    logs JSONB,
                    summary JSONB,
                    error TEXT,
                    details_path VARCHAR(512),
                    details_csv_bytes BYTEA,
                    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    started_at TIMESTAMP WITHOUT TIME ZONE,
                    completed_at TIMESTAMP WITHOUT TIME ZONE
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_csb_bt_status_created
                ON csb_backtest_tasks (status, created_at)
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_csb_backtest_tasks_status ON csb_backtest_tasks (status)"
            )
        )

        conn.commit()
        logger.info("CSB tables ready: csb_strategy_configs, csb_signal_trace, csb_backtest_tasks")


if __name__ == "__main__":
    upgrade()
    print("OK: add_csb_tables")
