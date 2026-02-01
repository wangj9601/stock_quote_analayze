"""
GMS 策略核心数据模型
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Any
from enum import Enum


class GMSException(Exception):
    """GMS 策略基础异常"""

    pass


class DataInsufficientException(GMSException):
    """数据不足异常"""

    pass


class CalculationException(GMSException):
    """计算异常"""

    pass


class GMSSignalType(Enum):
    """GMS 信号类型"""
    LEFT_BUY = "left_buy"   # 左侧买点：均值吸附
    RIGHT_BUY = "right_buy"  # 右侧买点：动量引爆
    SELL = "sell"
    HOLD = "hold"


@dataclass
class GMSIndicators:
    """GMS 指标结构（基于 mean_frequency_resonance_indicators 衍生）"""

    code: str
    date: str
    market_type: str

    # 从表直接映射
    delta: float                    # 宏观位移 Δ = d₂₀ - d₁ (macro_displacement_delta)
    d: float                        # 20 日均价 (ma20_d)
    ratio_d20: Optional[float]      # 偏离率 Δ/d₂₀
    ratio_d1: Optional[float]       # 突变率 Δ/d₁
    instant_deviation: float        # d₂₀ - d (价格 vs 均线)
    rising_days: int                # Z 上涨天数
    falling_days: int               # F 下跌天数
    avg_volume_20d: float           # m 20 日平均成交量
    current_volume: float           # m₂₀ 当日成交量

    # 衍生计算
    ratio_d: Optional[float] = None       # Δ/d = delta / d (相对位移)
    volume_ratio: Optional[float] = None  # m₂₀ / m 量比
    fz_ratio: Optional[float] = None      # F/Z 数方比 (Z>0 时)

    # 评分（双模块阶梯式）
    score_accumulation: float = 0.0   # 吸附态总分 0-100
    score_balance: float = 0.0        # 吸附态-引力粘合维度得分（保留兼容）
    score_momentum: float = 0.0       # 突变态总分 0-100（可含负分）
    score_total: float = 0.0          # 综合总分，用于排序

    # 执行等级
    accumulation_grade: str = ""      # 吸附态：S / A / 空
    momentum_grade: str = ""          # 突变态：全速切入 / 分批买入 / 空

    # 各维度得分（供 score_detail 展示）
    score_acc_fz: float = 0.0         # 吸附态-时间耗散 F/Z
    score_acc_balance: float = 0.0    # 吸附态-引力粘合 |Δ/d|
    score_acc_volume: float = 0.0     # 吸附态-成交量缩 m₂₀/m
    score_mom_ratio_d1: float = 0.0   # 突变态-盈亏反转 Δ/d₁
    score_mom_deviation: float = 0.0  # 突变态-推力支撑 d₂₀-d
    score_mom_volume: float = 0.0     # 突变态-攻击强度 m₂₀/m

    # 各维度判定结果（供得分明细展示）
    acc_fz_judge: str = ""
    acc_balance_judge: str = ""
    acc_volume_judge: str = ""
    mom_ratio_d1_judge: str = ""
    mom_deviation_judge: str = ""
    mom_volume_judge: str = ""

    # 买点/卖点标记
    left_buy_signal: bool = False
    right_buy_signal: bool = False
    sell_signal: bool = False

    # 扩展：原始行数据引用（便于调试）
    raw_row: Optional[Dict[str, Any]] = None


@dataclass
class GMSSignal:
    """GMS 交易信号"""

    symbol: str
    date: str
    signal_type: GMSSignalType
    price: float
    strength: float             # 0-1，可用 score_total/100 或自定义
    reason: str
    indicators: Optional[GMSIndicators] = None
    conditions_met: Dict[str, bool] = field(default_factory=dict)

    def __post_init__(self):
        if self.price <= 0:
            raise ValueError("信号价格必须大于0")
        if not 0 <= self.strength <= 1:
            raise ValueError("信号强度必须在0-1之间")
