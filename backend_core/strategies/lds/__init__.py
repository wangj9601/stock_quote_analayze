# -*- coding: utf-8 -*-
"""龙头战法（Leader Dragon Strategy / LDS）。"""

from .config import LdsConfigManager, get_default_lds_config
from .detector import evaluate_candidate, merge_hits_by_code
from .strategy_engine import LdsStrategyEngine

__all__ = [
    "LdsConfigManager",
    "LdsStrategyEngine",
    "evaluate_candidate",
    "merge_hits_by_code",
    "get_default_lds_config",
]
