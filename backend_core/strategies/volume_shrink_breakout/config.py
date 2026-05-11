"""
3倍量缩量突破策略 — 配置（本地 vsb_config.json + 运行时 Query 覆盖）
"""

import json
import logging
import os
from copy import deepcopy
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class VolumeShrinkBreakoutConfigManager:
    """与 GMS 命名风格一致；首版仅 JSON 文件，无数据库配置表。"""

    def __init__(self, config_file: str = "vsb_config.json"):
        self.config_file = config_file
        self.default_config_path = os.path.join(os.path.dirname(__file__), self.config_file)
        self._config: Optional[Dict[str, Any]] = None

    def get_default_config(self) -> Dict[str, Any]:
        return {
            "volume_ratio": 3.0,
            "boom_lookback_min": 5,
            "boom_lookback_max": 60,
            "ma_periods": [5, 10, 20],
            "history_calendar_days": 180,
            "evaluation_mode": "three_phase",
            "trend_ma_lookback": 5,
            "retracement_break_eps": 0.005,
            "ma_flat_tol": 0.008,
            "retracement_volume_half_ratio": 0.5,
        }

    def _load_from_json_file(self) -> Optional[Dict[str, Any]]:
        try:
            if os.path.exists(self.default_config_path):
                with open(self.default_config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning("读取 vsb_config.json 失败: %s", e)
        return None

    def load_config(self) -> Dict[str, Any]:
        if self._config is not None:
            return deepcopy(self._config)
        base = self.get_default_config()
        loaded = self._load_from_json_file()
        if loaded:
            base.update({k: v for k, v in loaded.items() if v is not None})
        self._config = base
        return deepcopy(base)

    def merge_overrides(
        self,
        base: Optional[Dict[str, Any]] = None,
        *,
        volume_ratio: Optional[float] = None,
        boom_lookback_min: Optional[int] = None,
        boom_lookback_max: Optional[int] = None,
        evaluation_mode: Optional[str] = None,
        trend_ma_lookback: Optional[int] = None,
        retracement_break_eps: Optional[float] = None,
        ma_flat_tol: Optional[float] = None,
        retracement_volume_half_ratio: Optional[float] = None,
    ) -> Dict[str, Any]:
        cfg = deepcopy(base or self.load_config())
        if volume_ratio is not None:
            cfg["volume_ratio"] = float(volume_ratio)
        if boom_lookback_min is not None:
            cfg["boom_lookback_min"] = int(boom_lookback_min)
        if boom_lookback_max is not None:
            cfg["boom_lookback_max"] = int(boom_lookback_max)
        if evaluation_mode is not None:
            cfg["evaluation_mode"] = str(evaluation_mode).strip().lower()
        if trend_ma_lookback is not None:
            cfg["trend_ma_lookback"] = int(trend_ma_lookback)
        if retracement_break_eps is not None:
            cfg["retracement_break_eps"] = float(retracement_break_eps)
        if ma_flat_tol is not None:
            cfg["ma_flat_tol"] = float(ma_flat_tol)
        if retracement_volume_half_ratio is not None:
            cfg["retracement_volume_half_ratio"] = float(retracement_volume_half_ratio)
        return cfg
