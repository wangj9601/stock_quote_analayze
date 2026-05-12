"""
迁移：3倍量观察股表 + user_push_configs 企业微信接收人覆盖列 + report_type 字段加长
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from backend_core.database.db import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upgrade():
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS triple_volume_observe_stocks (
                    id SERIAL PRIMARY KEY,
                    market VARCHAR(10) NOT NULL,
                    code VARCHAR(20) NOT NULL,
                    name VARCHAR(200),
                    observe_trade_date DATE NOT NULL,
                    prev_trade_date DATE,
                    prev_volume DOUBLE PRECISION,
                    curr_volume DOUBLE PRECISION,
                    volume_ratio_actual DOUBLE PRECISION,
                    status VARCHAR(20) NOT NULL DEFAULT '待观察',
                    vsb_evaluated_at TIMESTAMP,
                    vsb_detail_json JSONB,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_tvo_code_market_obdate UNIQUE (market, code, observe_trade_date)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_tvo_status ON triple_volume_observe_stocks (status)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_tvo_obdate ON triple_volume_observe_stocks (observe_trade_date DESC)
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE user_push_configs
                ADD COLUMN IF NOT EXISTS wechat_notify_userids JSON
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE user_push_configs
                ALTER COLUMN report_type TYPE VARCHAR(64)
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE push_records
                ALTER COLUMN report_type TYPE VARCHAR(64)
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE email_send_logs
                ALTER COLUMN report_type TYPE VARCHAR(64)
                """
            )
        )
        conn.commit()
    logger.info("triple_volume_observe + user_push_configs.wechat_notify_userids + varchar(64) 迁移完成")


def downgrade():
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS triple_volume_observe_stocks CASCADE"))
        conn.execute(
            text(
                """
                ALTER TABLE user_push_configs DROP COLUMN IF EXISTS wechat_notify_userids
                """
            )
        )
        conn.commit()
    logger.info("已回滚 triple_volume_observe 表（未回滚 report_type 长度以防数据截断）")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        downgrade()
    else:
        upgrade()
