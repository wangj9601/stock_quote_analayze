"""
PVFRS策略风险管理模块实现
负责止损止盈机制、时间管理和趋势反转检测
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from .models import MarketData, Signal, SignalType, Trade, CalculationException
from .interfaces import IRiskManager


class RiskManager(IRiskManager):
    """风险管理器
    
    负责PVFRS策略的风险管理功能：
    - 止损止盈机制
    - 最大持有期管理
    - 趋势反转检测
    - 动态风险调整
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """初始化风险管理器
        
        Args:
            config: 风险管理配置参数
        """
        self.config = config or self._get_default_config()
        
        # 风险管理参数
        self.stop_loss_pct = self.config.get('stop_loss', -0.06)  # 默认-6%止损
        self.take_profit_pct = self.config.get('take_profit', 0.25)  # 默认25%止盈
        self.max_holding_days = self.config.get('max_holding_days', 45)  # 默认45天最大持有期
        
        # 动态风险管理参数
        self.profit_stage1 = self.config.get('profit_stage1', 0.15)  # 盈利阶段1: 15%
        self.trailing_stop_enabled = self.config.get('trailing_stop_enabled', False)  # 移动止损
        self.trailing_stop_pct = self.config.get('trailing_stop_pct', 0.10)  # 移动止损10%
        
        # 趋势反转检测参数
        self.reversal_conditions_low_profit = self.config.get('sell_reversal_conditions_low_profit', 3)
        self.reversal_conditions_high_profit = self.config.get('sell_reversal_conditions_high_profit', 2)
        self.max_bias = self.config.get('sell_bias_max', 0.15)  # 最大偏离度15%
        self.max_instant_deviation = self.config.get('sell_instant_deviation_max', 0.10)  # 最大即时强度10%
        
        # 内部状态
        self.highest_price_since_entry = {}  # 记录每个持仓的最高价格
        
    def _get_default_config(self) -> Dict:
        """获取默认风险管理配置"""
        return {
            'stop_loss': -0.06,                   # 止损-6%
            'take_profit': 0.25,                  # 止盈25%
            'max_holding_days': 45,               # 最大持有天数
            'profit_stage1': 0.15,                # 盈利阶段1: 15%
            'trailing_stop_enabled': False,       # 移动止损
            'trailing_stop_pct': 0.10,           # 移动止损10%
            'sell_reversal_conditions_low_profit': 3,  # 低盈利时需要的反转条件数
            'sell_reversal_conditions_high_profit': 2, # 高盈利时需要的反转条件数
            'sell_bias_max': 0.15,               # 最大偏离度15%
            'sell_instant_deviation_max': 0.10,  # 最大即时强度10%
        }
    
    def check_stop_loss(self, current_price: float, entry_price: float, 
                       stop_loss_pct: Optional[float] = None) -> bool:
        """检查止损条件
        
        Args:
            current_price: 当前价格
            entry_price: 入场价格
            stop_loss_pct: 止损百分比，如果为None则使用默认配置
            
        Returns:
            bool: 是否触发止损
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        try:
            if entry_price <= 0:
                raise CalculationException("入场价格必须大于0")
            
            if current_price <= 0:
                raise CalculationException("当前价格必须大于0")
            
            # 使用传入的止损百分比或默认配置
            stop_loss_threshold = stop_loss_pct if stop_loss_pct is not None else self.stop_loss_pct
            
            # 计算当前盈亏百分比
            profit_pct = (current_price - entry_price) / entry_price
            
            # 检查是否触发止损
            return profit_pct <= stop_loss_threshold
            
        except Exception as e:
            raise CalculationException(f"止损检查失败: {str(e)}")
    
    def check_take_profit(self, current_price: float, entry_price: float, 
                         take_profit_pct: Optional[float] = None) -> bool:
        """检查止盈条件
        
        Args:
            current_price: 当前价格
            entry_price: 入场价格
            take_profit_pct: 止盈百分比，如果为None则使用默认配置
            
        Returns:
            bool: 是否触发止盈
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        try:
            if entry_price <= 0:
                raise CalculationException("入场价格必须大于0")
            
            if current_price <= 0:
                raise CalculationException("当前价格必须大于0")
            
            # 使用传入的止盈百分比或默认配置
            take_profit_threshold = take_profit_pct if take_profit_pct is not None else self.take_profit_pct
            
            # 计算当前盈亏百分比
            profit_pct = (current_price - entry_price) / entry_price
            
            # 检查是否触发止盈
            return profit_pct >= take_profit_threshold
            
        except Exception as e:
            raise CalculationException(f"止盈检查失败: {str(e)}")
    
    def check_trailing_stop(self, symbol: str, current_price: float, 
                           entry_price: float) -> Tuple[bool, Optional[str]]:
        """检查移动止损条件
        
        Args:
            symbol: 股票代码
            current_price: 当前价格
            entry_price: 入场价格
            
        Returns:
            Tuple[bool, Optional[str]]: (是否触发移动止损, 触发原因)
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        try:
            if not self.trailing_stop_enabled:
                return False, None
            
            if entry_price <= 0 or current_price <= 0:
                raise CalculationException("价格必须大于0")
            
            # 更新最高价格记录
            if symbol not in self.highest_price_since_entry:
                self.highest_price_since_entry[symbol] = entry_price
            
            # 更新最高价格
            if current_price > self.highest_price_since_entry[symbol]:
                self.highest_price_since_entry[symbol] = current_price
            
            highest_price = self.highest_price_since_entry[symbol]
            
            # 计算移动止损价格
            trailing_stop_price = highest_price * (1 - self.trailing_stop_pct)
            
            # 检查是否触发移动止损
            if current_price <= trailing_stop_price:
                reason = (f"移动止损触发: 当前价格{current_price:.2f} <= "
                         f"止损价格{trailing_stop_price:.2f} "
                         f"(最高价{highest_price:.2f}的{self.trailing_stop_pct:.1%})")
                return True, reason
            
            return False, None
            
        except Exception as e:
            raise CalculationException(f"移动止损检查失败: {str(e)}")
    
    def check_max_holding_period(self, entry_date: str, current_date: str, 
                                max_days: Optional[int] = None) -> bool:
        """检查最大持有期
        
        Args:
            entry_date: 入场日期 (YYYY-MM-DD格式)
            current_date: 当前日期 (YYYY-MM-DD格式)
            max_days: 最大持有天数，如果为None则使用默认配置
            
        Returns:
            bool: 是否超过最大持有期
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        try:
            # 使用传入的最大天数或默认配置
            max_holding_days = max_days if max_days is not None else self.max_holding_days
            
            # 解析日期
            entry_dt = datetime.strptime(entry_date, '%Y-%m-%d')
            current_dt = datetime.strptime(current_date, '%Y-%m-%d')
            
            # 计算持有天数
            holding_days = (current_dt - entry_dt).days
            
            # 检查是否超过最大持有期
            return holding_days >= max_holding_days
            
        except ValueError as e:
            raise CalculationException(f"日期格式错误: {str(e)}")
        except Exception as e:
            raise CalculationException(f"最大持有期检查失败: {str(e)}")
    
    def detect_trend_reversal(self, data: List[MarketData]) -> bool:
        """检测趋势反转
        
        基于PVFRS三维指标检测趋势反转信号。
        
        Args:
            data: 市场数据列表，至少需要20天数据
            
        Returns:
            bool: 是否检测到趋势反转
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        try:
            if len(data) < 20:
                raise CalculationException("趋势反转检测需要至少20天数据")
            
            # 获取最新数据进行分析
            current_data = data[-20:]  # 使用最近20天数据
            
            # 计算PVFRS指标
            reversal_indicators = self._calculate_reversal_indicators(current_data)
            
            # 检测反转条件
            reversal_conditions = self._check_reversal_conditions(reversal_indicators)
            
            # 根据反转条件数量判断是否反转
            reversal_count = sum(reversal_conditions.values())
            
            # 默认需要至少2个反转条件
            required_conditions = 2
            
            return reversal_count >= required_conditions
            
        except Exception as e:
            raise CalculationException(f"趋势反转检测失败: {str(e)}")
    
    def detect_trend_reversal_with_profit(self, data: List[MarketData], 
                                        current_profit_pct: float) -> Tuple[bool, Dict]:
        """基于盈利情况的趋势反转检测
        
        根据当前盈利情况动态调整反转条件的严格程度。
        
        Args:
            data: 市场数据列表
            current_profit_pct: 当前持仓盈利百分比
            
        Returns:
            Tuple[bool, Dict]: (是否检测到反转, 反转分析详情)
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        try:
            if len(data) < 20:
                raise CalculationException("趋势反转检测需要至少20天数据")
            
            # 根据盈利情况确定需要的反转条件数
            if current_profit_pct < self.profit_stage1:  # 盈利<15%
                required_conditions = self.reversal_conditions_low_profit  # 需要3个条件
            else:  # 盈利>=15%
                required_conditions = self.reversal_conditions_high_profit  # 需要2个条件
            
            # 获取最新数据进行分析
            current_data = data[-20:]
            
            # 计算PVFRS指标
            reversal_indicators = self._calculate_reversal_indicators(current_data)
            
            # 检测反转条件
            reversal_conditions = self._check_reversal_conditions(reversal_indicators)
            
            # 统计满足的反转条件数
            reversal_count = sum(reversal_conditions.values())
            
            # 判断是否触发反转
            is_reversal = reversal_count >= required_conditions
            
            # 生成分析详情
            analysis_details = {
                'current_profit_pct': current_profit_pct,
                'required_conditions': required_conditions,
                'reversal_count': reversal_count,
                'reversal_conditions': reversal_conditions,
                'reversal_indicators': reversal_indicators,
                'is_reversal': is_reversal,
                'reversal_strength': min(1.0, reversal_count / 6.0)  # 最多6个条件
            }
            
            return is_reversal, analysis_details
            
        except Exception as e:
            raise CalculationException(f"基于盈利的趋势反转检测失败: {str(e)}")
    
    def generate_risk_management_signal(self, symbol: str, current_data: MarketData,
                                      trade: Trade, data_history: List[MarketData]) -> Optional[Signal]:
        """生成风险管理卖出信号
        
        综合检查所有风险管理条件，生成相应的卖出信号。
        
        Args:
            symbol: 股票代码
            current_data: 当前市场数据
            trade: 当前交易记录
            data_history: 历史数据列表
            
        Returns:
            Optional[Signal]: 风险管理卖出信号，如果没有触发则返回None
            
        Raises:
            CalculationException: 计算异常时抛出
        """
        try:
            current_price = current_data.close
            entry_price = trade.entry_price
            entry_date = trade.entry_date
            current_date = current_data.date
            
            # 计算当前盈亏
            current_profit_pct = (current_price - entry_price) / entry_price
            
            # 检查止损
            if self.check_stop_loss(current_price, entry_price):
                return Signal(
                    symbol=symbol,
                    date=current_date,
                    signal_type=SignalType.SELL,
                    price=current_price,
                    strength=1.0,  # 止损信号强度最高
                    reason=f"止损: {current_profit_pct:.2%} <= {self.stop_loss_pct:.2%}",
                    conditions_met={'stop_loss': True}
                )
            
            # 检查止盈
            if self.check_take_profit(current_price, entry_price):
                return Signal(
                    symbol=symbol,
                    date=current_date,
                    signal_type=SignalType.SELL,
                    price=current_price,
                    strength=0.9,  # 止盈信号强度高
                    reason=f"止盈: {current_profit_pct:.2%} >= {self.take_profit_pct:.2%}",
                    conditions_met={'take_profit': True}
                )
            
            # 检查移动止损
            trailing_stop_triggered, trailing_reason = self.check_trailing_stop(
                symbol, current_price, entry_price
            )
            if trailing_stop_triggered:
                return Signal(
                    symbol=symbol,
                    date=current_date,
                    signal_type=SignalType.SELL,
                    price=current_price,
                    strength=0.95,  # 移动止损信号强度很高
                    reason=trailing_reason,
                    conditions_met={'trailing_stop': True}
                )
            
            # 检查最大持有期
            if self.check_max_holding_period(entry_date, current_date):
                return Signal(
                    symbol=symbol,
                    date=current_date,
                    signal_type=SignalType.SELL,
                    price=current_price,
                    strength=0.8,  # 时间止损信号强度较高
                    reason=f"最大持有期: 持有{self._calculate_holding_days(entry_date, current_date)}天 >= {self.max_holding_days}天",
                    conditions_met={'max_holding_period': True}
                )
            
            # 检查趋势反转
            if len(data_history) >= 20:
                is_reversal, reversal_details = self.detect_trend_reversal_with_profit(
                    data_history, current_profit_pct
                )
                
                if is_reversal:
                    # 生成反转原因描述
                    reversal_reasons = []
                    for condition, met in reversal_details['reversal_conditions'].items():
                        if met:
                            reversal_reasons.append(condition)
                    
                    reason = (f"趋势反转({reversal_details['reversal_count']}个条件): "
                             f"{', '.join(reversal_reasons)} "
                             f"(盈利{current_profit_pct:.2%})")
                    
                    return Signal(
                        symbol=symbol,
                        date=current_date,
                        signal_type=SignalType.SELL,
                        price=current_price,
                        strength=reversal_details['reversal_strength'],
                        reason=reason,
                        conditions_met={'trend_reversal': True, **reversal_details['reversal_conditions']}
                    )
            
            # 没有触发任何风险管理条件
            return None
            
        except Exception as e:
            raise CalculationException(f"风险管理信号生成失败: {str(e)}")
    
    def _calculate_reversal_indicators(self, data: List[MarketData]) -> Dict:
        """计算趋势反转指标
        
        Args:
            data: 市场数据列表（20天）
            
        Returns:
            Dict: 反转指标字典
        """
        if len(data) < 20:
            raise CalculationException("计算反转指标需要至少20天数据")
        
        # 计算价格维度指标
        prices = [d.close for d in data]
        current_price = prices[-1]
        first_price = prices[0]
        avg_price_20d = sum(prices) / len(prices)
        
        macro_displacement = current_price - first_price
        instant_deviation = current_price - avg_price_20d
        
        # 计算频率维度指标
        rising_days = 0
        falling_days = 0
        for i in range(1, len(data)):
            if data[i].close > data[i-1].close:
                rising_days += 1
            elif data[i].close < data[i-1].close:
                falling_days += 1
        
        # 计算成交量维度指标
        volumes = [d.volume for d in data]
        current_volume = volumes[-1]
        avg_volume_20d = sum(volumes) / len(volumes)
        efficiency = current_volume - avg_volume_20d
        
        # 计算偏离度（bias）
        bias = (current_price - avg_price_20d) / avg_price_20d
        
        return {
            'macro_displacement': macro_displacement,
            'instant_deviation': instant_deviation,
            'avg_price_20d': avg_price_20d,
            'rising_days': rising_days,
            'falling_days': falling_days,
            'current_volume': current_volume,
            'avg_volume_20d': avg_volume_20d,
            'efficiency': efficiency,
            'bias': bias,
            'current_price': current_price
        }
    
    def _check_reversal_conditions(self, indicators: Dict) -> Dict[str, bool]:
        """检查反转条件
        
        Args:
            indicators: 反转指标字典
            
        Returns:
            Dict[str, bool]: 反转条件满足情况
        """
        conditions = {}
        
        # 1. 价格维度反转
        conditions['price_reversal'] = indicators['instant_deviation'] < 0
        conditions['macro_reversal'] = indicators['macro_displacement'] < 0
        
        # 2. 频率维度反转
        conditions['frequency_reversal'] = indicators['falling_days'] > indicators['rising_days']
        
        # 3. 成交量维度反转
        conditions['volume_reversal'] = indicators['efficiency'] < 0
        
        # 4. 超买检查
        conditions['overbought'] = indicators['bias'] > self.max_bias
        conditions['overextended'] = indicators['instant_deviation'] > (
            indicators['avg_price_20d'] * self.max_instant_deviation
        )
        
        return conditions
    
    def _calculate_holding_days(self, entry_date: str, current_date: str) -> int:
        """计算持有天数
        
        Args:
            entry_date: 入场日期
            current_date: 当前日期
            
        Returns:
            int: 持有天数
        """
        entry_dt = datetime.strptime(entry_date, '%Y-%m-%d')
        current_dt = datetime.strptime(current_date, '%Y-%m-%d')
        return (current_dt - entry_dt).days
    
    def update_config(self, new_config: Dict) -> None:
        """更新风险管理配置
        
        Args:
            new_config: 新的配置参数
        """
        self.config.update(new_config)
        
        # 更新相关参数
        self.stop_loss_pct = self.config.get('stop_loss', self.stop_loss_pct)
        self.take_profit_pct = self.config.get('take_profit', self.take_profit_pct)
        self.max_holding_days = self.config.get('max_holding_days', self.max_holding_days)
        self.profit_stage1 = self.config.get('profit_stage1', self.profit_stage1)
        self.trailing_stop_enabled = self.config.get('trailing_stop_enabled', self.trailing_stop_enabled)
        self.trailing_stop_pct = self.config.get('trailing_stop_pct', self.trailing_stop_pct)
        
    def reset_position_tracking(self, symbol: str) -> None:
        """重置持仓跟踪状态
        
        在平仓后调用，清理相关的跟踪状态。
        
        Args:
            symbol: 股票代码
        """
        if symbol in self.highest_price_since_entry:
            del self.highest_price_since_entry[symbol]
    
    def get_risk_status(self, symbol: str, current_price: float, 
                       entry_price: float, entry_date: str, 
                       current_date: str) -> Dict:
        """获取当前风险状态
        
        Args:
            symbol: 股票代码
            current_price: 当前价格
            entry_price: 入场价格
            entry_date: 入场日期
            current_date: 当前日期
            
        Returns:
            Dict: 风险状态信息
        """
        try:
            # 计算基本指标
            profit_pct = (current_price - entry_price) / entry_price
            holding_days = self._calculate_holding_days(entry_date, current_date)
            
            # 检查各种风险条件
            stop_loss_triggered = self.check_stop_loss(current_price, entry_price)
            take_profit_triggered = self.check_take_profit(current_price, entry_price)
            max_holding_triggered = self.check_max_holding_period(entry_date, current_date)
            
            # 移动止损状态
            trailing_stop_triggered = False
            trailing_stop_price = None
            if self.trailing_stop_enabled and symbol in self.highest_price_since_entry:
                highest_price = self.highest_price_since_entry[symbol]
                trailing_stop_price = highest_price * (1 - self.trailing_stop_pct)
                trailing_stop_triggered = current_price <= trailing_stop_price
            
            return {
                'symbol': symbol,
                'current_price': current_price,
                'entry_price': entry_price,
                'profit_pct': profit_pct,
                'holding_days': holding_days,
                'stop_loss_triggered': stop_loss_triggered,
                'take_profit_triggered': take_profit_triggered,
                'max_holding_triggered': max_holding_triggered,
                'trailing_stop_enabled': self.trailing_stop_enabled,
                'trailing_stop_triggered': trailing_stop_triggered,
                'trailing_stop_price': trailing_stop_price,
                'highest_price_since_entry': self.highest_price_since_entry.get(symbol),
                'risk_level': self._assess_risk_level(profit_pct, holding_days)
            }
            
        except Exception as e:
            raise CalculationException(f"风险状态获取失败: {str(e)}")
    
    def _assess_risk_level(self, profit_pct: float, holding_days: int) -> str:
        """评估风险等级
        
        Args:
            profit_pct: 盈利百分比
            holding_days: 持有天数
            
        Returns:
            str: 风险等级 ('low', 'medium', 'high')
        """
        # 基于盈亏和持有时间评估风险
        if profit_pct <= -0.04:  # 亏损超过4%
            return 'high'
        elif profit_pct <= -0.02:  # 亏损2-4%
            return 'medium'
        elif holding_days >= self.max_holding_days * 0.8:  # 持有时间超过80%
            return 'medium'
        elif profit_pct >= self.take_profit_pct * 0.8:  # 接近止盈
            return 'medium'
        else:
            return 'low'
    
    def get_dynamic_max_holding_days(self, current_profit_pct: float) -> int:
        """根据盈利情况动态调整最大持有天数
        
        Args:
            current_profit_pct: 当前盈利百分比
            
        Returns:
            int: 动态调整后的最大持有天数
        """
        base_days = self.max_holding_days
        
        if current_profit_pct < 0:  # 亏损
            return int(base_days * 0.6)  # 缩短至60%
        elif current_profit_pct < 0.10:  # 盈利<10%
            return base_days  # 保持原有天数
        elif current_profit_pct < 0.20:  # 盈利10-20%
            return int(base_days * 1.3)  # 延长至130%
        else:  # 盈利>20%
            return int(base_days * 1.6)  # 延长至160%
    
    def check_time_based_exit(self, entry_date: str, current_date: str, 
                             current_profit_pct: float) -> Tuple[bool, Optional[str]]:
        """基于时间的退出检查
        
        结合持有时间和盈利情况，动态判断是否应该退出。
        
        Args:
            entry_date: 入场日期
            current_date: 当前日期
            current_profit_pct: 当前盈利百分比
            
        Returns:
            Tuple[bool, Optional[str]]: (是否应该退出, 退出原因)
        """
        try:
            holding_days = self._calculate_holding_days(entry_date, current_date)
            dynamic_max_days = self.get_dynamic_max_holding_days(current_profit_pct)
            
            if holding_days >= dynamic_max_days:
                reason = (f"动态时间止损: 持有{holding_days}天 >= "
                         f"动态最大持有期{dynamic_max_days}天 "
                         f"(盈利{current_profit_pct:.2%})")
                return True, reason
            
            # 检查是否接近时间限制（80%以上）
            if holding_days >= dynamic_max_days * 0.8:
                # 如果接近时间限制且盈利不佳，建议退出
                if current_profit_pct < 0.05:  # 盈利小于5%
                    reason = (f"时间风险预警: 持有{holding_days}天，接近限制且盈利不佳"
                             f"({current_profit_pct:.2%})")
                    return True, reason
            
            return False, None
            
        except Exception as e:
            raise CalculationException(f"基于时间的退出检查失败: {str(e)}")
    
    def detect_trend_weakening(self, data: List[MarketData], 
                              lookback_days: int = 5) -> Tuple[bool, Dict]:
        """检测趋势弱化信号
        
        通过分析最近几天的价格和成交量变化，检测趋势是否在弱化。
        
        Args:
            data: 市场数据列表
            lookback_days: 回看天数
            
        Returns:
            Tuple[bool, Dict]: (是否检测到趋势弱化, 弱化分析详情)
        """
        try:
            if len(data) < lookback_days + 5:
                return False, {'error': '数据不足'}
            
            # 获取最近的数据
            recent_data = data[-lookback_days:]
            previous_data = data[-(lookback_days + 5):-lookback_days]
            
            # 分析价格趋势
            recent_prices = [d.close for d in recent_data]
            previous_prices = [d.close for d in previous_data]
            
            recent_avg_price = sum(recent_prices) / len(recent_prices)
            previous_avg_price = sum(previous_prices) / len(previous_prices)
            
            # 分析成交量趋势
            recent_volumes = [d.volume for d in recent_data]
            previous_volumes = [d.volume for d in previous_data]
            
            recent_avg_volume = sum(recent_volumes) / len(recent_volumes)
            previous_avg_volume = sum(previous_volumes) / len(previous_volumes)
            
            # 检测弱化信号
            weakening_signals = {}
            
            # 1. 价格动能减弱
            price_momentum_change = (recent_avg_price - previous_avg_price) / previous_avg_price
            weakening_signals['price_momentum_weak'] = price_momentum_change < 0.01  # 涨幅小于1%
            
            # 2. 成交量萎缩
            volume_change = (recent_avg_volume - previous_avg_volume) / previous_avg_volume
            weakening_signals['volume_shrinking'] = volume_change < -0.2  # 成交量减少20%以上
            
            # 3. 价格波动性增加（不稳定）
            recent_volatility = self._calculate_volatility(recent_prices)
            previous_volatility = self._calculate_volatility(previous_prices)
            volatility_increase = recent_volatility > previous_volatility * 1.5
            weakening_signals['volatility_increase'] = volatility_increase
            
            # 4. 连续小幅下跌
            consecutive_declines = 0
            for i in range(1, len(recent_data)):
                if recent_data[i].close < recent_data[i-1].close:
                    consecutive_declines += 1
                else:
                    consecutive_declines = 0
            weakening_signals['consecutive_declines'] = consecutive_declines >= 3
            
            # 综合判断
            weakening_count = sum(weakening_signals.values())
            is_weakening = weakening_count >= 2  # 至少2个弱化信号
            
            analysis_details = {
                'weakening_signals': weakening_signals,
                'weakening_count': weakening_count,
                'is_weakening': is_weakening,
                'price_momentum_change': price_momentum_change,
                'volume_change': volume_change,
                'recent_volatility': recent_volatility,
                'previous_volatility': previous_volatility,
                'consecutive_declines': consecutive_declines
            }
            
            return is_weakening, analysis_details
            
        except Exception as e:
            raise CalculationException(f"趋势弱化检测失败: {str(e)}")
    
    def _calculate_volatility(self, prices: List[float]) -> float:
        """计算价格波动率
        
        Args:
            prices: 价格列表
            
        Returns:
            float: 波动率
        """
        if len(prices) < 2:
            return 0.0
        
        # 计算日收益率
        returns = []
        for i in range(1, len(prices)):
            daily_return = (prices[i] - prices[i-1]) / prices[i-1]
            returns.append(daily_return)
        
        # 计算标准差作为波动率
        if len(returns) == 0:
            return 0.0
        
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        volatility = variance ** 0.5
        
        return volatility
    
    def check_comprehensive_exit_conditions(self, symbol: str, current_data: MarketData,
                                          trade: Trade, data_history: List[MarketData]) -> Tuple[bool, Optional[Signal]]:
        """综合检查所有退出条件
        
        整合时间管理、趋势管理和风险管理的所有退出条件。
        
        Args:
            symbol: 股票代码
            current_data: 当前市场数据
            trade: 当前交易记录
            data_history: 历史数据列表
            
        Returns:
            Tuple[bool, Optional[Signal]]: (是否应该退出, 退出信号)
        """
        try:
            current_price = current_data.close
            entry_price = trade.entry_price
            entry_date = trade.entry_date
            current_date = current_data.date
            
            # 计算当前盈亏
            current_profit_pct = (current_price - entry_price) / entry_price
            
            # 1. 首先检查风险管理信号（优先级最高）
            risk_signal = self.generate_risk_management_signal(
                symbol, current_data, trade, data_history
            )
            if risk_signal:
                return True, risk_signal
            
            # 2. 检查基于时间的退出条件
            time_exit, time_reason = self.check_time_based_exit(
                entry_date, current_date, current_profit_pct
            )
            if time_exit:
                return True, Signal(
                    symbol=symbol,
                    date=current_date,
                    signal_type=SignalType.SELL,
                    price=current_price,
                    strength=0.7,
                    reason=time_reason,
                    conditions_met={'time_based_exit': True}
                )
            
            # 3. 检查趋势弱化
            if len(data_history) >= 10:
                is_weakening, weakening_details = self.detect_trend_weakening(data_history)
                
                if is_weakening:
                    # 根据盈利情况决定是否因趋势弱化而退出
                    if current_profit_pct > 0.10:  # 盈利超过10%，趋势弱化时可以考虑退出
                        weakening_reasons = []
                        for signal_name, triggered in weakening_details['weakening_signals'].items():
                            if triggered:
                                weakening_reasons.append(signal_name)
                        
                        reason = (f"趋势弱化退出({weakening_details['weakening_count']}个信号): "
                                 f"{', '.join(weakening_reasons)} "
                                 f"(盈利{current_profit_pct:.2%})")
                        
                        return True, Signal(
                            symbol=symbol,
                            date=current_date,
                            signal_type=SignalType.SELL,
                            price=current_price,
                            strength=0.6,
                            reason=reason,
                            conditions_met={'trend_weakening': True, **weakening_details['weakening_signals']}
                        )
            
            # 没有触发任何退出条件
            return False, None
            
        except Exception as e:
            raise CalculationException(f"综合退出条件检查失败: {str(e)}")
    
    def get_exit_recommendation(self, symbol: str, current_data: MarketData,
                               trade: Trade, data_history: List[MarketData]) -> Dict:
        """获取退出建议
        
        提供详细的退出分析和建议，不直接生成信号。
        
        Args:
            symbol: 股票代码
            current_data: 当前市场数据
            trade: 当前交易记录
            data_history: 历史数据列表
            
        Returns:
            Dict: 退出建议和分析
        """
        try:
            current_price = current_data.close
            entry_price = trade.entry_price
            entry_date = trade.entry_date
            current_date = current_data.date
            
            # 计算基本指标
            current_profit_pct = (current_price - entry_price) / entry_price
            holding_days = self._calculate_holding_days(entry_date, current_date)
            
            # 获取风险状态
            risk_status = self.get_risk_status(
                symbol, current_price, entry_price, entry_date, current_date
            )
            
            # 检查时间因素
            dynamic_max_days = self.get_dynamic_max_holding_days(current_profit_pct)
            time_pressure = holding_days / dynamic_max_days
            
            # 检查趋势状态
            trend_analysis = {}
            if len(data_history) >= 20:
                _, reversal_details = self.detect_trend_reversal_with_profit(
                    data_history, current_profit_pct
                )
                trend_analysis['reversal'] = reversal_details
            
            if len(data_history) >= 10:
                _, weakening_details = self.detect_trend_weakening(data_history)
                trend_analysis['weakening'] = weakening_details
            
            # 生成建议
            recommendation = self._generate_exit_recommendation(
                current_profit_pct, holding_days, dynamic_max_days, 
                risk_status, trend_analysis
            )
            
            return {
                'symbol': symbol,
                'current_date': current_date,
                'current_profit_pct': current_profit_pct,
                'holding_days': holding_days,
                'dynamic_max_days': dynamic_max_days,
                'time_pressure': time_pressure,
                'risk_status': risk_status,
                'trend_analysis': trend_analysis,
                'recommendation': recommendation
            }
            
        except Exception as e:
            raise CalculationException(f"退出建议生成失败: {str(e)}")
    
    def _generate_exit_recommendation(self, profit_pct: float, holding_days: int,
                                    max_days: int, risk_status: Dict, 
                                    trend_analysis: Dict) -> Dict:
        """生成退出建议
        
        Args:
            profit_pct: 盈利百分比
            holding_days: 持有天数
            max_days: 最大持有天数
            risk_status: 风险状态
            trend_analysis: 趋势分析
            
        Returns:
            Dict: 退出建议
        """
        recommendation = {
            'action': 'hold',  # hold, consider_exit, exit
            'urgency': 'low',  # low, medium, high
            'reasons': [],
            'score': 0  # 0-100, 越高越建议退出
        }
        
        # 基于风险状态评分
        if risk_status['stop_loss_triggered'] or risk_status['take_profit_triggered']:
            recommendation['action'] = 'exit'
            recommendation['urgency'] = 'high'
            recommendation['score'] = 100
            recommendation['reasons'].append('触发止损或止盈')
            return recommendation
        
        # 基于盈利情况评分
        if profit_pct < -0.03:  # 亏损超过3%
            recommendation['score'] += 30
            recommendation['reasons'].append('亏损较大')
        elif profit_pct > 0.15:  # 盈利超过15%
            recommendation['score'] += 20
            recommendation['reasons'].append('盈利丰厚，可考虑获利了结')
        
        # 基于时间压力评分
        time_pressure = holding_days / max_days
        if time_pressure > 0.8:
            recommendation['score'] += 25
            recommendation['reasons'].append('接近最大持有期')
        elif time_pressure > 0.6:
            recommendation['score'] += 15
            recommendation['reasons'].append('持有时间较长')
        
        # 基于趋势分析评分
        if 'reversal' in trend_analysis and trend_analysis['reversal']['is_reversal']:
            recommendation['score'] += 35
            recommendation['reasons'].append('检测到趋势反转')
        
        if 'weakening' in trend_analysis and trend_analysis['weakening']['is_weakening']:
            recommendation['score'] += 20
            recommendation['reasons'].append('趋势显示弱化')
        
        # 确定最终建议
        if recommendation['score'] >= 70:
            recommendation['action'] = 'exit'
            recommendation['urgency'] = 'high'
        elif recommendation['score'] >= 50:
            recommendation['action'] = 'consider_exit'
            recommendation['urgency'] = 'medium'
        elif recommendation['score'] >= 30:
            recommendation['action'] = 'consider_exit'
            recommendation['urgency'] = 'low'
        
        return recommendation