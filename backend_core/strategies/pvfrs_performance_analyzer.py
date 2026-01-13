"""
PVFRS策略性能分析器
计算回测性能指标，生成分析报告
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import logging

try:
    import matplotlib.pyplot as plt  # type: ignore
except Exception:  # pragma: no cover
    plt = None

try:
    import seaborn as sns  # type: ignore
except Exception:  # pragma: no cover
    sns = None

logger = logging.getLogger(__name__)

class PVFRSPerformanceAnalyzer:
    """PVFRS策略性能分析器"""
    
    def __init__(self):
        self.metrics_cache = {}
    
    def calculate_comprehensive_metrics(self, backtest_result) -> Dict:
        """计算全面的性能指标"""
        if not backtest_result.trades:
            return self._empty_metrics()
        
        # 基础收益指标
        return_metrics = self._calculate_return_metrics(backtest_result)
        
        # 风险指标
        risk_metrics = self._calculate_risk_metrics(backtest_result)
        
        # 交易统计
        trade_metrics = self._calculate_trade_metrics(backtest_result)
        
        # 时间分析
        time_metrics = self._calculate_time_metrics(backtest_result)
        
        # PVFRS特定分析
        pvfrs_metrics = self._calculate_pvfrs_specific_metrics(backtest_result)
        
        # 合并所有指标
        all_metrics = {
            **return_metrics,
            **risk_metrics,
            **trade_metrics,
            **time_metrics,
            **pvfrs_metrics
        }
        
        # 计算综合评分
        all_metrics['composite_score'] = self._calculate_composite_score(all_metrics)
        
        return all_metrics
    
    def _calculate_return_metrics(self, result) -> Dict:
        """计算收益相关指标"""
        initial_capital = result.initial_capital
        final_capital = result.final_capital
        total_return = result.total_return
        
        # 年化收益率
        if result.equity_curve is not None and len(result.equity_curve) > 1:
            start_date = pd.to_datetime(result.equity_curve['date'].iloc[0])
            end_date = pd.to_datetime(result.equity_curve['date'].iloc[-1])
            years = (end_date - start_date).days / 365.25
            annual_return = (final_capital / initial_capital) ** (1/years) - 1 if years > 0 else 0
        else:
            annual_return = 0
        
        # 月度收益率
        monthly_return = (1 + total_return) ** (1/12) - 1 if total_return > -1 else 0
        
        # 基准比较（假设年化基准收益率8%）
        benchmark_return = 0.08
        excess_return = annual_return - benchmark_return
        
        return {
            'total_return': total_return,
            'total_return_pct': f"{total_return:.2%}",
            'annual_return': annual_return,
            'annual_return_pct': f"{annual_return:.2%}",
            'monthly_return': monthly_return,
            'monthly_return_pct': f"{monthly_return:.2%}",
            'excess_return': excess_return,
            'excess_return_pct': f"{excess_return:.2%}",
            'final_capital': final_capital,
            'capital_multiple': final_capital / initial_capital
        }
    
    def _calculate_risk_metrics(self, result) -> Dict:
        """计算风险相关指标"""
        if result.equity_curve is None or len(result.equity_curve) == 0:
            return self._empty_risk_metrics()
        
        equity_series = result.equity_curve['equity']
        
        # 最大回撤
        rolling_max = equity_series.expanding().max()
        drawdown = (equity_series - rolling_max) / rolling_max
        max_drawdown = drawdown.min()
        
        # 平均回撤
        drawdown_periods = drawdown[drawdown < 0]
        avg_drawdown = drawdown_periods.mean() if len(drawdown_periods) > 0 else 0
        
        # 回撤持续时间
        in_drawdown = drawdown < 0
        drawdown_duration = 0
        max_drawdown_duration = 0
        current_duration = 0
        
        for is_dd in in_drawdown:
            if is_dd:
                current_duration += 1
                drawdown_duration += 1
                max_drawdown_duration = max(max_drawdown_duration, current_duration)
            else:
                current_duration = 0
        
        # 收益率标准差
        returns = equity_series.pct_change().dropna()
        volatility = returns.std()
        annual_volatility = volatility * np.sqrt(252)
        
        # 夏普比率（无风险利率3%）
        risk_free_rate = 0.03
        sharpe_ratio = (returns.mean() - risk_free_rate/252) / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        
        # 索提诺比率
        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std() if len(downside_returns) > 0 else 0
        sortino_ratio = (returns.mean() - risk_free_rate/252) / downside_std * np.sqrt(252) if downside_std > 0 else 0
        
        # 卡尔玛比率
        max_drawdown_abs = abs(max_drawdown)
        calmar_ratio = result.annual_return / max_drawdown_abs if max_drawdown_abs > 0 else 0
        
        return {
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': f"{max_drawdown:.2%}",
            'avg_drawdown': avg_drawdown,
            'avg_drawdown_pct': f"{avg_drawdown:.2%}",
            'max_drawdown_duration': max_drawdown_duration,
            'volatility': annual_volatility,
            'volatility_pct': f"{annual_volatility:.2%}",
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'calmar_ratio': calmar_ratio,
            'var_95': returns.quantile(0.05) if len(returns) > 0 else 0,
            'cvar_95': returns[returns <= returns.quantile(0.05)].mean() if len(returns) > 0 else 0
        }
    
    def _calculate_trade_metrics(self, result) -> Dict:
        """计算交易相关指标"""
        trades = result.trades
        
        if not trades:
            return self._empty_trade_metrics()
        
        # 基础统计
        total_trades = len(trades)
        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl < 0]
        
        win_count = len(winning_trades)
        loss_count = len(losing_trades)
        win_rate = win_count / total_trades if total_trades > 0 else 0
        
        # 盈亏统计
        total_profit = sum([t.pnl for t in winning_trades])
        total_loss = abs(sum([t.pnl for t in losing_trades]))
        
        avg_profit = total_profit / win_count if win_count > 0 else 0
        avg_loss = total_loss / loss_count if loss_count > 0 else 0
        
        # 盈亏比
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        avg_win_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else float('inf')
        
        # 最大单笔盈亏
        max_profit = max([t.pnl for t in trades]) if trades else 0
        max_loss = min([t.pnl for t in trades]) if trades else 0
        
        # 连续交易统计
        consecutive_wins, consecutive_losses = self._calculate_consecutive_trades(trades)
        
        return {
            'total_trades': total_trades,
            'winning_trades': win_count,
            'losing_trades': loss_count,
            'win_rate': win_rate,
            'win_rate_pct': f"{win_rate:.2%}",
            'total_profit': total_profit,
            'total_loss': -total_loss,
            'net_profit': total_profit - total_loss,
            'avg_profit': avg_profit,
            'avg_loss': avg_loss,
            'avg_win_loss_ratio': avg_win_loss_ratio,
            'profit_factor': profit_factor,
            'max_profit': max_profit,
            'max_loss': max_loss,
            'consecutive_wins': consecutive_wins,
            'consecutive_losses': consecutive_losses
        }
    
    def _calculate_time_metrics(self, result) -> Dict:
        """计算时间相关指标"""
        trades = result.trades
        
        if not trades:
            return self._empty_time_metrics()
        
        # 持有期统计
        holding_periods = []
        for trade in trades:
            if trade.exit_date and trade.entry_date:
                entry_date = pd.to_datetime(trade.entry_date)
                exit_date = pd.to_datetime(trade.exit_date)
                holding_days = (exit_date - entry_date).days
                holding_periods.append(holding_days)
        
        if not holding_periods:
            return self._empty_time_metrics()
        
        avg_holding_period = np.mean(holding_periods)
        max_holding_period = max(holding_periods)
        min_holding_period = min(holding_periods)
        
        # 交易频率
        if result.equity_curve is not None and len(result.equity_curve) > 1:
            start_date = pd.to_datetime(result.equity_curve['date'].iloc[0])
            end_date = pd.to_datetime(result.equity_curve['date'].iloc[-1])
            total_days = (end_date - start_date).days
            trade_frequency = total_days / len(trades) if len(trades) > 0 else 0
        else:
            trade_frequency = 0
        
        return {
            'avg_holding_period': avg_holding_period,
            'max_holding_period': max_holding_period,
            'min_holding_period': min_holding_period,
            'trade_frequency': trade_frequency,
            'trades_per_month': 30 / trade_frequency if trade_frequency > 0 else 0
        }
    
    def _calculate_pvfrs_specific_metrics(self, result) -> Dict:
        """计算PVFRS特定指标"""
        trades = result.trades
        
        if not trades:
            return self._empty_pvfrs_metrics()
        
        # 按信号类型分析
        buy_signals = [t for t in trades if t.entry_price > 0]
        sell_reasons = {}
        
        for trade in trades:
            reason = trade.exit_reason or "未知"
            if reason not in sell_reasons:
                sell_reasons[reason] = []
            sell_reasons[reason].append(trade)
        
        # 计算不同退出原因的统计
        exit_reason_stats = {}
        for reason, reason_trades in sell_reasons.items():
            profits = [t.pnl for t in reason_trades]
            win_count = len([p for p in profits if p > 0])
            total_count = len(reason_trades)
            
            exit_reason_stats[reason] = {
                'count': total_count,
                'win_rate': win_count / total_count if total_count > 0 else 0,
                'avg_pnl': np.mean(profits) if profits else 0,
                'total_pnl': sum(profits)
            }
        
        # 按月份分析表现
        monthly_performance = self._calculate_monthly_performance(trades)
        
        return {
            'exit_reason_stats': exit_reason_stats,
            'monthly_performance': monthly_performance,
            'signal_effectiveness': self._calculate_signal_effectiveness(trades)
        }
    
    def _calculate_consecutive_trades(self, trades: List) -> Tuple[int, int]:
        """计算连续交易统计"""
        if not trades:
            return 0, 0
        
        consecutive_wins = 0
        consecutive_losses = 0
        current_streak = 0
        current_type = None  # 'win' or 'loss'
        
        for trade in trades:
            if trade.pnl > 0:
                if current_type == 'win':
                    current_streak += 1
                else:
                    current_streak = 1
                    current_type = 'win'
                consecutive_wins = max(consecutive_wins, current_streak)
            else:
                if current_type == 'loss':
                    current_streak += 1
                else:
                    current_streak = 1
                    current_type = 'loss'
                consecutive_losses = max(consecutive_losses, current_streak)
        
        return consecutive_wins, consecutive_losses
    
    def _calculate_monthly_performance(self, trades: List) -> Dict:
        """计算月度表现"""
        monthly_data = {}
        
        for trade in trades:
            if trade.exit_date:
                month = pd.to_datetime(trade.exit_date).strftime('%Y-%m')
                if month not in monthly_data:
                    monthly_data[month] = []
                monthly_data[month].append(trade)
        
        monthly_stats = {}
        for month, month_trades in monthly_data.items():
            profits = [t.pnl for t in month_trades]
            win_count = len([p for p in profits if p > 0])
            total_count = len(month_trades)
            
            monthly_stats[month] = {
                'trades': total_count,
                'wins': win_count,
                'win_rate': win_count / total_count if total_count > 0 else 0,
                'pnl': sum(profits),
                'return_pct': sum(profits) / 100000  # 假设本金10万
            }
        
        return monthly_stats
    
    def _calculate_signal_effectiveness(self, trades: List) -> Dict:
        """计算信号有效性"""
        # 这里可以根据交易时的信号条件进行更详细的分析
        # 暂时返回基础统计
        if not trades:
            return {}
        
        profits = [t.pnl for t in trades]
        positive_returns = len([p for p in profits if p > 0])
        
        return {
            'signal_accuracy': positive_returns / len(trades) if len(trades) > 0 else 0,
            'avg_signal_return': np.mean(profits) if profits else 0,
            'signal_consistency': np.std(profits) / np.mean(profits) if np.mean(profits) != 0 else 0
        }
    
    def _calculate_composite_score(self, metrics: Dict) -> float:
        """计算综合评分"""
        score = 0
        
        # 收益评分 (30%)
        annual_return = metrics.get('annual_return', 0)
        score += min(30, annual_return * 100)  # 年化收益30%满分
        
        # 风险评分 (25%)
        sharpe_ratio = metrics.get('sharpe_ratio', 0)
        score += min(25, max(0, sharpe_ratio * 5))  # 夏普比率5为满分
        
        # 稳定性评分 (20%)
        max_drawdown = abs(metrics.get('max_drawdown', 0))
        score += min(20, max(0, (0.1 - max_drawdown) * 200))  # 最大回撤10%以内满分
        
        # 胜率评分 (15%)
        win_rate = metrics.get('win_rate', 0)
        score += min(15, win_rate * 15)  # 胜率100%满分
        
        # 盈亏比评分 (10%)
        profit_factor = min(metrics.get('profit_factor', 0), 5)  # 限制最大值
        score += profit_factor * 2  # 盈亏比5为满分
        
        return min(100, score)
    
    def _empty_metrics(self) -> Dict:
        """空指标"""
        return {
            'total_return': 0,
            'annual_return': 0,
            'max_drawdown': 0,
            'sharpe_ratio': 0,
            'win_rate': 0,
            'profit_factor': 0,
            'total_trades': 0
        }
    
    def _empty_risk_metrics(self) -> Dict:
        """空风险指标"""
        return {
            'max_drawdown': 0,
            'volatility': 0,
            'sharpe_ratio': 0,
            'sortino_ratio': 0,
            'calmar_ratio': 0
        }
    
    def _empty_trade_metrics(self) -> Dict:
        """空交易指标"""
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'profit_factor': 0
        }
    
    def _empty_time_metrics(self) -> Dict:
        """空时间指标"""
        return {
            'avg_holding_period': 0,
            'max_holding_period': 0,
            'trade_frequency': 0
        }
    
    def _empty_pvfrs_metrics(self) -> Dict:
        """空PVFRS指标"""
        return {
            'exit_reason_stats': {},
            'monthly_performance': {},
            'signal_effectiveness': {}
        }

class PVFRSReportGenerator:
    """PVFRS策略报告生成器"""
    
    def __init__(self):
        self.analyzer = PVFRSPerformanceAnalyzer()
    
    def generate_comprehensive_report(self, backtest_result, output_path: str = None) -> str:
        """生成综合报告"""
        # 计算性能指标
        metrics = self.analyzer.calculate_comprehensive_metrics(backtest_result)
        
        # 生成报告内容
        report_content = self._generate_text_report(metrics, backtest_result)
        
        # 保存到文件
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report_content)
            logger.info(f"报告已保存到: {output_path}")
        
        return report_content
    
    def _generate_text_report(self, metrics: Dict, result) -> str:
        """生成文本报告"""
        report = f"""
