"""
迁移：concept_board_basic_info + concept_board_constituents
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path

from sqlalchemy import text
from backend_core.database.db import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upgrade():
    sql_path = Path(__file__).parent / "sql" / "concept_board_constituents.sql"
    sql = sql_path.read_text(encoding="utf-8")
    with engine.connect() as conn:
        for stmt in sql.split(";"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))
        conn.commit()
    logger.info("concept_board 迁移完成")


if __name__ == "__main__":
    upgrade()
