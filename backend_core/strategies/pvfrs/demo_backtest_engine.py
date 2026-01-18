"""
PVFRS回测引擎演示脚本
展示回测引擎的完整功能，包括交易模拟、盈亏计算和报告生成
"""

import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict

# 添加路径
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from backend_core.strategies.pvfrs.backtest_engine import BacktestEngine
from backend_core.strategies.pvfrs.models import MarketData
from backend_core.strategies.pvfrs.config import PVFRSConfigManager


def create_demo_market_data() -> Dict[str, List[MarketData]]:
    """创建演示用的市场数据"""
    print("创建演示市场数据...")
    
    stock_data = {}
    
    # 创建3只股票的数据
    symbols = ["000001", "000002", "600000"]
    
    for symbol in symbols:
        market_data = []
        base_price = 10.0 + hash(symbol) % 10  # 不同股票不同起始价格
        base_volume = 1000000 + hash(symbol) % 500000
        
        # 创建60天的数据
        for i in range(60):
            date = (datetime(2024, 1, 1) + timedelta(days=i)).strftime('%Y-%m-%d')
            
            # 模拟不同的价格走势
            if symbol == "000001":
                # 上涨趋势
                trend = i * 0.008
                volatility = (i % 7 - 3) * 0.015
            elif symbol == "000002":
                # 震荡趋势
                trend = 0
                volatility = (i % 5 - 2) * 0.02
            else:
                # 先涨后跌
                if i < 30:
                    trend = i * 0.01
                else:
                    trend = (30 - (i - 30)) * 0.01
                volatility = (i % 6 - 2.5) * 0.012
            
            current_price = base_price * (1 + trend + volatility)
            
            # 模拟成交量变化
            volume_factor = 1 + (i % 4 - 1.5) * 0.2
            if abs(volatility) > 0.015:  # 价格波动大时成交量放大
                volume_factor *= 1.5
            
            current_volume = int(base_volume * volume_factor)
            
            market_data.append(MarketData(
                symbol=symbol,
                date=date,
                open=current_price * 0.995,
                high=current_price * 1.025,
                low=current_price * 0.985,
                close=current_price,
                volume=current_volume,
                amount=current_volume * current_price
            ))
        
        stock_data[symbol] = market_data
        print(f"  {symbol}: 创建了{len(market_data)}天的数据")
    
    return stock_data


