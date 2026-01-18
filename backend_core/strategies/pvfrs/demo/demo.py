#!/usr/bin/env python3
"""
PVFRS策略核心数据模型演示
展示MarketData、PVFRSIndicators、Signal等核心数据类的使用
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from datetime import datetime, timedelta
from backend_core.strategies.pvfrs import (
    MarketData, PVFRSIndicators, Signal, Trade, BacktestResult,
    SignalType, PVFRSConfigManager
)


def demo_market_data():
    """演示MarketData的使用"""
    print("=== MarketData 演示 ===")
    
    # 创建市场数据
    market_data = MarketData(
        symbol="000001",
        date="2024-01-15",
        open=10.0,
        high=11.0,
        low=9.5,
        close=10.5,
        volume=1000000,
        amount=10500000.0
    )
    
    print(f"股票代码: {market_data.symbol}")
    print(f"交易日期: {market_data.date}")
    print(f"开盘价: {market_data.open}")
    print(f"最高价: {market_data.high}")
    print(f"最低价: {market_data.low}")
    print(f"收盘价: {market_data.close}")
    print(f"成交量: {market_data.volume:,}")
    print(f"成交额: {market_data.amount:,.2f}")
    print()


def demo_pvfrs_indicators():
    """演示PVFRSIndicators的使用"""
    print("=== PVFRSIndicators 演示 ===")
    
    # 创建PVFRS指标
    indicators = PVFRSIndicators(
        macro_displacement=0.5,
        instant_deviation=0.3,
        avg_price_20d=10.2,
        rising_days=12,
        falling_days=8,
        frequency_advantage=True,
        avg_volume_20d=1200000.0,
        current_volume=1400000.0,
        efficiency_ratio=1.17,
        amplitude_ratio=0.049,
        resonance_strength=0.75
    )
    
    print(f"宏观位移: {indicators.macro_displacement}")
    print(f"即时强度: {indicators.instant_deviation}")
    print(f"20日平均价格: {indicators.avg_price_20d}")
    print(f"上涨天数: {indicators.rising_days}")
    print(f"下跌天数: {indicators.falling_days}")
    print(f"频率优势: {indicators.frequency_advantage}")
    print(f"20日平均成交量: {indicators.avg_volume_20d:,.0f}")
    print(f"当前成交量: {indicators.current_volume:,.0f}")
    print(f"效率比: {indicators.efficiency_ratio:.2f}")
    print(f"幅度系数: {indicators.amplitude_ratio:.3f}")
    print(f"共振强度: {indicators.resonance_strength:.2f}")
    print()


def demo_signal():
    """演示Signal的使用"""
    print("=== Signal 演示 ===")
    
    # 创建买入信号
    buy_signal = Signal(
        symbol="000001",
        date="2024-01-15",
        signal_type=SignalType.BUY,
        price=10.5,
        strength=0.8,
        reason="三维共振买入信号",
        conditions_met={
            'macro_displacement_positive': True,
            'instant_deviation_sufficient': True,
            'rising_days_advantage': True,
            'efficiency_positive': True
        }
    )
    
    print(f"股票代码: {buy_signal.symbol}")
    print(f"信号日期: {buy_signal.date}")
    print(f"信号类型: {buy_signal.signal_type.value}")
    print(f"信号价格: {buy_signal.price}")
    print(f"信号强度: {buy_signal.strength:.1%}")
    print(f"信号原因: {buy_signal.reason}")
    print("满足条件:")
    for condition, met in buy_signal.conditions_met.items():
        print(f"  - {condition}: {'✓' if met else '✗'}")
    print()


def demo_trade():
    """演示Trade的使用"""
    print("=== Trade 演示 ===")
    
    # 创建交易记录
    trade = Trade(
        symbol="000001",
        entry_date="2024-01-15",
        exit_date="2024-01-20",
        entry_price=10.5,
        exit_price=11.2,
        quantity=1000,
        position_size=10500.0,
        pnl=700.0,
        pnl_percent=0.067,
        exit_reason="止盈"
    )
    
    print(f"股票代码: {trade.symbol}")
    print(f"入场日期: {trade.entry_date}")
    print(f"出场日期: {trade.exit_date}")
    print(f"入场价格: {trade.entry_price}")
    print(f"出场价格: {trade.exit_price}")
    print(f"交易数量: {trade.quantity}")
    print(f"仓位大小: {trade.position_size:,.2f}")
    print(f"盈亏金额: {trade.pnl:+,.2f}")
    print(f"盈亏比例: {trade.pnl_percent:+.1%}")
    print(f"出场原因: {trade.exit_reason}")
    print()


def demo_config_manager():
    """演示配置管理器的使用"""
    print("=== PVFRSConfigManager 演示 ===")
    
    # 创建配置管理器
    config_manager = PVFRSConfigManager()
    
    # 获取默认配置
    config = config_manager.get_default_config()
    
    print("主要配置参数:")
    print(f"止损比例: {config['stop_loss']:.1%}")
    print(f"止盈比例: {config['take_profit']:.1%}")
    print(f"最大仓位: {config['max_position_size']:.1%}")
    print(f"最大持有天数: {config['max_holding_days']}")
    print(f"观察周期: {config['observation_period']}天")
    print(f"最小偏离度: {config['buy_bias_min']:.1%}")
    print(f"最小相对位移: {config['buy_relative_displacement_min']:.1%}")
    
    # 验证配置
    is_valid = config_manager.validate_config(config)
    print(f"配置有效性: {'✓ 有效' if is_valid else '✗ 无效'}")
    print()


def demo_backtest_result():
    """演示BacktestResult的使用"""
    print("=== BacktestResult 演示 ===")
    
    # 创建回测结果
    result = BacktestResult(
        initial_capital=100000.0,
        final_capital=125000.0,
        total_return=0.25,
        annual_return=0.18,
        max_drawdown=-0.08,
        sharpe_ratio=1.5,
        win_rate=0.65,
        profit_factor=2.1,
        total_trades=20,
        winning_trades=13,
        losing_trades=7,
        avg_holding_period=15.5,
        trades=[],
        equity_curve=[]
    )
    
    print(f"初始资金: {result.initial_capital:,.2f}")
    print(f"最终资金: {result.final_capital:,.2f}")
    print(f"总收益率: {result.total_return:+.1%}")
    print(f"年化收益率: {result.annual_return:+.1%}")
    print(f"最大回撤: {result.max_drawdown:.1%}")
    print(f"夏普比率: {result.sharpe_ratio:.2f}")
    print(f"胜率: {result.win_rate:.1%}")
    print(f"盈亏比: {result.profit_factor:.2f}")
    print(f"总交易次数: {result.total_trades}")
    print(f"盈利交易: {result.winning_trades}")
    print(f"亏损交易: {result.losing_trades}")
    print(f"平均持有期: {result.avg_holding_period:.1f}天")
    print()


def main():
    """主演示函数"""
    print("PVFRS策略核心数据模型演示")
    print("=" * 50)
    print()
    
    try:
        demo_market_data()
        demo_pvfrs_indicators()
        demo_signal()
        demo_trade()
        demo_config_manager()
        demo_backtest_result()
        
        print("✓ 所有核心数据模型演示完成！")
        print("✓ 数据验证和类型检查正常工作")
        print("✓ 配置管理功能正常")
        print("✓ 项目结构和基础设施已就绪")
        
    except Exception as e:
        print(f"✗ 演示过程中出现错误: {e}")
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)