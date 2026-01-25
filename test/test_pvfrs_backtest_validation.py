#!/usr/bin/env python3
"""
PVFRS策略改进后的回测验证脚本
对所有改进进行历史数据回测，验证效果并调优参数
"""

import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_api.database import SessionLocal
from backend_api.models import HistoricalQuotes, HistoricalQuotesHK
from backend_core.strategies.pvfrs import MarketData
from backend_core.strategies.pvfrs.backtest_engine import BacktestEngine
from backend_core.strategies.pvfrs.config import PVFRSConfigManager
from sqlalchemy import cast, Date as SA_Date, asc

def get_stock_data_from_db(db, symbol: str, start_date: str, end_date: str) -> List[MarketData]:
    """从数据库获取股票历史数据
    
    Args:
        db: 数据库会话
        symbol: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        
    Returns:
        List[MarketData]: 市场数据列表
    """
    try:
        # 判断是A股还是港股（与admin逻辑一致）
        is_hk = (symbol.startswith('0') and len(symbol) == 5) or symbol.startswith('HK') or symbol.startswith('hk')
        
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        
        market_data_list = []
        
        if is_hk:
            # 港股数据
            date_col = cast(HistoricalQuotesHK.date, SA_Date)
            quotes = db.query(HistoricalQuotesHK).filter(
                HistoricalQuotesHK.code == symbol,
                date_col >= start_dt,
                date_col <= end_dt
            ).order_by(asc(date_col)).all()
        else:
            # A股数据
            date_col = cast(HistoricalQuotes.date, SA_Date)
            quotes = db.query(HistoricalQuotes).filter(
                HistoricalQuotes.code == symbol,
                date_col >= start_dt,
                date_col <= end_dt
            ).order_by(asc(date_col)).all()
        
        for quote in quotes:
            try:
                market_data = MarketData(
                    symbol=symbol,
                    date=str(quote.date)[:10] if quote.date else "",
                    open=float(quote.open) if quote.open else 0.0,
                    high=float(quote.high) if quote.high else 0.0,
                    low=float(quote.low) if quote.low else 0.0,
                    close=float(quote.close) if quote.close else 0.0,
                    volume=int(quote.volume) if quote.volume else 0,
                    amount=float(quote.amount) if hasattr(quote, 'amount') and quote.amount else 0.0
                )
                market_data_list.append(market_data)
            except (ValueError, TypeError) as e:
                print(f"警告: 跳过无效数据 {symbol} {quote.date} - {e}")
                continue
        
        return market_data_list
        
    except Exception as e:
        print(f"错误: 从数据库获取股票 {symbol} 数据失败: {str(e)}")
        return []


