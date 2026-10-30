"""add stock_margin_daily (融资融券个股日明细)

Revision ID: 0003_stock_margin_daily
Revises: 0002_em_fund_flow_daily
Create Date: 2026-10-30

Tushare margin_detail / AkShare 沪深交易所明细旁路表。
金额统一为元；PK (code, trade_date)。

幂等：upgrade 使用 IF NOT EXISTS。
注意：revision id 须 <= 32 字符（alembic_version.version_num）。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_stock_margin_daily"
down_revision: Union[str, None] = "0002_em_fund_flow_daily"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS stock_margin_daily (
                code TEXT NOT NULL,
                trade_date VARCHAR(10) NOT NULL,
                name VARCHAR(64),
                rzye DOUBLE PRECISION,
                rzmre DOUBLE PRECISION,
                rzche DOUBLE PRECISION,
                rqye DOUBLE PRECISION,
                rqyl DOUBLE PRECISION,
                rqmcl DOUBLE PRECISION,
                rqchl DOUBLE PRECISION,
                rzrqye DOUBLE PRECISION,
                source VARCHAR(32) NOT NULL DEFAULT 'tushare',
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
            CREATE INDEX IF NOT EXISTS idx_stock_margin_daily_trade_date
            ON stock_margin_daily (trade_date)
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS idx_stock_margin_daily_code_date
            ON stock_margin_daily (code, trade_date DESC)
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS idx_stock_margin_daily_code_date"))
    op.execute(sa.text("DROP INDEX IF EXISTS idx_stock_margin_daily_trade_date"))
    op.execute(sa.text("DROP TABLE IF EXISTS stock_margin_daily"))
