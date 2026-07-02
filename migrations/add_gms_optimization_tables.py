"""
GMS 优化相关表与索引：预计算运行记录、筛选快照、任务运行、用户偏好、trace 索引与 risk_tags。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from sqlalchemy import text
from backend_core.database.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _table_exists(conn, name: str) -> bool:
    r = conn.execute(
        text("SELECT 1 FROM information_schema.tables WHERE table_name = :t"),
        {"t": name},
    ).scalar()
    return bool(r)


def _column_exists(conn, table: str, column: str) -> bool:
    r = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    ).scalar()
    return bool(r)


def upgrade():
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS gms_precompute_runs (
                    id SERIAL PRIMARY KEY,
                    config_id INTEGER NOT NULL,
                    market VARCHAR(10) NOT NULL,
                    trade_date VARCHAR(20) NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'running',
                    stock_count INTEGER NOT NULL DEFAULT 0,
                    duration_ms INTEGER,
                    error_message TEXT,
                    started_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                    finished_at TIMESTAMP WITHOUT TIME ZONE
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_gms_precompute_runs_cfg_date "
                "ON gms_precompute_runs (config_id, trade_date DESC)"
            )
        )

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS gms_selection_snapshots (
                    trade_date VARCHAR(20) NOT NULL,
                    config_id INTEGER NOT NULL,
                    scope_key VARCHAR(120) NOT NULL,
                    param_hash VARCHAR(64) NOT NULL,
                    result_json JSONB NOT NULL,
                    row_count INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (trade_date, config_id, scope_key, param_hash)
                )
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS gms_job_runs (
                    id SERIAL PRIMARY KEY,
                    job_type VARCHAR(40) NOT NULL,
                    status VARCHAR(20) NOT NULL,
                    config_id INTEGER,
                    trade_date VARCHAR(20),
                    message TEXT,
                    meta_json JSONB,
                    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_gms_job_runs_type_created "
                "ON gms_job_runs (job_type, created_at DESC)"
            )
        )

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS user_gms_preferences (
                    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    preferences_json JSONB NOT NULL DEFAULT '{}',
                    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
                )
                """
            )
        )

        if _table_exists(conn, "gms_signal_trace"):
            if not _column_exists(conn, "gms_signal_trace", "risk_tags"):
                conn.execute(text("ALTER TABLE gms_signal_trace ADD COLUMN risk_tags JSONB"))
                logger.info("gms_signal_trace.risk_tags 已添加")
            if not _column_exists(conn, "gms_signal_trace", "score_detail"):
                conn.execute(text("ALTER TABLE gms_signal_trace ADD COLUMN score_detail JSONB"))
                logger.info("gms_signal_trace.score_detail 已添加")
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_gms_signal_trace_date_config "
                    "ON gms_signal_trace (date, config_id)"
                )
            )

        if _table_exists(conn, "mean_frequency_resonance_indicators"):
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_mfr_date_code_market "
                    "ON mean_frequency_resonance_indicators (date, code, market_type)"
                )
            )

        conn.commit()
    logger.info("GMS 优化表与索引迁移完成")


if __name__ == "__main__":
    upgrade()
