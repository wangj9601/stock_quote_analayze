"""cupb_strategy_configs / cupb_signal_trace + 收盘流程节点

Revision ID: 0005_cupb_signal_trace
Revises: 0004_sepa_signal_trace
Create Date: 2026-11-14

杯底 CUPB 日终预计算与选股读库。幂等：IF NOT EXISTS；工作流节点已存在则跳过。
revision id 须 <= 32 字符。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_cupb_signal_trace"
down_revision: Union[str, None] = "0004_sepa_signal_trace"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

WF_NAME = "A股收盘后标准流程"
NODE_KEY = "cupb_signals_cn"
DISPLAY_NAME = "CUPB杯底信号预计算(A股)"
AFTER_NODE = "sepa_signals_cn"


def _insert_workflow_node(conn) -> None:
    wf = conn.execute(
        sa.text("SELECT id FROM collection_workflows WHERE name = :name LIMIT 1"),
        {"name": WF_NAME},
    ).fetchone()
    if not wf:
        return
    wf_id = int(wf[0])
    exists = conn.execute(
        sa.text(
            """
            SELECT id FROM collection_workflow_nodes
            WHERE workflow_id = :wid AND node_key = :nk
            LIMIT 1
            """
        ),
        {"wid": wf_id, "nk": NODE_KEY},
    ).fetchone()
    if exists:
        conn.execute(
            sa.text(
                """
                UPDATE collection_workflow_nodes
                SET display_name = :dn
                WHERE workflow_id = :wid AND node_key = :nk
                  AND (display_name IS DISTINCT FROM :dn)
                """
            ),
            {"dn": DISPLAY_NAME, "wid": wf_id, "nk": NODE_KEY},
        )
        return

    after = conn.execute(
        sa.text(
            """
            SELECT order_index FROM collection_workflow_nodes
            WHERE workflow_id = :wid AND node_key = :nk
            LIMIT 1
            """
        ),
        {"wid": wf_id, "nk": AFTER_NODE},
    ).fetchone()
    if after:
        target_order = int(after[0]) + 1
    else:
        mx = conn.execute(
            sa.text(
                """
                SELECT COALESCE(MAX(order_index), -1)
                FROM collection_workflow_nodes
                WHERE workflow_id = :wid
                """
            ),
            {"wid": wf_id},
        ).scalar()
        target_order = int(mx) + 1

    conn.execute(
        sa.text(
            """
            UPDATE collection_workflow_nodes
            SET order_index = order_index + 1000
            WHERE workflow_id = :wid AND order_index >= :ord
            """
        ),
        {"wid": wf_id, "ord": target_order},
    )
    conn.execute(
        sa.text(
            """
            UPDATE collection_workflow_nodes
            SET order_index = order_index - 999
            WHERE workflow_id = :wid AND order_index >= :ord_hi
            """
        ),
        {"wid": wf_id, "ord_hi": target_order + 1000},
    )
    conn.execute(
        sa.text(
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
            "nk": NODE_KEY,
            "dn": DISPLAY_NAME,
        },
    )


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS cupb_strategy_configs (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                description TEXT,
                config_params JSONB NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                is_default BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS ix_cupb_strategy_configs_is_default
            ON cupb_strategy_configs (is_default)
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS ix_cupb_strategy_configs_is_active
            ON cupb_strategy_configs (is_active)
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS cupb_signal_trace (
                id SERIAL PRIMARY KEY,
                code VARCHAR(20) NOT NULL,
                trade_date DATE NOT NULL,
                config_id INTEGER NOT NULL REFERENCES cupb_strategy_configs(id) ON DELETE CASCADE,
                name VARCHAR(200),
                status VARCHAR(20),
                left_rim_date VARCHAR(10),
                cup_bottom_date VARCHAR(10),
                right_rim_date VARCHAR(10),
                handle_low_date VARCHAR(10),
                left_rim_price DOUBLE PRECISION,
                cup_bottom_price DOUBLE PRECISION,
                right_rim_price DOUBLE PRECISION,
                handle_low_price DOUBLE PRECISION,
                rim DOUBLE PRECISION,
                last_close DOUBLE PRECISION,
                confirm_date VARCHAR(10),
                cup_depth_pct DOUBLE PRECISION,
                handle_retrace_pct DOUBLE PRECISION,
                board_labels VARCHAR(500),
                detail JSONB,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                CONSTRAINT uq_cupb_signal_trace_code_date_cfg UNIQUE (code, trade_date, config_id)
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS ix_cupb_signal_trace_date_cfg
            ON cupb_signal_trace (trade_date, config_id)
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS ix_cupb_signal_trace_status
            ON cupb_signal_trace (status)
            """
        )
    )
    # 种子默认配置（若尚无 is_default 行）
    op.execute(
        sa.text(
            """
            INSERT INTO cupb_strategy_configs
                (name, description, config_params, is_active, is_default)
            SELECT
                'default',
                '杯底形态策略默认参数',
                '{}'::jsonb,
                TRUE,
                TRUE
            WHERE NOT EXISTS (
                SELECT 1 FROM cupb_strategy_configs WHERE is_default = TRUE
            )
            """
        )
    )
    conn = op.get_bind()
    _insert_workflow_node(conn)


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            DELETE FROM collection_workflow_nodes
            WHERE node_key = :nk
              AND workflow_id IN (
                  SELECT id FROM collection_workflows WHERE name = :name
              )
            """
        ),
        {"nk": NODE_KEY, "name": WF_NAME},
    )
    op.execute(sa.text("DROP TABLE IF EXISTS cupb_signal_trace CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS cupb_strategy_configs CASCADE"))
