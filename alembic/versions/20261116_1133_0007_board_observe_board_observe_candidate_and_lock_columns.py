"""行业观察池候选日表 + observe_lock 列

Revision ID: 0007_board_observe
Revises: 0006_rpe_concept_trace
Create Date: 2026-11-16

请求路径不再执行 ALTER TABLE。列与候选表只在本 revision 落地。
幂等：表/列/索引已存在则跳过。目标表不存在时跳过加列。
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0007_board_observe"
down_revision: Union[str, None] = "0006_rpe_concept_trace"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS board_observe_candidate_daily (
            board_code VARCHAR(32) NOT NULL,
            board_code_source VARCHAR(32) NOT NULL DEFAULT 'tonghuashun',
            trade_date DATE NOT NULL,
            board_name VARCHAR(100),
            trade_observe_flag BOOLEAN NOT NULL DEFAULT FALSE,
            observe_lock VARCHAR(16) NOT NULL DEFAULT 'follow',
            action VARCHAR(16) NOT NULL,
            score INTEGER NOT NULL DEFAULT 0,
            sticky_count INTEGER NOT NULL DEFAULT 0,
            adoptable BOOLEAN NOT NULL DEFAULT FALSE,
            rank_in INTEGER,
            evidence_json JSONB,
            veto_json JSONB,
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            PRIMARY KEY (board_code, board_code_source, trade_date)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_board_observe_candidate_date_action
        ON board_observe_candidate_daily (trade_date DESC, action)
        """
    )
    for table, column_sql in (
        (
            "industry_board_basic_info",
            "observe_lock VARCHAR(16) NOT NULL DEFAULT 'follow'",
        ),
        (
            "industry_board_basic_info",
            "observe_source VARCHAR(32) NOT NULL DEFAULT 'manual'",
        ),
        (
            "industry_board_basic_info",
            "observe_updated_at TIMESTAMP WITHOUT TIME ZONE",
        ),
        (
            "industry_board_basic_info",
            "observe_updated_by VARCHAR(64)",
        ),
        (
            "concept_board_basic_info",
            "observe_lock VARCHAR(16) NOT NULL DEFAULT 'follow'",
        ),
        (
            "index_board_basic_info",
            "observe_lock VARCHAR(16) NOT NULL DEFAULT 'follow'",
        ),
    ):
        op.execute(
            f"""
            DO $$
            BEGIN
                IF to_regclass('public.{table}') IS NOT NULL THEN
                    ALTER TABLE {table}
                    ADD COLUMN IF NOT EXISTS {column_sql};
                END IF;
            END $$;
            """
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_board_observe_candidate_date_action")
    op.execute("DROP TABLE IF EXISTS board_observe_candidate_daily")
    for table, column in (
        ("industry_board_basic_info", "observe_updated_by"),
        ("industry_board_basic_info", "observe_updated_at"),
        ("industry_board_basic_info", "observe_source"),
        ("industry_board_basic_info", "observe_lock"),
        ("concept_board_basic_info", "observe_lock"),
        ("index_board_basic_info", "observe_lock"),
    ):
        op.execute(
            f"""
            DO $$
            BEGIN
                IF to_regclass('public.{table}') IS NOT NULL THEN
                    ALTER TABLE {table} DROP COLUMN IF EXISTS {column};
                END IF;
            END $$;
            """
        )