def run_backtest_validation(
    stock_codes: List[str],
    start_date: str,
    end_date: str,
    initial_capital: float = 100000,
    config_overrides: Optional[Dict] = None
) -> Dict:
    """运行回测验证
    
    Args:
        stock_codes: 股票代码列表
        start_date: 开始日期
        end_date: 结束日期
        initial_capital: 初始资金
        config_overrides: 配置覆盖参数（可选）
        
    Returns:
        Dict: 回测结果
    """
    print(f"\n{'='*80}")
    print(f"开始回测验证")
    print(f"{'='*80}")
    print(f"股票代码: {', '.join(stock_codes)}")
    print(f"回测区间: {start_date} 到 {end_date}")
    print(f"初始资金: {initial_capital:,.0f}")
    print(f"{'='*80}\n")
    
    # 加载历史数据
    print("正在加载历史数据...")
    stock_data_dict = {}
    
    db = SessionLocal()
    try:
        for symbol in stock_codes:
            data = get_stock_data_from_db(db, symbol, start_date, end_date)
            if data and len(data) >= 20:
                stock_data_dict[symbol] = data
                print(f"  ✓ {symbol}: {len(data)} 条数据")
            else:
                print(f"  ✗ {symbol}: 数据不足（需要至少20天）")
    finally:
        db.close()
    
    if not stock_data_dict:
        return {
            'success': False,
            'error': '没有获取到有效的股票数据'
        }
    
    # 创建回测引擎
    config_manager = PVFRSConfigManager()
    if config_overrides:
        # 应用配置覆盖
        config = config_manager.load_config()
        config.update(config_overrides)
        # 创建临时配置管理器
        class TempConfigManager:
            def load_config(self):
                return config
        config_manager = TempConfigManager()
    
    engine = BacktestEngine(config_manager)
    
    # 运行回测
    print(f"\n正在运行回测...")
    try:
        result = engine.run_backtest_with_data(
            stock_data_dict=stock_data_dict,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital
        )
        
        # 提取关键指标
        metrics = {
            'success': True,
            'initial_capital': result.initial_capital,
            'final_capital': result.final_capital,
            'total_return': result.total_return,
            'total_return_pct': f"{result.total_return:.2%}",
            'annual_return': result.annual_return,
            'annual_return_pct': f"{result.annual_return:.2%}",
            'max_drawdown': result.max_drawdown,
            'max_drawdown_pct': f"{result.max_drawdown:.2%}",
            'sharpe_ratio': result.sharpe_ratio,
            'win_rate': result.win_rate,
            'win_rate_pct': f"{result.win_rate:.2%}",
            'profit_factor': result.profit_factor,
            'total_trades': result.total_trades,
            'winning_trades': result.winning_trades,
            'losing_trades': result.losing_trades,
            'avg_holding_period': result.avg_holding_period,
            'trades': [
                {
                    'symbol': t.symbol,
                    'entry_date': t.entry_date,
                    'exit_date': t.exit_date,
                    'entry_price': t.entry_price,
                    'exit_price': t.exit_price,
                    'pnl': t.pnl,
                    'pnl_percent': t.pnl_percent,
                    'exit_reason': t.exit_reason
                }
                for t in result.trades
            ]
        }
        
        return metrics
        
    except Exception as e:
        print(f"回测执行失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e)
        }


def print_validation_report(metrics: Dict):
    """打印验证报告"""
    if not metrics.get('success'):
        print(f"\n❌ 回测失败: {metrics.get('error', '未知错误')}")
        return
    
    print(f"\n{'='*80}")
    print(f"回测验证报告")
    print(f"{'='*80}\n")
    
    print(f"【收益指标】")
    print(f"  初始资金: {metrics['initial_capital']:,.0f}")
    print(f"  最终资金: {metrics['final_capital']:,.0f}")
    print(f"  总收益率: {metrics['total_return_pct']}")
    print(f"  年化收益率: {metrics['annual_return_pct']}")
    
    print(f"\n【风险指标】")
    print(f"  最大回撤: {metrics['max_drawdown_pct']}")
    print(f"  夏普比率: {metrics['sharpe_ratio']:.2f}")
    
    print(f"\n【交易统计】")
    print(f"  总交易次数: {metrics['total_trades']}")
    print(f"  盈利交易: {metrics['winning_trades']}")
    print(f"  亏损交易: {metrics['losing_trades']}")
    print(f"  胜率: {metrics['win_rate_pct']}")
    print(f"  盈亏比: {metrics['profit_factor']:.2f}")
    print(f"  平均持有天数: {metrics['avg_holding_period']:.1f}")
    
    if metrics['trades']:
        print(f"\n【交易明细】")
        for i, trade in enumerate(metrics['trades'][:10], 1):  # 只显示前10笔
            pnl_sign = "+" if trade['pnl'] and trade['pnl'] > 0 else ""
            print(f"  {i}. {trade['symbol']} | {trade['entry_date']} → {trade['exit_date']}")
            print(f"     买入: ¥{trade['entry_price']:.2f} | 卖出: ¥{trade['exit_price']:.2f}")
            print(f"     盈亏: {pnl_sign}¥{trade['pnl']:.2f} ({trade['pnl_percent']:.2%}) | {trade['exit_reason']}")
        
        if len(metrics['trades']) > 10:
            print(f"  ... 还有 {len(metrics['trades']) - 10} 笔交易未显示")
    
    print(f"\n{'='*80}\n")


