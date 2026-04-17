"""
GMS 策略配置管理（PostgreSQL gms_runtime_config，兼容首次从 gms_config.json 引导）
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

_DEFAULT_ROW_NAME = "default"


class GMSConfigManager:
    """GMS 配置管理器"""

    def __init__(self, config_file: str = "gms_config.json"):
        self.config_file = config_file
        self.default_config_path = os.path.join(
            os.path.dirname(__file__),
            self.config_file,
        )
        self._config: Optional[Dict] = None

    def get_default_config(self) -> Dict:
        """获取默认策略参数"""
        return {
            "observation_period": 20,
            "ratio_indicators": {
                "use_ratio_d": True,
                "use_ratio_d_for_exit": False,
            },
            "left_buy": {
                "ratio_d20_abs_max": 0.015,  # |Δ/d₂₀| < 1.5%
                "volume_ratio_max": 0.8,  # m₂₀ < 0.8m
            },
            "right_buy": {
                "volume_ratio_min": 1.5,  # m₂₀ > 1.5m
            },
            "scoring": {
                "accumulation_fz_min": 1.5,  # F/Z > 1.5 → 蓄势 30
                "balance_ratio_max": 0.01,  # |Δ/d₂₀| < 1% → 平衡 40
                "momentum_volume_ratio_min": 1.5,  # Δ>0 且量比>1.5 → 动量 30
                "watch_threshold": 60,
                "alert_threshold": 90,
            },
            "exit": {
                "trend_break_days": 3,
                "overbought_ratio": 0.15,  # Δ/d₂₀ > 15%
            },
        }

    def _load_from_json_file(self) -> Optional[Dict]:
        try:
            if os.path.exists(self.default_config_path):
                with open(self.default_config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                default = self.get_default_config()
                return self._deep_merge(default, loaded)
        except Exception as e:
            logger.warning("读取本地 gms_config.json 失败: %s", e)
        return None

    def _persist_default_row(self, merged: Dict) -> None:
        from backend_api.database import SessionLocal
        from backend_api.models import GMSRuntimeConfig

        db = SessionLocal()
        try:
            row = db.query(GMSRuntimeConfig).filter(GMSRuntimeConfig.name == _DEFAULT_ROW_NAME).first()
            if row is None:
                db.add(
                    GMSRuntimeConfig(
                        name=_DEFAULT_ROW_NAME,
                        config_params=merged,
                        updated_at=datetime.now(),
                    )
                )
            else:
                row.config_params = merged
                row.updated_at = datetime.now()
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def load_config(self) -> Dict:
        """加载配置：优先数据库；无记录时合并默认与本地 json（若存在）并写入数据库。"""
        if self._config is not None:
            return self._config

        try:
            from backend_api.database import SessionLocal
            from backend_api.models import GMSRuntimeConfig

            db = SessionLocal()
            try:
                row = db.query(GMSRuntimeConfig).filter(GMSRuntimeConfig.name == _DEFAULT_ROW_NAME).first()
                if row and row.config_params is not None:
                    default = self.get_default_config()
                    self._config = self._deep_merge(default, dict(row.config_params))
                    return self._config
            finally:
                db.close()
        except Exception as e:
            logger.warning("从数据库加载 GMS 配置失败，尝试本地文件: %s", e)

        file_merged = self._load_from_json_file()
        if file_merged is not None:
            self._config = file_merged
            try:
                self._persist_default_row(file_merged)
            except Exception as e:
                logger.warning("将本地配置写入数据库失败（仍使用内存合并结果）: %s", e)
            return self._config

        self._config = self.get_default_config()
        try:
            self._persist_default_row(self._config)
        except Exception as e:
            logger.warning("写入默认 GMS 配置到数据库失败: %s", e)
        return self._config

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """深度合并字典"""
        result = base.copy()
        for k, v in override.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = self._deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    def get_config(self) -> Dict:
        """获取当前配置"""
        return self.load_config()

    def save_config(self, config: Dict) -> bool:
        """保存配置到数据库，并清除缓存。"""
        try:
            from backend_api.database import SessionLocal
            from backend_api.models import GMSRuntimeConfig

            db = SessionLocal()
            try:
                row = db.query(GMSRuntimeConfig).filter(GMSRuntimeConfig.name == _DEFAULT_ROW_NAME).first()
                if row is None:
                    db.add(
                        GMSRuntimeConfig(
                            name=_DEFAULT_ROW_NAME,
                            config_params=config,
                            updated_at=datetime.now(),
                        )
                    )
                else:
                    row.config_params = config
                    row.updated_at = datetime.now()
                db.commit()
                self._config = None
                return True
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()
        except Exception as e:
            logger.warning("保存 GMS 配置失败: %s", e)
            return False
