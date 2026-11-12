"""add sepa_signal_scan / sepa_signal_trace

Revision ID: 0004_sepa_signal_trace
Revises: 0003_stock_margin_daily
Create Date: 2026-11-12

SEPA 买点日终预计算。scan 记当日覆盖与漏斗，trace 记形态行。
幂等：upgrade 使用 IF NOT EXISTS。
revision id 须 <= 32 字符。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_sepa_signal_trace"
down_revision: Union[str, None] = "0003_stock_margin_daily"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS sepa_signal_scan (
                id SERIAL PRIMARY KEY,
                trade_date DATE NOT NULL UNIQUE,
                universe INTEGER NOT NULL DEFAULT 0,
                hit_count INTEGER NOT NULL DEFAULT 0,
                funnel JSONB NOT NULL DEFAULT '{}'::jsonb,
                pool JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS idx_sepa_signal_scan_trade_date
            ON sepa_signal_scan (trade_date)
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS sepa_signal_trace (
                id SERIAL PRIMARY KEY,
                code VARCHAR(20) NOT NULL,
                trade_date DATE NOT NULL,
                name VARCHAR(200),
                tier VARCHAR(8),
                vcp_status VARCHAR(32) NOT NULL,
                score DOUBLE PRECISION,
                row_data JSONB NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                CONSTRAINT uq_sepa_signal_trace_code_date UNIQUE (code, trade_date)
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS idx_sepa_signal_trace_trade_date
            ON sepa_signal_trace (trade_date)
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS idx_sepa_signal_trace_date_status
            ON sepa_signal_trace (trade_date, vcp_status)
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS idx_sepa_signal_trace_date_status"))
    op.execute(sa.text("DROP INDEX IF EXISTS idx_sepa_signal_trace_trade_date"))
    op.execute(sa.text("DROP TABLE IF EXISTS sepa_signal_trace"))
    op.execute(sa.text("DROP INDEX IF EXISTS idx_sepa_signal_scan_trade_date"))
    op.execute(sa.text("DROP TABLE IF EXISTS sepa_signal_scan"))
