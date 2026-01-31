"""
GMS (均值引力与动量突变策略) 模块
基于 mean_frequency_resonance_indicators 表，实现左侧均值吸附、右侧动量引爆选股。
"""

from .models import (
    GMSIndicators,
    GMSSignal,
    GMSException,
    DataInsufficientException,
    CalculationException,
)
from .config import GMSConfigManager
from .data_loader import GMSDataLoader
from .indicators_calculator import GMSIndicatorsCalculator
from .signal_detector import GMSSignalDetector
from .strategy_engine import GMSStrategyEngine
from .frontend_interface import GMSFrontendInterface

__version__ = "1.0.0"

__all__ = [
    "GMSIndicators",
    "GMSSignal",
    "GMSException",
    "DataInsufficientException",
    "CalculationException",
    "GMSConfigManager",
    "GMSDataLoader",
    "GMSIndicatorsCalculator",
    "GMSSignalDetector",
    "GMSStrategyEngine",
    "GMSFrontendInterface",
]
