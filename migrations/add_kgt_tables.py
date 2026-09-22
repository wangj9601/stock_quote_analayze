"""迁移：创建 KGT（袋鼠尾）相关表。"""

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
    CREATE TABLE IF NOT EXISTS kgt_strategy_configs (
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
    CREATE INDEX IF NOT EXISTS ix_kgt_strategy_configs_is_default
    ON kgt_strategy_configs (is_default)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_kgt_strategy_configs_is_active
    ON kgt_strategy_configs (is_active)
    """,
    """
    CREATE TABLE IF NOT EXISTS kgt_signal_trace (
        id SERIAL PRIMARY KEY,
        code VARCHAR(20) NOT NULL,
        trade_date DATE NOT NULL,
        config_id INTEGER NOT NULL REFERENCES kgt_strategy_configs(id) ON DELETE CASCADE,
        name VARCHAR(200),
        direction VARCHAR(16),
        status VARCHAR(20),
        score DOUBLE PRECISION,
        signal_date VARCHAR(10),
        open_price DOUBLE PRECISION,
        high_price DOUBLE PRECISION,
        low_price DOUBLE PRECISION,
        close_price DOUBLE PRECISION,
        last_close DOUBLE PRECISION,
        range_pct DOUBLE PRECISION,
        body_ratio DOUBLE PRECISION,
        shadow_ratio DOUBLE PRECISION,
        board_labels VARCHAR(500),
        detail JSONB,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_kgt_signal_trace_code_date_cfg UNIQUE (code, trade_date, config_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_kgt_signal_trace_date_cfg
    ON kgt_signal_trace (trade_date, config_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_kgt_signal_trace_direction
    ON kgt_signal_trace (direction)
    """,
]


def run():
    with engine.begin() as conn:
        for ddl in DDL:
            conn.execute(text(ddl))
        row = conn.execute(
            text("SELECT id FROM kgt_strategy_configs WHERE is_default = TRUE LIMIT 1")
        ).fetchone()
        if not row:
            from backend_core.strategies.kangaroo_tail.config import get_default_kgt_config

            params = json.dumps(get_default_kgt_config())
            conn.execute(
                text(
                    """
                    INSERT INTO kgt_strategy_configs
                    (name, description, config_params, is_active, is_default)
                    VALUES ('default', '袋鼠尾策略默认参数', CAST(:p AS JSONB), TRUE, TRUE)
                    """
                ),
                {"p": params},
            )
            logger.info("inserted default kgt config")
    logger.info("KGT tables ready")


if __name__ == "__main__":
    run()
