"""
迁移：gms_trace_recompute_tasks（GMS 信号追溯强制重算任务，多 worker 共享）
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
                CREATE TABLE IF NOT EXISTS gms_trace_recompute_tasks (
                    task_id VARCHAR(64) PRIMARY KEY,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    progress INTEGER NOT NULL DEFAULT 0,
                    message TEXT,
                    code VARCHAR(20) NOT NULL,
                    market_type VARCHAR(10) NOT NULL DEFAULT 'CN',
                    config_id INTEGER NOT NULL,
                    config_name VARCHAR(200),
                    current INTEGER NOT NULL DEFAULT 0,
                    total INTEGER NOT NULL DEFAULT 0,
                    saved_count INTEGER,
                    error TEXT,
                    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_gms_trace_recompute_tasks_code_cfg
                ON gms_trace_recompute_tasks (code, config_id, status)
                """
            )
        )
        conn.commit()
    logger.info("gms_trace_recompute_tasks 迁移完成")


if __name__ == "__main__":
    upgrade()
