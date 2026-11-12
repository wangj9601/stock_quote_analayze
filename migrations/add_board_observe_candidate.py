# -*- coding: utf-8 -*-
"""迁移：行业观察池自动候选日表 + industry observe_lock 元数据。

用法:
    python migrations/add_board_observe_candidate.py
"""

from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from backend_core.database.db import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upgrade() -> None:
    db = SessionLocal()
    try:
        from backend_core.board_observe.storage import ensure_board_observe_tables

        ensure_board_observe_tables(db)
        logger.info("board_observe_candidate_daily / observe_lock 列已就绪")
    finally:
        db.close()


if __name__ == "__main__":
    upgrade()
