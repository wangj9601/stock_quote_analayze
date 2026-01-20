"""
PVFRS策略回测报告生成和展示模块
负责生成包含收益率曲线、交易记录、风险指标的详细报告
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import logging
import json
import math
from dataclasses import dataclass, asdict

from .models import BacktestResult, Trade, PVFRSException

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """性能指标数据结构"""
    total_return: float           # 总收益率
    annual_return: float          # 年化收益率
    win_rate: float              # 胜率
    max_drawdown: float          # 最大回撤
    sharpe_ratio: float          # 夏普比率
    sortino_ratio: float         # 索提诺比率
    calmar_ratio: float          # 卡玛比率
    volatility: float            # 波动率
    beta: float                  # 贝塔系数
    alpha: float                 # 阿尔法系数
    information_ratio: float     # 信息比率
    treynor_ratio: float         # 特雷诺比率


@dataclass
class RiskMetrics:
    """风险指标数据结构"""
    max_drawdown: float          # 最大回撤
    max_drawdown_duration: int   # 最大回撤持续天数
    var_95: float               # 95% VaR
    var_99: float               # 99% VaR
    cvar_95: float              # 95% CVaR
    cvar_99: float              # 99% CVaR
    downside_deviation: float    # 下行偏差
    upside_deviation: float      # 上行偏差
    tracking_error: float        # 跟踪误差
    maximum_loss: float          # 最大单笔亏损
    consecutive_losses: int      # 最大连续亏损次数


@dataclass
class TradeAnalysis:
    """交易分析数据结构"""
    total_trades: int            # 总交易次数
    winning_trades: int          # 盈利交易次数
    losing_trades: int           # 亏损交易次数
    win_rate: float             # 胜率
    avg_win: float              # 平均盈利
    avg_loss: float             # 平均亏损
    profit_factor: float        # 盈亏比
    avg_holding_days: float     # 平均持有天数
    best_trade: float           # 最佳交易
    worst_trade: float          # 最差交易
    largest_win_streak: int     # 最大连胜次数
    largest_loss_streak: int    # 最大连败次数


@dataclass
class EquityPoint:
    """资金曲线点数据结构"""
    date: str                   # 日期
    equity: float              # 资金
    return_rate: float         # 收益率
    drawdown: float            # 回撤
    benchmark_return: float    # 基准收益率（可选）


class BacktestReportGenerator:
    """回测报告生成器
    
    负责生成详细的回测报告，包括：
    - 收益率曲线计算和可视化数据
    - 交易记录分析和统计
    - 风险指标计算
    - 性能指标计算
    - 报告格式化和可视化准备
    """
    
    def __init__(self, risk_free_rate: float = 0.03):
        """初始化回测报告生成器
        
        Args:
            risk_free_rate: 无风险利率，用于计算夏普比率等指标
        """
        self.risk_free_rate = risk_free_rate
        
        logger.info("回测报告生成器初始化完成")
    
    def _calculate_holding_days(self, trade: Trade) -> Optional[int]:
        """计算交易持有天数
        
        Args:
            trade: 交易记录
            
        Returns:
            Optional[int]: 持有天数，如果无法计算则返回 None
        """
        if not trade.entry_date or not trade.exit_date:
            return None
        
        try:
            entry_dt = datetime.strptime(trade.entry_date, '%Y-%m-%d')
            exit_dt = datetime.strptime(trade.exit_date, '%Y-%m-%d')
            return (exit_dt - entry_dt).days
        except (ValueError, TypeError):
            return None
    
    def _calculate_return_rate(self, trade: Trade) -> Optional[float]:
        """计算交易收益率
        
        Args:
            trade: 交易记录
            
        Returns:
            Optional[float]: 收益率，如果无法计算则返回 None
        """
        if trade.pnl_percent is not None:
            return trade.pnl_percent
        
        if trade.entry_price and trade.exit_price and trade.entry_price > 0:
            return (trade.exit_price - trade.entry_price) / trade.entry_price
        
        return None
    
    def generate_comprehensive_report(self, backtest_result: BacktestResult, 
                                    initial_capital: float,
                                    start_date: str, end_date: str) -> Dict:
        """生成综合回测报告
        
        Args:
            backtest_result: 回测结果
            initial_capital: 初始资金
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            Dict: 综合回测报告
        """
        try:
            logger.info("开始生成综合回测报告")
            
            # 1. 计算资金曲线
            equity_curve = self._calculate_equity_curve(
                backtest_result.trades, initial_capital, start_date, end_date
            )
            
            # 2. 计算性能指标
            performance_metrics = self._calculate_performance_metrics(
                equity_curve, backtest_result.trades, initial_capital
            )
            
            # 3. 计算风险指标
            risk_metrics = self._calculate_risk_metrics(
                equity_curve, backtest_result.trades
            )
            
            # 4. 分析交易记录
            trade_analysis = self._analyze_trades(backtest_result.trades)
            
            # 5. 生成月度收益统计
            monthly_returns = self._calculate_monthly_returns(equity_curve)
            
            # 6. 生成年度收益统计
            yearly_returns = self._calculate_yearly_returns(equity_curve)
            
            # 7. 计算回撤分析
            drawdown_analysis = self._analyze_drawdowns(equity_curve)
            
            # 8. 生成持仓分析
            position_analysis = self._analyze_positions(backtest_result.trades)
            
            # 9. 生成可视化数据
            visualization_data = self._prepare_visualization_data(
                equity_curve, backtest_result.trades, monthly_returns
            )
            
            # 10. 构建综合报告
            comprehensive_report = {
                'report_metadata': {
                    'generated_at': datetime.now().isoformat(),
                    'period': {
                        'start_date': start_date,
                        'end_date': end_date,
                        'duration_days': (datetime.strptime(end_date, '%Y-%m-%d') - 
                                        datetime.strptime(start_date, '%Y-%m-%d')).days
                    },
                    'initial_capital': initial_capital,
                    'final_capital': equity_curve[-1].equity if equity_curve else initial_capital
                },
                'performance_metrics': asdict(performance_metrics),
                'risk_metrics': asdict(risk_metrics),
                'trade_analysis': asdict(trade_analysis),
                'equity_curve': [asdict(point) for point in equity_curve],
                'monthly_returns': monthly_returns,
                'yearly_returns': yearly_returns,
                'drawdown_analysis': drawdown_analysis,
                'position_analysis': position_analysis,
                'visualization_data': visualization_data,
                'summary': self._generate_report_summary(
                    performance_metrics, risk_metrics, trade_analysis
                )
            }
            
            logger.info("综合回测报告生成完成")
            return comprehensive_report
            
        except Exception as e:
            logger.error(f"生成综合回测报告失败: {str(e)}")
            raise PVFRSException(f"生成综合回测报告失败: {str(e)}")
    
    def _calculate_equity_curve(self, trades: List[Trade], initial_capital: float,
                               start_date: str, end_date: str) -> List[EquityPoint]:
        """计算资金曲线
        
        Args:
            trades: 交易记录列表
            initial_capital: 初始资金
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            List[EquityPoint]: 资金曲线点列表
        """
        equity_curve = []
        current_equity = initial_capital
        
        # 按日期排序交易
        sorted_trades = sorted(trades, key=lambda t: t.exit_date or t.entry_date)
        
        # 生成日期序列
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        current_date = start_dt
        trade_index = 0
        
        while current_date <= end_dt:
            date_str = current_date.strftime('%Y-%m-%d')
            
            # 处理当日的交易
            while (trade_index < len(sorted_trades) and 
                   sorted_trades[trade_index].exit_date and
                   sorted_trades[trade_index].exit_date <= date_str):
                current_equity += sorted_trades[trade_index].pnl
                trade_index += 1
            
            # 计算收益率
            return_rate = (current_equity - initial_capital) / initial_capital
            
            # 计算回撤
            if equity_curve:
                peak_equity = max(point.equity for point in equity_curve)
                drawdown = (peak_equity - current_equity) / peak_equity if peak_equity > 0 else 0
            else:
                drawdown = 0
            
            equity_point = EquityPoint(
                date=date_str,
                equity=current_equity,
                return_rate=return_rate,
                drawdown=drawdown,
                benchmark_return=0.0  # 暂不实现基准对比
            )
            
            equity_curve.append(equity_point)
            current_date += timedelta(days=1)
        
        return equity_curve
    
    def _calculate_performance_metrics(self, equity_curve: List[EquityPoint],
                                     trades: List[Trade], initial_capital: float) -> PerformanceMetrics:
        """计算性能指标
        
        Args:
            equity_curve: 资金曲线
            trades: 交易记录
            initial_capital: 初始资金
            
        Returns:
            PerformanceMetrics: 性能指标
        """
        if not equity_curve:
            return PerformanceMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        
        # 基本收益指标
        final_equity = equity_curve[-1].equity
        total_return = (final_equity - initial_capital) / initial_capital
        
        # 年化收益率
        days = len(equity_curve)
        annual_return = (1 + total_return) ** (365 / days) - 1 if days > 0 else 0
        
        # 胜率（处理 None 值）
        winning_trades = len([t for t in trades if t.pnl is not None and t.pnl > 0])
        total_trades = len(trades)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        # 最大回撤
        max_drawdown = max(point.drawdown for point in equity_curve) if equity_curve else 0
        
        # 计算日收益率序列
        daily_returns = []
        for i in range(1, len(equity_curve)):
            prev_equity = equity_curve[i-1].equity
            curr_equity = equity_curve[i].equity
            if prev_equity > 0:
                daily_return = (curr_equity - prev_equity) / prev_equity
                daily_returns.append(daily_return)
        
        # 波动率
        if len(daily_returns) > 1:
            mean_return = sum(daily_returns) / len(daily_returns)
            variance = sum((r - mean_return) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
            volatility = math.sqrt(variance * 365)  # 年化波动率
        else:
            volatility = 0
        
        # 夏普比率
        if volatility > 0:
            sharpe_ratio = (annual_return - self.risk_free_rate) / volatility
        else:
            sharpe_ratio = 0
        
        # 下行偏差（用于索提诺比率）
        negative_returns = [r for r in daily_returns if r < 0]
        if negative_returns:
            downside_variance = sum(r ** 2 for r in negative_returns) / len(negative_returns)
            downside_deviation = math.sqrt(downside_variance * 365)
        else:
            downside_deviation = 0
        
        # 索提诺比率
        if downside_deviation > 0:
            sortino_ratio = (annual_return - self.risk_free_rate) / downside_deviation
        else:
            sortino_ratio = 0
        
        # 卡玛比率
        if max_drawdown > 0:
            calmar_ratio = annual_return / max_drawdown
        else:
            calmar_ratio = 0
        
        return PerformanceMetrics(
            total_return=total_return,
            annual_return=annual_return,
            win_rate=win_rate,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            volatility=volatility,
            beta=0.0,  # 需要基准数据计算
            alpha=0.0,  # 需要基准数据计算
            information_ratio=0.0,  # 需要基准数据计算
            treynor_ratio=0.0  # 需要基准数据计算
        )
    
    def _calculate_risk_metrics(self, equity_curve: List[EquityPoint],
                               trades: List[Trade]) -> RiskMetrics:
        """计算风险指标
        
        Args:
            equity_curve: 资金曲线
            trades: 交易记录
            
        Returns:
            RiskMetrics: 风险指标
        """
        if not equity_curve:
            return RiskMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        
        # 最大回撤和持续时间
        max_drawdown = 0
        max_drawdown_duration = 0
        current_drawdown_duration = 0
        
        for point in equity_curve:
            if point.drawdown > max_drawdown:
                max_drawdown = point.drawdown
            
            if point.drawdown > 0:
                current_drawdown_duration += 1
                max_drawdown_duration = max(max_drawdown_duration, current_drawdown_duration)
            else:
                current_drawdown_duration = 0
        
        # 计算日收益率
        daily_returns = []
        for i in range(1, len(equity_curve)):
            prev_equity = equity_curve[i-1].equity
            curr_equity = equity_curve[i].equity
            if prev_equity > 0:
                daily_return = (curr_equity - prev_equity) / prev_equity
                daily_returns.append(daily_return)
        
        # VaR计算（历史模拟法）
        if daily_returns:
            sorted_returns = sorted(daily_returns)
            var_95_index = int(len(sorted_returns) * 0.05)
            var_99_index = int(len(sorted_returns) * 0.01)
            
            var_95 = abs(sorted_returns[var_95_index]) if var_95_index < len(sorted_returns) else 0
            var_99 = abs(sorted_returns[var_99_index]) if var_99_index < len(sorted_returns) else 0
            
            # CVaR计算
            cvar_95_returns = sorted_returns[:var_95_index+1] if var_95_index < len(sorted_returns) else []
            cvar_99_returns = sorted_returns[:var_99_index+1] if var_99_index < len(sorted_returns) else []
            
            cvar_95 = abs(sum(cvar_95_returns) / len(cvar_95_returns)) if cvar_95_returns else 0
            cvar_99 = abs(sum(cvar_99_returns) / len(cvar_99_returns)) if cvar_99_returns else 0
        else:
            var_95 = var_99 = cvar_95 = cvar_99 = 0
        
        # 上行和下行偏差
        positive_returns = [r for r in daily_returns if r > 0]
        negative_returns = [r for r in daily_returns if r < 0]
        
        if positive_returns:
            upside_deviation = math.sqrt(sum(r ** 2 for r in positive_returns) / len(positive_returns))
        else:
            upside_deviation = 0
        
        if negative_returns:
            downside_deviation = math.sqrt(sum(r ** 2 for r in negative_returns) / len(negative_returns))
        else:
            downside_deviation = 0
        
        # 交易相关风险指标（过滤 None 值）
        pnl_values = [t.pnl for t in trades if t.pnl is not None]
        maximum_loss = min(pnl_values) if pnl_values else 0
        
        # 计算最大连续亏损次数（处理 None 值）
        consecutive_losses = 0
        max_consecutive_losses = 0
        for trade in trades:
            if trade.pnl is not None and trade.pnl < 0:
                consecutive_losses += 1
                max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
            else:
                consecutive_losses = 0
        
        return RiskMetrics(
            max_drawdown=max_drawdown,
            max_drawdown_duration=max_drawdown_duration,
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            downside_deviation=downside_deviation,
            upside_deviation=upside_deviation,
            tracking_error=0.0,  # 需要基准数据计算
            maximum_loss=abs(maximum_loss),
            consecutive_losses=max_consecutive_losses
        )
    
    def _analyze_trades(self, trades: List[Trade]) -> TradeAnalysis:
        """分析交易记录
        
        Args:
            trades: 交易记录列表
            
        Returns:
            TradeAnalysis: 交易分析结果
        """
        if not trades:
            return TradeAnalysis(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        
        total_trades = len(trades)
        # 处理 None 值，确保 pnl 不为 None
        winning_trades = len([t for t in trades if t.pnl is not None and t.pnl > 0])
        losing_trades = len([t for t in trades if t.pnl is not None and t.pnl < 0])
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        # 平均盈利和亏损（过滤 None 值）
        wins = [t.pnl for t in trades if t.pnl is not None and t.pnl > 0]
        losses = [t.pnl for t in trades if t.pnl is not None and t.pnl < 0]
        
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        
        # 盈亏比
        if avg_loss != 0:
            profit_factor = abs(avg_win / avg_loss)
        else:
            profit_factor = 999.0 if avg_win > 0 else 0
        
        # 平均持有天数（计算并过滤 None 值）
        holding_days_list = []
        for t in trades:
            holding_days = self._calculate_holding_days(t)
            if holding_days is not None:
                holding_days_list.append(holding_days)
        avg_holding_days = sum(holding_days_list) / len(holding_days_list) if holding_days_list else 0
        
        # 最佳和最差交易（过滤 None 值）
        pnl_values = [t.pnl for t in trades if t.pnl is not None]
        best_trade = max(pnl_values) if pnl_values else 0
        worst_trade = min(pnl_values) if pnl_values else 0
        
        # 连胜连败统计
        win_streak = 0
        loss_streak = 0
        largest_win_streak = 0
        largest_loss_streak = 0
        
        for trade in trades:
            # 处理 None 值
            if trade.pnl is None:
                win_streak = 0
                loss_streak = 0
            elif trade.pnl > 0:
                win_streak += 1
                loss_streak = 0
                largest_win_streak = max(largest_win_streak, win_streak)
            elif trade.pnl < 0:
                loss_streak += 1
                win_streak = 0
                largest_loss_streak = max(largest_loss_streak, loss_streak)
            else:  # pnl == 0
                win_streak = 0
                loss_streak = 0
        
        return TradeAnalysis(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            avg_holding_days=avg_holding_days,
            best_trade=best_trade,
            worst_trade=worst_trade,
            largest_win_streak=largest_win_streak,
            largest_loss_streak=largest_loss_streak
        )
    
    def _calculate_monthly_returns(self, equity_curve: List[EquityPoint]) -> Dict[str, float]:
        """计算月度收益率
        
        Args:
            equity_curve: 资金曲线
            
        Returns:
            Dict[str, float]: 月度收益率字典
        """
        monthly_returns = {}
        
        if not equity_curve:
            return monthly_returns
        
        current_month = None
        month_start_equity = None
        
        for point in equity_curve:
            date_obj = datetime.strptime(point.date, '%Y-%m-%d')
            month_key = date_obj.strftime('%Y-%m')
            
            if current_month != month_key:
                # 新月份开始
                if current_month is not None and month_start_equity is not None:
                    # 计算上个月的收益率
                    prev_point = equity_curve[equity_curve.index(point) - 1]
                    month_return = (prev_point.equity - month_start_equity) / month_start_equity
                    monthly_returns[current_month] = month_return
                
                current_month = month_key
                month_start_equity = point.equity
        
        # 处理最后一个月
        if current_month is not None and month_start_equity is not None:
            last_point = equity_curve[-1]
            month_return = (last_point.equity - month_start_equity) / month_start_equity
            monthly_returns[current_month] = month_return
        
        return monthly_returns
    
    def _calculate_yearly_returns(self, equity_curve: List[EquityPoint]) -> Dict[str, float]:
        """计算年度收益率
        
        Args:
            equity_curve: 资金曲线
            
        Returns:
            Dict[str, float]: 年度收益率字典
        """
        yearly_returns = {}
        
        if not equity_curve:
            return yearly_returns
        
        current_year = None
        year_start_equity = None
        
        for point in equity_curve:
            date_obj = datetime.strptime(point.date, '%Y-%m-%d')
            year_key = str(date_obj.year)
            
            if current_year != year_key:
                # 新年份开始
                if current_year is not None and year_start_equity is not None:
                    # 计算上一年的收益率
                    prev_point = equity_curve[equity_curve.index(point) - 1]
                    year_return = (prev_point.equity - year_start_equity) / year_start_equity
                    yearly_returns[current_year] = year_return
                
                current_year = year_key
                year_start_equity = point.equity
        
        # 处理最后一年
        if current_year is not None and year_start_equity is not None:
            last_point = equity_curve[-1]
            year_return = (last_point.equity - year_start_equity) / year_start_equity
            yearly_returns[current_year] = year_return
        
        return yearly_returns
    
    def _analyze_drawdowns(self, equity_curve: List[EquityPoint]) -> Dict:
        """分析回撤
        
        Args:
            equity_curve: 资金曲线
            
        Returns:
            Dict: 回撤分析结果
        """
        if not equity_curve:
            return {}
        
        drawdown_periods = []
        current_drawdown = None
        
        for i, point in enumerate(equity_curve):
            if point.drawdown > 0:
                if current_drawdown is None:
                    # 开始新的回撤期
                    current_drawdown = {
                        'start_date': point.date,
                        'start_index': i,
                        'peak_equity': equity_curve[i-1].equity if i > 0 else point.equity,
                        'max_drawdown': point.drawdown,
                        'end_date': None,
                        'duration': 0,
                        'recovery_date': None
                    }
                else:
                    # 更新当前回撤期
                    current_drawdown['max_drawdown'] = max(current_drawdown['max_drawdown'], point.drawdown)
                    current_drawdown['duration'] = i - current_drawdown['start_index'] + 1
            else:
                if current_drawdown is not None:
                    # 回撤期结束
                    current_drawdown['end_date'] = equity_curve[i-1].date if i > 0 else point.date
                    current_drawdown['recovery_date'] = point.date
                    drawdown_periods.append(current_drawdown)
                    current_drawdown = None
        
        # 处理未结束的回撤期
        if current_drawdown is not None:
            current_drawdown['end_date'] = equity_curve[-1].date
            current_drawdown['duration'] = len(equity_curve) - current_drawdown['start_index']
            drawdown_periods.append(current_drawdown)
        
        # 统计分析（过滤 None 值）
        if drawdown_periods:
            # 过滤掉 max_drawdown 或 duration 为 None 的项
            valid_drawdowns = [dd for dd in drawdown_periods if dd.get('max_drawdown') is not None and dd.get('duration') is not None]
            if valid_drawdowns:
                max_drawdown_period = max(valid_drawdowns, key=lambda x: x['max_drawdown'])
                longest_drawdown_period = max(valid_drawdowns, key=lambda x: x['duration'])
                avg_drawdown = sum(dd['max_drawdown'] for dd in valid_drawdowns) / len(valid_drawdowns)
                avg_duration = sum(dd['duration'] for dd in valid_drawdowns) / len(valid_drawdowns)
            else:
                max_drawdown_period = None
                longest_drawdown_period = None
                avg_drawdown = 0
                avg_duration = 0
        else:
            max_drawdown_period = None
            longest_drawdown_period = None
            avg_drawdown = 0
            avg_duration = 0
        
        return {
            'drawdown_periods': drawdown_periods,
            'total_drawdown_periods': len(drawdown_periods),
            'max_drawdown_period': max_drawdown_period,
            'longest_drawdown_period': longest_drawdown_period,
            'average_drawdown': avg_drawdown,
            'average_duration': avg_duration
        }
    
    def _analyze_positions(self, trades: List[Trade]) -> Dict:
        """分析持仓
        
        Args:
            trades: 交易记录列表
            
        Returns:
            Dict: 持仓分析结果
        """
        if not trades:
            return {}
        
        # 按股票分组统计
        symbol_stats = {}
        for trade in trades:
            symbol = trade.symbol
            if symbol not in symbol_stats:
                symbol_stats[symbol] = {
                    'total_trades': 0,
                    'winning_trades': 0,
                    'total_pnl': 0,
                    'total_return': 0,
                    'avg_holding_days': 0,
                    'best_trade': 0,
                    'worst_trade': 0
                }
            
            stats = symbol_stats[symbol]
            stats['total_trades'] += 1
            # 处理 None 值
            if trade.pnl is not None:
                if trade.pnl > 0:
                    stats['winning_trades'] += 1
                stats['total_pnl'] += trade.pnl
                stats['best_trade'] = max(stats['best_trade'], trade.pnl)
                stats['worst_trade'] = min(stats['worst_trade'], trade.pnl)
            
            return_rate = self._calculate_return_rate(trade)
            if return_rate is not None:
                stats['total_return'] += return_rate
            
            holding_days = self._calculate_holding_days(trade)
            if holding_days is not None:
                stats['avg_holding_days'] += holding_days
        
        # 计算平均值
        for symbol, stats in symbol_stats.items():
            if stats['total_trades'] > 0:
                stats['win_rate'] = stats['winning_trades'] / stats['total_trades']
                stats['avg_return'] = stats['total_return'] / stats['total_trades']
                stats['avg_holding_days'] = stats['avg_holding_days'] / stats['total_trades']
        
        # 排序
        top_performers = sorted(
            symbol_stats.items(), 
            key=lambda x: x[1]['total_pnl'], 
            reverse=True
        )[:10]
        
        worst_performers = sorted(
            symbol_stats.items(), 
            key=lambda x: x[1]['total_pnl']
        )[:10]
        
        return {
            'symbol_statistics': symbol_stats,
            'top_performers': dict(top_performers),
            'worst_performers': dict(worst_performers),
            'total_symbols_traded': len(symbol_stats)
        }
    
    def _prepare_visualization_data(self, equity_curve: List[EquityPoint],
                                  trades: List[Trade], monthly_returns: Dict) -> Dict:
        """准备可视化数据
        
        Args:
            equity_curve: 资金曲线
            trades: 交易记录
            monthly_returns: 月度收益率
            
        Returns:
            Dict: 可视化数据
        """
        # 资金曲线图数据
        equity_chart_data = {
            'dates': [point.date for point in equity_curve],
            'equity_values': [point.equity for point in equity_curve],
            'return_rates': [point.return_rate for point in equity_curve],
            'drawdowns': [point.drawdown for point in equity_curve]
        }
        
        # 月度收益热力图数据
        monthly_heatmap_data = []
        for month, return_rate in monthly_returns.items():
            year, month_num = month.split('-')
            monthly_heatmap_data.append({
                'year': int(year),
                'month': int(month_num),
                'return': return_rate
            })
        
        # 交易分布图数据（计算并过滤 None 值）
        pnl_values = [trade.pnl for trade in trades if trade.pnl is not None]
        holding_days_list = []
        return_rates_list = []
        
        for trade in trades:
            holding_days = self._calculate_holding_days(trade)
            if holding_days is not None:
                holding_days_list.append(holding_days)
            
            return_rate = self._calculate_return_rate(trade)
            if return_rate is not None:
                return_rates_list.append(return_rate)
        
        trade_distribution_data = {
            'pnl_values': pnl_values,
            'holding_days': holding_days_list,
            'return_rates': return_rates_list
        }
        
        # 胜率统计数据（处理 None 值）
        win_loss_data = {
            'wins': len([t for t in trades if t.pnl is not None and t.pnl > 0]),
            'losses': len([t for t in trades if t.pnl is not None and t.pnl < 0]),
            'breakevens': len([t for t in trades if t.pnl is not None and t.pnl == 0])
        }
        
        return {
            'equity_curve_chart': equity_chart_data,
            'monthly_returns_heatmap': monthly_heatmap_data,
            'trade_distribution': trade_distribution_data,
            'win_loss_pie': win_loss_data,
            'chart_config': {
                'equity_curve': {
                    'title': 'PVFRS策略资金曲线',
                    'x_axis': '日期',
                    'y_axis': '资金（元）'
                },
                'drawdown': {
                    'title': '回撤曲线',
                    'x_axis': '日期',
                    'y_axis': '回撤比例'
                },
                'monthly_returns': {
                    'title': '月度收益率热力图',
                    'x_axis': '月份',
                    'y_axis': '年份'
                }
            }
        }
    
    def _generate_report_summary(self, performance_metrics: PerformanceMetrics,
                                risk_metrics: RiskMetrics, trade_analysis: TradeAnalysis) -> Dict:
        """生成报告摘要
        
        Args:
            performance_metrics: 性能指标
            risk_metrics: 风险指标
            trade_analysis: 交易分析
            
        Returns:
            Dict: 报告摘要
        """
        # 策略评级
        def calculate_strategy_score():
            score = 0
            
            # 收益率评分 (30%)
            if performance_metrics.annual_return > 0.2:
                score += 30
            elif performance_metrics.annual_return > 0.1:
                score += 20
            elif performance_metrics.annual_return > 0.05:
                score += 10
            
            # 夏普比率评分 (25%)
            if performance_metrics.sharpe_ratio > 2.0:
                score += 25
            elif performance_metrics.sharpe_ratio > 1.0:
                score += 20
            elif performance_metrics.sharpe_ratio > 0.5:
                score += 10
            
            # 最大回撤评分 (25%)
            if risk_metrics.max_drawdown < 0.05:
                score += 25
            elif risk_metrics.max_drawdown < 0.1:
                score += 20
            elif risk_metrics.max_drawdown < 0.2:
                score += 10
            
            # 胜率评分 (20%)
            if trade_analysis.win_rate > 0.6:
                score += 20
            elif trade_analysis.win_rate > 0.5:
                score += 15
            elif trade_analysis.win_rate > 0.4:
                score += 10
            
            return min(score, 100)
        
        strategy_score = calculate_strategy_score()
        
        # 策略等级
        if strategy_score >= 80:
            strategy_grade = "优秀"
        elif strategy_score >= 60:
            strategy_grade = "良好"
        elif strategy_score >= 40:
            strategy_grade = "一般"
        else:
            strategy_grade = "较差"
        
        # 关键亮点
        highlights = []
        if performance_metrics.annual_return > 0.15:
            highlights.append(f"年化收益率达到 {performance_metrics.annual_return:.1%}")
        if performance_metrics.sharpe_ratio > 1.5:
            highlights.append(f"夏普比率优秀 ({performance_metrics.sharpe_ratio:.2f})")
        if risk_metrics.max_drawdown < 0.1:
            highlights.append(f"最大回撤控制良好 ({risk_metrics.max_drawdown:.1%})")
        if trade_analysis.win_rate > 0.55:
            highlights.append(f"胜率较高 ({trade_analysis.win_rate:.1%})")
        
        # 风险提示
        warnings = []
        if risk_metrics.max_drawdown > 0.2:
            warnings.append(f"最大回撤较大 ({risk_metrics.max_drawdown:.1%})")
        if performance_metrics.volatility > 0.3:
            warnings.append(f"波动率较高 ({performance_metrics.volatility:.1%})")
        if trade_analysis.win_rate < 0.4:
            warnings.append(f"胜率偏低 ({trade_analysis.win_rate:.1%})")
        if risk_metrics.consecutive_losses > 5:
            warnings.append(f"最大连续亏损次数较多 ({risk_metrics.consecutive_losses}次)")
        
        return {
            'strategy_score': strategy_score,
            'strategy_grade': strategy_grade,
            'key_highlights': highlights,
            'risk_warnings': warnings,
            'recommendation': self._generate_recommendation(strategy_score, performance_metrics, risk_metrics),
            'summary_text': f"PVFRS策略在回测期间实现了{performance_metrics.annual_return:.1%}的年化收益率，"
                          f"最大回撤为{risk_metrics.max_drawdown:.1%}，胜率为{trade_analysis.win_rate:.1%}。"
                          f"综合评分{strategy_score}分，评级为{strategy_grade}。"
        }
    
    def _generate_recommendation(self, score: int, performance: PerformanceMetrics, 
                               risk: RiskMetrics) -> str:
        """生成投资建议
        
        Args:
            score: 策略评分
            performance: 性能指标
            risk: 风险指标
            
        Returns:
            str: 投资建议
        """
        if score >= 80:
            return "该策略表现优秀，建议考虑实盘应用。建议适当控制仓位，并持续监控策略表现。"
        elif score >= 60:
            return "该策略表现良好，可以考虑小仓位试验。建议进一步优化参数以提升表现。"
        elif score >= 40:
            return "该策略表现一般，需要进一步优化。建议调整策略参数或增加过滤条件。"
        else:
            return "该策略表现较差，不建议直接使用。建议重新审视策略逻辑或更换策略框架。"


# 便捷函数
def create_report_generator(risk_free_rate: float = 0.03) -> BacktestReportGenerator:
    """创建回测报告生成器实例
    
    Args:
        risk_free_rate: 无风险利率
        
    Returns:
        BacktestReportGenerator: 报告生成器实例
    """
    return BacktestReportGenerator(risk_free_rate)