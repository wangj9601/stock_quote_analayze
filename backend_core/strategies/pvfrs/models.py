"""
PVFRS策略核心数据模型
定义MarketData、PVFRSIndicators、Signal等核心数据类
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Union, Any
from enum import Enum
from datetime import datetime


class SignalType(Enum):
    """信号类型枚举"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class MarketData:
    """市场数据结构"""
    symbol: str          # 股票代码
    date: str           # 交易日期 (YYYY-MM-DD)
    open: float         # 开盘价
    high: float         # 最高价
    low: float          # 最低价
    close: float        # 收盘价
    volume: int         # 成交量
    amount: float       # 成交额
    
    def __post_init__(self):
        """数据验证"""
        if self.open <= 0 or self.high <= 0 or self.low <= 0 or self.close <= 0:
            raise ValueError(f"价格数据不能为负或零: {self}")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError(f"价格数据不一致: {self}")
        if self.volume < 0 or self.amount < 0:
            raise ValueError(f"成交量或成交额不能为负: {self}")


@dataclass
class PVFRSIndicators:
    """PVFRS指标结构"""
    # 价格维度指标
    macro_displacement: float    # 宏观位移 Δ = d₂₀ - d₁
    instant_deviation: float     # 即时强度 d₂₀ - d
    avg_price_20d: float        # 20日平均价格 d
    
    # 频率维度指标
    rising_days: int            # 上涨天数 Z
    falling_days: int           # 下跌天数 F
    frequency_advantage: bool   # 频率权重 F > Z（买点侧）
    
    # 成交量维度指标
    avg_volume_20d: float       # 20日平均成交量 m
    current_volume: float       # 当前成交量 m₂₀
    efficiency_ratio: float     # 效率比 m₂₀ / m
    
    # 综合指标
    amplitude_ratio: float      # 幅度系数 Δ₂₀ / d
    resonance_strength: float   # 共振强度 (0-1)
    
    # 图片中幅度指标（可选）
    amplitude: Optional[float] = None       # 幅度 = |Δ|
    ratio_d20: Optional[float] = None      # Δ / d₂₀
    ratio_d1: Optional[float] = None       # Δ / d₁
    is_sideways: Optional[bool] = None     # Δ ≈ 0 横盘
    
    def __post_init__(self):
        """指标验证"""
        if self.avg_price_20d <= 0:
            raise ValueError("20日平均价格必须大于0")
        if self.rising_days < 0 or self.falling_days < 0:
            raise ValueError("涨跌天数不能为负")
        if self.avg_volume_20d < 0 or self.current_volume < 0:
            raise ValueError("成交量不能为负")
        if not 0 <= self.resonance_strength <= 1:
            raise ValueError("共振强度必须在0-1之间")


@dataclass
class Signal:
    """交易信号结构"""
    symbol: str
    date: str
    signal_type: SignalType     # BUY, SELL, HOLD
    price: float
    strength: float             # 信号强度 (0-1)
    reason: str                 # 信号原因
    indicators: Optional[PVFRSIndicators] = None  # 相关指标
    conditions_met: Optional[Dict[str, bool]] = None  # 满足的条件
    
    def __post_init__(self):
        """信号验证"""
        if self.price <= 0:
            raise ValueError("信号价格必须大于0")
        if not 0 <= self.strength <= 1:
            raise ValueError("信号强度必须在0-1之间")
        if self.conditions_met is None:
            self.conditions_met = {}


