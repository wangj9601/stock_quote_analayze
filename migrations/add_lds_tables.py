"""迁移：创建 LDS（龙头战法）相关表。"""

import json
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
    CREATE TABLE IF NOT EXISTS lds_strategy_configs (
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
    CREATE INDEX IF NOT EXISTS ix_lds_strategy_configs_is_default
    ON lds_strategy_configs (is_default)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_lds_strategy_configs_is_active
    ON lds_strategy_configs (is_active)
    """,
    """
    CREATE TABLE IF NOT EXISTS lds_signal_trace (
        id SERIAL PRIMARY KEY,
        code VARCHAR(20) NOT NULL,
        trade_date DATE NOT NULL,
        config_id INTEGER NOT NULL REFERENCES lds_strategy_configs(id) ON DELETE CASCADE,
        name VARCHAR(200),
        status VARCHAR(20),
        role VARCHAR(32) NOT NULL DEFAULT 'board_leader',
        board_code VARCHAR(64) NOT NULL DEFAULT '',
        board_name VARCHAR(200),
        identity_score DOUBLE PRECISION,
        drive_score DOUBLE PRECISION,
        watch_ready BOOLEAN NOT NULL DEFAULT FALSE,
        is_lonely BOOLEAN NOT NULL DEFAULT FALSE,
        is_primary BOOLEAN NOT NULL DEFAULT TRUE,
        same_as_height BOOLEAN NOT NULL DEFAULT FALSE,
        board_count INTEGER,
        identity_reasons JSONB,
        watch_reasons JSONB,
        detail JSONB,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_lds_signal_trace_code_date_cfg_role_board
            UNIQUE (code, trade_date, config_id, role, board_code)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_lds_signal_trace_date_cfg
    ON lds_signal_trace (trade_date, config_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_lds_signal_trace_code
    ON lds_signal_trace (code)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_lds_signal_trace_role
    ON lds_signal_trace (role)
    """,
]


def run():
    with engine.begin() as conn:
        for ddl in DDL:
            conn.execute(text(ddl))
        row = conn.execute(
            text("SELECT id FROM lds_strategy_configs WHERE is_default = TRUE LIMIT 1")
        ).fetchone()
        if not row:
            from backend_core.strategies.lds.config import get_default_lds_config

            params = json.dumps(get_default_lds_config())
            conn.execute(
                text(
                    """
                    INSERT INTO lds_strategy_configs
                    (name, description, config_params, is_active, is_default)
                    VALUES ('default', '龙头战法默认参数', CAST(:p AS JSONB), TRUE, TRUE)
                    """
                ),
                {"p": params},
            )
            logger.info("inserted default lds config")
    logger.info("LDS tables ready")


if __name__ == "__main__":
    run()
