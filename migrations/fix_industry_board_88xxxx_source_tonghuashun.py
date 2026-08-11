# -*- coding: utf-8 -*-
"""一次性修复：将误标为 eastmoney 的同花顺行业板码（88xxxx）改回 tonghuashun。

根因简述：
- 环境同步 import_board_data 曾用 board_code_source = EXCLUDED.board_code_source 无条件覆盖；
- 东财采集在空来源时会把板标成 eastmoney；88xxxx 被误匹配后无法再进前端 tonghuashun 目录。

用法：
  python migrations/fix_industry_board_88xxxx_source_tonghuashun.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sqlalchemy import text

from backend_api.database import SessionLocal


def main() -> None:
    db = SessionLocal()
    try:
        before = db.execute(
            text(
                """
                SELECT COALESCE(NULLIF(TRIM(board_code_source), ''), 'empty') AS src, COUNT(*)
                FROM industry_board_basic_info
                WHERE board_code ~ '^88[0-9]+$'
                GROUP BY 1 ORDER BY 1
                """
            )
        ).fetchall()
        print("before:", before)

        result = db.execute(
            text(
                """
                UPDATE industry_board_basic_info
                SET board_code_source = 'tonghuashun'
                WHERE board_code ~ '^88[0-9]+$'
                  AND COALESCE(NULLIF(TRIM(board_code_source), ''), 'eastmoney') = 'eastmoney'
                """
            )
        )
        db.commit()
        print(f"updated rows: {result.rowcount}")

        after = db.execute(
            text(
                """
                SELECT COALESCE(NULLIF(TRIM(board_code_source), ''), 'empty') AS src, COUNT(*)
                FROM industry_board_basic_info
                WHERE board_code ~ '^88[0-9]+$'
                GROUP BY 1 ORDER BY 1
                """
            )
        ).fetchall()
        print("after:", after)

        catalog_n = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM industry_board_basic_info b
                WHERE COALESCE(b.frontend_visible_flag, TRUE) = TRUE
                  AND COALESCE(NULLIF(TRIM(b.board_code_source), ''), 'eastmoney') = 'tonghuashun'
                """
            )
        ).scalar()
        print("frontend tonghuashun catalog count:", catalog_n)
    finally:
        db.close()


if __name__ == "__main__":
    main()