@dataclass
class StockSelectionResult:
    """选股结果数据类"""
    symbol: str
    name: str
    price: float
    signal_strength: float
    indicators: Union[PVFRSIndicators, Dict]  # 支持 PVFRSIndicators 对象或字典
    conditions_met: Dict[str, bool]
    analysis_time: str
    
    def __post_init__(self):
        """选股结果验证"""
        if self.price <= 0:
            raise ValueError("股票价格必须大于0")
        if not 0 <= self.signal_strength <= 1:
            raise ValueError("信号强度必须在0-1之间")
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        from dataclasses import asdict, is_dataclass
        
        result = {
            'symbol': self.symbol,
            'name': self.name,
            'price': self.price,
            'signal_strength': self.signal_strength,
            'conditions_met': self.conditions_met,
            'analysis_time': self.analysis_time
        }
        
        # 转换 indicators (PVFRSIndicators) 为字典
        if self.indicators:
            if isinstance(self.indicators, dict):
                # 如果已经是字典，递归检查并转换其中的 dataclass 对象
                indicators_dict = {}
                for key, value in self.indicators.items():
                    if is_dataclass(value):
                        # 如果是 dataclass 对象（如 PVFRSIndicators），转换为字典
                        indicators_dict[key] = asdict(value)
                    elif isinstance(value, dict):
                        # 递归处理嵌套字典
                        indicators_dict[key] = self._convert_dataclass_to_dict(value)
                    else:
                        indicators_dict[key] = value
                result['indicators'] = indicators_dict
            else:
                # 如果是 PVFRSIndicators 对象，使用 asdict 转换
                result['indicators'] = asdict(self.indicators)
        else:
            result['indicators'] = {}
        
        return result
    
    def _convert_dataclass_to_dict(self, obj: Any) -> Any:
        """递归将 dataclass 对象转换为字典"""
        from dataclasses import asdict, is_dataclass
        
        if is_dataclass(obj):
            return asdict(obj)
        elif isinstance(obj, dict):
            return {key: self._convert_dataclass_to_dict(value) for key, value in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._convert_dataclass_to_dict(item) for item in obj]
        else:
            return obj


@dataclass
class StockDetail:
    """股票详细信息数据类"""
    symbol: str
    name: str
    current_price: float
    analysis_date: str
    
    # 三维分析结果
    price_dimension: Dict
    frequency_dimension: Dict
    volume_dimension: Dict
    
    # 综合分析结果
    resonance_analysis: Dict
    signal_analysis: Dict
    strategy_assessment: Dict
    
    # 投资建议和风险评估
    investment_advice: str
    risk_assessment: Dict
    
    def __post_init__(self):
        """股票详情验证"""
        if self.current_price <= 0:
            raise ValueError("当前价格必须大于0")


@dataclass
class Trade:
    """交易记录数据类"""
    symbol: str
    entry_date: str
    exit_date: Optional[str]
    entry_price: float
    exit_price: Optional[float]
    quantity: int
    position_size: float
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    exit_reason: Optional[str] = None
    
    def __post_init__(self):
        """交易记录验证"""
        if self.entry_price <= 0:
            raise ValueError("入场价格必须大于0")
        if self.exit_price is not None and self.exit_price <= 0:
            raise ValueError("出场价格必须大于0")
        if self.quantity <= 0:
            raise ValueError("交易数量必须大于0")
        if self.position_size <= 0:
            raise ValueError("仓位大小必须大于0")


@dataclass
class BacktestResult:
    """回测结果数据类"""
    initial_capital: float
    final_capital: float
    total_return: float
    annual_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    profit_factor: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_holding_period: float
    trades: List[Trade]
    equity_curve: List[Dict]  # 权益曲线数据
    
    def __post_init__(self):
        """回测结果验证"""
        if self.initial_capital <= 0:
            raise ValueError("初始资金必须大于0")
        if self.total_trades < 0:
            raise ValueError("交易次数不能为负")
        if self.winning_trades + self.losing_trades != self.total_trades:
            raise ValueError("盈利和亏损交易次数之和必须等于总交易次数")


class PVFRSException(Exception):
    """PVFRS策略异常基类"""
    pass


class DataInsufficientException(PVFRSException):
    """数据不足异常"""
    pass


class CalculationException(PVFRSException):
    """计算异常"""
    pass


class ConfigurationException(PVFRSException):
    """配置异常"""
    pass


class ValidationException(PVFRSException):
    """数据验证异常"""
    pass