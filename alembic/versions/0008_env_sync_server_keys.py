"""环境同步服务端多 Key 表 env_sync_server_keys

Revision ID: 0008_env_sync_server_keys
Revises: 0007_board_observe
Create Date: 2026-11-21

对应手写脚本 migrations/add_env_sync_server_keys.py。
幂等：表/索引已存在则跳过；旧单行 hash 仅在 keys 表尚无该 hash 时迁入。
目标表 env_sync_server_config 不存在时跳过数据迁移。
revision id 须 <= 32 字符。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008_env_sync_server_keys"
down_revision: Union[str, None] = "0007_board_observe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS env_sync_server_keys (
                id SERIAL PRIMARY KEY,
                label VARCHAR(100) NOT NULL DEFAULT '',
                sync_key_hash VARCHAR(128) NOT NULL,
                key_hint VARCHAR(16),
                enabled BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS idx_env_sync_server_keys_hash "
            "ON env_sync_server_keys (sync_key_hash)"
        )
    )
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_env_sync_server_keys_hash "
            "ON env_sync_server_keys (sync_key_hash)"
        )
    )
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF to_regclass('public.env_sync_server_config') IS NOT NULL THEN
                    INSERT INTO env_sync_server_keys (label, sync_key_hash, key_hint, enabled)
                    SELECT
                        'legacy',
                        c.sync_key_hash,
                        c.key_hint,
                        TRUE
                    FROM env_sync_server_config c
                    WHERE c.id = 1
                      AND c.sync_key_hash IS NOT NULL
                      AND TRIM(c.sync_key_hash) <> ''
                      AND NOT EXISTS (
                          SELECT 1 FROM env_sync_server_keys k
                          WHERE k.sync_key_hash = c.sync_key_hash
                      );
                END IF;
            END $$;
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS env_sync_server_keys CASCADE"))
