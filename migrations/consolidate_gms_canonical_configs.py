"""
迁移：GMS 参数版本收敛为 default + gms_penalty，停用历史 auto_gms_* 版本。

用法:
    python migrations/consolidate_gms_canonical_configs.py
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_api.database import SessionLocal
from backend_api.models import GMSStrategyVersion
from backend_core.strategies.gms.config import GMSConfigManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    mgr = GMSConfigManager()
    ids = mgr.ensure_canonical_configs()
    logger.info("共享参数版本: default=%s, gms_penalty=%s", ids["default"], ids["gms_penalty"])

    db = SessionLocal()
    try:
        for v in db.query(GMSStrategyVersion).all():
            mechanism = "tiered_dual_max"
            if v.config_id:
                try:
                    cfg = mgr.get_config(int(v.config_id))
                    mechanism = (cfg.get("scoring") or {}).get("mechanism") or mechanism
                except Exception:
                    pass
            new_id = mgr.resolve_canonical_config_id(mechanism)
            if v.config_id != new_id:
                logger.info("策略版本 %s config_id %s -> %s", v.id, v.config_id, new_id)
                v.config_id = new_id
        db.commit()
    finally:
        db.close()

    n = mgr.deactivate_non_canonical_configs()
    logger.info("已停用 %s 个历史冗余参数版本", n)
    logger.info("完成。选股页与管理端仅展示 default / gms_penalty。")


if __name__ == "__main__":
    main()
