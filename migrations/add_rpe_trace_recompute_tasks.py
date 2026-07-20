"""
迁移：创建 rpe_trace_recompute_tasks（RPE 信号追溯强制重算任务表）。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging

from backend_api.database import engine
from backend_api.models import RPETraceRecomputeTask

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upgrade():
    RPETraceRecomputeTask.__table__.create(bind=engine, checkfirst=True)
    logger.info("rpe_trace_recompute_tasks 迁移完成")


if __name__ == "__main__":
    upgrade()
