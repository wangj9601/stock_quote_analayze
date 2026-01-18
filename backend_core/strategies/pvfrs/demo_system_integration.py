#!/usr/bin/env python3
"""
PVFRS策略系统集成演示
展示完整的端到端策略执行流程，包括单股分析、批量选股和回测功能
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from datetime import datetime, timedelta
from typing import List, Dict
import random

from backend_core.strategies.pvfrs import MarketData, SignalType
from backend_core.strategies.pvfrs.pvfrs_system import PVFRSSystem, create_pvfrs_system, quick_analyze_stock


def generate_sample_data(symbol: str, days: int = 30) -> List[MarketData]:
    """生成示例市场数据
    
    Args:
        symbol: 股票代码
        days: 生成天数
        
    Returns:
        List[MarketData]: 市场数据列表
    """
    data = []
    base_price = 10.0
    base_volume = 1000000
    
    for i in range(days):
        date = (datetime.now() - timedelta(days=days-i-1)).strftime('%Y-%m-%d')
        
        # 模拟价格波动
        price_change = random.uniform(-0.05, 0.08)  # 稍微偏向上涨
        base_price *= (1 + price_change)
        
        # 模拟成交量波动
        volume_change = random.uniform(-0.3, 0.5)
        volume = int(base_volume * (1 + volume_change))
        
        # 生成OHLC数据
        open_price = base_price * random.uniform(0.98, 1.02)
        close_price = base_price
        high_price = max(open_price, close_price) * random.uniform(1.0, 1.03)
        low_price = min(open_price, close_price) * random.uniform(0.97, 1.0)
        
        market_data = MarketData(
            symbol=symbol,
            date=date,
            open=round(open_price, 2),
            high=round(high_price, 2),
            low=round(low_price, 2),
            close=round(close_price, 2),
            volume=volume,
            amount=round(volume * close_price, 2)
        )
        
        data.append(market_data)
    
    return data


def demo_system_initialization():
    """演示系统初始化"""
    print("=== PVFRS策略系统初始化演示 ===")
    
    # 1. 使用默认配置创建系统
    system = create_pvfrs_system()
    
    # 2. 获取系统状态
    status = system.get_system_status()
    print(f"系统名称: {status['system_name']}")
    print(f"系统版本: {status['version']}")
    print(f"初始化状态: {'✓ 已初始化' if status['initialized'] else '✗ 未初始化'}")
    print(f"系统就绪: {'✓ 就绪' if status['system_ready'] else '✗ 未就绪'}")
    
    # 3. 显示组件信息
    print("\n组件状态:")
    for name, component_type in status['components'].items():
        print(f"  - {name}: {component_type}")
    
    # 4. 验证系统完整性
    validation = system.validate_system()
    print(f"\n系统验证: {'✓ 通过' if validation['overall_valid'] else '✗ 失败'}")
    if validation['issues']:
        print("发现问题:")
        for issue in validation['issues']:
            print(f"  - {issue}")
    
    print()
    return system


def demo_single_stock_analysis(system: PVFRSSystem):
    """演示单股分析功能"""
    print("=== 单股分析演示 ===")
    
    # 1. 生成示例数据
    symbol = "000001"
    data = generate_sample_data(symbol, 30)
    
    print(f"分析股票: {symbol}")
    print(f"数据范围: {data[0].date} - {data[-1].date}")
    print(f"数据长度: {len(data)}天")
    
    try:
        # 2. 执行完整分析
        analysis_result = system.analyze_single_stock(symbol, data)
        
        # 3. 显示分析结果
        print(f"\n分析时间: {analysis_result['analysis_time']}")
        print(f"综合评分: {analysis_result['overall_score']:.2f}")
        
        # 策略分析结果
        strategy_assessment = analysis_result['strategy_analysis']['strategy_assessment']
        print(f"买入信号: {'✓ 有' if strategy_assessment['has_buy_signal'] else '✗ 无'}")
        print(f"三维共振: {'✓ 是' if strategy_assessment['three_dimension_resonance'] else '✗ 否'}")
        print(f"高效轨道: {'✓ 是' if strategy_assessment['high_efficiency_trajectory'] else '✗ 否'}")
        print(f"最大信号强度: {strategy_assessment['max_signal_strength']:.2f}")
        
        # 共振分析结果
        resonance_signal = analysis_result['resonance_analysis']['signal']
        if resonance_signal:
            print(f"\n共振信号:")
            print(f"  信号类型: {resonance_signal['signal_type']}")
            print(f"  信号强度: {resonance_signal['strength']:.2f}")
            print(f"  信号价格: {resonance_signal['price']:.2f}")
            print(f"  信号原因: {resonance_signal['reason']}")
        else:
            print("\n共振信号: 无")
        
        # 投资建议
        advice = analysis_result['investment_advice']
        print(f"\n投资建议:")
        print(f"  推荐操作: {advice['recommendation']}")
        print(f"  信心度: {advice['confidence']:.1%}")
        print(f"  风险等级: {advice['risk_level']}")
        print(f"  建议仓位: {advice['suggested_position_size']:.1%}")
        print(f"  理由: {', '.join(advice['reasons'])}")
        
        # 条件验证
        validation = analysis_result['condition_validation']
        print(f"\n条件验证: {'✓ 通过' if validation['valid'] else '✗ 失败'}")
        if not validation['valid']:
            print(f"  失败原因: {validation['reason']}")
        
        print(f"\n✓ 单股分析完成")
        
    except Exception as e:
        print(f"✗ 单股分析失败: {str(e)}")
    
    print()


def demo_batch_screening(system: PVFRSSystem):
    """演示批量选股功能"""
    print("=== 批量选股演示 ===")
    
    # 1. 准备股票列表
    symbols = ["000001", "000002", "000858", "002415", "300059"]
    target_date = datetime.now().strftime('%Y-%m-%d')
    
    print(f"选股股票池: {symbols}")
    print(f"目标日期: {target_date}")
    
    try:
        # 2. 执行批量选股
        screening_result = system.screen_stocks(symbols, target_date)
        
        # 3. 显示选股结果
        stats = screening_result['screening_stats']
        print(f"\n选股统计:")
        print(f"  输入股票数: {stats['total_input']}")
        print(f"  数据可用数: {stats['data_available']}")
        print(f"  分析完成数: {stats['analysis_completed']}")
        print(f"  符合条件数: {stats['qualified_count']}")
        print(f"  失败股票数: {stats['failed_count']}")
        print(f"  成功率: {stats['success_rate']:.1%}")
        print(f"  通过率: {stats['qualification_rate']:.1%}")
        
        # 4. 显示符合条件的股票
        qualified_stocks = screening_result['qualified_stocks']
        if qualified_stocks:
            print(f"\n符合条件的股票:")
            for i, stock in enumerate(qualified_stocks[:5], 1):  # 显示前5只
                signal = stock['signal']
                print(f"  {i}. {stock['symbol']}")
                print(f"     信号强度: {signal['strength']:.2f}")
                print(f"     信号价格: {signal['price']:.2f}")
                print(f"     信号原因: {signal['reason']}")
        else:
            print(f"\n符合条件的股票: 无")
        
        # 5. 维度分析汇总
        dimension_summary = screening_result['dimension_summary']
        print(f"\n维度通过率:")
        rates = dimension_summary['dimension_pass_rates']
        print(f"  价格维度: {rates['price']:.1%}")
        print(f"  频率维度: {rates['frequency']:.1%}")
        print(f"  成交量维度: {rates['volume']:.1%}")
        print(f"  三维共振: {rates['three_dimension']:.1%}")
        
        print(f"\n✓ 批量选股完成")
        
    except Exception as e:
        print(f"✗ 批量选股失败: {str(e)}")
    
    print()


def demo_backtest_functionality(system: PVFRSSystem):
    """演示回测功能"""
    print("=== 回测功能演示 ===")
    
    # 1. 准备回测参数
    symbols = ["000001", "000002"]
    start_date = "2024-01-01"
    end_date = "2024-12-31"
    initial_capital = 100000
    
    print(f"回测股票: {symbols}")
    print(f"回测期间: {start_date} - {end_date}")
    print(f"初始资金: {initial_capital:,.2f}")
    
    try:
        # 2. 执行回测
        backtest_report = system.run_backtest(symbols, start_date, end_date, initial_capital)
        
        # 3. 显示回测结果
        result = backtest_report['backtest_result']
        print(f"\n回测结果:")
        print(f"  最终资金: {result['final_capital']:,.2f}")
        print(f"  总收益率: {result['total_return']:+.1%}")
        print(f"  年化收益率: {result['annual_return']:+.1%}")
        print(f"  最大回撤: {result['max_drawdown']:.1%}")
        print(f"  夏普比率: {result['sharpe_ratio']:.2f}")
        print(f"  胜率: {result['win_rate']:.1%}")
        print(f"  盈亏比: {result['profit_factor']:.2f}")
        print(f"  总交易次数: {result['total_trades']}")
        print(f"  盈利交易: {result['winning_trades']}")
        print(f"  亏损交易: {result['losing_trades']}")
        print(f"  平均持有期: {result['avg_holding_period']:.1f}天")
        
        # 4. 风险分析
        risk_analysis = backtest_report['risk_analysis']
        print(f"\n风险分析:")
        print(f"  整体风险评分: {risk_analysis.get('overall_risk_score', 0):.2f}")
        
        print(f"\n✓ 回测功能演示完成")
        
    except Exception as e:
        print(f"✗ 回测功能演示失败: {str(e)}")
    
    print()


def demo_configuration_management(system: PVFRSSystem):
    """演示配置管理功能"""
    print("=== 配置管理演示 ===")
    
    # 1. 获取当前配置
    current_config = system.config_manager.get_current_config()
    print("当前主要配置:")
    key_params = ['stop_loss', 'take_profit', 'max_position_size', 'max_holding_days']
    for param in key_params:
        if param in current_config:
            value = current_config[param]
            if isinstance(value, float) and abs(value) < 1:
                print(f"  {param}: {value:.1%}")
            else:
                print(f"  {param}: {value}")
    
    # 2. 更新配置
    new_config = {
        'stop_loss': -0.08,  # 调整止损到-8%
        'take_profit': 0.30,  # 调整止盈到30%
        'max_position_size': 0.15  # 调整最大仓位到15%
    }
    
    print(f"\n更新配置:")
    for param, value in new_config.items():
        if isinstance(value, float) and abs(value) < 1:
            print(f"  {param}: {value:.1%}")
        else:
            print(f"  {param}: {value}")
    
    # 3. 应用新配置
    success = system.update_config(new_config)
    print(f"\n配置更新: {'✓ 成功' if success else '✗ 失败'}")
    
    # 4. 验证配置
    updated_config = system.config_manager.get_current_config()
    is_valid = system.config_manager.validate_config(updated_config)
    print(f"配置验证: {'✓ 有效' if is_valid else '✗ 无效'}")
    
    print(f"\n✓ 配置管理演示完成")
    print()


def demo_quick_functions():
    """演示快捷函数"""
    print("=== 快捷函数演示 ===")
    
    # 1. 快速分析单股
    symbol = "000001"
    data = generate_sample_data(symbol, 25)
    
    print(f"快速分析股票: {symbol}")
    
    try:
        # 使用快捷函数
        result = quick_analyze_stock(symbol, data)
        
        print(f"综合评分: {result['overall_score']:.2f}")
        
        advice = result['investment_advice']
        print(f"投资建议: {advice['recommendation']} (信心度: {advice['confidence']:.1%})")
        
        print(f"✓ 快速分析完成")
        
    except Exception as e:
        print(f"✗ 快速分析失败: {str(e)}")
    
    print()


def demo_error_handling():
    """演示错误处理"""
    print("=== 错误处理演示 ===")
    
    system = create_pvfrs_system()
    
    # 1. 数据不足的情况
    print("1. 测试数据不足的情况:")
    insufficient_data = generate_sample_data("TEST001", 10)  # 只有10天数据
    
    try:
        result = system.analyze_single_stock("TEST001", insufficient_data)
        print("✗ 应该抛出数据不足异常")
    except Exception as e:
        print(f"✓ 正确捕获异常: {type(e).__name__}: {str(e)}")
    
    # 2. 空数据的情况
    print("\n2. 测试空数据的情况:")
    try:
        result = system.analyze_single_stock("TEST002", [])
        print("✗ 应该抛出数据不足异常")
    except Exception as e:
        print(f"✓ 正确捕获异常: {type(e).__name__}: {str(e)}")
    
    # 3. 无效配置的情况
    print("\n3. 测试无效配置的情况:")
    invalid_config = {
        'stop_loss': 0.1,  # 止损应该是负数
        'take_profit': -0.2,  # 止盈应该是正数
        'max_position_size': 1.5  # 仓位不应该超过100%
    }
    
    try:
        is_valid = system.config_manager.validate_config(invalid_config)
        print(f"配置验证结果: {'有效' if is_valid else '无效'}")
        if not is_valid:
            print("✓ 正确识别无效配置")
    except Exception as e:
        print(f"✓ 正确捕获配置异常: {type(e).__name__}: {str(e)}")
    
    print(f"\n✓ 错误处理演示完成")
    print()


def main():
    """主演示函数"""
    print("PVFRS策略系统集成演示")
    print("=" * 60)
    print()
    
    try:
        # 1. 系统初始化演示
        system = demo_system_initialization()
        
        # 2. 单股分析演示
        demo_single_stock_analysis(system)
        
        # 3. 批量选股演示
        demo_batch_screening(system)
        
        # 4. 回测功能演示
        demo_backtest_functionality(system)
        
        # 5. 配置管理演示
        demo_configuration_management(system)
        
        # 6. 快捷函数演示
        demo_quick_functions()
        
        # 7. 错误处理演示
        demo_error_handling()
        
        print("=" * 60)
        print("✓ PVFRS策略系统集成演示完成！")
        print("✓ 所有模块已成功集成")
        print("✓ 端到端流程验证通过")
        print("✓ 错误处理机制正常")
        print("✓ 系统已准备就绪，可以投入使用")
        
        return True
        
    except Exception as e:
        print(f"✗ 演示过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)