def run_parameter_optimization(
    stock_codes: List[str],
    start_date: str,
    end_date: str,
    initial_capital: float = 100000,
    param_grid: Optional[Dict] = None
) -> Dict:
    """参数优化
    
    Args:
        stock_codes: 股票代码列表
        start_date: 开始日期
        end_date: 结束日期
        initial_capital: 初始资金
        param_grid: 参数网格
        
    Returns:
        Dict: 优化结果
    """
    if param_grid is None:
        param_grid = {
            'stop_loss': [-0.05, -0.06, -0.08, -0.10],
            'take_profit': [0.15, 0.20, 0.25, 0.30],
            'max_position_size': [0.08, 0.10, 0.12]
        }
    
    print(f"\n{'='*80}")
    print(f"开始参数优化")
    print(f"{'='*80}\n")
    
    best_result = None
    best_score = -float('inf')
    best_params = None
    optimization_log = []
    
    # 计算总组合数
    total_combinations = 1
    for key, values in param_grid.items():
        total_combinations *= len(values)
    
    print(f"参数组合总数: {total_combinations}")
    print(f"参数网格: {json.dumps(param_grid, indent=2, ensure_ascii=False)}\n")
    
    combination_count = 0
    
    # 遍历所有参数组合
    for stop_loss in param_grid.get('stop_loss', [-0.06]):
        for take_profit in param_grid.get('take_profit', [0.25]):
            for max_position_size in param_grid.get('max_position_size', [0.10]):
                combination_count += 1
                
                config_overrides = {
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'max_position_size': max_position_size
                }
                
                print(f"[{combination_count}/{total_combinations}] 测试参数组合:")
                print(f"  stop_loss={stop_loss:.2%}, take_profit={take_profit:.2%}, max_position_size={max_position_size:.2%}")
                
                # 运行回测
                result = run_backtest_validation(
                    stock_codes=stock_codes,
                    start_date=start_date,
                    end_date=end_date,
                    initial_capital=initial_capital,
                    config_overrides=config_overrides
                )
                
                if result.get('success'):
                    # 计算综合评分（可以根据需要调整权重）
                    score = (
                        result['total_return'] * 0.4 +
                        result['sharpe_ratio'] * 0.3 +
                        result['win_rate'] * 0.2 +
                        (1 + result['profit_factor']) / 2 * 0.1
                    )
                    
                    optimization_log.append({
                        'params': config_overrides.copy(),
                        'score': score,
                        'total_return': result['total_return'],
                        'sharpe_ratio': result['sharpe_ratio'],
                        'win_rate': result['win_rate'],
                        'max_drawdown': result['max_drawdown'],
                        'total_trades': result['total_trades']
                    })
                    
                    print(f"  评分: {score:.4f} | 总收益: {result['total_return_pct']} | 夏普: {result['sharpe_ratio']:.2f} | 胜率: {result['win_rate_pct']}")
                    
                    if score > best_score:
                        best_score = score
                        best_result = result
                        best_params = config_overrides.copy()
                        print(f"  ✓ 新的最佳参数组合！\n")
                    else:
                        print()
                else:
                    print(f"  ✗ 回测失败: {result.get('error', '未知错误')}\n")
    
    return {
        'best_result': best_result,
        'best_params': best_params,
        'best_score': best_score,
        'optimization_log': optimization_log
    }


def main():
    """主函数"""
    # 默认回测参数
    stock_codes = ["688114", "000001"]  # 可以修改为要测试的股票代码
    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')  # 最近一年
    end_date = datetime.now().strftime('%Y-%m-%d')
    initial_capital = 100000
    
    # 运行基础回测验证
    print("="*80)
    print("PVFRS策略改进后的回测验证")
    print("="*80)
    
    metrics = run_backtest_validation(
        stock_codes=stock_codes,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital
    )
    
    print_validation_report(metrics)
    
    # 可选：运行参数优化
    # print("\n是否运行参数优化？(y/n): ", end="")
    # if input().lower() == 'y':
    #     optimization_result = run_parameter_optimization(
    #         stock_codes=stock_codes,
    #         start_date=start_date,
    #         end_date=end_date,
    #         initial_capital=initial_capital
    #     )
    #     
    #     if optimization_result['best_result']:
    #         print(f"\n{'='*80}")
    #         print(f"参数优化完成")
    #         print(f"{'='*80}")
    #         print(f"最佳参数: {json.dumps(optimization_result['best_params'], indent=2, ensure_ascii=False)}")
    #         print(f"最佳评分: {optimization_result['best_score']:.4f}")
    #         print_validation_report(optimization_result['best_result'])


if __name__ == "__main__":
    main()
