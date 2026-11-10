"""
PVFRS (量价频三维共振演化策略) 模块
提供完整的PVFRS策略实现，包括数据模型、接口定义和核心组件

重依赖（data_interface/analyzers 等）按需加载，避免仅 import models/异常时就拉起 pandas。
"""

from .models import (
    MarketData,
    PVFRSIndicators,
    Signal,
    Trade,
    BacktestResult,
    SignalType,
    PVFRSException,
    DataInsufficientException,
    CalculationException,
    ConfigurationException,
    ValidationException,
)

from .interfaces import (
    IDataInterface,
    IDimensionAnalyzer,
    IPriceDimensionAnalyzer,
    IFrequencyDimensionAnalyzer,
    IVolumeDimensionAnalyzer,
    IResonanceDetector,
    ISignalGenerator,
    IStrategyEngine,
    IBacktestEngine,
    IRiskManager,
    IConfigManager,
)

__version__ = "1.0.0"
__author__ = "PVFRS Strategy Team"

__all__ = [
    "MarketData",
    "PVFRSIndicators",
    "Signal",
    "Trade",
    "BacktestResult",
    "SignalType",
    "PVFRSException",
    "DataInsufficientException",
    "CalculationException",
    "ConfigurationException",
    "ValidationException",
    "IDataInterface",
    "IDimensionAnalyzer",
    "IPriceDimensionAnalyzer",
    "IFrequencyDimensionAnalyzer",
    "IVolumeDimensionAnalyzer",
    "IResonanceDetector",
    "ISignalGenerator",
    "IStrategyEngine",
    "IBacktestEngine",
    "IRiskManager",
    "IConfigManager",
    "PVFRSConfigManager",
    "PVFRSDataInterface",
    "PriceDimensionAnalyzer",
    "FrequencyDimensionAnalyzer",
    "VolumeDimensionAnalyzer",
    "ResonanceDetector",
    "SignalGenerator",
    "ThreeDimensionResonanceEngine",
    "RiskManager",
]

_LAZY_ATTRS = {
    "PVFRSConfigManager": (".config", "PVFRSConfigManager"),
    "PVFRSDataInterface": (".data_interface", "PVFRSDataInterface"),
    "PriceDimensionAnalyzer": (".analyzers", "PriceDimensionAnalyzer"),
    "FrequencyDimensionAnalyzer": (".analyzers", "FrequencyDimensionAnalyzer"),
    "VolumeDimensionAnalyzer": (".analyzers", "VolumeDimensionAnalyzer"),
    "ResonanceDetector": (".resonance_detector", "ResonanceDetector"),
    "SignalGenerator": (".signal_generator", "SignalGenerator"),
    "ThreeDimensionResonanceEngine": (".three_dimension_resonance", "ThreeDimensionResonanceEngine"),
    "RiskManager": (".risk_manager", "RiskManager"),
}


def __getattr__(name: str):
    spec = _LAZY_ATTRS.get(name)
    if spec is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    mod_name, attr = spec
    mod = import_module(mod_name, __name__)
    val = getattr(mod, attr)
    globals()[name] = val
    return val
