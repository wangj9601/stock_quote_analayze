"""
迁移：行业/概念板块基础信息表增加 frontend_visible_flag（是否对网站前端显示）
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from backend_core.database.db import engine
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

_TABLES = ("industry_board_basic_info", "concept_board_basic_info")
_LOCK_TIMEOUT = os.getenv("MIGRATION_LOCK_TIMEOUT", "30s")


def upgrade():
    logger.info("正在连接数据库…")
    with engine.connect() as conn:
        logger.info("已连接，设置 lock_timeout=%s", _LOCK_TIMEOUT)
        conn.execute(text(f"SET lock_timeout = '{_LOCK_TIMEOUT}'"))
        for table in _TABLES:
            logger.info("ALTER TABLE %s ADD COLUMN frontend_visible_flag …", table)
            conn.execute(
                text(
                    f"""
                    ALTER TABLE {table}
                    ADD COLUMN IF NOT EXISTS frontend_visible_flag BOOLEAN NOT NULL DEFAULT TRUE
                    """
                )
            )
            logger.info("COMMENT ON COLUMN %s.frontend_visible_flag …", table)
            conn.execute(
                text(
                    f"""
                    COMMENT ON COLUMN {table}.frontend_visible_flag IS '是否对网站前端显示（GMS等板块选择器）'
                    """
                )
            )
        conn.commit()
    logger.info("board frontend_visible_flag 迁移完成")


if __name__ == "__main__":
    try:
        upgrade()
    except Exception as e:
        err = str(e).lower()
        if "lock" in err or "timeout" in err:
            logger.error(
                "迁移失败：表被占用（常见原因：后端 API / 管理端正在访问板块表）。"
                "请先停止 start_backend_api.py 并关闭管理端「板块成分股」页面，再重试。"
            )
        raise SystemExit(1) from e
