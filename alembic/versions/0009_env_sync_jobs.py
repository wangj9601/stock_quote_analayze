"""环境同步异步任务表 env_sync_jobs

Revision ID: 0009_env_sync_jobs
Revises: 0008_env_sync_server_keys
Create Date: 2026-11-21

对应手写脚本 migrations/add_env_sync_jobs_table.py。
幂等：表/索引已存在则跳过。
revision id 须 <= 32 字符。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0009_env_sync_jobs"
down_revision: Union[str, None] = "0008_env_sync_server_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
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
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS idx_env_sync_jobs_created "
            "ON env_sync_jobs (created_at DESC)"
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS idx_env_sync_jobs_status "
            "ON env_sync_jobs (status, direction)"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS env_sync_jobs CASCADE"))
