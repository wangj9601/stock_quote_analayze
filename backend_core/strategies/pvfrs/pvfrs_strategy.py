"""
PVFRS (均值频率共振) 交易策略回测系统
基于量价频三维共振演化策略的完整实现
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging
from dataclasses import dataclass
from enum import Enum

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SignalType(Enum):
    """信号类型枚举"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"

@dataclass
class Signal:
    """交易信号数据类"""
    date: str
    signal_type: SignalType
    price: float
    reason: str
    strength: float  # 信号强度 0-1
    conditions_met: Dict[str, bool]  # 满足的条件

@dataclass
class Trade:
    """交易记录数据类"""
    entry_date: str
    exit_date: Optional[str]
    entry_price: float
    exit_price: Optional[float]
    quantity: int
    position_size: float
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    exit_reason: Optional[str] = None

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
    equity_curve: pd.DataFrame

class PVFRSStrategy:
    """PVFRS交易策略实现"""
    
    def __init__(self, params: Dict = None):
        """初始化策略参数"""
        self.params = params or self._get_default_params()
        self.signal_detector = PVFRSSignalDetector(self.params)
        self.divergence_detector = DivergenceDetector()
        self.momentum_confirmator = MomentumConfirmator()
        
    def _get_default_params(self) -> Dict:
        """获取默认策略参数"""
        return {
            # 高效率上涨严格条件
            'buy_macro_displacement_min': 0,              # Δ > 0
            'buy_instant_deviation_min': 0,               # d20 > d  
            'buy_rising_days_advantage': True,            # Z > F
            'buy_efficiency_min': 0,                      # m20 > m
            
            # 增强条件
            'buy_bias_min': 0.02,                         # bias > 2%
            'buy_relative_displacement_min': 0.05,         # Δ/d > 5%
            'buy_consecutive_days': 3,                    # 连续3天确认
            
            # 卖出条件
            'sell_bias_max': 0.08,                        # bias > 8%
            'sell_instant_deviation_max': 0.05,           # d20 - d > 5%
            'sell_price_volume_divergence': True,         # 价涨量缩
            
            # 风控参数
            'stop_loss': -0.10,                           # 止损：-10%
            'take_profit': 0.20,                          # 止盈：+20%
            'max_position_size': 0.1,                      # 最大仓位：10%
            'max_holding_days': 30,                        # 最大持有天数
        }
    
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        """生成交易信号"""
        signals = []
        
        # 检测高效率上涨信号
        buy_signals = self.signal_detector.detect_high_efficiency_uptrend(data)
        
        # 检测趋势反转和卖出信号
        sell_signals = self.signal_detector.detect_trend_reversal(data)
        
        # 检测量价背离
        divergence_signals = self.divergence_detector.detect_price_volume_divergence(data)
        
        # 合并所有信号
        all_signals = buy_signals + sell_signals + divergence_signals
        
        # 按日期排序
        all_signals.sort(key=lambda x: x.date)
        
        return all_signals

