"""
PVFRS (量价频三维共振演化策略) 模块
提供完整的PVFRS策略实现，包括数据模型、接口定义和核心组件
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
    ValidationException
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
    IConfigManager
)

from .config import PVFRSConfigManager
from .data_interface import PVFRSDataInterface
from .analyzers import PriceDimensionAnalyzer, FrequencyDimensionAnalyzer, VolumeDimensionAnalyzer
from .resonance_detector import ResonanceDetector
from .signal_generator import SignalGenerator
from .three_dimension_resonance import ThreeDimensionResonanceEngine
from .risk_manager import RiskManager

__version__ = "1.0.0"
__author__ = "PVFRS Strategy Team"

__all__ = [
    # 数据模型
    "MarketData",
    "PVFRSIndicators", 
    "Signal",
    "Trade",
    "BacktestResult",
    "SignalType",
    
    # 异常类
    "PVFRSException",
    "DataInsufficientException",
    "CalculationException",
    "ConfigurationException",
    "ValidationException",
    
    # 接口定义
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
    
    # 配置管理
    "PVFRSConfigManager",
    
    # 数据接口
    "PVFRSDataInterface",
    
    # 分析器
    "PriceDimensionAnalyzer", 
    "FrequencyDimensionAnalyzer", 
    "VolumeDimensionAnalyzer",
    
    # 三维共振检测器
    "ResonanceDetector", 
    "SignalGenerator", 
    "ThreeDimensionResonanceEngine",
    
    # 风险管理
    "RiskManager"
]