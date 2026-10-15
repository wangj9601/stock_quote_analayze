# -*- coding: utf-8 -*-
import json
from sqlalchemy import text
from backend_api.database import SessionLocal

db = SessionLocal()
rows = db.execute(
    text(
        """
        SELECT task_id, status, name,
               config->>'preset_id' AS preset_id,
               config->>'start_date' AS start_date,
               config->>'end_date' AS end_date,
               config->>'exit_mode' AS exit_mode,
               LEFT(CAST(created_at AS text), 19) AS created
        FROM csb_backtest_tasks
        ORDER BY created_at DESC NULLS LAST
        LIMIT 30
        """
    )
).fetchall()
print("count", len(rows))
for r in rows:
    print(dict(r._mapping))

# also check if details exist elsewhere / any task covering that range
rows2 = db.execute(
    text(
        """
        SELECT task_id, status,
               config->>'preset_id' AS preset_id,
               config->>'start_date' AS s,
               config->>'end_date' AS e,
               summary->>'sample_count' AS sample_count,
               summary->>'total_trades' AS total_trades,
               summary->>'hit_rate' AS hit_rate
        FROM csb_backtest_tasks
        WHERE config->>'start_date' = '2025-10-01'
           OR CAST(task_id AS text) LIKE '4b71%'
        ORDER BY created_at DESC NULLS LAST
        LIMIT 20
        """
    )
).fetchall()
print("range_match", len(rows2))
for r in rows2:
    print(dict(r._mapping))

# trace in that year window after fix
for r in db.execute(
    text(
        """
        SELECT signal_type, COUNT(*) n,
               MIN(trade_date)::text d0, MAX(trade_date)::text d1
        FROM csb_signal_trace
        WHERE trade_date >= DATE '2025-10-01' AND trade_date <= DATE '2026-10-01'
        GROUP BY 1 ORDER BY 2 DESC
        """
    )
):
    print("trace", dict(r._mapping))
db.close()