class PVFRSSignalDetector:
    """PVFRS信号检测器"""
    
    def __init__(self, params: Dict):
        self.params = params
        
    def detect_high_efficiency_uptrend(self, data: pd.DataFrame) -> List[Signal]:
        """检测高效率上涨信号"""
        signals = []
        
        for i in range(20, len(data)):  # 从第20行开始，确保有足够历史数据
            current_row = data.iloc[i]
            date = current_row['date']
            
            # 检查三个维度的严格条件
            conditions_met = {}
            signal_strength = 0
            
            # 1. 价格维度条件
            macro_displacement = current_row['macro_displacement_delta']
            instant_deviation = current_row['instant_deviation']
            
            conditions_met['macro_displacement_positive'] = macro_displacement > self.params['buy_macro_displacement_min']
            conditions_met['instant_deviation_positive'] = instant_deviation > self.params['buy_instant_deviation_min']
            
            # 2. 频率维度条件
            rising_days = current_row['rising_days_z']
            falling_days = current_row['falling_days_f']
            conditions_met['rising_days_advantage'] = rising_days > falling_days
            
            # 3. 成交量维度条件
            efficiency = current_row['efficiency_m20_minus_m']
            conditions_met['efficiency_positive'] = efficiency > self.params['buy_efficiency_min']
            
            # 检查是否满足所有严格条件
            strict_conditions_met = all([
                conditions_met['macro_displacement_positive'],
                conditions_met['instant_deviation_positive'],
                conditions_met['rising_days_advantage'],
                conditions_met['efficiency_positive']
            ])
            
            if not strict_conditions_met:
                continue
                
            # 检查增强条件
            bias = current_row['bias']
            ma20 = current_row['ma20_d']
            relative_displacement = macro_displacement / ma20 if ma20 > 0 else 0
            
            conditions_met['bias_sufficient'] = bias > self.params['buy_bias_min']
            conditions_met['relative_displacement_sufficient'] = relative_displacement > self.params['buy_relative_displacement_min']
            
            # 计算信号强度
            strength_factors = [
                conditions_met['bias_sufficient'],
                conditions_met['relative_displacement_sufficient']
            ]
            signal_strength = sum(strength_factors) / len(strength_factors)
            
            # 连续确认检查
            consecutive_days = self._check_consecutive_uptrend(data, i)
            conditions_met['consecutive_confirmation'] = consecutive_days >= self.params['buy_consecutive_days']
            
            if conditions_met['consecutive_confirmation']:
                signal_strength = min(1.0, signal_strength + 0.2)
            
            # 生成买入信号
            reason = f"高效率上涨确认: Δ={macro_displacement:.4f}, 偏离={instant_deviation:.4f}, Z>F({rising_days}>{falling_days}), 效率={efficiency:.4f}"
            
            signal = Signal(
                date=date,
                signal_type=SignalType.BUY,
                price=current_row['close'],
                reason=reason,
                strength=signal_strength,
                conditions_met=conditions_met
            )
            
            signals.append(signal)
            
        return signals
    
    def detect_trend_reversal(self, data: pd.DataFrame) -> List[Signal]:
        """检测趋势反转信号"""
        signals = []
        
        for i in range(20, len(data)):
            current_row = data.iloc[i]
            date = current_row['date']
            
            conditions_met = {}
            reversal_count = 0
            
            # 1. 价格维度反转
            instant_deviation = current_row['instant_deviation']
            macro_displacement = current_row['macro_displacement_delta']
            
            if instant_deviation < 0:
                conditions_met['price_reversal'] = True
                reversal_count += 1
            else:
                conditions_met['price_reversal'] = False
                
            if macro_displacement < 0:
                conditions_met['macro_reversal'] = True
                reversal_count += 1
            else:
                conditions_met['macro_reversal'] = False
            
            # 2. 频率维度反转
            rising_days = current_row['rising_days_z']
            falling_days = current_row['falling_days_f']
            
            if falling_days > rising_days:
                conditions_met['frequency_reversal'] = True
                reversal_count += 1
            else:
                conditions_met['frequency_reversal'] = False
            
            # 3. 成交量维度反转
            efficiency = current_row['efficiency_m20_minus_m']
            
            if efficiency < 0:
                conditions_met['volume_reversal'] = True
                reversal_count += 1
            else:
                conditions_met['volume_reversal'] = False
            
            # 超买检查
            bias = current_row['bias']
            if bias > self.params['sell_bias_max']:
                conditions_met['overbought'] = True
                reversal_count += 1
            else:
                conditions_met['overbought'] = False
            
            if instant_deviation > self.params['sell_instant_deviation_max']:
                conditions_met['overextended'] = True
                reversal_count += 1
            else:
                conditions_met['overextended'] = False
            
            # 如果满足2个或以上反转条件，生成卖出信号
            if reversal_count >= 2:
                signal_strength = min(1.0, reversal_count / 6.0)
                
                reason_parts = []
                if conditions_met['price_reversal']:
                    reason_parts.append("价格跌破均线")
                if conditions_met['macro_reversal']:
                    reason_parts.append("宏观位移转负")
                if conditions_met['frequency_reversal']:
                    reason_parts.append("下跌频率占优")
                if conditions_met['volume_reversal']:
                    reason_parts.append("成交量萎缩")
                if conditions_met['overbought']:
                    reason_parts.append("超买")
                if conditions_met['overextended']:
                    reason_parts.append("偏离过远")
                
                reason = "趋势反转: " + ", ".join(reason_parts)
                
                signal = Signal(
                    date=date,
                    signal_type=SignalType.SELL,
                    price=current_row['close'],
                    reason=reason,
                    strength=signal_strength,
                    conditions_met=conditions_met
                )
                
                signals.append(signal)
                
        return signals
    
    def _check_consecutive_uptrend(self, data: pd.DataFrame, current_index: int) -> int:
        """检查连续上涨天数"""
        consecutive_days = 0
        
        for i in range(current_index, max(0, current_index - 10), -1):
            if i < 20:  # 确保有足够数据
                break
                
            row = data.iloc[i]
            
            # 检查是否满足高效率上涨的基本条件
            if (row['macro_displacement_delta'] > 0 and 
                row['instant_deviation'] > 0 and
                row['rising_days_z'] > row['falling_days_f'] and
                row['efficiency_m20_minus_m'] > 0):
                consecutive_days += 1
            else:
                break
                
        return consecutive_days

