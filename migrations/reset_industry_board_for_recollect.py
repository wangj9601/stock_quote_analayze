"""
恢复：误合并后的行业板块数据需从东财重新拉取。
清空 industry_board_basic_info / industry_board_constituents 后，
请运行行业板块实时采集 + 成分股同步。
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from backend_core.database.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upgrade(*, clear_constituents: bool = True, clear_realtime: bool = False) -> dict:
    stats = {"basic_deleted": 0, "constituents_deleted": 0, "realtime_deleted": 0}
    with engine.connect() as conn:
        if clear_constituents:
            stats["constituents_deleted"] = (
                conn.execute(text("DELETE FROM industry_board_constituents")).rowcount or 0
            )
        stats["basic_deleted"] = (
            conn.execute(text("DELETE FROM industry_board_basic_info")).rowcount or 0
        )
        if clear_realtime:
            stats["realtime_deleted"] = (
                conn.execute(text("DELETE FROM industry_board_realtime_quotes")).rowcount or 0
            )
        conn.commit()
    logger.info("已清空行业板块表，请执行采集重建: %s", stats)
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="清空行业板块 basic/成分股以便重新采集")
    parser.add_argument("--keep-constituents", action="store_true")
    parser.add_argument("--clear-realtime", action="store_true")
    args = parser.parse_args()
    upgrade(
        clear_constituents=not args.keep_constituents,
        clear_realtime=args.clear_realtime,
    )
