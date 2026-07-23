"""URT 管理操作审计，写入 operation_logs。"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend_api.services.operation_logs_schema import ensure_operation_logs_system_schema

logger = logging.getLogger(__name__)


def write_urt_audit(
    db: Session,
    log_type: str,
    log_message: Dict[str, Any],
    *,
    affected_count: int = 0,
    log_status: str = "success",
    error_info: Optional[str] = None,
) -> None:
    if not log_type.startswith("urt_"):
        log_type = f"urt_{log_type}"
    try:
        ensure_operation_logs_system_schema(db)
        db.execute(
            text(
                """
                INSERT INTO operation_logs
                (log_type, log_message, affected_count, log_status, error_info, log_time)
                VALUES (:lt, :lm, :ac, :st, :err, NOW())
                """
            ),
            {
                "lt": log_type,
                "lm": json.dumps(log_message, ensure_ascii=False, default=str),
                "ac": affected_count,
                "st": log_status,
                "err": error_info,
            },
        )
        db.commit()
    except Exception as e:
        logger.warning("写入 URT 审计日志失败: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
