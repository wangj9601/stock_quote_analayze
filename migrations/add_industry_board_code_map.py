"""
迁移：板块同花顺 ↔ 东财代码映射表，并按同名自动回填（行业 + 概念）。

用法:
    python migrations/add_industry_board_code_map.py
"""

from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_api.database import SessionLocal
from backend_api.utils.industry_board_code_map import (
    ensure_industry_board_code_map_table,
    rebuild_name_exact_maps,
)

logger = logging.getLogger(__name__)


def run() -> None:
    db = SessionLocal()
    try:
        ensure_industry_board_code_map_table(db)
        industry_stats = rebuild_name_exact_maps(
            db, board_kind="industry", replace_auto=True
        )
        concept_stats = rebuild_name_exact_maps(
            db, board_kind="concept", replace_auto=True
        )
        db.commit()
        logger.info(
            "board_code_map 已就绪: industry=%s concept=%s",
            industry_stats,
            concept_stats,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