def demo_backtest_execution():
    """演示回测执行"""
    print("\n" + "="*50)
    print("PVFRS回测引擎演示")
    print("="*50)
    
    # 1. 创建回测引擎
    print("\n1. 初始化回测引擎...")
    engine = BacktestEngine()
    
    # 显示配置信息
    config = engine.config
    print(f"   初始资金: {config['initial_capital']:,}")
    print(f"   手续费率: {config['commission_rate']*100:.3f}%")
    print(f"   滑点率: {config['slippage_rate']*100:.3f}%")
    print(f"   最大仓位: {config['max_position_size']*100:.1f}%")
    print(f"   止损: {config['stop_loss']*100:.1f}%")
    print(f"   止盈: {config['take_profit']*100:.1f}%")
    
    # 2. 创建市场数据
    stock_data = create_demo_market_data()
    
    # 3. 执行回测
    print("\n2. 执行回测...")
    try:
        result = engine.run_backtest_with_data(
            stock_data_dict=stock_data,
            start_date="2024-01-01",
            end_date="2024-02-29",
            initial_capital=100000
        )
        
        print("   回测执行成功！")
        
        # 4. 显示基本结果
        print("\n3. 回测结果摘要:")
        print(f"   初始资金: {result.initial_capital:,.2f}")
        print(f"   最终资金: {result.final_capital:,.2f}")
        print(f"   总收益率: {result.total_return*100:.2f}%")
        print(f"   年化收益率: {result.annual_return*100:.2f}%")
        print(f"   最大回撤: {result.max_drawdown*100:.2f}%")
        print(f"   夏普比率: {result.sharpe_ratio:.2f}")
        print(f"   胜率: {result.win_rate*100:.1f}%")
        print(f"   盈亏比: {result.profit_factor:.2f}")
        print(f"   总交易次数: {result.total_trades}")
        print(f"   平均持仓期: {result.avg_holding_period:.1f}天")
        
        # 5. 生成详细报告
        print("\n4. 生成回测报告...")
        
        # 生成摘要报告
        summary_report = engine.generate_backtest_report(report_type='summary')
        
        print("   摘要报告生成完成")
        print(f"   性能评级: {summary_report['performance_grade']}")
        print(f"   风险评估: {summary_report['risk_assessment']}")
        
        # 生成综合报告
        comprehensive_report = engine.generate_backtest_report(report_type='comprehensive')
        
        print("   综合报告生成完成")
        
        # 显示执行摘要
        exec_summary = comprehensive_report['executive_summary']
        strategy_performance = exec_summary['strategy_performance']
        
        print(f"   策略评级: {strategy_performance['overall_grade']}")
        print(f"   风险水平: {strategy_performance['risk_level']}")
        print(f"   总体建议: {strategy_performance['recommendation']}")
        
        # 6. 交易分析
        print("\n5. 交易分析:")
        if result.trades:
            completed_trades = [t for t in result.trades if t.exit_price is not None]
            open_trades = [t for t in result.trades if t.exit_price is None]
            
            print(f"   已完成交易: {len(completed_trades)}")
            print(f"   持仓中交易: {len(open_trades)}")
            
            if completed_trades:
                winning_trades = [t for t in completed_trades if t.pnl and t.pnl > 0]
                losing_trades = [t for t in completed_trades if t.pnl and t.pnl < 0]
                
                print(f"   盈利交易: {len(winning_trades)}")
                print(f"   亏损交易: {len(losing_trades)}")
                
                if winning_trades:
                    avg_win = sum([t.pnl for t in winning_trades]) / len(winning_trades)
                    print(f"   平均盈利: {avg_win:.2f}")
                
                if losing_trades:
                    avg_loss = sum([t.pnl for t in losing_trades]) / len(losing_trades)
                    print(f"   平均亏损: {avg_loss:.2f}")
                
                # 显示前5笔交易
                print("\n   前5笔已完成交易:")
                for i, trade in enumerate(completed_trades[:5]):
                    pnl_str = f"{trade.pnl:+.2f}" if trade.pnl else "N/A"
                    pnl_pct_str = f"{trade.pnl_percent*100:+.2f}%" if trade.pnl_percent else "N/A"
                    print(f"     {i+1}. {trade.symbol} {trade.entry_date} -> {trade.exit_date}")
                    print(f"        {trade.entry_price:.2f} -> {trade.exit_price:.2f} | {pnl_str} ({pnl_pct_str})")
        
        # 7. 导出报告
        print("\n6. 导出报告...")
        try:
            # 导出JSON报告
            json_path = "demo_backtest_report.json"
            engine.generate_backtest_report(
                report_type='comprehensive',
                export_format='json',
                export_path=json_path
            )
            print(f"   JSON报告已导出: {json_path}")
            
            # 导出HTML报告
            html_path = "demo_backtest_report.html"
            engine.generate_backtest_report(
                report_type='comprehensive',
                export_format='html',
                export_path=html_path
            )
            print(f"   HTML报告已导出: {html_path}")
            
        except Exception as e:
            print(f"   报告导出失败: {str(e)}")
        
        # 8. 投资组合分析
        print("\n7. 投资组合分析:")
        portfolio_analysis = engine.get_portfolio_analysis()
        
        portfolio_summary = portfolio_analysis['portfolio_summary']
        print(f"   交易股票数: {portfolio_summary['symbols_traded']}")
        print(f"   总盈亏: {portfolio_summary['total_pnl']:.2f}")
        print(f"   已实现盈亏: {portfolio_summary['realized_pnl']:.2f}")
        print(f"   浮动盈亏: {portfolio_summary['floating_pnl']:.2f}")
        
        # 9. 风险分析
        risk_analysis = portfolio_analysis['risk_analysis']
        print(f"   最大连续亏损: {risk_analysis['max_consecutive_losses']}")
        print(f"   最大连续盈利: {risk_analysis['max_consecutive_wins']}")
        print(f"   风险收益比: {risk_analysis['risk_reward_ratio']:.2f}")
        
    except Exception as e:
        print(f"   回测执行失败: {str(e)}")
        print("   这可能是因为策略没有生成足够的信号，或者数据不满足PVFRS条件")
        return
    
    print("\n" + "="*50)
    print("演示完成！")
    print("="*50)