# PVFRS策略回测报告

## 基本信息
- 回测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 初始资金: ¥{result.initial_capital:,.0f}
- 最终资金: ¥{result.final_capital:,.0f}
- 交易次数: {metrics.get('total_trades', 0)}

## 收益表现
- 总收益率: {metrics.get('total_return_pct', '0%')}
- 年化收益率: {metrics.get('annual_return_pct', '0%')}
- 月均收益率: {metrics.get('monthly_return_pct', '0%')}
- 资金倍数: {metrics.get('capital_multiple', 1):.2f}x
- 超额收益: {metrics.get('excess_return_pct', '0%')}

## 风险指标
- 最大回撤: {metrics.get('max_drawdown_pct', '0%')}
- 平均回撤: {metrics.get('avg_drawdown_pct', '0%')}
- 年化波动率: {metrics.get('volatility_pct', '0%')}
- 夏普比率: {metrics.get('sharpe_ratio', 0):.2f}
- 索提诺比率: {metrics.get('sortino_ratio', 0):.2f}
- 卡尔玛比率: {metrics.get('calmar_ratio', 0):.2f}

## 交易统计
- 胜率: {metrics.get('win_rate_pct', '0%')}
- 盈利交易: {metrics.get('winning_trades', 0)}
- 亏损交易: {metrics.get('losing_trades', 0)}
- 盈亏比: {metrics.get('profit_factor', 0):.2f}
- 平均盈利: ¥{metrics.get('avg_profit', 0):,.2f}
- 平均亏损: ¥{metrics.get('avg_loss', 0):,.2f}
- 最大盈利: ¥{metrics.get('max_profit', 0):,.2f}
- 最大亏损: ¥{metrics.get('max_loss', 0):,.2f}
- 连续盈利: {metrics.get('consecutive_wins', 0)}次
- 连续亏损: {metrics.get('consecutive_losses', 0)}次

