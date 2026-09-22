# -*- coding: utf-8 -*-
"""杯底形态（Cup Bottom / CUPB）策略。"""

from .config import CupbConfigManager, get_default_cupb_config

__all__ = ["CupbConfigManager", "CupbStrategyEngine", "get_default_cupb_config"]


def __getattr__(name: str):
    if name == "CupbStrategyEngine":
        from .strategy_engine import CupbStrategyEngine

        return CupbStrategyEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
