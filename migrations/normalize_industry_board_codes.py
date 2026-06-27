"""
迁移：行业板块 basic/成分股/实时行情中的中文或非唯一 BK 编码统一为 BK 编码。
规则与概念板块相同（BK+数字），且全局不与概念板块编码重复。
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Dict, List, Optional, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from backend_api.utils.bk_board_code import (
    allocate_bk_board_code,
    collect_concept_bk_codes,
    collect_used_bk_codes,
    is_valid_bk_board_code,
    normalize_bk_board_code,
)
from backend_core.database.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _load_industry_basic(conn) -> List[Tuple[str, Optional[str], Optional[object]]]:
    return conn.execute(
        text(
            """
            SELECT board_code, board_name, create_date
            FROM industry_board_basic_info
            ORDER BY board_code
            """
        )
    ).fetchall()


def _rename_industry_board(conn, old_code: str, new_code: str) -> None:
    if old_code == new_code:
        return
    conn.execute(
        text(
            """
            INSERT INTO industry_board_constituents (board_code, stock_code, stock_name, updated_at)
            SELECT :new, stock_code, stock_name, updated_at
            FROM industry_board_constituents
            WHERE board_code = :old
            ON CONFLICT (board_code, stock_code) DO UPDATE SET
                stock_name = EXCLUDED.stock_name,
                updated_at = EXCLUDED.updated_at
            """
        ),
        {"old": old_code, "new": new_code},
    )
    conn.execute(
        text("DELETE FROM industry_board_constituents WHERE board_code = :old"),
        {"old": old_code},
    )
    row = conn.execute(
        text(
            "SELECT board_name, create_date, trade_observe_flag FROM industry_board_basic_info WHERE board_code = :old"
        ),
        {"old": old_code},
    ).fetchone()
    if row:
        conn.execute(
            text(
                """
                INSERT INTO industry_board_basic_info (board_code, board_name, create_date, trade_observe_flag)
                VALUES (:new, :name, :create_date, COALESCE(:flag, FALSE))
                ON CONFLICT (board_code) DO UPDATE SET
                    board_name = COALESCE(EXCLUDED.board_name, industry_board_basic_info.board_name),
                    trade_observe_flag = industry_board_basic_info.trade_observe_flag
                        OR EXCLUDED.trade_observe_flag
                """
            ),
            {
                "new": new_code,
                "name": row[0],
                "create_date": row[1],
                "flag": row[2] if len(row) > 2 else False,
            },
        )
    conn.execute(
        text("DELETE FROM industry_board_basic_info WHERE board_code = :old"),
        {"old": old_code},
    )
    conn.execute(
        text("DELETE FROM industry_board_realtime_quotes WHERE board_code = :old"),
        {"old": old_code},
    )


def _next_industry_bk(conn, used: Set[str], concept_bk: Set[str]) -> str:
    code = allocate_bk_board_code(
        conn,
        exclude=concept_bk | used,
    )  # type: ignore[arg-type]
    used.add(code)
    return code


def upgrade(dry_run: bool = False) -> dict:
    stats = {
        "renamed": 0,
        "assigned_new": 0,
        "realtime_deleted": 0,
    }
    renames: Dict[str, str] = {}

    with engine.connect() as conn:
        concept_bk = collect_concept_bk_codes(conn)  # type: ignore[arg-type]
        used_bk: Set[str] = set(collect_used_bk_codes(conn)) | concept_bk  # type: ignore[arg-type]
        rows = _load_industry_basic(conn)

        for code, name, _ in rows:
            c = str(code or "").strip()
            if not c:
                continue
            nc = normalize_bk_board_code(c)
            if (
                is_valid_bk_board_code(nc)
                and nc not in concept_bk
                and c not in renames
            ):
                used_bk.add(nc)
                key = str(name or c).strip()
                if key:
                    name_to_bk[key] = nc
                continue

            key = str(name or c).strip()
            target = name_to_bk.get(key)
            if not target or target in concept_bk:
                target = _next_industry_bk(conn, used_bk, concept_bk)
                stats["assigned_new"] += 1
                if key:
                    name_to_bk[key] = target

            if c != target and nc != target:
                renames[c] = target

        for old, new in sorted(renames.items(), key=lambda x: x[0]):
            if old == new:
                continue
            logger.info("行业板块编码 %s -> %s", old, new)
            _rename_industry_board(conn, old, new)
            stats["renamed"] += 1

        rt_del = conn.execute(
            text(
                """
                DELETE FROM industry_board_realtime_quotes q
                WHERE q.board_code !~ '^BK[0-9]+$'
                   OR EXISTS (
                        SELECT 1 FROM concept_board_basic_info c
                        WHERE c.board_code = q.board_code
                   )
                """
            )
        )
        stats["realtime_deleted"] = rt_del.rowcount or 0

        if dry_run:
            conn.rollback()
            logger.info("dry_run=true，已回滚")
        else:
            conn.commit()

    logger.info("行业板块编码规范化完成: %s", stats)
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="行业板块编码统一为 BK 格式")
    parser.add_argument("--dry-run", action="store_true", help="仅演练并回滚")
    args = parser.parse_args()
    upgrade(dry_run=args.dry_run)
