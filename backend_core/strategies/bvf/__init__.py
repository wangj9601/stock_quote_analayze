# -*- coding: utf-8 -*-
"""底部放量分型（Bottom Volume Fractal / BVF）策略。"""

from .config import BvfConfigManager, get_default_bvf_config
from .detector import detect_bottom_volume_fractal
from .strategy_engine import BvfStrategyEngine

__all__ = [
    "BvfConfigManager",
    "BvfStrategyEngine",
    "detect_bottom_volume_fractal",
    "get_default_bvf_config",
]
