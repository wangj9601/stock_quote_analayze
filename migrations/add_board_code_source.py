"""
迁移：industry/concept_board_basic_info 增加 board_code_source（板块代码来源）。

用法:
    python migrations/add_board_code_source.py
"""

from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from backend_api.database import SessionLocal

logger = logging.getLogger(__name__)

_TABLES = ("industry_board_basic_info", "concept_board_basic_info")


def run() -> None:
    db = SessionLocal()
    try:
        for table in _TABLES:
            db.execute(
                text(
                    f"""
                    ALTER TABLE {table}
                    ADD COLUMN IF NOT EXISTS board_code_source VARCHAR(32)
                    """
                )
            )
            db.execute(
                text(
                    f"""
                    UPDATE {table}
                    SET board_code_source = 'eastmoney'
                    WHERE board_code_source IS NULL OR TRIM(board_code_source) = ''
                    """
                )
            )
        db.commit()
        logger.info("board_code_source 列已就绪（历史数据默认 eastmoney）")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