## 时间分析
- 平均持有期: {metrics.get('avg_holding_period', 0):.1f}天
- 最长持有期: {metrics.get('max_holding_period', 0)}天
- 交易频率: {metrics.get('trade_frequency', 0):.1f}天/次
- 月均交易: {metrics.get('trades_per_month', 0):.1f}次

## PVFRS策略分析
### 退出原因统计
"""
        
        # 添加退出原因统计
        exit_reason_stats = metrics.get('exit_reason_stats', {})
        for reason, stats in exit_reason_stats.items():
            report += f"- {reason}: {stats['count']}次, 胜率{stats['win_rate']:.2%}, 平均盈亏¥{stats['avg_pnl']:,.2f}\n"
        
        report += f"""
### 月度表现
"""
        # 添加月度表现
        monthly_performance = metrics.get('monthly_performance', {})
        for month, stats in monthly_performance.items():
            report += f"- {month}: {stats['trades']}次, 胜率{stats['win_rate']:.2%}, 收益率{stats['return_pct']:.2%}\n"
        
        report += f"""
## 综合评分
- 策略评分: {metrics.get('composite_score', 0):.1f}/100

## 交易明细
"""
        
        # 添加交易明细
        for i, trade in enumerate(result.trades[-10:], 1):  # 只显示最近10笔
            report += f"{i}. {trade.entry_date} -> {trade.exit_date}: "
            report += f"¥{trade.entry_price:.2f} -> ¥{trade.exit_price:.2f}, "
            report += f"盈亏¥{trade.pnl:.2f} ({trade.pnl_percent:.2%}), "
            report += f"原因: {trade.exit_reason}\n"
        
        report += f"""