class DivergenceDetector:
    """量价背离检测器"""
    
    def detect_price_volume_divergence(self, data: pd.DataFrame) -> List[Signal]:
        """检测价涨量缩背离"""
        signals = []
        
        for i in range(20, len(data)):
            current_row = data.iloc[i]
            date = current_row['date']
            
            # 价涨量缩检测
            price_rising = current_row['instant_deviation'] > 0
            volume_shrinking = current_row['efficiency_m20_minus_m'] < 0
            
            if price_rising and volume_shrinking:
                # 检查是否持续了多天
                divergence_days = self._check_divergence_duration(data, i)
                
                if divergence_days >= 2:  # 连续2天以上
                    signal_strength = min(1.0, divergence_days / 5.0)
                    
                    reason = f"价涨量缩背离持续{divergence_days}天"
                    
                    signal = Signal(
                        date=date,
                        signal_type=SignalType.SELL,
                        price=current_row['close'],
                        reason=reason,
                        strength=signal_strength,
                        conditions_met={'price_volume_divergence': True}
                    )
                    
                    signals.append(signal)
                    
        return signals
    
    def _check_divergence_duration(self, data: pd.DataFrame, current_index: int) -> int:
        """检查背离持续时间"""
        duration = 0
        
        for i in range(current_index, max(0, current_index - 5), -1):
            if i < 20:
                break
                
            row = data.iloc[i]
            
            if (row['instant_deviation'] > 0 and 
                row['efficiency_m20_minus_m'] < 0):
                duration += 1
            else:
                break
                
        return duration

class MomentumConfirmator:
    """动能确认器"""
    
    def confirm_momentum(self, data: pd.DataFrame, window: int = 3) -> Dict:
        """确认动能连续性"""
        momentum_status = {}
        
        for i in range(window, len(data)):
            date = data.iloc[i]['date']
            
            # 检查连续window天的动能
            momentum_score = 0
            
            for j in range(window):
                row_index = i - j
                if row_index < 20:
                    break
                    
                row = data.iloc[row_index]
                
                # 计算当日动能得分
                daily_score = 0
                
                if row['macro_displacement_delta'] > 0:
                    daily_score += 0.25
                if row['instant_deviation'] > 0:
                    daily_score += 0.25
                if row['rising_days_z'] > row['falling_days_f']:
                    daily_score += 0.25
                if row['efficiency_m20_minus_m'] > 0:
                    daily_score += 0.25
                    
                momentum_score += daily_score
            
            # 平均动能得分
            avg_momentum = momentum_score / window
            momentum_status[date] = avg_momentum
            
        return momentum_status

