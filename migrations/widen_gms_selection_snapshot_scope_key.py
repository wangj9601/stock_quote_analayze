"""
迁移：扩大 gms_selection_snapshots.scope_key 长度（多选概念/行业板块时原 VARCHAR(120) 不足）
"""

import logging

from sqlalchemy import text

from backend_api.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                ALTER TABLE gms_selection_snapshots
                ALTER COLUMN scope_key TYPE VARCHAR(256)
                """
            )
        )
        conn.commit()
    logger.info("gms_selection_snapshots.scope_key 已扩至 VARCHAR(256)")


if __name__ == "__main__":
    run_migration()
