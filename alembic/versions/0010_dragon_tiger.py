"""龙虎榜落库表 dragon_tiger_*

Revision ID: 0010_dragon_tiger
Revises: 0009_env_sync_jobs
Create Date: 2026-11-21

对应手写脚本 migrations/add_dragon_tiger_tables.py。
幂等：表/索引已存在则跳过。
金额单位：元；org_net_value / hot_money_net_value 仅同花顺有值。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010_dragon_tiger"
down_revision: Union[str, None] = "0009_env_sync_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS dragon_tiger_snapshot (
                trade_date VARCHAR(10) NOT NULL,
                board_type VARCHAR(16) NOT NULL,
                source VARCHAR(20) NOT NULL,
                source_label TEXT,
                stock_count INTEGER,
                item_count INTEGER,
                amount_unit VARCHAR(16) NOT NULL DEFAULT 'yuan',
                fallback_reason TEXT,
                board_type_note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (trade_date, board_type)
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS dragon_tiger_stock (
                trade_date VARCHAR(10) NOT NULL,
                board_type VARCHAR(16) NOT NULL,
                seq INTEGER NOT NULL,
                code VARCHAR(10) NOT NULL,
                name TEXT,
                change_percent DOUBLE PRECISION,
                close DOUBLE PRECISION,
                buy_value DOUBLE PRECISION,
                sell_value DOUBLE PRECISION,
                net_value DOUBLE PRECISION,
                net_rate DOUBLE PRECISION,
                org_net_value DOUBLE PRECISION,
                hot_money_net_value DOUBLE PRECISION,
                deal_value DOUBLE PRECISION,
                market_turnover DOUBLE PRECISION,
                turnover_rate DOUBLE PRECISION,
                reason TEXT,
                interpretation TEXT,
                range_days INTEGER,
                hot_rank INTEGER,
                concepts TEXT,
                after_1d DOUBLE PRECISION,
                after_2d DOUBLE PRECISION,
                after_5d DOUBLE PRECISION,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (trade_date, board_type, seq),
                FOREIGN KEY (trade_date, board_type)
                    REFERENCES dragon_tiger_snapshot (trade_date, board_type)
                    ON DELETE CASCADE
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS idx_dragon_tiger_stock_code_date
            ON dragon_tiger_stock (code, trade_date)
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS dragon_tiger_hot_money (
                trade_date VARCHAR(10) NOT NULL,
                board_type VARCHAR(16) NOT NULL,
                seq INTEGER NOT NULL,
                seat_name TEXT NOT NULL,
                buy_value DOUBLE PRECISION,
                sell_value DOUBLE PRECISION,
                net_value DOUBLE PRECISION,
                stocks JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (trade_date, board_type, seq),
                FOREIGN KEY (trade_date, board_type)
                    REFERENCES dragon_tiger_snapshot (trade_date, board_type)
                    ON DELETE CASCADE
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            COMMENT ON COLUMN dragon_tiger_stock.org_net_value IS
            '机构净额，单位元；仅同花顺有值，东方财富为 NULL。展示时除以 1e8 为亿'
            """
        )
    )
    op.execute(
        sa.text(
            """
            COMMENT ON COLUMN dragon_tiger_stock.hot_money_net_value IS
            '游资净额，单位元；仅同花顺有值，东方财富为 NULL。展示时除以 1e8 为亿'
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS dragon_tiger_hot_money"))
    op.execute(sa.text("DROP TABLE IF EXISTS dragon_tiger_stock"))
    op.execute(sa.text("DROP TABLE IF EXISTS dragon_tiger_snapshot"))
