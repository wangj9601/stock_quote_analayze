# -*- coding: utf-8 -*-
"""创建 user_login_logs 表，并注册管理端「登录日志」权限。"""

from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from backend_core.database.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PERMS = [
    {
        "code": "admin.login_logs",
        "name": "登录日志",
        "level": 2,
        "parent_code": "admin",
        "channel_code": "admin",
        "sort_order": 88,
    },
    {
        "code": "admin.login_logs.read",
        "name": "登录日志-查看",
        "level": 3,
        "parent_code": "admin.login_logs",
        "channel_code": "admin",
        "sort_order": 1,
    },
]


def upgrade():
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS user_login_logs (
                    id SERIAL PRIMARY KEY,
                    channel VARCHAR(16) NOT NULL,
                    user_id INTEGER NULL,
                    username VARCHAR(128) NOT NULL,
                    success BOOLEAN NOT NULL,
                    failure_reason VARCHAR(500) NULL,
                    ip VARCHAR(64) NULL,
                    user_agent VARCHAR(512) NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_user_login_logs_created_at "
                "ON user_login_logs (created_at DESC)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_user_login_logs_username "
                "ON user_login_logs (username)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_user_login_logs_channel_created "
                "ON user_login_logs (channel, created_at DESC)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_user_login_logs_success "
                "ON user_login_logs (success)"
            )
        )
        logger.info("user_login_logs 表就绪")

        try:
            for p in PERMS:
                conn.execute(
                    text(
                        """
                        INSERT INTO frontend_permissions
                            (code, name, level, parent_code, channel_code, sort_order, is_active)
                        VALUES
                            (:code, :name, :level, :parent_code, :channel_code, :sort_order, TRUE)
                        ON CONFLICT (code) DO UPDATE SET
                            name = EXCLUDED.name,
                            level = EXCLUDED.level,
                            parent_code = EXCLUDED.parent_code,
                            channel_code = EXCLUDED.channel_code,
                            sort_order = EXCLUDED.sort_order,
                            is_active = TRUE
                        """
                    ),
                    p,
                )
            conn.execute(
                text(
                    """
                    INSERT INTO role_permissions (role_id, permission_id)
                    SELECT r.id, p.id
                    FROM frontend_roles r
                    CROSS JOIN frontend_permissions p
                    WHERE r.code IN ('admin')
                      AND p.code LIKE 'admin.login_logs%'
                      AND p.is_active = TRUE
                    ON CONFLICT DO NOTHING
                    """
                )
            )
            logger.info("admin.login_logs* 权限已同步")
        except Exception as e:
            logger.warning("写入 frontend_permissions 跳过: %s", e)


if __name__ == "__main__":
    upgrade()
