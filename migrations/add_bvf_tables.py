"""迁移：创建 BVF（底部放量分型）相关表。"""

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
    CREATE TABLE IF NOT EXISTS bvf_strategy_configs (
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
    CREATE INDEX IF NOT EXISTS ix_bvf_strategy_configs_is_default
    ON bvf_strategy_configs (is_default)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_bvf_strategy_configs_is_active
    ON bvf_strategy_configs (is_active)
    """,
    """
    CREATE TABLE IF NOT EXISTS bvf_signal_trace (
        id SERIAL PRIMARY KEY,
        code VARCHAR(20) NOT NULL,
        trade_date DATE NOT NULL,
        config_id INTEGER NOT NULL REFERENCES bvf_strategy_configs(id) ON DELETE CASCADE,
        name VARCHAR(200),
        status VARCHAR(20),
        left_date VARCHAR(10),
        mid_date VARCHAR(10),
        right_date VARCHAR(10),
        mid_low DOUBLE PRECISION,
        min_low DOUBLE PRECISION,
        bottom_dev_pct DOUBLE PRECISION,
        vol_ratio_actual DOUBLE PRECISION,
        mid_volume DOUBLE PRECISION,
        last_close DOUBLE PRECISION,
        limit_flag VARCHAR(20),
        price_adjust VARCHAR(16),
        board_labels VARCHAR(500),
        detail JSONB,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_bvf_signal_trace_code_date_cfg UNIQUE (code, trade_date, config_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_bvf_signal_trace_date_cfg
    ON bvf_signal_trace (trade_date, config_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_bvf_signal_trace_code
    ON bvf_signal_trace (code)
    """,
]


def run():
    with engine.begin() as conn:
        for ddl in DDL:
            conn.execute(text(ddl))
        row = conn.execute(
            text("SELECT id FROM bvf_strategy_configs WHERE is_default = TRUE LIMIT 1")
        ).fetchone()
        if not row:
            from backend_core.strategies.bvf.config import get_default_bvf_config

            params = json.dumps(get_default_bvf_config())
            conn.execute(
                text(
                    """
                    INSERT INTO bvf_strategy_configs
                    (name, description, config_params, is_active, is_default)
                    VALUES ('default', '底部放量分型默认参数', CAST(:p AS JSONB), TRUE, TRUE)
                    """
                ),
                {"p": params},
            )
            logger.info("inserted default bvf config")
    logger.info("BVF tables ready")


if __name__ == "__main__":
    run()
