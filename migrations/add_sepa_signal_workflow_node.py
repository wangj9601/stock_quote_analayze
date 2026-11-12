"""
迁移：将 sepa_signals_cn 挂入「A股收盘后标准流程」（RPE 之后、推荐简报之前）。

已有节点则跳过。建表走 Alembic：python scripts/db_migrate.py upgrade --yes
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migrations.add_em_fund_flow_workflow_node import _insert_after

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WF_NAME = "A股收盘后标准流程"
NODE_KEY = "sepa_signals_cn"
DISPLAY_NAME = "SEPA买点信号预计算(A股)"
AFTER_NODE = "rpe_signals_cn"


def upgrade():
    from backend_core.database.db import engine

    with engine.begin() as conn:
        _insert_after(
            conn,
            workflow_name=WF_NAME,
            after_node_key=AFTER_NODE,
            node_key=NODE_KEY,
            display_name=DISPLAY_NAME,
            on_failure="continue",
        )


if __name__ == "__main__":
    upgrade()
