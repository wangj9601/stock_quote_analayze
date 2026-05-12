"""
迁移：VSB 选股观察股表（选股命中后写入，与 volume_shrink_breakout_signals 配套）
"""

import sys
import os

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
                CREATE TABLE IF NOT EXISTS vsb_observe_stocks (
                    id SERIAL PRIMARY KEY,
                    market VARCHAR(10) NOT NULL DEFAULT 'CN',
                    code VARCHAR(20) NOT NULL,
                    name VARCHAR(200),
                    signal_date DATE NOT NULL,
                    boom_date VARCHAR(20),
                    run_search_date VARCHAR(20),
                    signal_strength INTEGER,
                    signal_strength_level VARCHAR(20),
                    buy_signal_text VARCHAR(220),
                    screen_snapshot_json JSONB,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_vsb_observe_market_code_signal_date
                        UNIQUE (market, code, signal_date)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_vsb_observe_signal_date
                ON vsb_observe_stocks (signal_date DESC)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_vsb_observe_code
                ON vsb_observe_stocks (code)
                """
            )
        )
        conn.commit()
    logger.info("vsb_observe_stocks 迁移完成")


def downgrade():
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS vsb_observe_stocks CASCADE"))
        conn.commit()
    logger.info("已回滚 vsb_observe_stocks 表")


if __name__ == "__main__":
    upgrade()
