"""
迁移：stock_adj_factor 主键改为 (code, trade_date, source)，
使新浪与 BaoStock 因子可并存；清理无效日期 1900-01-01。

用法:
    python migrations/alter_stock_adj_factor_pk_add_source.py
"""

from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from backend_api.database import SessionLocal

logger = logging.getLogger(__name__)


def run() -> None:
    db = SessionLocal()
    try:
        # 确保表存在（兼容尚未跑过建表迁移的环境）
        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS stock_adj_factor (
                    code VARCHAR(32) NOT NULL,
                    trade_date DATE NOT NULL,
                    adj_factor DOUBLE PRECISION NOT NULL,
                    source VARCHAR(64) NOT NULL DEFAULT 'akshare_sina_qfq',
                    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (code, trade_date, source)
                )
                """
            )
        )

        # 存量：source 空值填默认，避免 NOT NULL / 主键失败
        db.execute(
            text(
                """
                UPDATE stock_adj_factor
                SET source = 'akshare_sina_qfq'
                WHERE source IS NULL OR TRIM(source) = ''
                """
            )
        )
        # 丢弃新浪占位无效日
        db.execute(
            text(
                """
                DELETE FROM stock_adj_factor
                WHERE trade_date <= DATE '1900-01-01'
                """
            )
        )

        # 若仍是旧主键 (code, trade_date)，改为含 source
        pk_cols = db.execute(
            text(
                """
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a
                  ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = 'public.stock_adj_factor'::regclass
                  AND i.indisprimary
                ORDER BY array_position(i.indkey, a.attnum)
                """
            )
        ).fetchall()
        pk_names = [str(r[0]) for r in pk_cols]

        if pk_names != ["code", "trade_date", "source"]:
            db.execute(
                text(
                    """
                    ALTER TABLE stock_adj_factor
                    ALTER COLUMN source SET NOT NULL
                    """
                )
            )
            db.execute(
                text(
                    """
                    ALTER TABLE stock_adj_factor
                    ALTER COLUMN source SET DEFAULT 'akshare_sina_qfq'
                    """
                )
            )
            # 旧主键下同 code+date 仅一行，可直接换主键
            db.execute(
                text(
                    """
                    ALTER TABLE stock_adj_factor
                    DROP CONSTRAINT IF EXISTS stock_adj_factor_pkey
                    """
                )
            )
            db.execute(
                text(
                    """
                    ALTER TABLE stock_adj_factor
                    ADD CONSTRAINT stock_adj_factor_pkey
                    PRIMARY KEY (code, trade_date, source)
                    """
                )
            )
            logger.info(
                "已将主键由 %s 调整为 (code, trade_date, source)",
                pk_names or "(无)",
            )
        else:
            logger.info("主键已是 (code, trade_date, source)，跳过变更")

        db.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_stock_adj_factor_trade_date
                ON stock_adj_factor (trade_date)
                """
            )
        )
        db.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_stock_adj_factor_code_source
                ON stock_adj_factor (code, source)
                """
            )
        )
        db.commit()
        logger.info("stock_adj_factor 主键迁移完成")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
