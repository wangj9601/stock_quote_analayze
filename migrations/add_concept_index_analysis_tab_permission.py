# -*- coding: utf-8 -*-
"""同步「概念指数分析」Tab 权限，并复制已有指数/行业指数分析角色授权。

本次只写权限数据，不改表结构。
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

from backend_api.config import DATABASE_CONFIG

PERMS = [
    {
        "code": "channel.analyze.tab.concept_index",
        "name": "概念指数分析",
        "level": 2,
        "parent_code": "channel.analyze",
        "channel_code": "analyze",
        "sort_order": 54,
    },
    {
        "code": "channel.analyze.tab.concept_index.btn.analyze",
        "name": "概念指数分析执行",
        "level": 3,
        "parent_code": "channel.analyze.tab.concept_index",
        "channel_code": "analyze",
        "sort_order": 10,
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
                  AND p.code LIKE 'channel.analyze.tab.concept_index%'
                  AND p.is_active = TRUE
                ON CONFLICT DO NOTHING
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO role_permissions (role_id, permission_id)
                SELECT DISTINCT rp.role_id, p_new.id
                FROM role_permissions rp
                JOIN frontend_permissions p_src
                  ON p_src.id = rp.permission_id
                 AND p_src.code IN (
                    'channel.analyze.tab.index',
                    'channel.analyze.tab.industry_index'
                 )
                JOIN frontend_permissions p_new
                  ON p_new.code LIKE 'channel.analyze.tab.concept_index%'
                 AND p_new.is_active = TRUE
                ON CONFLICT DO NOTHING
                """
            )
        )
    print("OK: channel.analyze.tab.concept_index* permissions synced")


if __name__ == "__main__":
    main()