class PVFRSBacktestEngine:
    """PVFRS回测引擎"""
    
    def __init__(self, strategy: PVFRSStrategy, initial_capital: float = 100000, market_type: str = "CN"):
        self.strategy = strategy
        self.params = strategy.params
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.market_type = market_type
        self.position = None  # 当前持仓
        self.trades = []
        self.equity_curve = []
        
    def run_backtest(self, data: pd.DataFrame) -> BacktestResult:
        """执行回测"""
        logger.info(f"开始回测，数据范围: {data['date'].min()} 到 {data['date'].max()}")
        
        # 生成交易信号
        signals = self.strategy.generate_signals(data)
        logger.info(f"生成 {len(signals)} 个交易信号")
        
        # 初始化权益曲线
        self.equity_curve = []
        self.current_capital = self.initial_capital
        self.trades = []
        self.position = None
        
        # 模拟交易
        for i, row in data.iterrows():
            date = row['date']
            current_price = row['close']
            
            # 更新权益曲线
            if self.position:
                # 计算当前权益
                unrealized_pnl = (current_price - self.position['entry_price']) * self.position['quantity']
                current_equity = self.current_capital + unrealized_pnl
            else:
                current_equity = self.current_capital
                
            self.equity_curve.append({
                'date': date,
                'equity': current_equity,
                'position': 1 if self.position else 0,
                'price': current_price
            })
            
            # 检查当日的信号
            daily_signals = [s for s in signals if s.date == date]
            
            for signal in daily_signals:
                if signal.signal_type == SignalType.BUY and not self.position:
                    # 买入信号
                    self._execute_buy(signal, row)
                elif signal.signal_type == SignalType.SELL and self.position:
                    # 卖出信号
                    self._execute_sell(signal, row)
            
            # 检查止损止盈
            if self.position:
                self._check_risk_management(row)
        
        # 如果还有持仓，最后一天平仓
        if self.position:
            last_row = data.iloc[-1]
            self._close_position(last_row['date'], last_row['close'], "回测结束")
        
        # 计算回测结果
        result = self._calculate_results()
        
        logger.info(f"回测完成，总收益率: {result.total_return:.2%}")
        
        return result
    
    def _execute_buy(self, signal: Signal, row: pd.Series):
        """执行买入"""
        entry_price = row['close']
        position_size = self.current_capital * self.params['max_position_size']
        quantity = int(position_size / entry_price)
        
        if quantity > 0:
            self.position = {
                'entry_date': signal.date,
                'entry_price': entry_price,
                'quantity': quantity,
                'position_size': position_size,
                'signal': signal
            }
            
            logger.info(f"买入: {signal.date}, 价格: {entry_price:.2f}, 数量: {quantity}, 原因: {signal.reason}")
    
    def _execute_sell(self, signal: Signal, row: pd.Series):
        """执行卖出"""
        if self.position and self._can_sell(signal.date):
            self._close_position(signal.date, row['close'], signal.reason)
    
    def _close_position(self, exit_date: str, exit_price: float, reason: str):
        """平仓"""
        if not self.position:
            return
            
        entry_price = self.position['entry_price']
        quantity = self.position['quantity']
        position_size = self.position['position_size']
        
        # 计算盈亏
        pnl = (exit_price - entry_price) * quantity
        pnl_percent = pnl / position_size
        
        # 更新资金
        self.current_capital += pnl
        
        # 记录交易
        trade = Trade(
            entry_date=self.position['entry_date'],
            exit_date=exit_date,
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=quantity,
            position_size=position_size,
            pnl=pnl,
            pnl_percent=pnl_percent,
            exit_reason=reason
        )
        
        self.trades.append(trade)
        
        logger.info(f"卖出: {exit_date}, 价格: {exit_price:.2f}, 盈亏: {pnl:.2f} ({pnl_percent:.2%}), 原因: {reason}")
        
        # 清空持仓
        self.position = None
    
    def _check_risk_management(self, row: pd.Series):
        """检查风险管理"""
        if not self.position:
            return

        # A股 T+1：买入当日不允许卖出（止损/止盈/强制平仓也一样）
        if not self._can_sell(row['date']):
            return
            
        entry_price = self.position['entry_price']
        current_price = row['close']
        pnl_percent = (current_price - entry_price) / entry_price
        
        # 止损
        if pnl_percent <= self.params['stop_loss']:
            self._close_position(row['date'], current_price, f"止损: {pnl_percent:.2%}")
        
        # 止盈
        elif pnl_percent >= self.params['take_profit']:
            self._close_position(row['date'], current_price, f"止盈: {pnl_percent:.2%}")
        
        # 最大持有天数
        elif self._get_holding_days(row['date']) >= self.params['max_holding_days']:
            self._close_position(row['date'], current_price, f"最大持有天数: {self.params['max_holding_days']}天")

    def _can_sell(self, current_date: str) -> bool:
        """是否允许卖出（A股 T+1：买入当日不可卖出）"""
        if not self.position:
            return False
        if self.market_type != 'CN':
            return True

        # 日期字符串按 YYYY-MM-DD 可直接比较
        entry_date = self.position.get('entry_date')
        if not entry_date:
            return True
        if str(current_date)[:10] <= str(entry_date)[:10]:
            return False
        return True
    
    def _get_holding_days(self, current_date: str) -> int:
        """计算持有天数"""
        if not self.position:
            return 0
            
        entry_date = datetime.strptime(self.position['entry_date'], '%Y-%m-%d')
        current_dt = datetime.strptime(current_date, '%Y-%m-%d')
        
        return (current_dt - entry_date).days
    
    def _calculate_results(self) -> BacktestResult:
        """计算回测结果"""
        if not self.trades:
            return BacktestResult(
                initial_capital=self.initial_capital,
                final_capital=self.current_capital,
                total_return=0,
                annual_return=0,
                max_drawdown=0,
                sharpe_ratio=0,
                win_rate=0,
                profit_factor=0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                avg_holding_period=0,
                trades=[],
                equity_curve=pd.DataFrame(self.equity_curve)
            )
        
        # 基本统计
        total_trades = len(self.trades)
        winning_trades = len([t for t in self.trades if t.pnl > 0])
        losing_trades = total_trades - winning_trades
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        # 收益统计
        total_return = (self.current_capital - self.initial_capital) / self.initial_capital
        
        # 计算年化收益率
        if len(self.equity_curve) > 1:
            start_date = datetime.strptime(self.equity_curve[0]['date'], '%Y-%m-%d')
            end_date = datetime.strptime(self.equity_curve[-1]['date'], '%Y-%m-%d')
            years = (end_date - start_date).days / 365.25
            annual_return = (self.current_capital / self.initial_capital) ** (1/years) - 1 if years > 0 else 0
        else:
            annual_return = 0
        
        # 计算最大回撤
        equity_series = pd.DataFrame(self.equity_curve)['equity']
        rolling_max = equity_series.expanding().max()
        drawdown = (equity_series - rolling_max) / rolling_max
        max_drawdown = drawdown.min()
        
        # 计算夏普比率
        if len(self.equity_curve) > 1:
            returns = equity_series.pct_change().dropna()
            sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        else:
            sharpe_ratio = 0
        
        # 计算盈亏比
        total_profit = sum([t.pnl for t in self.trades if t.pnl > 0])
        total_loss = abs(sum([t.pnl for t in self.trades if t.pnl < 0]))
        profit_factor = total_profit / total_loss if total_loss > 0 else 0
        
        # 计算平均持有期
        holding_periods = []
        for trade in self.trades:
            if trade.exit_date and trade.entry_date:
                entry_date = datetime.strptime(trade.entry_date, '%Y-%m-%d')
                exit_date = datetime.strptime(trade.exit_date, '%Y-%m-%d')
                holding_periods.append((exit_date - entry_date).days)
        
        avg_holding_period = np.mean(holding_periods) if holding_periods else 0
        
        return BacktestResult(
            initial_capital=self.initial_capital,
            final_capital=self.current_capital,
            total_return=total_return,
            annual_return=annual_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            avg_holding_period=avg_holding_period,
            trades=self.trades,
            equity_curve=pd.DataFrame(self.equity_curve)
        )

# 全局参数引用
params = PVFRSStrategy()._get_default_params()
