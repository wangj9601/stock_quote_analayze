"""
GMS 策略核心接口定义
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from .models import GMSIndicators


class IDataLoader(ABC):
    """数据加载器接口：从 mean_frequency_resonance_indicators 加载"""

    @abstractmethod
    def load_indicators(
        self,
        codes: List[str],
        date: str,
        market_type: str = "CN",
    ) -> List[Dict[str, Any]]:
        """批量加载指定日期、市场的指标数据"""
        pass


class IIndicatorsCalculator(ABC):
    """指标计算器接口：计算 Δ/d、量比、评分"""

    @abstractmethod
    def calculate(self, row: Dict[str, Any]) -> Optional[GMSIndicators]:
        """从单行指标数据计算 GMS 衍生指标及评分"""
        pass


class ISignalDetector(ABC):
    """信号检测器接口：左/右买点、卖点"""

    @abstractmethod
    def detect_left_buy(self, indicators: GMSIndicators) -> bool:
        """检测左侧买点（均值吸附）"""
        pass

    @abstractmethod
    def detect_right_buy(self, indicators: GMSIndicators) -> bool:
        """检测右侧买点（动量引爆）"""
        pass

    @abstractmethod
    def detect_sell(self, indicators: GMSIndicators) -> bool:
        """检测卖点（趋势破坏或乖离过大）"""
        pass


class IStrategyEngine(ABC):
    """策略引擎接口"""

    @abstractmethod
    def screen(
        self,
        codes: List[str],
        date: str,
        market: str = "CN",
        config: Optional[Dict] = None,
    ) -> List[Dict]:
        """选股：返回符合条件的股票列表"""
        pass
