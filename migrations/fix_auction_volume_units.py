"""
修复集合竞价量单位：历史数据曾把 Fuyao「手」误当「股」再 ÷100。

正确口径：
- auction_volume / auction_unmatched = 手
- auction_volume_shares / auction_unmatched_shares = 股（手 × 100）

历史错误特征（用成交额交叉验证）：
- amount ≈ price × volume_shares × 100   （volume_shares 实际存的是手数）
正确数据特征：
- amount ≈ price × volume_shares         （volume_shares 才是股数）

本脚本仅在「错误特征」命中时校正，可重复执行。
"""

from __future__ import annotations

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
        result = conn.execute(
            text(
                """
                UPDATE stock_auction_daily
                SET
                    auction_volume = auction_volume_shares,
                    auction_volume_shares = auction_volume_shares * 100,
                    auction_unmatched = CASE
                        WHEN auction_unmatched_shares IS NOT NULL THEN auction_unmatched_shares
                        WHEN auction_unmatched IS NOT NULL THEN auction_unmatched * 100
                        ELSE NULL
                    END,
                    auction_unmatched_shares = CASE
                        WHEN auction_unmatched_shares IS NOT NULL THEN auction_unmatched_shares * 100
                        WHEN auction_unmatched IS NOT NULL THEN auction_unmatched * 10000
                        ELSE NULL
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE auction_volume_shares IS NOT NULL
                  AND auction_price IS NOT NULL
                  AND auction_amount IS NOT NULL
                  AND auction_price > 0
                  AND auction_volume_shares > 0
                  AND auction_amount > 0
                  -- 错误态：amount ≈ price × shares × 100
                  AND ABS(
                      auction_amount
                      / NULLIF(auction_price * auction_volume_shares * 100, 0)
                      - 1
                  ) < 0.15
                  -- 排除已正确：amount ≈ price × shares
                  AND ABS(
                      auction_amount
                      / NULLIF(auction_price * auction_volume_shares, 0)
                      - 1
                  ) > 0.5
                """
            )
        )
        logger.info("stock_auction_daily 竞价量单位校正完成，更新行数=%s", result.rowcount)


if __name__ == "__main__":
    upgrade()
