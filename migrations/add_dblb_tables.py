"""迁移：创建 DBLB（双底）相关表。"""

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
    CREATE TABLE IF NOT EXISTS dblb_strategy_configs (
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
    CREATE INDEX IF NOT EXISTS ix_dblb_strategy_configs_is_default
    ON dblb_strategy_configs (is_default)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_dblb_strategy_configs_is_active
    ON dblb_strategy_configs (is_active)
    """,
    """
    CREATE TABLE IF NOT EXISTS dblb_signal_trace (
        id SERIAL PRIMARY KEY,
        code VARCHAR(20) NOT NULL,
        trade_date DATE NOT NULL,
        config_id INTEGER NOT NULL REFERENCES dblb_strategy_configs(id) ON DELETE CASCADE,
        name VARCHAR(200),
        status VARCHAR(20),
        l1_date VARCHAR(10),
        l2_date VARCHAR(10),
        l1_price DOUBLE PRECISION,
        l2_price DOUBLE PRECISION,
        neckline DOUBLE PRECISION,
        neck_date VARCHAR(10),
        last_close DOUBLE PRECISION,
        confirm_date VARCHAR(10),
        board_labels VARCHAR(500),
        detail JSONB,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_dblb_signal_trace_code_date_cfg UNIQUE (code, trade_date, config_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_dblb_signal_trace_date_cfg
    ON dblb_signal_trace (trade_date, config_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_dblb_signal_trace_status
    ON dblb_signal_trace (status)
    """,
]


def run():
    with engine.begin() as conn:
        for ddl in DDL:
            conn.execute(text(ddl))
        row = conn.execute(
            text("SELECT id FROM dblb_strategy_configs WHERE is_default = TRUE LIMIT 1")
        ).fetchone()
        if not row:
            from backend_core.strategies.double_bottom.config import get_default_dblb_config
            import json

            params = json.dumps(get_default_dblb_config())
            conn.execute(
                text(
                    """
                    INSERT INTO dblb_strategy_configs
                    (name, description, config_params, is_active, is_default)
                    VALUES ('default', '双底策略默认参数', CAST(:p AS JSONB), TRUE, TRUE)
                    """
                ),
                {"p": params},
            )
            logger.info("inserted default dblb config")
    logger.info("DBLB tables ready")


if __name__ == "__main__":
    run()
