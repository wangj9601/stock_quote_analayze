"""
迁移：将 tushare_moneyflow_daily 挂入「A股收盘后标准流程」（东财资金流之后）。
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migrations.add_em_fund_flow_workflow_node import _insert_after

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WF_NAME = "A股收盘后标准流程"
NODE_KEY = "tushare_moneyflow_daily"
DISPLAY_NAME = "Tushare个股资金流向日采"
AFTER_NODE = "em_stock_fund_flow_daily"


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
