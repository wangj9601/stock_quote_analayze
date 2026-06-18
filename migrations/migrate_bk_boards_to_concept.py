"""
迁移：将 industry_board_basic_info 中 BK 前缀板块迁入 concept_board_basic_info，
并同步迁移 industry_board_constituents 中对应成分股到 concept_board_constituents。
"""

from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path

from sqlalchemy import text

from backend_core.database.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _ensure_concept_tables(conn) -> None:
    sql_path = Path(__file__).parent / "sql" / "concept_board_constituents.sql"
    if sql_path.exists():
        for stmt in sql_path.read_text(encoding="utf-8").split(";"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))


def upgrade(dry_run: bool = False) -> dict:
    stats = {
        "basic_migrated": 0,
        "constituents_migrated": 0,
        "basic_deleted": 0,
        "constituents_deleted": 0,
        "realtime_deleted": 0,
    }
    with engine.connect() as conn:
        _ensure_concept_tables(conn)

        stats["basic_migrated"] = conn.execute(
            text(
                """
                INSERT INTO concept_board_basic_info (board_code, board_name, create_date)
                SELECT board_code, board_name, create_date
                FROM industry_board_basic_info
                WHERE UPPER(board_code) LIKE 'BK%'
                ON CONFLICT (board_code) DO UPDATE SET
                    board_name = EXCLUDED.board_name,
                    create_date = EXCLUDED.create_date
                """
            )
        ).rowcount or 0

        stats["constituents_migrated"] = conn.execute(
            text(
                """
                INSERT INTO concept_board_constituents (board_code, stock_code, stock_name, updated_at)
                SELECT board_code, stock_code, stock_name, updated_at
                FROM industry_board_constituents
                WHERE UPPER(board_code) LIKE 'BK%'
                ON CONFLICT (board_code, stock_code) DO UPDATE SET
                    stock_name = EXCLUDED.stock_name,
                    updated_at = EXCLUDED.updated_at
                """
            )
        ).rowcount or 0

        stats["constituents_deleted"] = conn.execute(
            text("DELETE FROM industry_board_constituents WHERE UPPER(board_code) LIKE 'BK%'")
        ).rowcount or 0
        stats["basic_deleted"] = conn.execute(
            text("DELETE FROM industry_board_basic_info WHERE UPPER(board_code) LIKE 'BK%'")
        ).rowcount or 0
        stats["realtime_deleted"] = conn.execute(
            text("DELETE FROM industry_board_realtime_quotes WHERE UPPER(board_code) LIKE 'BK%'")
        ).rowcount or 0

        if dry_run:
            conn.rollback()
            logger.info("dry_run=true，已回滚")
        else:
            conn.commit()

    logger.info("BK 板块迁移完成: %s", stats)
    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="迁移 BK 前缀板块到概念板块表")
    parser.add_argument("--dry-run", action="store_true", help="仅演练并回滚")
    args = parser.parse_args()
    upgrade(dry_run=args.dry_run)
