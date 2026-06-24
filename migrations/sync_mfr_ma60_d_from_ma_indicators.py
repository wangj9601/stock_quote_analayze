"""
迁移：将 mean_frequency_resonance_indicators.ma60_d 与 ma_indicators.ma60 批量对齐。

用法:
    python migrations/sync_mfr_ma60_d_from_ma_indicators.py
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_api.database import SessionLocal
from backend_core.strategies.gms.ma60_source import sync_mfr_ma60_d_from_ma_indicators

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    logger.info("开始同步 mean_frequency_resonance_indicators.ma60_d ← ma_indicators.ma60")
    logger.info("约 9900 只标的、近千万行，预计 20~40 分钟；请勿同时开多个窗口执行。")
    db = SessionLocal()
    try:
        total = sync_mfr_ma60_d_from_ma_indicators(db)
        logger.info("ma60_d 回填完成，共更新 %s 行", total)
    finally:
        db.close()


if __name__ == "__main__":
    main()
