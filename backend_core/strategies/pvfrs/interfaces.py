"""
PVFRS策略核心接口定义
定义各个组件的标准接口
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from .models import MarketData, PVFRSIndicators, Signal, Trade, BacktestResult


class IDataInterface(ABC):
    """数据接口抽象类"""
    
    @abstractmethod
    def get_market_data(self, symbol: str, start_date: str, end_date: str) -> List[MarketData]:
        """获取市场数据"""
        pass
    
    @abstractmethod
    def validate_data(self, data: List[MarketData]) -> bool:
        """验证数据完整性"""
        pass
    
    @abstractmethod
    def clean_data(self, data: List[MarketData]) -> List[MarketData]:
        """清洗数据"""
        pass


class IDimensionAnalyzer(ABC):
    """维度分析器抽象类"""
    
    @abstractmethod
    def analyze(self, data: List[MarketData]) -> Dict:
        """分析指定维度的指标"""
        pass
    
    @abstractmethod
    def validate_conditions(self, indicators: Dict) -> bool:
        """验证维度条件是否满足"""
        pass


class IPriceDimensionAnalyzer(IDimensionAnalyzer):
    """价格维度分析器接口"""
    
    @abstractmethod
    def calculate_macro_displacement(self, data: List[MarketData]) -> float:
        """计算宏观位移指标 Δ = d₂₀ - d₁"""
        pass
    
    @abstractmethod
    def calculate_instant_deviation(self, data: List[MarketData]) -> float:
        """计算即时强度指标 d₂₀ - d"""
        pass
    
    @abstractmethod
    def calculate_avg_price_20d(self, data: List[MarketData]) -> float:
        """计算20日平均价格"""
        pass


class IFrequencyDimensionAnalyzer(IDimensionAnalyzer):
    """频率维度分析器接口"""
    
    @abstractmethod
    def count_rising_days(self, data: List[MarketData]) -> int:
        """统计上涨天数 Z"""
        pass
    
    @abstractmethod
    def count_falling_days(self, data: List[MarketData]) -> int:
        """统计下跌天数 F"""
        pass
    
    @abstractmethod
    def check_frequency_advantage(self, rising_days: int, falling_days: int) -> bool:
        """检查频率权重 F > Z（买点侧：下跌天数大于上涨天数）"""
        pass


class IVolumeDimensionAnalyzer(IDimensionAnalyzer):
    """成交量维度分析器接口"""
    
    @abstractmethod
    def calculate_avg_volume_20d(self, data: List[MarketData]) -> float:
        """计算20日平均成交量"""
        pass
    
    @abstractmethod
    def calculate_efficiency_ratio(self, current_volume: float, avg_volume: float) -> float:
        """计算效率比 m₂₀ / m"""
        pass
    
    @abstractmethod
    def detect_volume_price_resonance(self, price_rising: bool, volume_increasing: bool) -> bool:
        """检测量价共振状态"""
        pass


class IResonanceDetector(ABC):
    """三维共振检测器接口"""
    
    @abstractmethod
    def detect_resonance(self, price_indicators: Dict, frequency_indicators: Dict, 
                        volume_indicators: Dict) -> Dict:
        """检测三维共振状态"""
        pass
    
    @abstractmethod
    def calculate_resonance_strength(self, conditions_met: Dict[str, bool]) -> float:
        """计算共振强度"""
        pass


class ISignalGenerator(ABC):
    """信号生成器接口"""
    
    @abstractmethod
    def generate_buy_signal(self, symbol: str, date: str, price: float, 
                           indicators: PVFRSIndicators, conditions_met: Dict[str, bool]) -> Signal:
        """生成买入信号"""
        pass
    
    @abstractmethod
    def generate_sell_signal(self, symbol: str, date: str, price: float, 
                            reason: str, strength: float) -> Signal:
        """生成卖出信号"""
        pass
    
    @abstractmethod
    def optimize_entry_timing(self, data: List[MarketData], base_signal: Signal) -> Optional[Signal]:
        """优化入场时机"""
        pass


class IStrategyEngine(ABC):
    """策略引擎接口"""
    
    @abstractmethod
    def analyze_stock(self, symbol: str, data: List[MarketData]) -> PVFRSIndicators:
        """分析单只股票的PVFRS指标"""
        pass
    
    @abstractmethod
    def screen_stocks(self, symbols: List[str], date: str) -> List[str]:
        """选股：筛选符合PVFRS条件的股票"""
        pass
    
    @abstractmethod
    def generate_signals(self, symbol: str, data: List[MarketData]) -> List[Signal]:
        """生成交易信号"""
        pass


class IBacktestEngine(ABC):
    """回测引擎接口"""
    
    @abstractmethod
    def run_backtest(self, symbols: List[str], start_date: str, end_date: str, 
                    initial_capital: float = 100000) -> BacktestResult:
        """执行回测"""
        pass
    
    @abstractmethod
    def simulate_trade(self, signal: Signal, current_capital: float) -> Optional[Trade]:
        """模拟交易"""
        pass
    
    @abstractmethod
    def calculate_performance(self, trades: List[Trade]) -> Dict:
        """计算绩效指标"""
        pass


class IRiskManager(ABC):
    """风险管理器接口"""
    
    @abstractmethod
    def check_stop_loss(self, current_price: float, entry_price: float, 
                       stop_loss_pct: float) -> bool:
        """检查止损条件"""
        pass
    
    @abstractmethod
    def check_take_profit(self, current_price: float, entry_price: float, 
                         take_profit_pct: float) -> bool:
        """检查止盈条件"""
        pass
    
    @abstractmethod
    def check_max_holding_period(self, entry_date: str, current_date: str, 
                                max_days: int) -> bool:
        """检查最大持有期"""
        pass
    
    @abstractmethod
    def detect_trend_reversal(self, data: List[MarketData]) -> bool:
        """检测趋势反转"""
        pass


class IConfigManager(ABC):
    """配置管理器接口"""
    
    @abstractmethod
    def load_config(self, config_path: Optional[str] = None) -> Dict:
        """加载配置"""
        pass
    
    @abstractmethod
    def save_config(self, config: Dict, config_path: Optional[str] = None) -> bool:
        """保存配置"""
        pass
    
    @abstractmethod
    def validate_config(self, config: Dict) -> bool:
        """验证配置有效性"""
        pass
    
    @abstractmethod
    def get_default_config(self) -> Dict:
        """获取默认配置"""
        pass
    
    @abstractmethod
    def update_config(self, updates: Dict, config_path: Optional[str] = None) -> Dict:
        """更新配置"""
        pass
    
    @abstractmethod
    def get_current_config(self) -> Dict:
        """获取当前配置"""
        pass
    
    @abstractmethod
    def get_config_value(self, key: str, default = None):
        """获取单个配置值"""
        pass
    
    @abstractmethod
    def set_config_value(self, key: str, value, config_path: Optional[str] = None):
        """设置单个配置值"""
        pass