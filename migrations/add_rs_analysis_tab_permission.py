# -*- coding: utf-8 -*-
"""同步「个股相对强度分析」Tab 权限到 frontend_permissions，并授予 standard/admin。"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

from backend_api.config import DATABASE_CONFIG

PERMS = [
    {
        "code": "channel.analyze.tab.rs",
        "name": "个股相对强度分析",
        "level": 2,
        "parent_code": "channel.analyze",
        "channel_code": "analyze",
        "sort_order": 52,
    },
    {
        "code": "channel.analyze.tab.rs.btn.query",
        "name": "查询相对强度",
        "level": 3,
        "parent_code": "channel.analyze.tab.rs",
        "channel_code": "analyze",
        "sort_order": 10,
    },
    {
        "code": "channel.analyze.tab.rs.btn.batch",
        "name": "批量个股分析",
        "level": 3,
        "parent_code": "channel.analyze.tab.rs",
        "channel_code": "analyze",
        "sort_order": 20,
    },
]


def main() -> None:
    engine = create_engine(DATABASE_CONFIG["url"])
    with engine.begin() as conn:
        for p in PERMS:
            conn.execute(
                text(
                    """
                    INSERT INTO frontend_permissions
                        (code, name, level, parent_code, channel_code, sort_order)
                    VALUES
                        (:code, :name, :level, :parent_code, :channel_code, :sort_order)
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
                WHERE r.code IN ('standard', 'admin')
                  AND p.code LIKE 'channel.analyze.tab.rs%'
                  AND p.is_active = TRUE
                ON CONFLICT DO NOTHING
                """
            )
        )
    print("OK: channel.analyze.tab.rs* permissions synced")


if __name__ == "__main__":
    main()
