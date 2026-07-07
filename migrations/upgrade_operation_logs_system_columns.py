"""
迁移：为 operation_logs 补齐系统日志列（log_type、log_message 等）。
旧库可能仅有 user_id / action / stock_code 等自选股操作列，本迁移仅 ADD COLUMN，不删旧列。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging

from backend_api.database import SessionLocal
from backend_api.services.operation_logs_schema import ensure_operation_logs_system_schema

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upgrade():
    db = SessionLocal()
    try:
        ensure_operation_logs_system_schema(db)
        logger.info("operation_logs 系统日志列迁移完成")
    finally:
        db.close()


if __name__ == "__main__":
    upgrade()
