"""迁移：环境同步服务端多 Key 表 env_sync_server_keys，并迁入旧单 Key。"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_dotenv(path: Path) -> None:
    """写入 os.environ（不覆盖已有变量），供 backend_core.database 读 DATABASE_URL。"""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


_load_dotenv(Path("/opt/stock_quote/shared/.env"))
_load_dotenv(Path(__file__).resolve().parents[1] / ".env")

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
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_env_sync_server_keys_hash "
                "ON env_sync_server_keys (sync_key_hash)"
            )
        )
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_env_sync_server_keys_hash "
                "ON env_sync_server_keys (sync_key_hash)"
            )
        )
        # 旧单行 hash 迁入多 Key 表（仅当 keys 表尚无该 hash）
        conn.execute(
            text(
                """
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
                  )
                """
            )
        )
        conn.commit()
    logger.info("env_sync_server_keys 表迁移完成")


def downgrade():
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS env_sync_server_keys CASCADE"))
        conn.commit()


if __name__ == "__main__":
    upgrade()
