"""add stock_fund_flow_em_daily (East Money fund-flow tiers)

Revision ID: 0002_em_fund_flow_daily
Revises: 0001_baseline
Create Date: 2026-10-07

东财个股主力/超大/大/中/小单日序列旁路表。
与同花顺 stock_fund_flow_daily（流入/流出/净额）分表、分口径。

幂等：upgrade 使用 IF NOT EXISTS，已用手写 migrations/add_stock_fund_flow_em_daily.py
建过表的环境可安全 upgrade。

注意：revision id 须 <= 32 字符（alembic_version.version_num）。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_em_fund_flow_daily"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS stock_fund_flow_em_daily (
                code TEXT NOT NULL,
                trade_date VARCHAR(10) NOT NULL,
                main_net_inflow DOUBLE PRECISION,
                main_net_inflow_pct DOUBLE PRECISION,
                super_large_net_inflow DOUBLE PRECISION,
                super_large_net_inflow_pct DOUBLE PRECISION,
                large_net_inflow DOUBLE PRECISION,
                large_net_inflow_pct DOUBLE PRECISION,
                mid_net_inflow DOUBLE PRECISION,
                mid_net_inflow_pct DOUBLE PRECISION,
                small_net_inflow DOUBLE PRECISION,
                small_net_inflow_pct DOUBLE PRECISION,
                close_price DOUBLE PRECISION,
                change_percent DOUBLE PRECISION,
                source VARCHAR(20) NOT NULL DEFAULT 'em',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (code, trade_date)
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS idx_stock_fund_flow_em_daily_trade_date
            ON stock_fund_flow_em_daily (trade_date)
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS idx_stock_fund_flow_em_daily_code_date
            ON stock_fund_flow_em_daily (code, trade_date DESC)
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("DROP INDEX IF EXISTS idx_stock_fund_flow_em_daily_code_date")
    )
    op.execute(
        sa.text("DROP INDEX IF EXISTS idx_stock_fund_flow_em_daily_trade_date")
    )
    op.execute(sa.text("DROP TABLE IF EXISTS stock_fund_flow_em_daily"))
