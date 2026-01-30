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
        self.divergence_detector = DivergenceDetector(self.params)
        self.momentum_confirmator = MomentumConfirmator()
        
    def _get_default_params(self) -> Dict:
        """获取默认策略参数"""
        return {
            # PVFRS四维度条件
            'buy_macro_displacement_min': 0,
            'buy_instant_deviation_min': 0,
            'buy_rising_days_advantage': True,
            'buy_efficiency_min': 0,
            
            # 增强条件
            'buy_bias_min': 0.02,
            'buy_relative_displacement_min': 0.05,
            'buy_consecutive_days': 2,
            'buy_price_above_ma5': False,
            'buy_ma5_above_ma20': False,
            
            # 买点条件（与两图及详细说明一致）
            'buy_ratio_d20_max': 0.5,                    # Δ/d₂₀ 上限，0 表示不启用
            'buy_exclude_sideways': True,                 # 横盘(Δ≈0)不参与买点
            
            # 卖出条件 - 简单有效
            'sell_below_ma20': True,                      # 收盘价跌破20日均线卖出
            'stop_loss': -0.06,                           # 止损-6%
            'take_profit': 0.25,                          # 止盈25%
            'max_position_size': 0.1,
            'max_holding_days': 45,
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
        """检测高效率上涨信号 - 提高质量"""
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
            
            conditions_met['macro_displacement_positive'] = macro_displacement > self.params.get('buy_macro_displacement_min', 0)
            conditions_met['instant_deviation_sufficient'] = instant_deviation > self.params.get('buy_instant_deviation_min', 0)
            
            # 2. 频率维度条件（买点权重 F > Z）
            rising_days = current_row['rising_days_z']
            falling_days = current_row['falling_days_f']
            conditions_met['rising_days_advantage'] = falling_days > rising_days
            
            # 3. 成交量维度条件
            efficiency = current_row['efficiency_m20_minus_m']
            conditions_met['efficiency_positive'] = efficiency > self.params.get('buy_efficiency_min', 0)
            
            # 检查是否满足所有严格条件
            strict_conditions_met = all([
                conditions_met['macro_displacement_positive'],
                conditions_met['instant_deviation_sufficient'],
                conditions_met['rising_days_advantage'],
                conditions_met['efficiency_positive']
            ])
            
            if not strict_conditions_met:
                continue
            
            # 新增：均线趋势确认（可选，默认不启用）
            current_price = current_row['close']
            ma5 = current_row.get('ma5', current_price)
            ma20 = current_row.get('ma20_d', current_price)
            
            # 价格必须在5日均线之上（默认不启用）
            if self.params.get('buy_price_above_ma5', False):
                conditions_met['price_above_ma5'] = current_price > ma5
                if not conditions_met['price_above_ma5']:
                    continue
            
            # 5日均线必须在20日均线之上（默认不启用）
            if self.params.get('buy_ma5_above_ma20', False):
                conditions_met['ma5_above_ma20'] = ma5 > ma20
                if not conditions_met['ma5_above_ma20']:
                    continue
                
            # 检查增强条件
            bias = current_row['bias']
            ma20_val = current_row['ma20_d']
            relative_displacement = macro_displacement / ma20_val if ma20_val > 0 else 0
            
            conditions_met['bias_sufficient'] = bias > self.params.get('buy_bias_min', 0.02)
            conditions_met['relative_displacement_sufficient'] = relative_displacement > self.params.get('buy_relative_displacement_min', 0.05)
            
            # 必须满足增强条件
            if not (conditions_met['bias_sufficient'] and conditions_met['relative_displacement_sufficient']):
                continue
            
            # 计算信号强度
            strength_factors = [
                conditions_met['bias_sufficient'],
                conditions_met['relative_displacement_sufficient'],
                conditions_met.get('price_above_ma5', True),
                conditions_met.get('ma5_above_ma20', True)
            ]
            signal_strength = sum(strength_factors) / len(strength_factors)
            
            # 连续确认检查
            consecutive_days = self._check_consecutive_uptrend(data, i)
            conditions_met['consecutive_confirmation'] = consecutive_days >= self.params.get('buy_consecutive_days', 2)
            
            if not conditions_met['consecutive_confirmation']:
                continue
            
            signal_strength = min(1.0, signal_strength + 0.2)
            
            # 生成买入信号
            reason = f"高质量上涨: Δ={macro_displacement:.4f}, 偏离={instant_deviation:.4f}, F>Z({falling_days}>{rising_days}), 效率={efficiency:.4f}, bias={bias:.2%}"
            
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
    
    def detect_trend_reversal(self, data: pd.DataFrame, current_profit_pct: float = 0) -> List[Signal]:
        """检测趋势反转信号
        
        Args:
            data: 行情数据
            current_profit_pct: 当前持仓盈利百分比，用于动态调整反转条件
        """
        signals = []
        
        # 根据盈利情况动态调整需要的反转条件数
        if current_profit_pct < self.params['profit_stage1']:  # 盈利<15%
            required_conditions = self.params['sell_reversal_conditions_low_profit']  # 需要3个条件
        else:  # 盈利>=15%
            required_conditions = self.params['sell_reversal_conditions_high_profit']  # 需要2个条件
        
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
            
            # 根据盈利情况动态判断是否满足反转条件
            if reversal_count >= required_conditions:
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
                
                reason = f"趋势反转({reversal_count}个条件): " + ", ".join(reason_parts)
                
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
    
    def __init__(self, params: Dict = None):
        """初始化背离检测器"""
        self.params = params or {}
    
    def detect_price_volume_divergence(self, data: pd.DataFrame) -> List[Signal]:
        """检测价涨量缩背离"""
        signals = []
        
        # 获取背离天数参数，如果没有则使用默认值3
        divergence_days_required = self.params.get('sell_divergence_days', 3)
        
        for i in range(20, len(data)):
            current_row = data.iloc[i]
            date = current_row['date']
            
            # 价涨量缩检测
            price_rising = current_row['instant_deviation'] > 0
            volume_shrinking = current_row['efficiency_m20_minus_m'] < 0
            
            if price_rising and volume_shrinking:
                # 检查是否持续了多天
                divergence_days = self._check_divergence_duration(data, i)
                
                # 从2天提升到3天
                if divergence_days >= divergence_days_required:
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
        
        # 从2天提升到3天
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
        self.highest_price = 0  # 记录持仓期间最高价，用于移动止盈
        
    def run_backtest(self, data: pd.DataFrame) -> BacktestResult:
        """执行回测 - 完全重构"""
        logger.info(f"开始回测，数据范围: {data['date'].min()} 到 {data['date'].max()}")
        
        # 生成买入信号
        buy_signals = self.strategy.signal_detector.detect_high_efficiency_uptrend(data)
        logger.info(f"生成 {len(buy_signals)} 个买入信号")
        
        # 初始化
        self.equity_curve = []
        self.current_capital = self.initial_capital
        self.trades = []
        self.position = None
        self.highest_price = 0
        self.last_trade_date = None
        self.ma_cross_down_days = 0  # 均线死叉天数
        
        # 模拟交易
        for i, row in data.iterrows():
            date = row['date']
            current_price = row['close']
            ma5 = row.get('ma5', current_price)
            ma20 = row.get('ma20_d', current_price)
            
            # 更新权益曲线
            if self.position:
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
            
            # 检查是否已经在今天交易过
            already_traded_today = (self.last_trade_date == date)
            
            # === 卖出逻辑 - 简单有效 ===
            if self.position and self._can_sell(date) and not already_traded_today:
                should_sell = False
                sell_reason = ""
                
                entry_price = self.position['entry_price']
                profit_pct = (current_price - entry_price) / entry_price
                
                # 卖出条件1：收盘价跌破20日均线
                if self.params.get('sell_below_ma20', True) and current_price < ma20:
                    should_sell = True
                    sell_reason = f"收盘价{current_price:.2f}跌破20日均线{ma20:.2f}"
                
                # 卖出条件2：止损
                if not should_sell and profit_pct <= self.params.get('stop_loss', -0.06):
                    should_sell = True
                    sell_reason = f"止损: {profit_pct:.2%}"
                
                # 卖出条件3：止盈
                if not should_sell and profit_pct >= self.params.get('take_profit', 0.25):
                    should_sell = True
                    sell_reason = f"止盈: {profit_pct:.2%}"
                
                # 卖出条件4：最大持有天数
                if not should_sell:
                    holding_days = self._get_holding_days(date)
                    max_days = self.params.get('max_holding_days', 45)
                    if holding_days >= max_days:
                        should_sell = True
                        sell_reason = f"最大持有{holding_days}天 (盈利{profit_pct:.2%})"
                
                # 执行卖出
                if should_sell:
                    self._close_position(date, current_price, sell_reason)
                    self.last_trade_date = date
                    already_traded_today = True  # 更新标志，防止同一天再买入
            
            # === 买入逻辑 ===
            if not self.position and not already_traded_today:
                daily_buy_signals = [s for s in buy_signals if s.date == date]
                if daily_buy_signals:
                    signal = daily_buy_signals[0]
                    self._execute_buy(signal, row)
                    self.last_trade_date = date
        
        # 最后一天平仓
        if self.position:
            last_row = data.iloc[-1]
            self._close_position(last_row['date'], last_row['close'], "回测结束")
        
        result = self._calculate_results()
        logger.info(f"回测完成，总收益率: {result.total_return:.2%}")
        
        return result
    
    def _execute_buy(self, signal: Signal, row: pd.Series):
        """执行买入"""
        entry_price = row['close']
        position_size = self.current_capital * self.params.get('max_position_size', 0.1)
        quantity = int(position_size / entry_price)
        
        if quantity > 0:
            self.position = {
                'entry_date': signal.date,
                'entry_price': entry_price,
                'quantity': quantity,
                'initial_quantity': quantity,
                'position_size': position_size,
                'signal': signal,
                'highest_profit': 0  # 记录最高盈利
            }
            
            # 初始化最高价
            self.highest_price = entry_price
            
            logger.info(f"买入: {signal.date}, 价格: {entry_price:.2f}, 数量: {quantity}, 原因: {signal.reason}")
    
    def _execute_sell(self, signal: Signal, row: pd.Series):
        """执行卖出 - 已废弃，逻辑已整合到run_backtest中"""
        pass
    
    def _calculate_reduce_percentage(self, signal: Signal, profit_pct: float) -> float:
        """计算减仓比例 - 已废弃"""
        pass
    
    def _reduce_position(self, exit_date: str, exit_price: float, reduce_pct: float, reason: str):
        """分批减仓 - 已废弃"""
        pass
    
    def _close_position(self, exit_date: str, exit_price: float, reason: str):
        """平仓"""
        if not self.position:
            return
            
        entry_price = self.position['entry_price']
        quantity = self.position['quantity']
        position_size = entry_price * quantity
        
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
        
        logger.info(f"清仓: {exit_date}, 价格: {exit_price:.2f}, 盈亏: {pnl:.2f} ({pnl_percent:.2%}), 原因: {reason}")
        
        # 清空持仓
        self.position = None
        self.highest_price = 0
    
    def _check_risk_management(self, row: pd.Series):
        """检查风险管理 - 已废弃，逻辑已整合到run_backtest中"""
        pass
    
    def _get_max_holding_days(self, profit_pct: float) -> int:
        """根据盈利情况动态调整最大持有天数"""
        base_days = self.params['max_holding_days_base']
        
        if profit_pct < 0:  # 亏损
            return int(base_days * 0.6)  # 27天
        elif profit_pct < 0.10:  # 盈利<10%
            return base_days  # 45天
        elif profit_pct < 0.20:  # 盈利10-20%
            return int(base_days * 1.3)  # 58天
        else:  # 盈利>20%
            return int(base_days * 1.6)  # 72天

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
