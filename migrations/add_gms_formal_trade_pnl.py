"""
迁移：gms_formal_trades 增加盈亏金额/盈亏比例字段（平仓时写入）
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from backend_core.database.db import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# A 股 / 港股默认 1 手 = 100 股（与系统行情「手」约定一致）
LOT_SIZE = 100


def upgrade():
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                ALTER TABLE gms_formal_trades
                ADD COLUMN IF NOT EXISTS pnl_amount DOUBLE PRECISION
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE gms_formal_trades
                ADD COLUMN IF NOT EXISTS pnl_percent DOUBLE PRECISION
                """
            )
        )
        # 回填已有已平仓记录（PostgreSQL ROUND 两参数仅支持 numeric，需先转型）
        conn.execute(
            text(
                f"""
                UPDATE gms_formal_trades
                SET pnl_percent = ROUND(
                        CAST(
                            ((exit_price - entry_price) / NULLIF(entry_price, 0)) * 100.0
                            AS numeric
                        ),
                        2
                    )::double precision,
                    pnl_amount = ROUND(
                        CAST(
                            (exit_price - entry_price) * COALESCE(position_lots, 0) * {LOT_SIZE}
                            AS numeric
                        ),
                        2
                    )::double precision
                WHERE status = 'closed'
                  AND exit_price IS NOT NULL
                  AND entry_price IS NOT NULL
                  AND entry_price > 0
                  AND (pnl_amount IS NULL OR pnl_percent IS NULL)
                """
            )
        )
        conn.commit()
    logger.info("gms_formal_trades pnl_amount/pnl_percent 迁移完成")


if __name__ == "__main__":
    upgrade()
