"""
迁移：预置「A股集合竞价终态采集」流程（单节点 cn_auction_final，cron 09:26）。
已存在同名流程时：若缺节点则追加；并校正 cron / skip_on_holiday。
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from backend_core.database.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WORKFLOW_NAME = "A股集合竞价终态采集"
NODE_KEY = "cn_auction_final"
NODE_DISPLAY = "A股集合竞价终态"
DESCRIPTION = (
    "交易日开盘前采集 A 股集合竞价终态（final）及短线风向标基准。"
    "默认 cron mon-fri 09:26；休市（CN）跳过。"
)


def upgrade():
    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT id FROM collection_workflows WHERE name = :name LIMIT 1"),
            {"name": WORKFLOW_NAME},
        ).fetchone()

        if not existing:
            row = conn.execute(
                text(
                    """
                    INSERT INTO collection_workflows (
                        name, description, enabled, trigger_type,
                        cron_dow, cron_hour, cron_minute, skip_on_holiday
                    ) VALUES (
                        :name, :description, TRUE, 'cron',
                        'mon-fri', '9', 26, 'CN'
                    ) RETURNING id
                    """
                ),
                {"name": WORKFLOW_NAME, "description": DESCRIPTION},
            ).fetchone()
            wf_id = int(row[0])
            conn.execute(
                text(
                    """
                    INSERT INTO collection_workflow_nodes (
                        workflow_id, order_index, node_key, display_name,
                        params, on_failure, retry_count, wait_seconds, enabled
                    ) VALUES (
                        :wid, 0, :nk, :dn,
                        '{}'::jsonb, 'stop', 1, 0, TRUE
                    )
                    """
                ),
                {"wid": wf_id, "nk": NODE_KEY, "dn": NODE_DISPLAY},
            )
            logger.info("已预置流程「%s」id=%s @ 09:26", WORKFLOW_NAME, wf_id)
            return

        wf_id = int(existing[0])
        conn.execute(
            text(
                """
                UPDATE collection_workflows
                SET description = :description,
                    trigger_type = 'cron',
                    cron_dow = 'mon-fri',
                    cron_hour = '9',
                    cron_minute = 26,
                    skip_on_holiday = 'CN'
                WHERE id = :wid
                """
            ),
            {"wid": wf_id, "description": DESCRIPTION},
        )
        has_node = conn.execute(
            text(
                """
                SELECT id FROM collection_workflow_nodes
                WHERE workflow_id = :wid AND node_key = :nk
                LIMIT 1
                """
            ),
            {"wid": wf_id, "nk": NODE_KEY},
        ).fetchone()
        if has_node:
            logger.info("流程「%s」已存在且含节点 %s，已同步 cron 09:26", WORKFLOW_NAME, NODE_KEY)
            return

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
        conn.execute(
            text(
                """
                INSERT INTO collection_workflow_nodes (
                    workflow_id, order_index, node_key, display_name,
                    params, on_failure, retry_count, wait_seconds, enabled
                ) VALUES (
                    :wid, :ord, :nk, :dn,
                    '{}'::jsonb, 'stop', 1, 0, TRUE
                )
                """
            ),
            {
                "wid": wf_id,
                "ord": int(mx) + 1,
                "nk": NODE_KEY,
                "dn": NODE_DISPLAY,
            },
        )
        logger.info("已为流程「%s」追加节点 %s", WORKFLOW_NAME, NODE_KEY)


if __name__ == "__main__":
    upgrade()
