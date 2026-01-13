"""
多指标综合交易策略执行器
用于运行和测试基于MACD、KDJ、RSI、BOLL、PVFRS指标的交易策略
"""

import argparse
import sys
from pathlib import Path
import pandas as pd

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent))

from backend_core.strategies.multi_indicator_strategy import MultiIndicatorStrategy
from backend_core.backtest.strategy_backtest import StrategyBacktester


def main():
    parser = argparse.ArgumentParser(description='多指标综合交易策略执行器')
    parser.add_argument('--mode', choices=['backtest', 'live', 'paper'], default='backtest',
                       help='运行模式: backtest(回测), live(实盘), paper(模拟盘)')
    parser.add_argument('--symbol', type=str, default='000001',
                       help='股票代码 (默认: 000001)')
    parser.add_argument('--start-date', type=str, default='2023-01-01',
                       help='开始日期 (YYYY-MM-DD格式, 默认: 2023-01-01)')
    parser.add_argument('--end-date', type=str, default='2023-12-31',
                       help='结束日期 (YYYY-MM-DD格式, 默认: 2023-12-31)')
    parser.add_argument('--capital', type=float, default=100000,
                       help='初始资金 (默认: 100000)')
    parser.add_argument('--risk-per-trade', type=float, default=0.02,
                       help='每次交易风险比例 (默认: 0.02, 即2%)')
    parser.add_argument('--market-type', choices=['CN', 'HK'], default='CN',
                       help='市场类型: CN(A股), HK(港股) (默认: CN)')
    parser.add_argument('--plot', action='store_true',
                       help='是否绘制回测结果图表')
    parser.add_argument('--export-results', type=str,
                       help='导出结果到指定JSON文件路径')
    
    args = parser.parse_args()
    
    print("="*60)
    print("多指标综合交易策略执行器")
    print("="*60)
    print(f"运行模式: {args.mode}")
    print(f"股票代码: {args.symbol}")
    print(f"日期范围: {args.start_date} 至 {args.end_date}")
    print(f"初始资金: {args.capital:,.2f}")
    print(f"市场类型: {args.market_type}")
    print("="*60)
    
    # 创建策略实例
    strategy = MultiIndicatorStrategy(
        initial_capital=args.capital,
        risk_per_trade=args.risk_per_trade
    )
    
    # 创建回测器
    backtester = StrategyBacktester(strategy)
    
    if args.mode == 'backtest':
        print("开始回测...")
        
        # 加载数据
        print("加载历史数据...")
        data = backtester.load_data_from_db(
            symbol=args.symbol,
            start_date=args.start_date,
            end_date=args.end_date,
            market_type=args.market_type
        )
        
        if not data:
            print("警告: 无法从数据库加载数据，使用示例数据进行回测...")
            data = backtester.load_sample_data()
        
        print(f"加载了 {len(data)} 天的历史数据")
        
        # 运行回测
        results = backtester.run_backtest(data, initial_capital=args.capital)
        
        # 打印摘要
        backtester.print_summary()
        
        # 绘制结果
        if args.plot:
            print("生成回测图表...")
            output_dir = Path("backtest_results")
            output_dir.mkdir(exist_ok=True)
            chart_path = output_dir / f"backtest_chart_{args.symbol}_{args.start_date}_to_{args.end_date}.png"
            backtester.plot_results(data, str(chart_path))
            print(f"图表已保存到: {chart_path}")
        
        # 导出结果
        if args.export_results:
            backtester.export_results(args.export_results)
            print(f"结果已导出到: {args.export_results}")
        
        # 如果没有指定导出路径，也保存到默认位置
        elif args.mode == 'backtest':
            from datetime import datetime
            output_dir = Path("backtest_results")
            output_dir.mkdir(exist_ok=True)
            result_file = output_dir / f"backtest_result_{args.symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            backtester.export_results(str(result_file))
            print(f"结果已保存到: {result_file}")
    
    elif args.mode in ['live', 'paper']:
        print("注意: 实盘和模拟盘功能尚未完全实现")
        print("当前仅支持回测模式")
        print("如需实现实盘交易，请联系开发者")
    
    print("\n策略执行完成!")


def run_default_backtest():
    """运行默认回测配置"""
    print("运行默认配置的回测...")
    
    # 创建策略实例
    strategy = MultiIndicatorStrategy(initial_capital=100000, risk_per_trade=0.02)
    
    # 创建回测器
    backtester = StrategyBacktester(strategy)
    
    # 加载示例数据
    print("加载示例历史数据...")
    data = backtester.load_sample_data()
    print(f"加载了 {len(data)} 天的示例数据")
    
    # 运行回测
    results = backtester.run_backtest(data, initial_capital=100000)
    
    # 打印摘要
    backtester.print_summary()
    
    # 绘制结果
    print("生成回测图表...")
    backtester.plot_results(data)
    
    # 导出结果
    from datetime import datetime
    output_dir = Path("backtest_results")
    output_dir.mkdir(exist_ok=True)
    result_file = output_dir / f"default_backtest_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    backtester.export_results(str(result_file))
    print(f"结果已保存到: {result_file}")
    
    return results


if __name__ == "__main__":
    # 如果没有命令行参数，运行默认回测
    if len(sys.argv) == 1:
        run_default_backtest()
    else:
        main()