def demo_individual_components():
    """演示各个组件的功能"""
    print("\n" + "="*50)
    print("组件功能演示")
    print("="*50)
    
    # 1. 演示PnL计算器
    print("\n1. PnL计算器演示:")
    from backend_core.strategies.pvfrs.trade_recorder import PnLCalculator
    from backend_core.strategies.pvfrs.models import Trade
    
    calculator = PnLCalculator()
    
    # 创建示例交易
    demo_trade = Trade(
        symbol="000001",
        entry_date="2024-01-01",
        exit_date="2024-01-10",
        entry_price=10.0,
        exit_price=11.0,
        quantity=1000,
        position_size=10000.0
    )
    
    pnl, pnl_pct, details = calculator.calculate_trade_pnl(demo_trade)
    
    print(f"   交易: {demo_trade.symbol}")
    print(f"   买入: {demo_trade.entry_price:.2f} x {demo_trade.quantity}")
    print(f"   卖出: {demo_trade.exit_price:.2f} x {demo_trade.quantity}")
    print(f"   绝对盈亏: {pnl:.2f}")
    print(f"   百分比盈亏: {pnl_pct*100:.2f}%")
    print(f"   总手续费: {details['total_commission']:.2f}")
    print(f"   总滑点: {details['total_slippage']:.2f}")
    print(f"   持有天数: {details['holding_days']}")
    
    # 2. 演示风险管理器
    print("\n2. 风险管理器演示:")
    from backend_core.strategies.pvfrs.backtest_engine import RiskManager
    
    config = {
        'stop_loss': -0.06,
        'take_profit': 0.25,
        'max_holding_days': 45
    }
    risk_manager = RiskManager(config)
    
    entry_price = 10.0
    
    # 测试不同价格的风险检查
    test_prices = [9.3, 9.5, 10.5, 12.6]
    
    for price in test_prices:
        stop_loss = risk_manager.check_stop_loss(price, entry_price)
        take_profit = risk_manager.check_take_profit(price, entry_price)
        change_pct = (price - entry_price) / entry_price * 100
        
        print(f"   价格 {price:.2f} ({change_pct:+.1f}%): ", end="")
        if stop_loss:
            print("触发止损")
        elif take_profit:
            print("触发止盈")
        else:
            print("正常持有")
    
    # 3. 演示报告生成器
    print("\n3. 报告生成器演示:")
    from backend_core.strategies.pvfrs.backtest_report_generator import BacktestReportGenerator
    from backend_core.strategies.pvfrs.models import BacktestResult
    
    # 创建示例回测结果
    sample_trades = [demo_trade]
    sample_equity_curve = [
        {'date': '2024-01-01', 'total_value': 100000, 'cash': 90000, 'positions_value': 10000},
        {'date': '2024-01-10', 'total_value': 101000, 'cash': 91000, 'positions_value': 10000}
    ]
    
    sample_result = BacktestResult(
        initial_capital=100000,
        final_capital=101000,
        total_return=0.01,
        annual_return=0.04,
        max_drawdown=0.02,
        sharpe_ratio=1.5,
        win_rate=1.0,
        profit_factor=float('inf'),
        total_trades=1,
        winning_trades=1,
        losing_trades=0,
        avg_holding_period=9.0,
        trades=sample_trades,
        equity_curve=sample_equity_curve
    )
    
    generator = BacktestReportGenerator()
    summary = generator.generate_summary_report(sample_result)
    
    print(f"   性能评级: {summary['performance_grade']}")
    print(f"   风险评估: {summary['risk_assessment']}")
    print(f"   总收益率: {summary['key_metrics']['total_return']*100:.2f}%")
    print(f"   夏普比率: {summary['key_metrics']['sharpe_ratio']:.2f}")


if __name__ == "__main__":
    print("PVFRS回测引擎演示程序")
    print("本程序将演示回测引擎的完整功能")
    
    # 主要演示
    demo_backtest_execution()
    
    # 组件演示
    demo_individual_components()
    
    print("\n演示程序结束。")
    print("您可以查看生成的报告文件：")
    print("- demo_backtest_report.json")
    print("- demo_backtest_report.html")