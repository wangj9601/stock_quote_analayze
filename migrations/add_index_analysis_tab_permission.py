# -*- coding: utf-8 -*-
"""同步「指数分析」Tab 权限，并复制 stock_ai 已有角色授权。"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

from backend_api.config import DATABASE_CONFIG

PERMS = [
    {
        "code": "channel.analyze.tab.index",
        "name": "指数分析",
        "level": 2,
        "parent_code": "channel.analyze",
        "channel_code": "analyze",
        "sort_order": 51,
    },
    {
        "code": "channel.analyze.tab.index.btn.analyze",
        "name": "指数分析执行",
        "level": 3,
        "parent_code": "channel.analyze.tab.index",
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
        # standard/admin 保底
        conn.execute(
            text(
                """
                INSERT INTO role_permissions (role_id, permission_id)
                SELECT r.id, p.id
                FROM frontend_roles r
                CROSS JOIN frontend_permissions p
                WHERE r.code IN ('standard', 'admin')
                  AND p.code LIKE 'channel.analyze.tab.index%'
                  AND p.is_active = TRUE
                ON CONFLICT DO NOTHING
                """
            )
        )
        # 复制已有 stock_ai 角色授权到 index（同批开通）
        conn.execute(
            text(
                """
                INSERT INTO role_permissions (role_id, permission_id)
                SELECT DISTINCT rp.role_id, p_index.id
                FROM role_permissions rp
                JOIN frontend_permissions p_stock
                  ON p_stock.id = rp.permission_id
                 AND p_stock.code = 'channel.analyze.tab.stock_ai'
                JOIN frontend_permissions p_index
                  ON p_index.code LIKE 'channel.analyze.tab.index%'
                 AND p_index.is_active = TRUE
                ON CONFLICT DO NOTHING
                """
            )
        )
    print("OK: channel.analyze.tab.index* permissions synced")


if __name__ == "__main__":
    main()
