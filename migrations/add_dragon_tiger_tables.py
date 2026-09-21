"""
迁移：龙虎榜落库。

- dragon_tiger_snapshot：某交易日、某榜别（all/org/hot_money）的一次快照
- dragon_tiger_stock：上榜个股；org_net_value / hot_money_net_value 仅同花顺有值（单位：元）
- dragon_tiger_hot_money：游资席位（东方财富无此数据）

同花顺快照优先：已有 source=fuyao 时，不再被东方财富空字段覆盖。
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from backend_core.database.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upgrade():
    with engine.begin() as conn:
        conn.execute(
            text(
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
        conn.execute(
            text(
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
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_dragon_tiger_stock_code_date
                ON dragon_tiger_stock (code, trade_date)
                """
            )
        )
        conn.execute(
            text(
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
        conn.execute(
            text(
                """
                COMMENT ON COLUMN dragon_tiger_stock.org_net_value IS
                '机构净额，单位元；仅同花顺有值，东方财富为 NULL。展示时除以 1e8 为亿'
                """
            )
        )
        conn.execute(
            text(
                """
                COMMENT ON COLUMN dragon_tiger_stock.hot_money_net_value IS
                '游资净额，单位元；仅同花顺有值，东方财富为 NULL。展示时除以 1e8 为亿'
                """
            )
        )
    logger.info("dragon_tiger_snapshot / stock / hot_money 表迁移完成")


if __name__ == "__main__":
    upgrade()
