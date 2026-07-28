"""迁移：环境同步配置表与审计日志。"""
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
                CREATE TABLE IF NOT EXISTS env_sync_server_config (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    sync_key_hash VARCHAR(128),
                    key_hint VARCHAR(16),
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO env_sync_server_config (id, enabled)
                VALUES (1, FALSE)
                ON CONFLICT (id) DO NOTHING
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS env_sync_client_config (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    prod_base_url VARCHAR(500) NOT NULL DEFAULT '',
                    sync_key VARCHAR(500),
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO env_sync_client_config (id, enabled, prod_base_url)
                VALUES (1, FALSE, '')
                ON CONFLICT (id) DO NOTHING
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS env_sync_audit_logs (
                    id SERIAL PRIMARY KEY,
                    direction VARCHAR(16) NOT NULL,
                    modules JSON,
                    operator VARCHAR(100),
                    success BOOLEAN NOT NULL DEFAULT FALSE,
                    summary JSON,
                    error_message TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_env_sync_audit_created "
                "ON env_sync_audit_logs (created_at)"
            )
        )
        conn.commit()
    logger.info("env_sync 表迁移完成")


def downgrade():
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS env_sync_audit_logs CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS env_sync_client_config CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS env_sync_server_config CASCADE"))
        conn.commit()


if __name__ == "__main__":
    upgrade()
