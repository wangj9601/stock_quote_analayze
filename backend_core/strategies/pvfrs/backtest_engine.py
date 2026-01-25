"""
PVFRS策略回测引擎实现
提供完整的回测功能，包括交易模拟、盈亏计算和回测报告生成
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import asdict
import copy

from .models import (
    MarketData, Signal, Trade, BacktestResult, SignalType,
    CalculationException, DataInsufficientException, ValidationException
)
from .interfaces import IBacktestEngine, IRiskManager
from .strategy_engine import StrategyEngine
from .config import PVFRSConfigManager
from .trade_recorder import TradeRecorder, PnLCalculator
from .backtest_report_generator import BacktestReportGenerator


class TradeSimulator:
    """交易模拟器
    
    使用历史数据模拟买入卖出操作，记录所有交易详情
    """
    
    def __init__(self, config: Dict):
        """初始化交易模拟器
        
        Args:
            config: 配置参数
        """
        self.config = config
        self.commission_rate = config.get('commission_rate', 0.0003)  # 手续费率
        self.slippage_rate = config.get('slippage_rate', 0.001)      # 滑点率
        self.max_position_size = config.get('max_position_size', 0.1)  # 最大仓位
        
        # 交易记录
        self.trades: List[Trade] = []
        self.open_positions: Dict[str, Trade] = {}  # 当前持仓
        self.cash = 0.0  # 当前现金
        self.total_value = 0.0  # 总资产价值
        
        # 交易统计
        self.total_commission = 0.0
        self.total_slippage = 0.0
    
    def reset(self, initial_capital: float):
        """重置模拟器状态
        
        Args:
            initial_capital: 初始资金
        """
        self.trades.clear()
        self.open_positions.clear()
        self.cash = initial_capital
        self.total_value = initial_capital
        self.total_commission = 0.0
        self.total_slippage = 0.0
    
    def simulate_buy_order(self, signal: Signal, available_cash: float) -> Optional[Trade]:
        """模拟买入订单
        
        Args:
            signal: 买入信号
            available_cash: 可用现金
            
        Returns:
            Optional[Trade]: 交易记录，如果无法执行则返回None
        """
        try:
            # 检查是否已有该股票的持仓
            if signal.symbol in self.open_positions:
                return None  # 已有持仓，不重复买入
            
            # 计算实际买入价格（考虑滑点）
            actual_price = signal.price * (1 + self.slippage_rate)
            
            # 计算可买入的仓位大小
            max_position_value = available_cash * self.max_position_size
            
            # 计算可买入数量（考虑手续费）
            commission_factor = 1 + self.commission_rate
            max_shares = int(max_position_value / (actual_price * commission_factor))
            
            if max_shares <= 0:
                return None  # 资金不足
            
            # 计算实际交易金额
            position_value = max_shares * actual_price
            commission = position_value * self.commission_rate
            total_cost = position_value + commission
            
            # 检查资金是否充足
            if total_cost > available_cash:
                return None  # 资金不足
            
            # 创建交易记录
            trade = Trade(
                symbol=signal.symbol,
                entry_date=signal.date,
                exit_date=None,
                entry_price=actual_price,
                exit_price=None,
                quantity=max_shares,
                position_size=position_value,
                pnl=None,
                pnl_percent=None,
                exit_reason=None
            )
            
            # 更新统计
            self.total_commission += commission
            self.total_slippage += max_shares * signal.price * self.slippage_rate
            
            return trade
            
        except Exception as e:
            raise CalculationException(f"模拟买入订单失败: {str(e)}")
    
    def simulate_sell_order(self, trade: Trade, signal: Signal) -> Trade:
        """模拟卖出订单
        
        Args:
            trade: 要卖出的交易记录
            signal: 卖出信号
            
        Returns:
            Trade: 更新后的交易记录
        """
        try:
            # 计算实际卖出价格（考虑滑点）
            actual_price = signal.price * (1 - self.slippage_rate)
            
            # 计算交易金额和手续费
            sell_value = trade.quantity * actual_price
            commission = sell_value * self.commission_rate
            net_proceeds = sell_value - commission
            
            # 计算盈亏
            total_cost = trade.position_size + (trade.position_size * self.commission_rate)
            pnl = net_proceeds - total_cost
            pnl_percent = pnl / total_cost if total_cost > 0 else 0.0
            
            # 更新交易记录
            completed_trade = Trade(
                symbol=trade.symbol,
                entry_date=trade.entry_date,
                exit_date=signal.date,
                entry_price=trade.entry_price,
                exit_price=actual_price,
                quantity=trade.quantity,
                position_size=trade.position_size,
                pnl=pnl,
                pnl_percent=pnl_percent,
                exit_reason=signal.reason
            )
            
            # 更新统计
            self.total_commission += commission
            self.total_slippage += trade.quantity * signal.price * self.slippage_rate
            
            return completed_trade
            
        except Exception as e:
            raise CalculationException(f"模拟卖出订单失败: {str(e)}")
    
    def calculate_position_value(self, symbol: str, current_price: float) -> float:
        """计算持仓价值
        
        Args:
            symbol: 股票代码
            current_price: 当前价格
            
        Returns:
            float: 持仓价值
        """
        if symbol not in self.open_positions:
            return 0.0
        
        trade = self.open_positions[symbol]
        return trade.quantity * current_price
    
    def get_portfolio_value(self, current_prices: Dict[str, float]) -> float:
        """计算投资组合总价值
        
        Args:
            current_prices: 当前价格字典
            
        Returns:
            float: 投资组合总价值
        """
        portfolio_value = self.cash
        
        for symbol, trade in self.open_positions.items():
            if symbol in current_prices:
                portfolio_value += self.calculate_position_value(symbol, current_prices[symbol])
        
        return portfolio_value
    
    def get_trading_summary(self) -> Dict:
        """获取交易汇总统计
        
        Returns:
            Dict: 交易汇总信息
        """
        completed_trades = [t for t in self.trades if t.exit_date is not None]
        
        return {
            'total_trades': len(completed_trades),
            'open_positions': len(self.open_positions),
            'total_commission': self.total_commission,
            'total_slippage': self.total_slippage,
            'winning_trades': len([t for t in completed_trades if t.pnl and t.pnl > 0]),
            'losing_trades': len([t for t in completed_trades if t.pnl and t.pnl < 0]),
            'total_pnl': sum([t.pnl for t in completed_trades if t.pnl is not None]),
            'avg_holding_period': self._calculate_avg_holding_period(completed_trades)
        }
    
    def _calculate_avg_holding_period(self, trades: List[Trade]) -> float:
        """计算平均持有期
        
        Args:
            trades: 已完成的交易列表
            
        Returns:
            float: 平均持有期（天数）
        """
        if not trades:
            return 0.0
        
        total_days = 0
        valid_trades = 0
        
        for trade in trades:
            if trade.entry_date and trade.exit_date:
                try:
                    entry_date = datetime.strptime(trade.entry_date, '%Y-%m-%d')
                    exit_date = datetime.strptime(trade.exit_date, '%Y-%m-%d')
                    holding_days = (exit_date - entry_date).days
                    total_days += holding_days
                    valid_trades += 1
                except ValueError:
                    continue  # 跳过日期格式错误的交易
        
        return total_days / valid_trades if valid_trades > 0 else 0.0


class RiskManager(IRiskManager):
    """风险管理器
    
    实现止损止盈、最大持有期和趋势反转检测
    """
    
    def __init__(self, config: Dict):
        """初始化风险管理器
        
        Args:
            config: 配置参数
        """
        self.config = config
        self.stop_loss_pct = config.get('stop_loss', -0.06)      # 止损比例
        self.take_profit_pct = config.get('take_profit', 0.25)   # 止盈比例
        self.max_holding_days = config.get('max_holding_days', 45)  # 最大持有天数
    
    def check_stop_loss(self, current_price: float, entry_price: float, 
                       stop_loss_pct: Optional[float] = None) -> bool:
        """检查止损条件
        
        Args:
            current_price: 当前价格
            entry_price: 入场价格
            stop_loss_pct: 止损比例（可选，使用配置默认值）
            
        Returns:
            bool: 是否触发止损
        """
        if stop_loss_pct is None:
            stop_loss_pct = self.stop_loss_pct
        
        if entry_price <= 0:
            return False
        
        price_change = (current_price - entry_price) / entry_price
        return price_change <= stop_loss_pct
    
    def check_take_profit(self, current_price: float, entry_price: float, 
                         take_profit_pct: Optional[float] = None) -> bool:
        """检查止盈条件
        
        Args:
            current_price: 当前价格
            entry_price: 入场价格
            take_profit_pct: 止盈比例（可选，使用配置默认值）
            
        Returns:
            bool: 是否触发止盈
        """
        if take_profit_pct is None:
            take_profit_pct = self.take_profit_pct
        
        if entry_price <= 0:
            return False
        
        price_change = (current_price - entry_price) / entry_price
        return price_change >= take_profit_pct
    
    def check_max_holding_period(self, entry_date: str, current_date: str, 
                                max_days: Optional[int] = None) -> bool:
        """检查最大持有期
        
        Args:
            entry_date: 入场日期
            current_date: 当前日期
            max_days: 最大持有天数（可选，使用配置默认值）
            
        Returns:
            bool: 是否超过最大持有期
        """
        if max_days is None:
            max_days = self.max_holding_days
        
        try:
            entry_dt = datetime.strptime(entry_date, '%Y-%m-%d')
            current_dt = datetime.strptime(current_date, '%Y-%m-%d')
            holding_days = (current_dt - entry_dt).days
            return holding_days >= max_days
        except ValueError:
            return False  # 日期格式错误，不触发
    
    def detect_trend_reversal(self, data: List[MarketData]) -> bool:
        """检测趋势反转
        
        Args:
            data: 市场数据列表
            
        Returns:
            bool: 是否检测到趋势反转
        """
        if len(data) < 5:
            return False
        
        # 简单的趋势反转检测：连续3天下跌且成交量放大
        recent_data = data[-5:]
        
        # 检查连续下跌
        consecutive_down = 0
        for i in range(1, len(recent_data)):
            if recent_data[i].close < recent_data[i-1].close:
                consecutive_down += 1
            else:
                consecutive_down = 0
        
        if consecutive_down < 3:
            return False
        
        # 检查成交量是否放大
        recent_volume = sum([d.volume for d in recent_data[-3:]]) / 3
        earlier_volume = sum([d.volume for d in recent_data[-5:-2]]) / 2
        
        volume_increase = recent_volume > earlier_volume * 1.2
        
        return volume_increase
    
    def generate_exit_signal(self, trade: Trade, current_data: MarketData, 
                           historical_data: List[MarketData]) -> Optional[Signal]:
        """生成退出信号
        
        Args:
            trade: 当前交易
            current_data: 当前市场数据
            historical_data: 历史数据
            
        Returns:
            Optional[Signal]: 退出信号，如果不需要退出则返回None
        """
        current_price = current_data.close
        current_date = current_data.date
        
        # 检查止损
        if self.check_stop_loss(current_price, trade.entry_price):
            return Signal(
                symbol=trade.symbol,
                date=current_date,
                signal_type=SignalType.SELL,
                price=current_price,
                strength=1.0,
                reason="止损退出",
                conditions_met={'stop_loss': True}
            )
        
        # 检查止盈
        if self.check_take_profit(current_price, trade.entry_price):
            return Signal(
                symbol=trade.symbol,
                date=current_date,
                signal_type=SignalType.SELL,
                price=current_price,
                strength=0.8,
                reason="止盈退出",
                conditions_met={'take_profit': True}
            )
        
        # 检查最大持有期
        if self.check_max_holding_period(trade.entry_date, current_date):
            return Signal(
                symbol=trade.symbol,
                date=current_date,
                signal_type=SignalType.SELL,
                price=current_price,
                strength=0.6,
                reason="最大持有期退出",
                conditions_met={'max_holding_period': True}
            )
        
        # 检查趋势反转
        if self.detect_trend_reversal(historical_data):
            return Signal(
                symbol=trade.symbol,
                date=current_date,
                signal_type=SignalType.SELL,
                price=current_price,
                strength=0.7,
                reason="趋势反转退出",
                conditions_met={'trend_reversal': True}
            )
        
        return None


class BacktestEngine(IBacktestEngine):
    """PVFRS策略回测引擎
    
    提供完整的回测功能，包括交易模拟、盈亏计算和回测报告生成
    """
    
    def __init__(self, config_manager: Optional[PVFRSConfigManager] = None):
        """初始化回测引擎
        
        Args:
            config_manager: 配置管理器（可选）
        """
        self.config_manager = config_manager or PVFRSConfigManager()
        self.config = self.config_manager.load_config()
        
        # 初始化组件
        self.strategy_engine = StrategyEngine()
        self.trade_simulator = TradeSimulator(self.config)
        self.risk_manager = RiskManager(self.config)
        self.trade_recorder = TradeRecorder()  # 交易记录管理器
        self.pnl_calculator = PnLCalculator(
            commission_rate=self.config.get('commission_rate', 0.0003),
            slippage_rate=self.config.get('slippage_rate', 0.001)
        )
        self.report_generator = BacktestReportGenerator()  # 报告生成器
        
        # 回测状态
        self.is_running = False
        self.current_backtest_result: Optional[BacktestResult] = None
    
    def run_backtest(self, symbols: List[str], start_date: str, end_date: str, 
                    initial_capital: float = 100000) -> BacktestResult:
        """执行回测
        
        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            initial_capital: 初始资金
            
        Returns:
            BacktestResult: 回测结果
            
        Raises:
            DataInsufficientException: 数据不足时抛出
            CalculationException: 计算异常时抛出
        """
        try:
            self.is_running = True
            
            # 重置模拟器状态
            self.trade_simulator.reset(initial_capital)
            
            # 这里需要外部提供数据接口，暂时抛出未实现异常
            # 在实际使用时，需要注入数据获取器
            raise NotImplementedError(
                "回测功能需要数据接口支持。请使用 run_backtest_with_data 方法，"
                "或者实现 IDataInterface 接口并通过 set_data_interface 方法注入。"
            )
            
        except Exception as e:
            self.is_running = False
            raise CalculationException(f"回测执行失败: {str(e)}")
        finally:
            self.is_running = False
    
    def run_backtest_with_data(self, stock_data_dict: Dict[str, List[MarketData]], 
                              start_date: str, end_date: str, 
                              initial_capital: float = 100000) -> BacktestResult:
        """使用提供的数据执行回测
        
        Args:
            stock_data_dict: 股票数据字典
            start_date: 开始日期
            end_date: 结束日期
            initial_capital: 初始资金
            
        Returns:
            BacktestResult: 回测结果
        """
        try:
            self.is_running = True
            
            # 重置模拟器状态
            self.trade_simulator.reset(initial_capital)
            
            # 获取所有交易日期
            all_dates = self._get_trading_dates(stock_data_dict, start_date, end_date)
            
            if not all_dates:
                raise DataInsufficientException("没有找到有效的交易日期")
            
            # 权益曲线记录
            equity_curve = []
            
            # 按日期逐日回测
            for current_date in all_dates:
                daily_result = self._process_trading_day(
                    stock_data_dict, current_date, initial_capital
                )
                
                # 记录权益曲线
                equity_curve.append({
                    'date': current_date,
                    'total_value': daily_result['total_value'],
                    'cash': daily_result['cash'],
                    'positions_value': daily_result['positions_value'],
                    'daily_pnl': daily_result.get('daily_pnl', 0.0)
                })
            
            # 计算最终结果
            final_result = self._calculate_final_result(
                initial_capital, equity_curve, self.trade_simulator.trades
            )
            
            self.current_backtest_result = final_result
            return final_result
            
        except Exception as e:
            raise CalculationException(f"回测执行失败: {str(e)}")
        finally:
            self.is_running = False
    
    def simulate_trade(self, signal: Signal, current_capital: float) -> Optional[Trade]:
        """模拟交易
        
        Args:
            signal: 交易信号
            current_capital: 当前资金
            
        Returns:
            Optional[Trade]: 交易记录
        """
        if signal.signal_type == SignalType.BUY:
            return self.trade_simulator.simulate_buy_order(signal, current_capital)
        elif signal.signal_type == SignalType.SELL:
            # 卖出信号需要有对应的持仓
            if signal.symbol in self.trade_simulator.open_positions:
                trade = self.trade_simulator.open_positions[signal.symbol]
                return self.trade_simulator.simulate_sell_order(trade, signal)
        
        return None
    
    def calculate_performance(self, trades: List[Trade]) -> Dict:
        """计算绩效指标
        
        Args:
            trades: 交易记录列表
            
        Returns:
            Dict: 绩效指标
        """
        if not trades:
            return {
                'total_return': 0.0,
                'annual_return': 0.0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'max_drawdown': 0.0,
                'sharpe_ratio': 0.0,
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0
            }
        
        completed_trades = [t for t in trades if t.pnl is not None]
        
        if not completed_trades:
            return self.calculate_performance([])
        
        # 使用PnLCalculator重新计算所有交易的盈亏
        recalculated_trades = []
        for trade in completed_trades:
            try:
                pnl, pnl_pct, details = self.pnl_calculator.calculate_trade_pnl(trade)
                # 更新交易记录
                updated_trade = Trade(
                    symbol=trade.symbol,
                    entry_date=trade.entry_date,
                    exit_date=trade.exit_date,
                    entry_price=trade.entry_price,
                    exit_price=trade.exit_price,
                    quantity=trade.quantity,
                    position_size=trade.position_size,
                    pnl=pnl,
                    pnl_percent=pnl_pct,
                    exit_reason=trade.exit_reason
                )
                recalculated_trades.append(updated_trade)
            except Exception:
                # 如果重新计算失败，使用原始数据
                recalculated_trades.append(trade)
        
        # 基础统计（盈亏平衡算入 losing，以满足 winning + losing == total_trades）
        total_pnl = sum([t.pnl for t in recalculated_trades if t.pnl is not None])
        winning_trades = [t for t in recalculated_trades if t.pnl is not None and t.pnl > 0]
        losing_trades = [t for t in recalculated_trades if t.pnl is not None and t.pnl <= 0]
        
        # 计算各项指标
        win_rate = len(winning_trades) / len(recalculated_trades) if recalculated_trades else 0.0
        
        gross_profit = sum([t.pnl for t in winning_trades]) if winning_trades else 0.0
        gross_loss = abs(sum([t.pnl for t in losing_trades])) if losing_trades else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 999.0
        
        # 计算平均持有期
        avg_holding_period = 0.0
        valid_holding_periods = []
        for trade in recalculated_trades:
            if trade.entry_date and trade.exit_date:
                try:
                    entry_date = datetime.strptime(trade.entry_date, '%Y-%m-%d')
                    exit_date = datetime.strptime(trade.exit_date, '%Y-%m-%d')
                    holding_days = (exit_date - entry_date).days
                    valid_holding_periods.append(holding_days)
                except ValueError:
                    continue
        
        if valid_holding_periods:
            avg_holding_period = sum(valid_holding_periods) / len(valid_holding_periods)
        
        return {
            'total_pnl': total_pnl,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_trades': len(recalculated_trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'avg_win': gross_profit / len(winning_trades) if winning_trades else 0.0,
            'avg_loss': gross_loss / len(losing_trades) if losing_trades else 0.0,
            'largest_win': max([t.pnl for t in winning_trades], default=0.0),
            'largest_loss': min([t.pnl for t in losing_trades], default=0.0),
            'avg_holding_period': avg_holding_period,
            'avg_win_percentage': sum([t.pnl_percent for t in winning_trades]) / len(winning_trades) if winning_trades else 0.0,
            'avg_loss_percentage': sum([t.pnl_percent for t in losing_trades]) / len(losing_trades) if losing_trades else 0.0,
            'total_commission': sum([details.get('total_commission', 0) for details in [self._get_trade_details(t) for t in recalculated_trades]]),
            'total_slippage': sum([details.get('total_slippage', 0) for details in [self._get_trade_details(t) for t in recalculated_trades]])
        }
    
    def _get_trading_dates(self, stock_data_dict: Dict[str, List[MarketData]], 
                          start_date: str, end_date: str) -> List[str]:
        """获取交易日期列表
        
        Args:
            stock_data_dict: 股票数据字典
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            List[str]: 交易日期列表
        """
        all_dates = set()
        
        for symbol, data_list in stock_data_dict.items():
            for data in data_list:
                if start_date <= data.date <= end_date:
                    all_dates.add(data.date)
        
        return sorted(list(all_dates))
    
    def _process_trading_day(self, stock_data_dict: Dict[str, List[MarketData]], 
                           current_date: str, initial_capital: float) -> Dict:
        """处理单个交易日
        
        Args:
            stock_data_dict: 股票数据字典
            current_date: 当前日期
            initial_capital: 初始资金
            
        Returns:
            Dict: 当日处理结果
        """
        daily_signals = []
        current_prices = {}
        
        # 1. 收集当日所有股票的信号和价格
        for symbol, data_list in stock_data_dict.items():
            # 获取到当前日期的历史数据
            historical_data = [d for d in data_list if d.date <= current_date]
            
            if len(historical_data) < 20:  # 数据不足
                continue
            
            current_data = historical_data[-1]
            current_prices[symbol] = current_data.close
            
            try:
                # 生成交易信号
                signals = self.strategy_engine.generate_signals(symbol, historical_data)
                daily_signals.extend(signals)
                
                # 检查现有持仓的退出信号
                if symbol in self.trade_simulator.open_positions:
                    trade = self.trade_simulator.open_positions[symbol]
                    exit_signal = self.risk_manager.generate_exit_signal(
                        trade, current_data, historical_data
                    )
                    if exit_signal:
                        daily_signals.append(exit_signal)
                        
            except Exception as e:
                print(f"处理股票 {symbol} 在 {current_date} 的信号时出错: {str(e)}")
                continue
        
        # 2. 处理卖出信号（先卖后买）
        for signal in daily_signals:
            if signal.signal_type == SignalType.SELL and signal.date == current_date:
                if signal.symbol in self.trade_simulator.open_positions:
                    trade = self.trade_simulator.open_positions[signal.symbol]
                    completed_trade = self.trade_simulator.simulate_sell_order(trade, signal)
                    
                    # 更新现金和记录
                    sell_proceeds = completed_trade.quantity * completed_trade.exit_price
                    commission = sell_proceeds * self.trade_simulator.commission_rate
                    self.trade_simulator.cash += (sell_proceeds - commission)
                    
                    # 移除持仓并记录交易
                    del self.trade_simulator.open_positions[signal.symbol]
                    self.trade_simulator.trades.append(completed_trade)
        
        # 3. 处理买入信号
        for signal in daily_signals:
            if signal.signal_type == SignalType.BUY and signal.date == current_date:
                trade = self.trade_simulator.simulate_buy_order(signal, self.trade_simulator.cash)
                if trade:
                    # 更新现金和持仓
                    total_cost = trade.position_size + (trade.position_size * self.trade_simulator.commission_rate)
                    self.trade_simulator.cash -= total_cost
                    self.trade_simulator.open_positions[signal.symbol] = trade
                    self.trade_simulator.trades.append(trade)
        
        # 4. 计算当日总价值
        total_value = self.trade_simulator.get_portfolio_value(current_prices)
        positions_value = total_value - self.trade_simulator.cash
        
        return {
            'total_value': total_value,
            'cash': self.trade_simulator.cash,
            'positions_value': positions_value,
            'signals_count': len(daily_signals)
        }
    
    def _calculate_final_result(self, initial_capital: float, 
                              equity_curve: List[Dict], 
                              trades: List[Trade]) -> BacktestResult:
        """计算最终回测结果
        
        Args:
            initial_capital: 初始资金
            equity_curve: 权益曲线
            trades: 交易记录
            
        Returns:
            BacktestResult: 回测结果
        """
        if not equity_curve:
            raise CalculationException("权益曲线数据为空")
        
        final_value = equity_curve[-1]['total_value']
        
        # 计算基础收益指标
        total_return = (final_value - initial_capital) / initial_capital
        
        # 计算年化收益率
        start_date = equity_curve[0]['date']
        end_date = equity_curve[-1]['date']
        trading_days = len(equity_curve)
        annual_return = self._calculate_annual_return(total_return, trading_days)
        
        # 计算最大回撤
        max_drawdown = self._calculate_max_drawdown(equity_curve)
        
        # 计算夏普比率
        sharpe_ratio = self._calculate_sharpe_ratio(equity_curve)
        
        # 计算交易统计
        performance = self.calculate_performance(trades)
        
        return BacktestResult(
            initial_capital=initial_capital,
            final_capital=final_value,
            total_return=total_return,
            annual_return=annual_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            win_rate=performance['win_rate'],
            profit_factor=performance['profit_factor'],
            total_trades=performance['total_trades'],
            winning_trades=performance['winning_trades'],
            losing_trades=performance['losing_trades'],
            avg_holding_period=self.trade_simulator._calculate_avg_holding_period(
                [t for t in trades if t.exit_date is not None]
            ),
            trades=trades,
            equity_curve=equity_curve
        )
    
    def _calculate_annual_return(self, total_return: float, trading_days: int) -> float:
        """计算年化收益率
        
        Args:
            total_return: 总收益率
            trading_days: 交易天数
            
        Returns:
            float: 年化收益率
        """
        if trading_days <= 0:
            return 0.0
        
        # 使用252个交易日作为基准
        years = trading_days / 252
        if years <= 0:
            return 0.0
        
        # 防止负收益导致计算异常
        if total_return <= -1:
            return -1.0
            
        return (1 + total_return) ** (1 / years) - 1
    
    def _calculate_max_drawdown(self, equity_curve: List[Dict]) -> float:
        """计算最大回撤
        
        Args:
            equity_curve: 权益曲线
            
        Returns:
            float: 最大回撤
        """
        if not equity_curve:
            return 0.0
        
        peak = equity_curve[0]['total_value']
        max_dd = 0.0
        
        for point in equity_curve:
            current_value = point['total_value']
            if current_value > peak:
                peak = current_value
            
            drawdown = (peak - current_value) / peak if peak > 0 else 0.0
            max_dd = max(max_dd, drawdown)
        
        return max_dd
    
    def _calculate_sharpe_ratio(self, equity_curve: List[Dict], risk_free_rate: float = 0.03) -> float:
        """计算夏普比率
        
        Args:
            equity_curve: 权益曲线
            risk_free_rate: 年化无风险利率 (默认3%)
            
        Returns:
            float: 夏普比率
        """
        if len(equity_curve) < 2:
            return 0.0
        
        # 计算日收益率
        daily_returns = []
        for i in range(1, len(equity_curve)):
            prev_value = equity_curve[i-1]['total_value']
            curr_value = equity_curve[i]['total_value']
            if prev_value > 0:
                daily_return = (curr_value - prev_value) / prev_value
                daily_returns.append(daily_return)
        
        if not daily_returns:
            return 0.0
        
        # 计算平均日收益率和标准差
        avg_daily_return = sum(daily_returns) / len(daily_returns)
        variance = sum([(r - avg_daily_return) ** 2 for r in daily_returns]) / len(daily_returns)
        daily_std_dev = variance ** 0.5
        
        if daily_std_dev == 0:
            return 0.0
        
        # 将年化无风险利率转换为日无风险利率
        daily_rf = risk_free_rate / 252
        
        # 年化夏普比率 = (平均日收益率 - 日无风险利率) / 日收益率标准差 * sqrt(252)
        sharpe = ((avg_daily_return - daily_rf) / daily_std_dev) * (252 ** 0.5)
        return sharpe
    
    def get_backtest_status(self) -> Dict:
        """获取回测状态
        
        Returns:
            Dict: 回测状态信息
        """
        return {
            'is_running': self.is_running,
            'has_result': self.current_backtest_result is not None,
            'config': self.config,
            'components': {
                'strategy_engine': type(self.strategy_engine).__name__,
                'trade_simulator': type(self.trade_simulator).__name__,
                'risk_manager': type(self.risk_manager).__name__
            }
        }
    
    def set_config(self, config: Dict):
        """设置配置
        
        Args:
            config: 新配置
        """
        self.config.update(config)
        self.trade_simulator.config.update(config)
        self.risk_manager.config.update(config)
    
    def get_detailed_trade_analysis(self, trade: Trade) -> Dict:
        """获取详细的交易分析
        
        Args:
            trade: 交易记录
            
        Returns:
            Dict: 详细的交易分析结果
        """
        try:
            if trade.exit_price is None:
                return {
                    'trade': asdict(trade),
                    'status': 'open',
                    'analysis': 'Trade not completed yet'
                }
            
            # 计算详细盈亏
            pnl, pnl_pct, details = self.pnl_calculator.calculate_trade_pnl(trade)
            
            return {
                'trade': asdict(trade),
                'status': 'completed',
                'pnl_analysis': {
                    'absolute_pnl': pnl,
                    'percentage_pnl': pnl_pct,
                    'calculation_details': details
                },
                'performance_metrics': {
                    'is_winning_trade': pnl > 0,
                    'holding_period': details.get('holding_days', 0),
                    'total_costs': details.get('total_commission', 0) + details.get('total_slippage', 0),
                    'cost_percentage': (details.get('total_commission', 0) + details.get('total_slippage', 0)) / details.get('total_buy_cost', 1) * 100
                }
            }
            
        except Exception as e:
            return {
                'trade': asdict(trade),
                'status': 'error',
                'error': str(e)
            }
    
    def get_portfolio_analysis(self, current_prices: Optional[Dict[str, float]] = None) -> Dict:
        """获取投资组合分析
        
        Args:
            current_prices: 当前价格字典（用于计算浮动盈亏）
            
        Returns:
            Dict: 投资组合分析结果
        """
        try:
            # 获取所有交易记录
            all_trades = self.trade_simulator.trades
            
            if not all_trades:
                return {
                    'portfolio_summary': {
                        'total_trades': 0,
                        'total_pnl': 0.0,
                        'current_positions': 0
                    },
                    'performance_analysis': {},
                    'risk_analysis': {}
                }
            
            # 使用PnLCalculator计算投资组合盈亏
            portfolio_pnl = self.pnl_calculator.calculate_portfolio_pnl(all_trades, current_prices)
            
            # 计算绩效指标
            performance = self.calculate_performance(all_trades)
            
            # 风险分析
            risk_analysis = self._calculate_risk_metrics(all_trades)
            
            return {
                'portfolio_summary': {
                    'total_trades': len(all_trades),
                    'completed_trades': portfolio_pnl['completed_trades_count'],
                    'open_positions': portfolio_pnl['open_trades_count'],
                    'total_pnl': portfolio_pnl['total_pnl'],
                    'realized_pnl': portfolio_pnl['realized_pnl'],
                    'floating_pnl': portfolio_pnl['floating_pnl'],
                    'symbols_traded': len(set([t.symbol for t in all_trades]))
                },
                'performance_analysis': performance,
                'pnl_breakdown': portfolio_pnl,
                'risk_analysis': risk_analysis,
                'trading_summary': self.trade_simulator.get_trading_summary()
            }
            
        except Exception as e:
            raise CalculationException(f"投资组合分析失败: {str(e)}")
    
    def export_trade_records(self, format_type: str = 'dict') -> Dict:
        """导出交易记录
        
        Args:
            format_type: 导出格式类型
            
        Returns:
            Dict: 导出的交易记录
        """
        try:
            all_trades = self.trade_simulator.trades
            
            if format_type == 'dict':
                return {
                    'trades': [asdict(trade) for trade in all_trades],
                    'metadata': {
                        'total_trades': len(all_trades),
                        'export_date': datetime.now().isoformat(),
                        'backtest_config': self.config
                    }
                }
            else:
                raise ValidationException(f"不支持的导出格式: {format_type}")
                
        except Exception as e:
            raise CalculationException(f"导出交易记录失败: {str(e)}")
    
    def _get_trade_details(self, trade: Trade) -> Dict:
        """获取交易详细信息
        
        Args:
            trade: 交易记录
            
        Returns:
            Dict: 交易详细信息
        """
        try:
            if trade.exit_price is None:
                return {}
            
            _, _, details = self.pnl_calculator.calculate_trade_pnl(trade)
            return details
        except Exception:
            return {}
    
    def _calculate_risk_metrics(self, trades: List[Trade]) -> Dict:
        """计算风险指标
        
        Args:
            trades: 交易记录列表
            
        Returns:
            Dict: 风险指标
        """
        completed_trades = [t for t in trades if t.pnl is not None]
        
        if not completed_trades:
            return {
                'max_consecutive_losses': 0,
                'max_consecutive_wins': 0,
                'largest_drawdown_trade': 0.0,
                'risk_reward_ratio': 0.0
            }
        
        # 计算连续亏损和盈利
        max_consecutive_losses = 0
        max_consecutive_wins = 0
        current_losses = 0
        current_wins = 0
        
        for trade in completed_trades:
            if trade.pnl > 0:
                current_wins += 1
                current_losses = 0
                max_consecutive_wins = max(max_consecutive_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_consecutive_losses = max(max_consecutive_losses, current_losses)
        
        # 计算风险收益比
        winning_trades = [t for t in completed_trades if t.pnl > 0]
        losing_trades = [t for t in completed_trades if t.pnl < 0]
        
        avg_win = sum([t.pnl for t in winning_trades]) / len(winning_trades) if winning_trades else 0.0
        avg_loss = abs(sum([t.pnl for t in losing_trades]) / len(losing_trades)) if losing_trades else 0.0
        
        risk_reward_ratio = avg_win / avg_loss if avg_loss > 0 else 0.0
        
        return {
            'max_consecutive_losses': max_consecutive_losses,
            'max_consecutive_wins': max_consecutive_wins,
            'largest_loss_trade': min([t.pnl for t in completed_trades], default=0.0),
            'largest_win_trade': max([t.pnl for t in completed_trades], default=0.0),
            'risk_reward_ratio': risk_reward_ratio,
            'volatility': self._calculate_returns_volatility(completed_trades)
        }
    
    def _calculate_returns_volatility(self, trades: List[Trade]) -> float:
        """计算收益率波动性
        
        Args:
            trades: 交易记录列表
            
        Returns:
            float: 收益率标准差
        """
        if len(trades) < 2:
            return 0.0
        
        returns = [t.pnl_percent for t in trades if t.pnl_percent is not None]
        
        if not returns:
            return 0.0
        
        mean_return = sum(returns) / len(returns)
        variance = sum([(r - mean_return) ** 2 for r in returns]) / len(returns)
        
        return variance ** 0.5
    
    def generate_backtest_report(self, report_type: str = 'comprehensive', 
                                export_format: Optional[str] = None,
                                export_path: Optional[str] = None) -> Dict:
        """生成回测报告
        
        Args:
            report_type: 报告类型 ('comprehensive' 或 'summary')
            export_format: 导出格式 ('json' 或 'html')，可选
            export_path: 导出路径，可选
            
        Returns:
            Dict: 回测报告
            
        Raises:
            ValidationException: 没有回测结果时抛出
            CalculationException: 生成报告失败时抛出
        """
        try:
            if self.current_backtest_result is None:
                raise ValidationException("没有可用的回测结果，请先执行回测")
            
            # 生成报告
            if report_type == 'comprehensive':
                report = self.report_generator.generate_comprehensive_report(
                    self.current_backtest_result,
                    additional_data={
                        'config': self.config,
                        'strategy_name': 'PVFARS Strategy',
                        'backtest_engine_version': '1.0.0'
                    }
                )
            elif report_type == 'summary':
                report = self.report_generator.generate_summary_report(self.current_backtest_result)
            else:
                raise ValidationException(f"不支持的报告类型: {report_type}")
            
            # 导出报告（如果指定了格式和路径）
            if export_format and export_path:
                if export_format == 'json':
                    self.report_generator.export_report_to_json(report, export_path)
                elif export_format == 'html':
                    self.report_generator.export_report_to_html(report, export_path)
                else:
                    raise ValidationException(f"不支持的导出格式: {export_format}")
            
            return report
            
        except (ValidationException, CalculationException):
            raise
        except Exception as e:
            raise CalculationException(f"生成回测报告失败: {str(e)}")
    
    def get_performance_summary(self) -> Dict:
        """获取绩效摘要
        
        Returns:
            Dict: 绩效摘要
            
        Raises:
            ValidationException: 没有回测结果时抛出
        """
        try:
            if self.current_backtest_result is None:
                raise ValidationException("没有可用的回测结果")
            
            return self.report_generator.generate_summary_report(self.current_backtest_result)
            
        except Exception as e:
            raise CalculationException(f"获取绩效摘要失败: {str(e)}")
    
    def compare_with_benchmark(self, benchmark_returns: List[float]) -> Dict:
        """与基准进行比较
        
        Args:
            benchmark_returns: 基准收益率列表
            
        Returns:
            Dict: 比较结果
            
        Raises:
            ValidationException: 数据无效时抛出
        """
        try:
            if self.current_backtest_result is None:
                raise ValidationException("没有可用的回测结果")
            
            if not benchmark_returns:
                raise ValidationException("基准收益率数据为空")
            
            # 计算策略收益率
            strategy_returns = []
            equity_curve = self.current_backtest_result.equity_curve
            
            for i in range(1, len(equity_curve)):
                prev_value = equity_curve[i-1]['total_value']
                curr_value = equity_curve[i]['total_value']
                if prev_value > 0:
                    strategy_return = (curr_value - prev_value) / prev_value
                    strategy_returns.append(strategy_return)
            
            # 确保数据长度一致
            min_length = min(len(strategy_returns), len(benchmark_returns))
            strategy_returns = strategy_returns[:min_length]
            benchmark_returns = benchmark_returns[:min_length]
            
            if not strategy_returns:
                raise ValidationException("策略收益率数据为空")
            
            # 计算比较指标
            strategy_total_return = sum(strategy_returns)
            benchmark_total_return = sum(benchmark_returns)
            
            excess_returns = [s - b for s, b in zip(strategy_returns, benchmark_returns)]
            
            # 计算跟踪误差
            tracking_error = self._calculate_std(excess_returns) * (252 ** 0.5)  # 年化
            
            # 计算信息比率
            avg_excess_return = sum(excess_returns) / len(excess_returns)
            information_ratio = (avg_excess_return * 252) / tracking_error if tracking_error > 0 else 0
            
            # 计算Beta
            beta = self._calculate_beta(strategy_returns, benchmark_returns)
            
            # 计算Alpha
            risk_free_rate = 0.03 / 252  # 假设年化无风险利率3%
            alpha = avg_excess_return - beta * (sum(benchmark_returns) / len(benchmark_returns) - risk_free_rate)
            
            return {
                'comparison_summary': {
                    'strategy_total_return': strategy_total_return,
                    'benchmark_total_return': benchmark_total_return,
                    'excess_return': strategy_total_return - benchmark_total_return,
                    'outperformance': strategy_total_return > benchmark_total_return
                },
                'risk_adjusted_metrics': {
                    'alpha': alpha * 252,  # 年化
                    'beta': beta,
                    'information_ratio': information_ratio,
                    'tracking_error': tracking_error
                },
                'correlation_analysis': {
                    'correlation': self._calculate_correlation(strategy_returns, benchmark_returns),
                    'up_capture': self._calculate_up_capture(strategy_returns, benchmark_returns),
                    'down_capture': self._calculate_down_capture(strategy_returns, benchmark_returns)
                }
            }
            
        except (ValidationException, CalculationException):
            raise
        except Exception as e:
            raise CalculationException(f"基准比较失败: {str(e)}")
    
    def _calculate_std(self, values: List[float]) -> float:
        """计算标准差"""
        if len(values) < 2:
            return 0.0
        
        mean_val = sum(values) / len(values)
        variance = sum([(v - mean_val) ** 2 for v in values]) / len(values)
        return variance ** 0.5
    
    def _calculate_beta(self, strategy_returns: List[float], benchmark_returns: List[float]) -> float:
        """计算Beta系数"""
        if len(strategy_returns) != len(benchmark_returns) or len(strategy_returns) < 2:
            return 0.0
        
        # 计算协方差和方差
        strategy_mean = sum(strategy_returns) / len(strategy_returns)
        benchmark_mean = sum(benchmark_returns) / len(benchmark_returns)
        
        covariance = sum([(s - strategy_mean) * (b - benchmark_mean) 
                         for s, b in zip(strategy_returns, benchmark_returns)]) / len(strategy_returns)
        
        benchmark_variance = sum([(b - benchmark_mean) ** 2 
                                 for b in benchmark_returns]) / len(benchmark_returns)
        
        return covariance / benchmark_variance if benchmark_variance > 0 else 0.0
    
    def _calculate_correlation(self, x: List[float], y: List[float]) -> float:
        """计算相关系数"""
        if len(x) != len(y) or len(x) < 2:
            return 0.0
        
        x_mean = sum(x) / len(x)
        y_mean = sum(y) / len(y)
        
        numerator = sum([(xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y)])
        x_std = sum([(xi - x_mean) ** 2 for xi in x]) ** 0.5
        y_std = sum([(yi - y_mean) ** 2 for yi in y]) ** 0.5
        
        denominator = x_std * y_std
        
        return numerator / denominator if denominator > 0 else 0.0
    
    def _calculate_up_capture(self, strategy_returns: List[float], benchmark_returns: List[float]) -> float:
        """计算上行捕获率"""
        up_periods = [(s, b) for s, b in zip(strategy_returns, benchmark_returns) if b > 0]
        
        if not up_periods:
            return 0.0
        
        strategy_up_return = sum([s for s, b in up_periods]) / len(up_periods)
        benchmark_up_return = sum([b for s, b in up_periods]) / len(up_periods)
        
        return strategy_up_return / benchmark_up_return if benchmark_up_return > 0 else 0.0
    
    def _calculate_down_capture(self, strategy_returns: List[float], benchmark_returns: List[float]) -> float:
        """计算下行捕获率"""
        down_periods = [(s, b) for s, b in zip(strategy_returns, benchmark_returns) if b < 0]
        
        if not down_periods:
            return 0.0
        
        strategy_down_return = sum([s for s, b in down_periods]) / len(down_periods)
        benchmark_down_return = sum([b for s, b in down_periods]) / len(down_periods)
        
        return strategy_down_return / benchmark_down_return if benchmark_down_return < 0 else 0.0