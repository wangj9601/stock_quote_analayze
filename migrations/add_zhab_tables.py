"""迁移：创建 ZHAB（涨停后高位蓄势再突破）相关表。"""

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
    CREATE TABLE IF NOT EXISTS zhab_strategy_configs (
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
    CREATE INDEX IF NOT EXISTS ix_zhab_strategy_configs_is_default
    ON zhab_strategy_configs (is_default)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_zhab_strategy_configs_is_active
    ON zhab_strategy_configs (is_active)
    """,
    """
    CREATE TABLE IF NOT EXISTS zhab_signal_trace (
        id SERIAL PRIMARY KEY,
        code VARCHAR(20) NOT NULL,
        trade_date DATE NOT NULL,
        config_id INTEGER NOT NULL REFERENCES zhab_strategy_configs(id) ON DELETE CASCADE,
        name VARCHAR(200),
        signal_type VARCHAR(32),
        setup_ok BOOLEAN,
        entry_signal BOOLEAN,
        score DOUBLE PRECISION,
        zt_date VARCHAR(10),
        consol_days INTEGER,
        zt_mid DOUBLE PRECISION,
        box_low DOUBLE PRECISION,
        box_high DOUBLE PRECISION,
        close_price DOUBLE PRECISION,
        detail JSONB,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_zhab_signal_trace_code_date_cfg UNIQUE (code, trade_date, config_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_zhab_signal_trace_date_cfg
    ON zhab_signal_trace (trade_date, config_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_zhab_signal_trace_signal_type
    ON zhab_signal_trace (signal_type)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_zhab_signal_trace_entry
    ON zhab_signal_trace (trade_date, entry_signal)
    """,
]


def run():
    with engine.begin() as conn:
        for ddl in DDL:
            conn.execute(text(ddl))
        row = conn.execute(
            text("SELECT id FROM zhab_strategy_configs WHERE is_default = TRUE LIMIT 1")
        ).fetchone()
        if not row:
            from backend_core.strategies.zhab.config import get_default_zhab_config

            params = json.dumps(get_default_zhab_config())
            conn.execute(
                text(
                    """
                    INSERT INTO zhab_strategy_configs
                    (name, description, config_params, is_active, is_default)
                    VALUES ('default', '涨停后高位蓄势再突破默认参数', CAST(:p AS JSONB), TRUE, TRUE)
                    """
                ),
                {"p": params},
            )
            logger.info("inserted default zhab config")
    logger.info("ZHAB tables ready")


if __name__ == "__main__":
    run()
