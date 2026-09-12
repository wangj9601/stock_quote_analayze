#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""核查行业板历史归档：近日入库与运行痕迹。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text
from backend_api.database import SessionLocal


def main() -> int:
    db = SessionLocal()
    try:
        print("=== hist by date (10d) ===")
        for r in db.execute(
            text(
                """
                SELECT trade_date::text AS d, count(*) AS n,
                       count(*) FILTER (WHERE collected_source='tonghuashun') AS ths,
                       count(*) FILTER (WHERE collected_source='realtime_archive') AS rt_arch,
                       count(*) FILTER (WHERE collected_source='realtime_index_fill') AS rt_fill
                FROM industry_board_historical_quotes
                WHERE trade_date >= CURRENT_DATE - 10
                GROUP BY trade_date
                ORDER BY trade_date DESC
                """
            )
        ).mappings():
            print(dict(r))

        print("=== 2026-09-11 tonghuashun only ===")
        for r in db.execute(
            text(
                """
                SELECT board_code, board_name, close, collected_source, update_time
                FROM industry_board_historical_quotes
                WHERE trade_date = DATE '2026-09-11'
                  AND collected_source = 'tonghuashun'
                """
            )
        ).mappings():
            print(dict(r))

        print("=== 881101 recent ===")
        for r in db.execute(
            text(
                """
                SELECT trade_date::text, close, collected_source, update_time
                FROM industry_board_historical_quotes
                WHERE board_code = '881101' AND trade_date >= DATE '2026-09-08'
                ORDER BY trade_date
                """
            )
        ).mappings():
            print(dict(r))

        # workflow runs
        has = db.execute(
            text(
                """
                SELECT to_regclass('public.collection_workflow_runs') IS NOT NULL
                """
            )
        ).scalar()
        print("has collection_workflow_runs", has)
        if has:
            for r in db.execute(
                text(
                    """
                    SELECT id, status, started_at, finished_at, trigger_type
                    FROM collection_workflow_runs
                    WHERE started_at >= DATE '2026-09-10'
                    ORDER BY started_at DESC
                    LIMIT 20
                    """
                )
            ).mappings():
                print("run", dict(r))
            for r in db.execute(
                text(
                    """
                    SELECT r.id AS run_id, n.node_key, n.status, n.started_at, n.finished_at,
                           left(coalesce(n.error_message,''), 120) AS err
                    FROM collection_workflow_node_runs n
                    JOIN collection_workflow_runs r ON r.id = n.run_id
                    WHERE n.node_key = 'cn_board_historical'
                      AND n.started_at >= DATE '2026-09-10'
                    ORDER BY n.started_at DESC
                    LIMIT 20
                    """
                )
            ).mappings():
                print("node", dict(r))

        # operation logs variants
        for tbl in (
            "realtime_collect_operation_logs",
            "system_operation_logs",
            "operation_logs",
        ):
            exists = db.execute(
                text(f"SELECT to_regclass('public.{tbl}') IS NOT NULL")
            ).scalar()
            print(f"table {tbl}", exists)
            if not exists:
                continue
            cols = [
                c[0]
                for c in db.execute(
                    text(
                        """
                        SELECT column_name FROM information_schema.columns
                        WHERE table_name = :t
                        """
                    ),
                    {"t": tbl},
                ).fetchall()
            ]
            print(" cols", cols[:20])
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