## 策略建议
{self._generate_strategy_recommendations(metrics)}
"""
        
        return report
    
    def _generate_strategy_recommendations(self, metrics: Dict) -> str:
        """生成策略建议"""
        recommendations = []
        
        # 基于收益率的建议
        annual_return = metrics.get('annual_return', 0)
        if annual_return < 0.1:
            recommendations.append("- 年化收益率较低，建议优化入场条件或增加过滤条件")
        elif annual_return > 0.3:
            recommendations.append("- 年化收益率很高，建议关注过拟合风险，进行样本外测试")
        
        # 基于回撤的建议
        max_drawdown = abs(metrics.get('max_drawdown', 0))
        if max_drawdown > 0.2:
            recommendations.append("- 最大回撤较大，建议加强止损策略或降低仓位")
        
        # 基于胜率的建议
        win_rate = metrics.get('win_rate', 0)
        if win_rate < 0.4:
            recommendations.append("- 胜率较低，建议重新评估信号生成逻辑")
        elif win_rate > 0.7:
            recommendations.append("- 胜率很高，检查是否存在未来函数或数据泄露")
        
        # 基于夏普比率的建议
        sharpe_ratio = metrics.get('sharpe_ratio', 0)
        if sharpe_ratio < 1:
            recommendations.append("- 夏普比率偏低，建议提高风险调整后收益")
        
        # 基于交易频率的建议
        trade_frequency = metrics.get('trade_frequency', 0)
        if trade_frequency > 30:
            recommendations.append("- 交易频率过高，建议增加信号过滤条件")
        elif trade_frequency < 5:
            recommendations.append("- 交易频率过低，可能错过机会，建议适当放宽条件")
        
        return "\n".join(recommendations) if recommendations else "- 策略表现良好，建议继续监控和微调"

# 便捷函数
def analyze_pvfrs_performance(backtest_result, output_path: str = None) -> Dict:
    """便捷函数：分析PVFRS策略性能"""
    analyzer = PVFRSPerformanceAnalyzer()
    return analyzer.calculate_comprehensive_metrics(backtest_result)

def generate_pvfrs_report(backtest_result, output_path: str = None) -> str:
    """便捷函数：生成PVFRS策略报告"""
    generator = PVFRSReportGenerator()
    return generator.generate_comprehensive_report(backtest_result, output_path)
