"""operation_logs 系统日志列（log_type 等）按需补齐。"""

from __future__ import annotations

import threading

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

_schema_lock = threading.Lock()
_schema_ensured = False

_SYSTEM_COLUMNS = (
    ("log_type", "VARCHAR(64)"),
    ("log_message", "TEXT"),
    ("affected_count", "INTEGER NOT NULL DEFAULT 0"),
    ("log_status", "VARCHAR(32)"),
    ("error_info", "TEXT"),
    ("log_time", "TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()"),
)


def ensure_operation_logs_system_schema(db: Session) -> None:
    """旧库 operation_logs 可能仅有 user_id/action 等列，补齐系统日志字段。"""
    global _schema_ensured
    if _schema_ensured:
        return
    with _schema_lock:
        if _schema_ensured:
            return
        bind = db.get_bind()
        if bind is None or bind.dialect.name != "postgresql":
            _schema_ensured = True
            return
        existing = {c["name"] for c in inspect(bind).get_columns("operation_logs")}
        if "log_type" in existing:
            _schema_ensured = True
            return
        for col_name, col_def in _SYSTEM_COLUMNS:
            if col_name not in existing:
                db.execute(
                    text(
                        f"ALTER TABLE operation_logs ADD COLUMN IF NOT EXISTS {col_name} {col_def}"
                    )
                )
        db.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_operation_logs_log_type_time
                ON operation_logs (log_type, log_time DESC)
                """
            )
        )
        db.commit()
        _schema_ensured = True
