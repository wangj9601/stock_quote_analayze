"""
迁移：GMS 策略参数多版本
- 新建 gms_strategy_configs
- gms_runtime_config.default 导入为默认版本
- gms_signal_trace 增加 config_id 并重建主键
- gms_strategy_versions 增加可选 config_id
"""

import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from backend_core.database.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _table_exists(conn, name: str) -> bool:
    row = conn.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = :t LIMIT 1"
        ),
        {"t": name},
    ).fetchone()
    return row is not None


def _column_exists(conn, table: str, column: str) -> bool:
    row = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c LIMIT 1"
        ),
        {"t": table, "c": column},
    ).fetchone()
    return row is not None


def upgrade():
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS gms_strategy_configs (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL UNIQUE,
                    version_label VARCHAR(32),
                    description TEXT,
                    config_params JSONB NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    is_default BOOLEAN NOT NULL DEFAULT FALSE,
                    precompute_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    parent_id INTEGER REFERENCES gms_strategy_configs(id) ON DELETE SET NULL,
                    created_by VARCHAR(50),
                    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_gms_strategy_configs_is_default "
                "ON gms_strategy_configs (is_default)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_gms_strategy_configs_precompute "
                "ON gms_strategy_configs (precompute_enabled)"
            )
        )

        default_id = conn.execute(
            text("SELECT id FROM gms_strategy_configs WHERE is_default = TRUE LIMIT 1")
        ).scalar()

        if default_id is None:
            runtime_row = None
            if _table_exists(conn, "gms_runtime_config"):
                runtime_row = conn.execute(
                    text(
                        "SELECT config_params FROM gms_runtime_config "
                        "WHERE name = 'default' LIMIT 1"
                    )
                ).fetchone()

            if runtime_row and runtime_row[0] is not None:
                params = runtime_row[0]
                if isinstance(params, str):
                    params = json.loads(params)
            else:
                from backend_core.strategies.gms.config import GMSConfigManager

                params = GMSConfigManager().get_default_config()

            conn.execute(
                text(
                    """
                    INSERT INTO gms_strategy_configs (
                        name, version_label, description, config_params,
                        is_active, is_default, precompute_enabled, created_by
                    ) VALUES (
                        'default', '1.0.0', '从 gms_runtime_config 迁移的默认版本',
                        CAST(:params AS JSONB), TRUE, TRUE, TRUE, 'migration'
                    )
                    ON CONFLICT (name) DO NOTHING
                    """
                ),
                {"params": json.dumps(params, ensure_ascii=False)},
            )
            default_id = conn.execute(
                text("SELECT id FROM gms_strategy_configs WHERE name = 'default' LIMIT 1")
            ).scalar()
            if default_id is None:
                default_id = conn.execute(
                    text("SELECT id FROM gms_strategy_configs ORDER BY id LIMIT 1")
                ).scalar()
            logger.info("已创建默认 GMS 策略配置 id=%s", default_id)

        if default_id is None:
            raise RuntimeError("无法确定默认 gms_strategy_configs.id")

        if _table_exists(conn, "gms_signal_trace") and not _column_exists(
            conn, "gms_signal_trace", "config_id"
        ):
            conn.execute(
                text(
                    f"ALTER TABLE gms_signal_trace "
                    f"ADD COLUMN config_id INTEGER NOT NULL DEFAULT {int(default_id)}"
                )
            )
            conn.execute(
                text(
                    f"UPDATE gms_signal_trace SET config_id = {int(default_id)} "
                    f"WHERE config_id IS NULL"
                )
            )
            conn.execute(
                text("ALTER TABLE gms_signal_trace DROP CONSTRAINT IF EXISTS gms_signal_trace_pkey")
            )
            conn.execute(
                text(
                    "ALTER TABLE gms_signal_trace "
                    "ADD PRIMARY KEY (code, date, market_type, config_id)"
                )
            )
            conn.execute(
                text(
                    f"ALTER TABLE gms_signal_trace "
                    f"ADD CONSTRAINT fk_gms_signal_trace_config "
                    f"FOREIGN KEY (config_id) REFERENCES gms_strategy_configs(id) ON DELETE CASCADE"
                )
            )
            logger.info("gms_signal_trace 已增加 config_id 主键维度")

        if _table_exists(conn, "gms_strategy_versions") and not _column_exists(
            conn, "gms_strategy_versions", "config_id"
        ):
            conn.execute(
                text(
                    "ALTER TABLE gms_strategy_versions "
                    "ADD COLUMN config_id INTEGER REFERENCES gms_strategy_configs(id) ON DELETE SET NULL"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_gms_strategy_versions_config_id "
                    "ON gms_strategy_versions (config_id)"
                )
            )
            logger.info("gms_strategy_versions 已增加 config_id")

        conn.commit()
    logger.info("GMS 策略参数多版本迁移完成")


if __name__ == "__main__":
    upgrade()
