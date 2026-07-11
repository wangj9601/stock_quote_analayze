"""
数据库迁移 - 用户级权限覆盖表 user_permissions
同一角色下不同用户可有不同权限（grant 额外授予 / deny 相对角色撤销）
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from backend_api.config import DATABASE_CONFIG
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

LOCK_TIMEOUT_MS = int(os.environ.get("MIGRATION_LOCK_TIMEOUT_MS", "300000"))

engine = create_engine(
    DATABASE_CONFIG["url"],
    pool_pre_ping=True,
    pool_size=1,
    max_overflow=0,
    connect_args={
        "connect_timeout": 15,
        "options": f"-c lock_timeout={LOCK_TIMEOUT_MS} -c statement_timeout=600000",
    },
)


def upgrade():
    logger.info("创建 user_permissions 表...")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_permissions (
                user_id       INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                permission_id INT NOT NULL REFERENCES frontend_permissions(id) ON DELETE CASCADE,
                granted       BOOLEAN NOT NULL,
                created_at    TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (user_id, permission_id)
            )
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_user_permissions_user_id ON user_permissions(user_id)
        """))
    logger.info("✅ user_permissions 表迁移完成")


if __name__ == "__main__":
    upgrade()
