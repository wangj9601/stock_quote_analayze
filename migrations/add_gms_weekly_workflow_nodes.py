"""
迁移：将 weekly_mf_cn、gms_signals_weekly_cn 挂入「A股收盘后标准流程」。

顺序：cn_weekly → weekly_mf_cn → gms_signals_weekly_cn
已有节点则跳过。对应 Alembic revision：0011_gms_weekly
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migrations.add_em_fund_flow_workflow_node import _insert_after

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WF_NAME = "A股收盘后标准流程"

# (after_node_key, node_key, display_name, on_failure)
INSERTS = [
    ("cn_weekly", "weekly_mf_cn", "A股周频MF", "continue"),
    ("weekly_mf_cn", "gms_signals_weekly_cn", "GMS周线信号预计算(A股)", "continue"),
]


def upgrade():
    from backend_core.database.db import engine

    with engine.begin() as conn:
        for after_key, node_key, display_name, on_failure in INSERTS:
            _insert_after(
                conn,
                workflow_name=WF_NAME,
                after_node_key=after_key,
                node_key=node_key,
                display_name=display_name,
                on_failure=on_failure,
            )
            logger.info("已处理节点 %s（锚点 %s）", node_key, after_key)


if __name__ == "__main__":
    upgrade()
