"""
3倍量缩量突破策略（Volume Shrink Breakout）
独立模块，结构与 GMS 分包思路一致。
"""

from .config import VolumeShrinkBreakoutConfigManager
from .data_loader import VolumeShrinkBreakoutDataLoader
from .frontend_interface import VolumeShrinkBreakoutFrontendInterface
from .strategy_engine import (
    VolumeShrinkBreakoutStrategyEngine,
    evaluate_stock,
    find_boom_index,
    pass_ma_bull_at_k,
    pass_shrink_breakout,
)

__version__ = "1.0.0"

__all__ = [
    "VolumeShrinkBreakoutConfigManager",
    "VolumeShrinkBreakoutDataLoader",
    "VolumeShrinkBreakoutFrontendInterface",
    "VolumeShrinkBreakoutStrategyEngine",
    "evaluate_stock",
    "find_boom_index",
    "pass_ma_bull_at_k",
    "pass_shrink_breakout",
]
