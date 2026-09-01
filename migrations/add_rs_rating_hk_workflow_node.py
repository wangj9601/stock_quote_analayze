"""
迁移：将 rs_rating_hk 节点插入「港股收盘后标准流程」
（位于 hk_index_historical 之后、urt_signals_hk 之前）

说明：因存在 (workflow_id, order_index) 唯一约束，后移节点时先整体偏移再回写，避免中间冲突。
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from backend_core.database.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WF_NAME = "港股收盘后标准流程"
NODE_KEY = "rs_rating_hk"
DISPLAY_NAME = "港股相对强度RS预计算"
# 模板目标：… index_historical(8) → rs(9) → urt(10) → gms(11)
TARGET_ORDER = 9
TEMP_OFFSET = 1000


def upgrade():
    with engine.begin() as conn:
        wf = conn.execute(
            text("SELECT id FROM collection_workflows WHERE name = :name LIMIT 1"),
            {"name": WF_NAME},
        ).fetchone()
        if not wf:
            logger.warning("未找到流程「%s」，跳过节点挂载（可在管理端手动添加）", WF_NAME)
            return
        wf_id = int(wf[0])

        exists = conn.execute(
            text(
                """
                SELECT id FROM collection_workflow_nodes
                WHERE workflow_id = :wid AND node_key = :nk
                LIMIT 1
                """
            ),
            {"wid": wf_id, "nk": NODE_KEY},
        ).fetchone()
        if exists:
            logger.info("流程已包含节点 %s，跳过", NODE_KEY)
            return

        # 先整体偏移，避开 uq_wf_node_order 中间冲突
        conn.execute(
            text(
                """
                UPDATE collection_workflow_nodes
                SET order_index = order_index + :off
                WHERE workflow_id = :wid AND order_index >= :ord
                """
            ),
            {"wid": wf_id, "ord": TARGET_ORDER, "off": TEMP_OFFSET},
        )
        conn.execute(
            text(
                """
                UPDATE collection_workflow_nodes
                SET order_index = order_index - :off + 1
                WHERE workflow_id = :wid AND order_index >= :ord + :off
                """
            ),
            {"wid": wf_id, "ord": TARGET_ORDER, "off": TEMP_OFFSET},
        )
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
                "ord": TARGET_ORDER,
                "nk": NODE_KEY,
                "dn": DISPLAY_NAME,
            },
        )
        logger.info(
            "已向流程 id=%s 插入节点 %s @ order_index=%s",
            wf_id,
            NODE_KEY,
            TARGET_ORDER,
        )


if __name__ == "__main__":
    upgrade()
