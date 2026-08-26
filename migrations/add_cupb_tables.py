"""迁移：创建 CUPB（杯底形态）相关表。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging

from sqlalchemy import text

from backend_core.database.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


DDL = [
    """
    CREATE TABLE IF NOT EXISTS cupb_strategy_configs (
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
    CREATE INDEX IF NOT EXISTS ix_cupb_strategy_configs_is_default
    ON cupb_strategy_configs (is_default)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_cupb_strategy_configs_is_active
    ON cupb_strategy_configs (is_active)
    """,
    """
    CREATE TABLE IF NOT EXISTS cupb_signal_trace (
        id SERIAL PRIMARY KEY,
        code VARCHAR(20) NOT NULL,
        trade_date DATE NOT NULL,
        config_id INTEGER NOT NULL REFERENCES cupb_strategy_configs(id) ON DELETE CASCADE,
        name VARCHAR(200),
        status VARCHAR(20),
        left_rim_date VARCHAR(10),
        cup_bottom_date VARCHAR(10),
        right_rim_date VARCHAR(10),
        handle_low_date VARCHAR(10),
        left_rim_price DOUBLE PRECISION,
        cup_bottom_price DOUBLE PRECISION,
        right_rim_price DOUBLE PRECISION,
        handle_low_price DOUBLE PRECISION,
        rim DOUBLE PRECISION,
        last_close DOUBLE PRECISION,
        confirm_date VARCHAR(10),
        cup_depth_pct DOUBLE PRECISION,
        handle_retrace_pct DOUBLE PRECISION,
        board_labels VARCHAR(500),
        detail JSONB,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_cupb_signal_trace_code_date_cfg UNIQUE (code, trade_date, config_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_cupb_signal_trace_date_cfg
    ON cupb_signal_trace (trade_date, config_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_cupb_signal_trace_status
    ON cupb_signal_trace (status)
    """,
]


def run():
    with engine.begin() as conn:
        for ddl in DDL:
            conn.execute(text(ddl))
        row = conn.execute(
            text("SELECT id FROM cupb_strategy_configs WHERE is_default = TRUE LIMIT 1")
        ).fetchone()
        if not row:
            from backend_core.strategies.cup_bottom.config import get_default_cupb_config
            import json

            params = json.dumps(get_default_cupb_config())
            conn.execute(
                text(
                    """
                    INSERT INTO cupb_strategy_configs
                    (name, description, config_params, is_active, is_default)
                    VALUES ('default', '杯底形态策略默认参数', CAST(:p AS JSONB), TRUE, TRUE)
                    """
                ),
                {"p": params},
            )
            logger.info("inserted default cupb config")
    logger.info("CUPB tables ready")


if __name__ == "__main__":
    run()
