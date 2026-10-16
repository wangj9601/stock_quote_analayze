"""
数据脚本：将已入库流程节点显示名改为「Tushare 主源 / 东财兜底」口径。

用法：
  python migrations/update_main_force_flow_node_labels.py

亦可分别重跑：
  python migrations/add_em_fund_flow_workflow_node.py
  python migrations/add_tushare_moneyflow_workflow_node.py
（已存在节点时会按 DISPLAY_NAME 更新 display_name）
"""

from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPDATES = [
    ("em_stock_fund_flow_daily", "东财个股分档资金流日采（兜底）"),
    ("tushare_moneyflow_daily", "Tushare个股资金流向日采（主源）"),
]


def upgrade() -> None:
    from backend_core.database.db import engine

    with engine.begin() as conn:
        for node_key, display_name in UPDATES:
            r = conn.execute(
                text(
                    """
                    UPDATE collection_workflow_nodes
                    SET display_name = :dn
                    WHERE node_key = :nk
                      AND (display_name IS DISTINCT FROM :dn)
                    """
                ),
                {"dn": display_name, "nk": node_key},
            )
            logger.info(
                "collection_workflow_nodes %s -> %s (rows=%s)",
                node_key,
                display_name,
                r.rowcount,
            )

    logger.info("main force flow node labels update done")


if __name__ == "__main__":
    upgrade()
