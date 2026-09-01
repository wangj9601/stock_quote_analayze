"""
迁移：向「A股收盘后标准流程」插入指数/板块历史归档节点
（位于 cn_industry_board 之后、rs_rating_cn 之前）
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from backend_core.database.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WF_NAME = "A股收盘后标准流程"

NEW_NODES = [
    (11, "cn_index_historical", "A股指数历史归档"),
    (12, "index_daily_cn", "A股指数日线采集"),
    (13, "cn_board_historical", "同花顺板块历史归档"),
]


def upgrade():
    with engine.begin() as conn:
        wf = conn.execute(
            text("SELECT id FROM collection_workflows WHERE name = :name LIMIT 1"),
            {"name": WF_NAME},
        ).fetchone()
        if not wf:
            logger.warning("未找到流程「%s」，跳过节点挂载", WF_NAME)
            return
        wf_id = int(wf[0])

        existing_keys = {
            row[0]
            for row in conn.execute(
                text(
                    "SELECT node_key FROM collection_workflow_nodes WHERE workflow_id = :wid"
                ),
                {"wid": wf_id},
            ).fetchall()
        }

        to_insert = [n for n in NEW_NODES if n[1] not in existing_keys]
        if not to_insert:
            logger.info("流程已包含全部历史归档节点，跳过")
            return

        first_order = min(n[0] for n in to_insert)
        shift = len(to_insert)
        conn.execute(
            text(
                """
                UPDATE collection_workflow_nodes
                SET order_index = order_index + :shift
                WHERE workflow_id = :wid AND order_index >= :ord
                """
            ),
            {"wid": wf_id, "ord": first_order, "shift": shift},
        )

        for order_index, node_key, display_name in to_insert:
            conn.execute(
                text(
                    """
                    INSERT INTO collection_workflow_nodes (
                        workflow_id, order_index, node_key, display_name,
                        params, on_failure, retry_count, wait_seconds, enabled
                    ) VALUES (
                        :wid, :ord, :nk, :dn,
                        '{}'::jsonb, 'stop', 0, 0, TRUE
                    )
                    """
                ),
                {
                    "wid": wf_id,
                    "ord": order_index,
                    "nk": node_key,
                    "dn": display_name,
                },
            )
            logger.info("已插入节点 %s @ order_index=%s", node_key, order_index)


if __name__ == "__main__":
    upgrade()
