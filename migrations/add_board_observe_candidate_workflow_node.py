# -*- coding: utf-8 -*-
"""将 board_observe_candidates_daily 挂入标准流程（board_gates_daily 之前）。

用法:
    python migrations/add_board_observe_candidate_workflow_node.py
"""

from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from backend_core.database.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WF_NAME = "A股收盘后标准流程"
BEFORE_KEY = "board_gates_daily"
FALLBACK_AFTER = "market_daily_review"
NODE_KEY = "board_observe_candidates_daily"
DISPLAY = "行业观察池自动候选"


def upgrade() -> None:
    with engine.begin() as conn:
        wf = conn.execute(
            text("SELECT id FROM collection_workflows WHERE name = :name LIMIT 1"),
            {"name": WF_NAME},
        ).fetchone()
        if not wf:
            logger.warning("未找到流程「%s」，跳过", WF_NAME)
            return
        wf_id = int(wf[0])

        exists = conn.execute(
            text(
                """
                SELECT id FROM collection_workflow_nodes
                WHERE workflow_id = :wid AND node_key = :nk LIMIT 1
                """
            ),
            {"wid": wf_id, "nk": NODE_KEY},
        ).fetchone()
        if exists:
            logger.info("流程已含节点 %s，跳过", NODE_KEY)
            return

        before = conn.execute(
            text(
                """
                SELECT order_index FROM collection_workflow_nodes
                WHERE workflow_id = :wid AND node_key = :nk LIMIT 1
                """
            ),
            {"wid": wf_id, "nk": BEFORE_KEY},
        ).fetchone()
        if before:
            target = int(before[0])
        else:
            after = conn.execute(
                text(
                    """
                    SELECT order_index FROM collection_workflow_nodes
                    WHERE workflow_id = :wid AND node_key = :nk LIMIT 1
                    """
                ),
                {"wid": wf_id, "nk": FALLBACK_AFTER},
            ).fetchone()
            if after:
                target = int(after[0]) + 1
            else:
                mx = conn.execute(
                    text(
                        """
                        SELECT COALESCE(MAX(order_index), 0)
                        FROM collection_workflow_nodes WHERE workflow_id = :wid
                        """
                    ),
                    {"wid": wf_id},
                ).fetchone()
                target = int(mx[0] or 0) + 1

        # 两段移位，避开 uq_wf_node_order 瞬时冲突
        conn.execute(
            text(
                """
                UPDATE collection_workflow_nodes
                SET order_index = order_index + 1000
                WHERE workflow_id = :wid AND order_index >= :ord
                """
            ),
            {"wid": wf_id, "ord": target},
        )
        conn.execute(
            text(
                """
                UPDATE collection_workflow_nodes
                SET order_index = order_index - 999
                WHERE workflow_id = :wid AND order_index >= :ord
                """
            ),
            {"wid": wf_id, "ord": target + 1000},
        )
        conn.execute(
            text(
                """
                INSERT INTO collection_workflow_nodes
                    (workflow_id, node_key, display_name, order_index, enabled, on_failure)
                VALUES
                    (:wid, :nk, :dn, :ord, TRUE, 'continue')
                """
            ),
            {"wid": wf_id, "nk": NODE_KEY, "dn": DISPLAY, "ord": target},
        )
        logger.info("已插入节点 %s @ order=%s（位于 %s 之前）", NODE_KEY, target, BEFORE_KEY)


if __name__ == "__main__":
    upgrade()
