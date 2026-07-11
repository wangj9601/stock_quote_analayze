"""
诊断 PostgreSQL 锁等待（迁移前执行）

用法:
  python migrations/diagnose_db_locks.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from backend_api.config import DATABASE_CONFIG

engine = create_engine(
    DATABASE_CONFIG["url"],
    pool_pre_ping=True,
    connect_args={"connect_timeout": 15},
)

QUERIES = [
    ("当前连接", """
        SELECT pid, usename, application_name, client_addr, state,
               wait_event_type, wait_event,
               now() - query_start AS query_age,
               left(query, 120) AS query
        FROM pg_stat_activity
        WHERE datname = current_database()
          AND pid <> pg_backend_pid()
        ORDER BY query_start NULLS LAST
    """),
    ("阻塞关系", """
        SELECT blocked.pid AS blocked_pid,
               left(blocked.query, 80) AS blocked_query,
               blocking.pid AS blocking_pid,
               left(blocking.query, 80) AS blocking_query,
               now() - blocking.query_start AS blocking_age
        FROM pg_stat_activity blocked
        JOIN pg_stat_activity blocking
          ON blocking.pid = ANY(pg_catalog.pg_blocking_pids(blocked.pid))
        WHERE blocked.datname = current_database()
    """),
    ("长事务 (>60s)", """
        SELECT pid, state, usename, application_name,
               now() - xact_start AS xact_age,
               left(query, 100) AS query
        FROM pg_stat_activity
        WHERE datname = current_database()
          AND xact_start IS NOT NULL
          AND now() - xact_start > interval '60 seconds'
          AND pid <> pg_backend_pid()
        ORDER BY xact_start
    """),
    ("idle in transaction", """
        SELECT pid, usename, application_name,
               now() - state_change AS idle_age,
               left(query, 100) AS last_query
        FROM pg_stat_activity
        WHERE datname = current_database()
          AND state = 'idle in transaction'
          AND pid <> pg_backend_pid()
        ORDER BY state_change
    """),
]


def main():
    db_label = DATABASE_CONFIG["url"].split("@")[-1] if "@" in DATABASE_CONFIG["url"] else "?"
    print(f"=== 数据库锁诊断: {db_label} ===\n")

    with engine.connect() as conn:
        for title, sql in QUERIES:
            print(f"--- {title} ---")
            rows = conn.execute(text(sql)).mappings().all()
            if not rows:
                print("  (无)\n")
                continue
            for row in rows:
                print(" ", dict(row))
            print()

    print("建议:")
    print("  1. 低峰期执行迁移，或先停止 backend / uvicorn 服务")
    print("  2. 终止 idle in transaction 或长时间阻塞的 pid:")
    print("     SELECT pg_terminate_backend(<blocking_pid>);")
    print("  3. 再执行: python migrations/add_frontend_permissions.py")


if __name__ == "__main__":
    main()
