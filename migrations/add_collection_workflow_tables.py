"""
迁移：采集流程自动化四表 + 预置「A股收盘后标准流程」模板
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from backend_core.database.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


CN_CLOSE_TEMPLATE_NODES = [
    (0, "cn_realtime", "A股实时行情"),
    (1, "cn_historical", "A股日K"),
    (2, "etf_realtime", "ETF实时"),
    (3, "etf_historical", "ETF历史"),
    (4, "cn_weekly", "A股周K"),
    (5, "cn_monthly", "A股月K"),
    (6, "cn_quarterly", "A股季K"),
    (7, "cn_semiannual", "A股半年K"),
    (8, "cn_annual", "A股年K"),
    (9, "cn_index_realtime", "A股指数实时"),
    (10, "cn_industry_board", "行业板块实时"),
    (11, "cn_index_historical", "A股指数历史归档"),
    (12, "index_daily_cn", "A股指数日线采集"),
    (13, "cn_board_historical", "同花顺板块历史归档"),
    (14, "rs_rating_cn", "A股相对强度RS预计算"),
    (15, "gms_signals_cn", "GMS信号预计算"),
    (16, "urt_signals_cn", "URT信号预计算"),
]


def upgrade():
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS collection_workflows (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(120) NOT NULL,
                    description TEXT,
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    trigger_type VARCHAR(20) NOT NULL DEFAULT 'manual',
                    cron_dow VARCHAR(32),
                    cron_hour VARCHAR(32),
                    cron_minute INTEGER,
                    skip_on_holiday VARCHAR(10) DEFAULT 'NONE',
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS collection_workflow_nodes (
                    id SERIAL PRIMARY KEY,
                    workflow_id INTEGER NOT NULL
                        REFERENCES collection_workflows(id) ON DELETE CASCADE,
                    order_index INTEGER NOT NULL,
                    node_key VARCHAR(64) NOT NULL,
                    display_name VARCHAR(120),
                    params JSONB DEFAULT '{}'::jsonb,
                    on_failure VARCHAR(20) DEFAULT 'stop',
                    retry_count INTEGER DEFAULT 0,
                    wait_seconds INTEGER DEFAULT 0,
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    CONSTRAINT uq_wf_node_order UNIQUE (workflow_id, order_index)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_collection_workflow_nodes_wf
                ON collection_workflow_nodes (workflow_id)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS collection_workflow_runs (
                    run_id VARCHAR(64) PRIMARY KEY,
                    workflow_id INTEGER NOT NULL,
                    workflow_name VARCHAR(120),
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    trigger_source VARCHAR(20) NOT NULL,
                    current_node_index INTEGER,
                    started_at TIMESTAMP WITHOUT TIME ZONE,
                    finished_at TIMESTAMP WITHOUT TIME ZONE,
                    error_message TEXT,
                    context JSONB DEFAULT '{}'::jsonb
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_collection_workflow_runs_wf
                ON collection_workflow_runs (workflow_id)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_collection_workflow_runs_status
                ON collection_workflow_runs (status)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS collection_workflow_node_runs (
                    id SERIAL PRIMARY KEY,
                    run_id VARCHAR(64) NOT NULL
                        REFERENCES collection_workflow_runs(run_id) ON DELETE CASCADE,
                    node_key VARCHAR(64) NOT NULL,
                    order_index INTEGER NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    progress INTEGER DEFAULT 0,
                    message TEXT,
                    error TEXT,
                    started_at TIMESTAMP WITHOUT TIME ZONE,
                    finished_at TIMESTAMP WITHOUT TIME ZONE,
                    result JSONB DEFAULT '{}'::jsonb
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_collection_workflow_node_runs_run
                ON collection_workflow_node_runs (run_id)
                """
            )
        )

        # 预置模板（仅当不存在同名流程时）
        existing = conn.execute(
            text(
                "SELECT id FROM collection_workflows WHERE name = :name LIMIT 1"
            ),
            {"name": "A股收盘后标准流程"},
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
                        'mon-fri', '15', 35, 'CN'
                    ) RETURNING id
                    """
                ),
                {
                    "name": "A股收盘后标准流程",
                    "description": (
                        "对齐生产收盘链路：实时→日K→ETF→周期K→指数/板块→策略预计算。"
                        "默认 cron 15:35；启用后请将 ENABLE_LEGACY_COLLECTION_CRON=false "
                        "以避免与分散 cron 重复执行。"
                    ),
                },
            ).fetchone()
            wf_id = row[0]
            for order_index, node_key, display_name in CN_CLOSE_TEMPLATE_NODES:
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
            logger.info("已预置流程模板「A股收盘后标准流程」id=%s", wf_id)
        else:
            logger.info("流程模板「A股收盘后标准流程」已存在，跳过预置")

        # 前端权限（若表存在）
        try:
            conn.execute(
                text(
                    """
                    INSERT INTO frontend_permissions (code, name, level, parent_code, channel_code, sort_order, is_active)
                    VALUES
                        ('admin.collection_workflows', '采集流程', 2, 'admin', 'admin', 85, TRUE),
                        ('admin.collection_workflows.read', '采集流程-查看', 3, 'admin.collection_workflows', 'admin', 1, TRUE),
                        ('admin.collection_workflows.write', '采集流程-编辑', 3, 'admin.collection_workflows', 'admin', 2, TRUE)
                    ON CONFLICT (code) DO NOTHING
                    """
                )
            )
        except Exception as e:
            logger.warning("写入 frontend_permissions 跳过: %s", e)

        conn.commit()
        logger.info("collection_workflow 表迁移完成")


if __name__ == "__main__":
    upgrade()
