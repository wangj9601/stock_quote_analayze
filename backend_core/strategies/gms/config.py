"""
GMS 策略配置管理
"""

import json
import os
import logging
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


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

    def load_config(self) -> Dict:
        """加载配置（文件不存在则返回默认）"""
        if self._config is not None:
            return self._config
        try:
            if os.path.exists(self.default_config_path):
                with open(self.default_config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                default = self.get_default_config()
                self._config = self._deep_merge(default, loaded)
            else:
                self._config = self.get_default_config()
        except Exception as e:
            logger.warning(f"加载 GMS 配置失败: {e}，使用默认配置")
            self._config = self.get_default_config()
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
