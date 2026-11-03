"""迁移：环境同步异步任务表 env_sync_jobs。"""
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
                CREATE TABLE IF NOT EXISTS env_sync_jobs (
                    id VARCHAR(36) PRIMARY KEY,
                    direction VARCHAR(32) NOT NULL,
                    status VARCHAR(32) NOT NULL DEFAULT 'pending',
                    modules JSON,
                    start_date VARCHAR(16),
                    end_date VARCHAR(16),
                    progress INTEGER NOT NULL DEFAULT 0,
                    stage VARCHAR(64),
                    message TEXT,
                    artifact_dir VARCHAR(1000),
                    remote_job_id VARCHAR(36),
                    summary JSON,
                    error_message TEXT,
                    cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,
                    created_by VARCHAR(100),
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_env_sync_jobs_created "
                "ON env_sync_jobs (created_at DESC)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_env_sync_jobs_status "
                "ON env_sync_jobs (status, direction)"
            )
        )
        conn.commit()
    logger.info("env_sync_jobs 表迁移完成")


def downgrade():
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS env_sync_jobs CASCADE"))
        conn.commit()


if __name__ == "__main__":
    upgrade()
