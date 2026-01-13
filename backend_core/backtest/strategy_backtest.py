"""
策略回测程序
用于测试多指标综合交易策略的表现
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import json
import os
from pathlib import Path

from backend_core.strategies.multi_indicator_strategy import MultiIndicatorStrategy, TradeSignal


class StrategyBacktester:
    """策略回测器"""
    
    def __init__(self, strategy: MultiIndicatorStrategy):
        """
        初始化回测器
        :param strategy: 交易策略实例
        """
        self.strategy = strategy
        self.results = {}
        
    def load_data_from_db(self, symbol: str, start_date: str, end_date: str, market_type: str = "CN") -> List[Dict]:
        """
        从数据库加载历史数据
        :param symbol: 股票代码
        :param start_date: 开始日期
        :param end_date: 结束日期
        :param market_type: 市场类型(CN/HK)
        :return: 历史数据列表
        """
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from backend_api.models import HistoricalQuotes, HistoricalQuotesHK
            
            # 从配置获取数据库连接信息
            import os
            from backend_api.database import DATABASE_URL
            
            engine = create_engine(DATABASE_URL)
            Session = sessionmaker(bind=engine)
            session = Session()
            
            if market_type == "CN":
                query = session.query(HistoricalQuotes).filter(
                    HistoricalQuotes.code == symbol,
                    HistoricalQuotes.date >= start_date,
                    HistoricalQuotes.date <= end_date
                ).order_by(HistoricalQuotes.date).all()
                
                data = []
                for row in query:
                    data.append({
                        'date': str(row.date),
                        'open': float(row.open) if row.open else 0.0,
                        'high': float(row.high) if row.high else 0.0,
                        'low': float(row.low) if row.low else 0.0,
                        'close': float(row.close) if row.close else 0.0,
                        'volume': float(row.volume) if row.volume else 0.0,
                        'amount': float(row.amount) if row.amount else 0.0,
                    })
            else:  # HK
                query = session.query(HistoricalQuotesHK).filter(
                    HistoricalQuotesHK.code == symbol,
                    HistoricalQuotesHK.date >= start_date,
                    HistoricalQuotesHK.date <= end_date
                ).order_by(HistoricalQuotesHK.date).all()
                
                data = []
                for row in query:
                    data.append({
                        'date': str(row.date),
                        'open': float(row.open) if row.open else 0.0,
                        'high': float(row.high) if row.high else 0.0,
                        'low': float(row.low) if row.low else 0.0,
                        'close': float(row.close) if row.close else 0.0,
                        'volume': float(row.volume) if row.volume else 0.0,
                        'amount': float(row.amount) if row.amount else 0.0,
                    })
            
            session.close()
            return data
            
        except Exception as e:
            print(f"从数据库加载数据失败: {e}")
            return self.load_sample_data()  # 使用示例数据
    
    def load_sample_data(self) -> List[Dict]:
        """
        加载示例数据用于测试
        :return: 示例数据列表
        """
        print("使用示例数据进行回测...")
        import random
        
        data = []
        base_price = 50.0
        start_date = datetime(2023, 1, 1)
        
        for i in range(500):  # 500个交易日的数据
            current_date = start_date + timedelta(days=i)
            # 添加周末跳过逻辑
            if current_date.weekday() >= 5:  # 周六、周日跳过
                continue
            
            # 生成价格波动，模拟真实市场
            volatility = 0.02  # 波动率
            change_percent = random.uniform(-volatility, volatility)
            close = base_price * (1 + change_percent)
            
            # 随机生成高低价
            high = close * (1 + abs(random.uniform(0, 0.015)))
            low = close * (1 - abs(random.uniform(0, 0.015)))
            open_price = base_price if i > 0 else close
            
            data.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': random.randint(1000000, 10000000)  # 随机成交量
            })
            
            base_price = close
            if len(data) >= 300:  # 限制数据量
                break
        
        return data
    
    def load_data_from_csv(self, csv_path: str) -> List[Dict]:
        """
        从CSV文件加载历史数据
        :param csv_path: CSV文件路径
        :return: 历史数据列表
        """
        try:
            df = pd.read_csv(csv_path)
            # 确保列名正确
            required_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_columns):
                raise ValueError(f"CSV文件必须包含以下列: {required_columns}")
            
            data = []
            for _, row in df.iterrows():
                data.append({
                    'date': str(row['date']),
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': float(row['volume'])
                })
            
            return data
        except Exception as e:
            print(f"从CSV加载数据失败: {e}")
            return self.load_sample_data()
    
    def run_backtest(self, data: List[Dict], initial_capital: float = 100000) -> Dict:
        """
        运行回测
        :param data: 历史数据
        :param initial_capital: 初始资金
        :return: 回测结果
        """
        # 重置策略
        self.strategy = MultiIndicatorStrategy(initial_capital=initial_capital)
        
        # 执行回测
        results = self.strategy.backtest(data)
        
        # 计算额外指标
        results['sharpe_ratio'] = self._calculate_sharpe_ratio(data, results)
        results['max_drawdown'] = self._calculate_max_drawdown(data, results)
        results['profit_factor'] = self._calculate_profit_factor(results)
        
        self.results = results
        return results
    
    def _calculate_sharpe_ratio(self, data: List[Dict], results: Dict) -> float:
        """计算夏普比率"""
        if len(data) < 2:
            return 0.0
        
        # 计算日收益率
        returns = []
        for i in range(1, len(data)):
            daily_return = (data[i]['close'] - data[i-1]['close']) / data[i-1]['close']
            returns.append(daily_return)
        
        if not returns:
            return 0.0
        
        # 计算年化收益率和波动率
        avg_return = np.mean(returns) * 252  # 年化
        volatility = np.std(returns) * np.sqrt(252)  # 年化波动率
        
        # 假设无风险利率为3%
        risk_free_rate = 0.03
        
        if volatility == 0:
            return 0.0
        
        return (avg_return - risk_free_rate) / volatility
    
    def _calculate_max_drawdown(self, data: List[Dict], results: Dict) -> float:
        """计算最大回撤"""
        if len(data) < 2:
            return 0.0
        
        # 计算模拟的资产净值变化
        prices = [item['close'] for item in data]
        returns = [0] + [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
        
        # 计算累计净值
        equity_curve = [1.0]  # 基准为1
        for ret in returns[1:]:
            equity_curve.append(equity_curve[-1] * (1 + ret))
        
        # 计算回撤
        running_max = 0
        max_drawdown = 0
        
        for value in equity_curve:
            if value > running_max:
                running_max = value
            drawdown = (running_max - value) / running_max if running_max > 0 else 0
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return max_drawdown
    
    def _calculate_profit_factor(self, results: Dict) -> float:
        """计算盈利因子"""
        winning_trades = results.get('winning_trades', 0)
        losing_trades = results.get('losing_trades', 0)
        
        if losing_trades == 0:
            return float('inf') if winning_trades > 0 else 0
        
        # 这里简化计算，实际应该基于每笔交易的盈亏金额
        # 为了更精确的计算，我们需要修改策略以记录每笔交易的盈亏
        total_profit = sum(pos.exit_price - pos.entry_price 
                          for pos in results.get('positions', []) 
                          if pos.exit_price and pos.exit_price > pos.entry_price)
        total_loss = sum(pos.entry_price - pos.exit_price 
                        for pos in results.get('positions', []) 
                        if pos.exit_price and pos.exit_price < pos.entry_price)
        
        if total_loss == 0:
            return float('inf') if total_profit > 0 else 0
        
        return total_profit / total_loss
    
    def plot_results(self, data: List[Dict], save_path: Optional[str] = None):
        """
        绘制回测结果图表
        :param data: 历史数据
        :param save_path: 保存路径，如果为None则显示图表
        """
        if not self.results or not data:
            print("没有回测结果或数据可绘制")
            return
        
        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        
        # 创建子图
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('多指标综合策略回测结果', fontsize=16)
        
        # 1. 价格走势和交易信号
        ax1 = axes[0, 0]
        dates = [item['date'] for item in data]
        closes = [item['close'] for item in data]
        
        ax1.plot(dates, closes, label='收盘价', linewidth=1)
        
        # 标记买入和卖出点
        buy_signals = []
        buy_prices = []
        sell_signals = []
        sell_prices = []
        
        for signal in self.results.get('signals', []):
            idx = next((i for i, item in enumerate(data) if item['date'] == signal.date), None)
            if idx is not None:
                if signal.action == 'buy':
                    buy_signals.append(signal.date)
                    buy_prices.append(data[idx]['close'])
                elif signal.action == 'sell':
                    sell_signals.append(signal.date)
                    sell_prices.append(data[idx]['close'])
        
        if buy_signals:
            ax1.scatter(buy_signals, buy_prices, color='red', marker='^', s=100, label='买入信号', zorder=5)
        if sell_signals:
            ax1.scatter(sell_signals, sell_prices, color='green', marker='v', s=100, label='卖出信号', zorder=5)
        
        ax1.set_title('价格走势与交易信号')
        ax1.set_ylabel('价格')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 为了显示清晰，只显示部分日期标签
        ax1.set_xticks(ax1.get_xticks()[::max(1, len(dates)//10)])
        plt.setp(ax1.get_xticklabels(), rotation=45, ha="right")
        
        # 2. 资产净值曲线
        ax2 = axes[0, 1]
        
        # 计算净值曲线
        initial_capital = self.results['initial_capital']
        if self.results['positions']:
            # 计算每笔交易后的净值变化
            trade_dates = []
            net_values = []
            
            current_capital = initial_capital
            position = None
            
            # 按日期排序的交易历史
            all_trades = sorted(
                self.results['trade_history'], 
                key=lambda x: x.date
            )
            
            # 计算净值变化
            for trade in all_trades:
                idx = next((i for i, item in enumerate(data) if item['date'] == trade.date), None)
                if idx is not None:
                    current_price = data[idx]['close']
                    
                    if trade.action == 'buy' and position is None:
                        # 买入
                        cost = trade.indicators['close'] * 100  # 假设买入100股
                        current_capital -= cost
                        position = {
                            'entry_price': trade.indicators['close'],
                            'quantity': 100,
                            'entry_date': trade.date
                        }
                    elif trade.action == 'sell' and position is not None:
                        # 卖出
                        revenue = current_price * position['quantity']
                        current_capital += revenue
                        position = None
                    
                    trade_dates.append(trade.date)
                    net_values.append(current_capital)
            
            # 如果还有持仓，按最后价格计算
            if position:
                last_price = data[-1]['close']
                current_capital += position['quantity'] * last_price
            
            if trade_dates:
                ax2.plot(trade_dates, net_values, label='资产净值', color='blue', linewidth=2)
            else:
                # 如果没有交易，画一条水平线
                net_values = [initial_capital] * len(dates)
                ax2.plot(dates, net_values, label='初始资金', color='blue', linewidth=2)
        else:
            # 没有交易，画一条水平线
            net_values = [initial_capital] * len(dates)
            ax2.plot(dates, net_values, label='资产净值', color='blue', linewidth=2)
        
        ax2.set_title('资产净值曲线')
        ax2.set_ylabel('净值')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        plt.setp(ax2.get_xticklabels(), rotation=45, ha="right")
        
        # 3. 收益分布
        ax3 = axes[1, 0]
        
        if self.results['positions']:
            profits = []
            for pos in self.results['positions']:
                if pos.exit_price:
                    profit = (pos.exit_price - pos.entry_price) / pos.entry_price * 100
                    profits.append(profit)
            
            if profits:
                ax3.hist(profits, bins=20, alpha=0.7, color='skyblue', edgecolor='black')
                ax3.set_title('交易盈亏分布')
                ax3.set_xlabel('收益率 (%)')
                ax3.set_ylabel('交易次数')
                ax3.grid(True, alpha=0.3)
            else:
                ax3.text(0.5, 0.5, '无完成交易', horizontalalignment='center', 
                        verticalalignment='center', transform=ax3.transAxes)
                ax3.set_title('交易盈亏分布')
        else:
            ax3.text(0.5, 0.5, '无完成交易', horizontalalignment='center', 
                    verticalalignment='center', transform=ax3.transAxes)
            ax3.set_title('交易盈亏分布')
        
        # 4. 指标统计
        ax4 = axes[1, 1]
        ax4.axis('off')  # 关闭坐标轴
        
        # 准备显示的统计信息
        stats_text = f"""
        回测统计指标:

        初始资金: {self.results['initial_capital']:,.2f}
        最终资金: {self.results['final_capital']:,.2f}
        总收益率: {self.results['total_return']:.2%}

        总交易数: {self.results['total_trades']}
        盈利交易: {self.results['winning_trades']}
        亏损交易: {self.results['losing_trades']}
        胜率: {self.results['win_rate']:.2%}

        夏普比率: {self.results.get('sharpe_ratio', 0):.4f}
        最大回撤: {self.results.get('max_drawdown', 0):.2%}
        盈利因子: {self.results.get('profit_factor', 0):.4f}
        """
        
        ax4.text(0.1, 0.9, stats_text, transform=ax4.transAxes, fontsize=12,
                verticalalignment='top', bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8))
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"图表已保存到: {save_path}")
        else:
            plt.show()
    
    def export_results(self, file_path: str):
        """
        导出回测结果到文件
        :param file_path: 输出文件路径
        """
        if not self.results:
            print("没有回测结果可导出")
            return
        
        # 准备导出数据
        export_data = {
            'backtest_info': {
                'run_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'initial_capital': self.results['initial_capital'],
                'final_capital': self.results['final_capital'],
                'total_return': self.results['total_return']
            },
            'performance_metrics': {
                'total_trades': self.results['total_trades'],
                'winning_trades': self.results['winning_trades'],
                'losing_trades': self.results['losing_trades'],
                'win_rate': self.results['win_rate'],
                'sharpe_ratio': self.results.get('sharpe_ratio', 0),
                'max_drawdown': self.results.get('max_drawdown', 0),
                'profit_factor': self.results.get('profit_factor', 0)
            },
            'trade_history': [
                {
                    'date': signal.date,
                    'action': signal.action,
                    'confidence': signal.confidence,
                    'reason': signal.reason,
                    'indicators': signal.indicators
                } for signal in self.results.get('signals', [])
            ],
            'positions': [
                {
                    'symbol': pos.symbol,
                    'entry_date': pos.entry_date,
                    'entry_price': pos.entry_price,
                    'quantity': pos.quantity,
                    'exit_date': pos.exit_date,
                    'exit_price': pos.exit_price,
                    'profit_loss': (pos.exit_price - pos.entry_price) * pos.quantity if pos.exit_price else None,
                    'return_rate': (pos.exit_price - pos.entry_price) / pos.entry_price if pos.exit_price else None
                } for pos in self.results.get('positions', [])
            ]
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        print(f"回测结果已导出到: {file_path}")
    
    def print_summary(self):
        """打印回测摘要"""
        if not self.results:
            print("没有回测结果")
            return
        
        print("="*50)
        print("多指标综合策略回测摘要")
        print("="*50)
        print(f"初始资金:     {self.results['initial_capital']:>12,.2f}")
        print(f"最终资金:     {self.results['final_capital']:>12,.2f}")
        print(f"总收益率:     {self.results['total_return']:>12.2%}")
        print("-" * 50)
        print(f"总交易次数:   {self.results['total_trades']:>12}")
        print(f"盈利交易:     {self.results['winning_trades']:>12}")
        print(f"亏损交易:     {self.results['losing_trades']:>12}")
        print(f"胜率:         {self.results['win_rate']:>12.2%}")
        print("-" * 50)
        print(f"夏普比率:     {self.results.get('sharpe_ratio', 0):>12.4f}")
        print(f"最大回撤:     {self.results.get('max_drawdown', 0):>12.2%}")
        print(f"盈利因子:     {self.results.get('profit_factor', 0):>12.4f}")
        print("="*50)


def run_sample_backtest():
    """运行示例回测"""
    print("开始运行多指标综合策略回测...")
    
    # 创建策略实例
    strategy = MultiIndicatorStrategy(initial_capital=100000, risk_per_trade=0.02)
    
    # 创建回测器
    backtester = StrategyBacktester(strategy)
    
    # 加载示例数据
    print("加载历史数据...")
    data = backtester.load_sample_data()
    print(f"加载了 {len(data)} 天的历史数据")
    
    # 运行回测
    print("开始回测...")
    results = backtester.run_backtest(data, initial_capital=100000)
    
    # 打印摘要
    backtester.print_summary()
    
    # 绘制结果图表
    print("生成回测图表...")
    backtester.plot_results(data)
    
    # 导出结果
    output_dir = Path("backtest_results")
    output_dir.mkdir(exist_ok=True)
    result_file = output_dir / f"backtest_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    backtester.export_results(str(result_file))
    
    return results


if __name__ == "__main__":
    # 运行示例回测
    results = run_sample_backtest()