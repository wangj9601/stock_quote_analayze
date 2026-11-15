"""RPE 信号按概念板块落库：唯一键加入 sector_id

Revision ID: 0006_rpe_concept_trace
Revises: 0005_cupb_signal_trace
Create Date: 2026-11-15

日终预计算以概念板块为处理单位，同一股票同一日可对应多个概念。
幂等：旧约束不存在则跳过删除；新约束已存在则跳过创建。
revision id 须 <= 32 字符。
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0006_rpe_concept_trace"
down_revision: Union[str, None] = "0005_cupb_signal_trace"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD = "uq_rpe_signal_trace_code_date_mkt_cfg"
_NEW = "uq_rpe_signal_trace_code_date_mkt_cfg_sector"


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE rpe_signal_trace DROP CONSTRAINT IF EXISTS {_OLD}"
    )
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = '{_NEW}'
            ) THEN
                ALTER TABLE rpe_signal_trace
                ADD CONSTRAINT {_NEW}
                UNIQUE (code, trade_date, market_type, config_id, sector_id);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # 同一股票多个概念行无法回到旧唯一键，降级时保留 id 最小的一行。
    op.execute(
        """
        DELETE FROM rpe_signal_trace a
        USING rpe_signal_trace b
        WHERE a.id > b.id
          AND a.code = b.code
          AND a.trade_date = b.trade_date
          AND a.market_type = b.market_type
          AND a.config_id = b.config_id
        """
    )
    op.execute(
        f"ALTER TABLE rpe_signal_trace DROP CONSTRAINT IF EXISTS {_NEW}"
    )
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = '{_OLD}'
            ) THEN
                ALTER TABLE rpe_signal_trace
                ADD CONSTRAINT {_OLD}
                UNIQUE (code, trade_date, market_type, config_id);
            END IF;
        END $$;
        """
    )
