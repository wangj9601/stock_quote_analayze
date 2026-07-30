# -*- coding: utf-8 -*-
"""
迁移：为已有库补齐 urt_strategy_configs.precompute_enabled（幂等）。

背景：
  旧环境可能先建表、后加 ORM 字段；此前在请求路径里执行
  ALTER TABLE ... ADD COLUMN，易与 idle in transaction 互相锁死。
  请在低峰期单独跑本脚本，并停止或减少并发写后再执行。

用法:
  python migrations/add_urt_precompute_enabled_column.py

环境变量（可选）:
  MIGRATION_LOCK_TIMEOUT_MS  锁等待毫秒，默认 30000（30 秒，拿不到锁则失败而不是无限堵）
"""

from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from backend_api.config import DATABASE_CONFIG

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

LOCK_TIMEOUT_MS = int(os.environ.get("MIGRATION_LOCK_TIMEOUT_MS", "30000"))


def _engine():
    return create_engine(
        DATABASE_CONFIG["url"],
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
        connect_args={
            "connect_timeout": 15,
            "options": f"-c lock_timeout={LOCK_TIMEOUT_MS} -c statement_timeout=120000",
        },
    )


def column_exists(conn, table: str, column: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :t
              AND column_name = :c
            """
        ),
        {"t": table, "c": column},
    ).first()
    return row is not None


def upgrade() -> None:
    eng = _engine()
    with eng.begin() as conn:
        # 表不存在时交给 add_urt_core_tables.py 建全表（含该列）
        has_table = conn.execute(
            text(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'urt_strategy_configs'
                """
            )
        ).first()
        if not has_table:
            logger.warning(
                "表 urt_strategy_configs 不存在，请先执行: python migrations/add_urt_core_tables.py"
            )
            return

        if column_exists(conn, "urt_strategy_configs", "precompute_enabled"):
            logger.info("列 precompute_enabled 已存在，跳过 ALTER")
        else:
            logger.info(
                "ADD COLUMN precompute_enabled（lock_timeout=%sms）...",
                LOCK_TIMEOUT_MS,
            )
            conn.execute(
                text(
                    """
                    ALTER TABLE urt_strategy_configs
                    ADD COLUMN precompute_enabled BOOLEAN NOT NULL DEFAULT FALSE
                    """
                )
            )
            logger.info("列 precompute_enabled 已添加")

        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_urt_strategy_configs_precompute_enabled
                ON urt_strategy_configs (precompute_enabled)
                """
            )
        )
        logger.info("索引 ix_urt_strategy_configs_precompute_enabled 已确保")


if __name__ == "__main__":
    try:
        upgrade()
        logger.info("完成")
    except Exception as e:
        logger.error("迁移失败: %s", e)
        logger.error(
            "若为锁超时：先 python migrations/diagnose_db_locks.py，"
            "结束 idle in transaction 后再重试；或短暂停止 backend。"
        )
        raise
