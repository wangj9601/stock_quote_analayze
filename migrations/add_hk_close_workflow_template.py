"""
迁移：预置「港股收盘后标准流程」模板（含 GMS/URT 港股策略预计算节点）
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from backend_core.database.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WORKFLOW_NAME = "港股收盘后标准流程"

HK_CLOSE_TEMPLATE_NODES = [
    (0, "hk_realtime", "港股实时行情"),
    (1, "hk_historical", "港股日K"),
    (2, "hk_weekly", "港股周K"),
    (3, "hk_monthly", "港股月K"),
    (4, "hk_quarterly", "港股季K"),
    (5, "hk_semiannual", "港股半年K"),
    (6, "hk_annual", "港股年K"),
    (7, "hk_index_realtime", "港股指数实时"),
    (8, "hk_index_historical", "港股指数历史归档"),
    (9, "rs_rating_hk", "港股相对强度RS预计算"),
    (10, "urt_signals_hk", "URT信号预计算(港股)"),
    (11, "gms_signals_hk", "GMS信号预计算(港股)"),
]

HK_STRATEGY_NODES = [
    ("rs_rating_hk", "港股相对强度RS预计算"),
    ("urt_signals_hk", "URT信号预计算(港股)"),
    ("gms_signals_hk", "GMS信号预计算(港股)"),
]

DESCRIPTION = (
    "对齐生产港股收盘链路：实时→日K→周期K→指数→RS/URT/GMS 策略预计算。"
    "默认 cron 17:00（港股日K约 16:55 完成后）；启用后请将 "
    "ENABLE_LEGACY_COLLECTION_CRON=false 以避免与分散 cron 重复执行。"
)


def _insert_nodes(conn, wf_id: int, nodes) -> None:
    for order_index, node_key, display_name in nodes:
        conn.execute(
            text(
                """
                INSERT INTO collection_workflow_nodes (
                    workflow_id, order_index, node_key, display_name,
                    params, on_failure, retry_count, wait_seconds, enabled
                ) VALUES (
                    :wf_id, :order_index, :node_key, :display_name,
                    '{}'::jsonb, 'stop', 0, 0, TRUE
                )
                """
            ),
            {
                "wf_id": wf_id,
                "order_index": order_index,
                "node_key": node_key,
                "display_name": display_name,
            },
        )


def _append_missing_strategy_nodes(conn, wf_id: int) -> None:
    existing_keys = {
        row[0]
        for row in conn.execute(
            text(
                "SELECT node_key FROM collection_workflow_nodes WHERE workflow_id = :wf_id"
            ),
            {"wf_id": wf_id},
        ).fetchall()
    }
    max_order = conn.execute(
        text(
            "SELECT COALESCE(MAX(order_index), -1) FROM collection_workflow_nodes "
            "WHERE workflow_id = :wf_id"
        ),
        {"wf_id": wf_id},
    ).scalar()
    next_order = int(max_order) + 1
    added = []
    for node_key, display_name in HK_STRATEGY_NODES:
        if node_key in existing_keys:
            continue
        conn.execute(
            text(
                """
                INSERT INTO collection_workflow_nodes (
                    workflow_id, order_index, node_key, display_name,
                    params, on_failure, retry_count, wait_seconds, enabled
                ) VALUES (
                    :wf_id, :order_index, :node_key, :display_name,
                    '{}'::jsonb, 'stop', 0, 0, TRUE
                )
                """
            ),
            {
                "wf_id": wf_id,
                "order_index": next_order,
                "node_key": node_key,
                "display_name": display_name,
            },
        )
        added.append(node_key)
        next_order += 1
    if added:
        logger.info("已为流程 id=%s 追加节点: %s", wf_id, ", ".join(added))


def upgrade():
    with engine.connect() as conn:
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
                        :name, :description, FALSE, 'cron',
                        'mon-fri', '17', 0, 'HK'
                    ) RETURNING id
                    """
                ),
                {"name": WORKFLOW_NAME, "description": DESCRIPTION},
            ).fetchone()
            wf_id = row[0]
            _insert_nodes(conn, wf_id, HK_CLOSE_TEMPLATE_NODES)
            logger.info("已预置流程模板「%s」id=%s", WORKFLOW_NAME, wf_id)
        else:
            wf_id = existing[0]
            conn.execute(
                text(
                    """
                    UPDATE collection_workflows
                    SET description = :description,
                        skip_on_holiday = 'HK',
                        cron_dow = 'mon-fri',
                        cron_hour = '17',
                        cron_minute = 0,
                        updated_at = NOW()
                    WHERE id = :wf_id
                    """
                ),
                {"wf_id": wf_id, "description": DESCRIPTION},
            )
            _append_missing_strategy_nodes(conn, wf_id)
            logger.info("流程模板「%s」已存在 id=%s，已校正休市/cron 并补全策略节点", WORKFLOW_NAME, wf_id)

        conn.commit()
        logger.info("港股收盘流程模板迁移完成")


if __name__ == "__main__":
    upgrade()
