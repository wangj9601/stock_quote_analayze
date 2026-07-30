"""
迁移：URT 核心表（urt_strategy_configs、urt_signal_trace、urt_backtest_tasks）
对齐 backend_api/models.py 中 URTStrategyConfig / URTSignalTrace / URTBacktestTask。

若表已存在但缺 precompute_enabled 列，请另跑（勿在请求路径 ALTER）：
  python migrations/add_urt_precompute_enabled_column.py
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
                CREATE TABLE IF NOT EXISTS urt_strategy_configs (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL UNIQUE,
                    version_label VARCHAR(32),
                    description TEXT,
                    config_params JSONB NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    is_default BOOLEAN NOT NULL DEFAULT FALSE,
                    precompute_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    created_by VARCHAR(50),
                    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_urt_strategy_configs_name
                ON urt_strategy_configs (name)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_urt_strategy_configs_is_active
                ON urt_strategy_configs (is_active)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_urt_strategy_configs_is_default
                ON urt_strategy_configs (is_default)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_urt_strategy_configs_precompute_enabled
                ON urt_strategy_configs (precompute_enabled)
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS urt_signal_trace (
                    code VARCHAR(32) NOT NULL,
                    date VARCHAR(20) NOT NULL,
                    config_id INTEGER NOT NULL REFERENCES urt_strategy_configs(id) ON DELETE CASCADE,
                    name VARCHAR(100),
                    buy_signal BOOLEAN,
                    score DOUBLE PRECISION,
                    signal_strength DOUBLE PRECISION,
                    close DOUBLE PRECISION,
                    open DOUBLE PRECISION,
                    ma20 DOUBLE PRECISION,
                    above_ma20 BOOLEAN,
                    yang_count_4 INTEGER,
                    yang_count_5 INTEGER,
                    yang_rule VARCHAR(32),
                    volume DOUBLE PRECISION,
                    avg_volume_20 DOUBLE PRECISION,
                    volume_multiple DOUBLE PRECISION,
                    volume_ratio DOUBLE PRECISION,
                    turnover_rate DOUBLE PRECISION,
                    score_detail JSONB,
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                    PRIMARY KEY (code, date, config_id)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_urt_signal_trace_buy_signal
                ON urt_signal_trace (buy_signal)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_urt_signal_trace_score
                ON urt_signal_trace (score)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_urt_trace_date_score
                ON urt_signal_trace (date, score)
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS urt_backtest_tasks (
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
                    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                    started_at TIMESTAMP WITHOUT TIME ZONE,
                    completed_at TIMESTAMP WITHOUT TIME ZONE
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_urt_backtest_tasks_status
                ON urt_backtest_tasks (status)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_urt_bt_status_created
                ON urt_backtest_tasks (status, created_at)
                """
            )
        )
        conn.commit()
    logger.info("URT 核心表（configs / signal_trace / backtest_tasks）迁移完成")


if __name__ == "__main__":
    upgrade()
