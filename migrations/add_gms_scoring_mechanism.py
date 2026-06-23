"""
迁移：GMS 打分机制字段 + ma60_d + 策略版本 config 绑定补全
"""

import copy
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from backend_core.database.db import engine
from backend_core.strategies.gms.config import GMSConfigManager
from backend_core.strategies.gms.scoring import normalize_scoring_defaults

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _table_exists(conn, table: str) -> bool:
    r = conn.execute(
        text("SELECT to_regclass(:t)"),
        {"t": table},
    ).scalar()
    return r is not None


def _column_exists(conn, table: str, column: str) -> bool:
    r = conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = :table AND column_name = :column
            """
        ),
        {"table": table, "column": column},
    ).first()
    return r is not None


def upgrade():
    mgr = GMSConfigManager()
    with engine.connect() as conn:
        if _table_exists(conn, "mean_frequency_resonance_indicators") and not _column_exists(
            conn, "mean_frequency_resonance_indicators", "ma60_d"
        ):
            conn.execute(
                text("ALTER TABLE mean_frequency_resonance_indicators ADD COLUMN ma60_d DOUBLE PRECISION")
            )
            logger.info("mean_frequency_resonance_indicators.ma60_d 已添加")
        conn.commit()

    # 补全 gms_strategy_configs.scoring.mechanism
    from backend_api.models import GMSStrategyConfig
    from backend_api.database import SessionLocal

    db = SessionLocal()
    try:
        rows = db.query(GMSStrategyConfig).all()
        for row in rows:
            params = copy.deepcopy(row.config_params or {})
            scoring = normalize_scoring_defaults(params.get("scoring") or {})
            params["scoring"] = scoring
            row.config_params = params
        db.commit()
        logger.info("已更新 %s 条 gms_strategy_configs 的 scoring.mechanism", len(rows))

        with engine.connect() as conn:
            has_versions_table = _table_exists(conn, "gms_strategy_versions")
        if has_versions_table:
            from backend_api.models import GMSStrategyVersion

            versions = db.query(GMSStrategyVersion).all()
            used_configs = {}
            for v in versions:
                if v.config_id:
                    used_configs.setdefault(int(v.config_id), []).append(v.id)
            for v in versions:
                if v.config_id:
                    continue
                name = f"auto_{v.strategy_code}_v{v.version_no}".lower()[:90]
                new_id = mgr.create_config(
                    name=name,
                    config_params=mgr.get_default_config(),
                    description=f"迁移自动创建：{v.version_name}",
                    is_active=True,
                    precompute_enabled=False,
                    created_by="migration",
                )
                v.config_id = new_id
                logger.info("策略版本 %s 绑定新 config_id=%s", v.id, new_id)
            for cid, vids in used_configs.items():
                if len(vids) > 1:
                    for vid in vids[1:]:
                        v = db.query(GMSStrategyVersion).filter(GMSStrategyVersion.id == vid).first()
                        if not v:
                            continue
                        name = f"auto_{v.strategy_code}_v{v.version_no}_clone".lower()[:90]
                        new_id = mgr.clone_config(int(cid), name, created_by="migration")
                        v.config_id = new_id
                        logger.info("策略版本 %s 克隆专用 config_id=%s", vid, new_id)
            db.commit()
    finally:
        db.close()

    logger.info("GMS 打分机制迁移完成")


if __name__ == "__main__":
    upgrade()
