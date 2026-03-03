"""
数据库迁移脚本 - 添加发件邮箱配置表与邮件发送日志表
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from backend_core.database.db import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upgrade():
    """创建 email_sender_config 和 email_send_logs 表"""
    # 1. 创建 email_sender_config 表（单行配置）
    logger.info("创建 email_sender_config 表...")
    create_email_sender_config = text("""
        CREATE TABLE IF NOT EXISTS email_sender_config (
            id INTEGER PRIMARY KEY DEFAULT 1,
            host VARCHAR(255) NOT NULL DEFAULT 'smtp.example.com',
            port INTEGER NOT NULL DEFAULT 587,
            username VARCHAR(255) NOT NULL DEFAULT '',
            password VARCHAR(500),
            from_email VARCHAR(255) NOT NULL DEFAULT '',
            from_name VARCHAR(100) NOT NULL DEFAULT '股票分析系统',
            use_tls BOOLEAN NOT NULL DEFAULT TRUE,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    with engine.connect() as conn:
        conn.execute(create_email_sender_config)
        conn.execute(text("""
            INSERT INTO email_sender_config (id, host, port, username, from_email, from_name, use_tls)
            VALUES (1, 'smtp.example.com', 587, '', '', '股票分析系统', TRUE)
            ON CONFLICT (id) DO NOTHING
        """))
        conn.commit()
        logger.info("✅ email_sender_config 表创建成功")

    # 2. 创建 email_send_logs 表
    logger.info("创建 email_send_logs 表...")
    create_email_send_logs = text("""
        CREATE TABLE IF NOT EXISTS email_send_logs (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            to_email VARCHAR(255) NOT NULL,
            subject VARCHAR(500) NOT NULL,
            report_type VARCHAR(20) NOT NULL,
            push_record_id INTEGER REFERENCES push_records(id) ON DELETE SET NULL,
            sent_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            success BOOLEAN NOT NULL,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    with engine.connect() as conn:
        conn.execute(create_email_send_logs)
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_email_send_logs_user_id ON email_send_logs(user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_email_send_logs_sent_at ON email_send_logs(sent_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_email_send_logs_success ON email_send_logs(success)"))
        conn.commit()
        logger.info("✅ email_send_logs 表创建成功")


def downgrade():
    """删除表"""
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS email_send_logs CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS email_sender_config CASCADE"))
        conn.commit()
        logger.info("✅ 已删除 email_send_logs 和 email_sender_config 表")


if __name__ == "__main__":
    upgrade()
