"""
迁移：将 macd_cn / macd_hk 独立节点插入收盘后标准流程
（分别紧挨 cn_historical / hk_historical 之后）
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from backend_core.database.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _insert_after(
    conn,
    workflow_name: str,
    after_node_key: str,
    node_key: str,
    display_name: str,
) -> None:
    wf = conn.execute(
        text("SELECT id FROM collection_workflows WHERE name = :name LIMIT 1"),
        {"name": workflow_name},
    ).fetchone()
    if not wf:
        logger.warning("未找到流程「%s」，跳过节点 %s", workflow_name, node_key)
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
        {"wid": wf_id, "nk": node_key},
    ).fetchone()
    if exists:
        logger.info("流程「%s」已包含节点 %s，跳过", workflow_name, node_key)
        return

    after = conn.execute(
        text(
            """
            SELECT order_index FROM collection_workflow_nodes
            WHERE workflow_id = :wid AND node_key = :nk
            LIMIT 1
            """
        ),
        {"wid": wf_id, "nk": after_node_key},
    ).fetchone()
    if after:
        target_order = int(after[0]) + 1
    else:
        mx = conn.execute(
            text(
                """
                SELECT COALESCE(MAX(order_index), -1)
                FROM collection_workflow_nodes
                WHERE workflow_id = :wid
                """
            ),
            {"wid": wf_id},
        ).scalar()
        target_order = int(mx) + 1
        logger.warning(
            "流程「%s」未找到锚点节点 %s，将 %s 追加到末尾 order=%s",
            workflow_name,
            after_node_key,
            node_key,
            target_order,
        )

    # 唯一约束 (workflow_id, order_index)：先整体抬高再回写，避免递增冲突
    conn.execute(
        text(
            """
            UPDATE collection_workflow_nodes
            SET order_index = order_index + 1000
            WHERE workflow_id = :wid AND order_index >= :ord
            """
        ),
        {"wid": wf_id, "ord": target_order},
    )
    conn.execute(
        text(
            """
            UPDATE collection_workflow_nodes
            SET order_index = order_index - 999
            WHERE workflow_id = :wid AND order_index >= :ord_hi
            """
        ),
        {"wid": wf_id, "ord_hi": target_order + 1000},
    )
    conn.execute(
        text(
            """
            INSERT INTO collection_workflow_nodes (
                workflow_id, order_index, node_key, display_name,
                params, on_failure, retry_count, wait_seconds, enabled
            ) VALUES (
                :wid, :ord, :nk, :dn,
                '{}'::jsonb, 'continue', 0, 0, TRUE
            )
            """
        ),
        {
            "wid": wf_id,
            "ord": target_order,
            "nk": node_key,
            "dn": display_name,
        },
    )
    logger.info(
        "已向「%s」插入节点 %s @ order_index=%s（%s 之后）",
        workflow_name,
        node_key,
        target_order,
        after_node_key,
    )


def upgrade():
    with engine.begin() as conn:
        _insert_after(
            conn,
            "A股收盘后标准流程",
            "cn_historical",
            "macd_cn",
            "A股MACD日算",
        )
        _insert_after(
            conn,
            "港股收盘后标准流程",
            "hk_historical",
            "macd_hk",
            "港股MACD日算",
        )


if __name__ == "__main__":
    upgrade()
