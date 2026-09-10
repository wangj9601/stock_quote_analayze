# -*- coding: utf-8 -*-
"""CSB（通道粘合突破）策略包。"""

from .config import (
    BUY_SIGNAL_TYPES,
    CSB_BREAKOUT,
    CSB_FALSE_BREAK,
    CSB_PROBE,
    CSB_SETUP,
    CSB_STOP,
    CSB_TRAIL,
    CSBConfigManager,
    get_default_csb_config,
)
from .strategy_engine import CSBStrategyEngine, evaluate_one

__all__ = [
    "CSBConfigManager",
    "CSBStrategyEngine",
    "get_default_csb_config",
    "evaluate_one",
    "CSB_SETUP",
    "CSB_PROBE",
    "CSB_BREAKOUT",
    "CSB_FALSE_BREAK",
    "CSB_STOP",
    "CSB_TRAIL",
    "BUY_SIGNAL_TYPES",
]
