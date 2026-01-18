"""
PVFRS策略引擎和选股功能演示
展示如何使用策略引擎进行股票分析和批量选股
"""

from datetime import datetime, timedelta
from typing import List, Dict
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from strategies.pvfrs.models import MarketData
from strategies.pvfrs.strategy_engine import StrategyEngine
from strategies.pvfrs.stock_screener import StockScreener, ScreeningConfig
from strategies.pvfrs.screening_report import ScreeningReportGenerator, ReportConfig


def create_sample_market_data(symbol: str, days: int = 25) -> List[MarketData]:
    """创建示例市场数据
    
    Args:
        symbol: 股票代码
        days: 数据天数
        
    Returns:
        List[MarketData]: 示例市场数据列表
    """
    import random
    
    data = []
    base_price = random.uniform(10, 100)
    base_volume = random.randint(1000000, 10000000)
    
    start_date = datetime.now() - timedelta(days=days)
    
    for i in range(days):
        date = start_date + timedelta(days=i)
        
        # 模拟价格走势（整体上涨趋势）
        price_change = random.uniform(-0.05, 0.08)  # 轻微上涨偏向
        base_price *= (1 + price_change)
        
        # 确保价格合理
        base_price = max(1.0, base_price)
        
        # 模拟成交量变化
        volume_change = random.uniform(-0.3, 0.5)
        current_volume = int(base_volume * (1 + volume_change))
        current_volume = max(100000, current_volume)
        
        # 生成OHLC数据
        open_price = base_price * random.uniform(0.98, 1.02)
        close_price = base_price
        high_price = max(open_price, close_price) * random.uniform(1.0, 1.05)
        low_price = min(open_price, close_price) * random.uniform(0.95, 1.0)
        
        market_data = MarketData(
            symbol=symbol,
            date=date.strftime('%Y-%m-%d'),
            open=round(open_price, 2),
            high=round(high_price, 2),
            low=round(low_price, 2),
            close=round(close_price, 2),
            volume=current_volume,
            amount=round(current_volume * close_price, 2)
        )
        
        data.append(market_data)
    
    return data


def demo_strategy_engine_analysis():
    """演示策略引擎分析功能"""
    print("=" * 80)
    print("PVFRS策略引擎分析演示")
    print("=" * 80)
    
    # 1. 创建策略引擎
    engine = StrategyEngine()
    
    print(f"策略引擎状态: {engine.get_engine_status()}")
    print()
    
    # 2. 创建示例数据
    print("创建示例股票数据...")
    sample_data = create_sample_market_data("000001", 25)
    print(f"生成了 {len(sample_data)} 天的数据")
    print(f"数据范围: {sample_data[0].date} 到 {sample_data[-1].date}")
    print()
    
    # 3. 分析单只股票
    print("分析单只股票...")
    try:
        indicators = engine.analyze_stock("000001", sample_data)
        print("PVFRS指标分析结果:")
        print(f"  宏观位移: {indicators.macro_displacement:.4f}")
        print(f"  即时强度: {indicators.instant_deviation:.4f}")
        print(f"  20日均价: {indicators.avg_price_20d:.2f}")
        print(f"  上涨天数: {indicators.rising_days}")
        print(f"  下跌天数: {indicators.falling_days}")
        print(f"  频率优势: {indicators.frequency_advantage}")
        print(f"  平均成交量: {indicators.avg_volume_20d:,.0f}")
        print(f"  当前成交量: {indicators.current_volume:,.0f}")
        print(f"  效率比: {indicators.efficiency_ratio:.2f}")
        print(f"  幅度系数: {indicators.amplitude_ratio:.4f}")
        print(f"  共振强度: {indicators.resonance_strength:.4f}")
        print()
    except Exception as e:
        print(f"分析失败: {str(e)}")
        print()
    
    # 4. 生成交易信号
    print("生成交易信号...")
    try:
        signals = engine.generate_signals("000001", sample_data)
        if signals:
            for i, signal in enumerate(signals):
                print(f"信号 {i+1}:")
                print(f"  类型: {signal.signal_type.value}")
                print(f"  强度: {signal.strength:.4f}")
                print(f"  价格: {signal.price:.2f}")
                print(f"  原因: {signal.reason}")
                print(f"  满足条件数: {len([k for k, v in signal.conditions_met.items() if v])}")
                print()
        else:
            print("未生成任何信号")
            print()
    except Exception as e:
        print(f"信号生成失败: {str(e)}")
        print()
    
    # 5. 获取完整策略分析
    print("获取完整策略分析...")
    try:
        analysis = engine.get_strategy_analysis("000001", sample_data)
        print("策略分析摘要:")
        print(f"  数据长度: {analysis['data_length']} 天")
        print(f"  价格维度有效: {analysis['price_dimension']['price_dimension_valid']}")
        print(f"  频率维度有效: {analysis['frequency_dimension']['frequency_dimension_valid']}")
        print(f"  成交量维度有效: {analysis['volume_dimension']['volume_dimension_valid']}")
        print(f"  三维共振: {analysis['resonance_detection']['three_dimension_resonance']}")
        print(f"  高效率轨道: {analysis['resonance_detection']['high_efficiency_trajectory']}")
        print(f"  信号数量: {len(analysis['signals'])}")
        print(f"  最大信号强度: {analysis['strategy_assessment']['max_signal_strength']:.4f}")
        print()
    except Exception as e:
        print(f"策略分析失败: {str(e)}")
        print()


def demo_stock_screening():
    """演示批量选股功能"""
    print("=" * 80)
    print("PVFRS批量选股演示")
    print("=" * 80)
    
    # 1. 创建股票筛选器
    screener = StockScreener()
    
    # 2. 创建多只股票的示例数据
    print("创建股票池数据...")
    stock_symbols = ["000001", "000002", "600000", "600036", "000858"]
    stock_data_dict = {}
    
    for symbol in stock_symbols:
        stock_data_dict[symbol] = create_sample_market_data(symbol, 25)
    
    print(f"创建了 {len(stock_symbols)} 只股票的数据")
    print()
    
    # 3. 配置筛选参数
    screening_config = ScreeningConfig(
        min_signal_strength=0.6,
        max_results=10,
        enable_parallel_processing=False,  # 演示用，关闭并行处理
        min_price=5.0,
        max_price=200.0,
        min_volume=500000
    )
    
    print("筛选配置:")
    print(f"  最小信号强度: {screening_config.min_signal_strength}")
    print(f"  最大结果数: {screening_config.max_results}")
    print(f"  价格范围: {screening_config.min_price} - {screening_config.max_price}")
    print(f"  最小成交量: {screening_config.min_volume:,}")
    print()
    
    # 4. 执行批量选股
    print("执行批量选股...")
    target_date = datetime.now().strftime('%Y-%m-%d')
    
    try:
        results = screener.screen_stocks(stock_data_dict, target_date, screening_config)
        
        print(f"选股完成，共发现 {len(results)} 只符合条件的股票")
        print()
        
        # 5. 显示选股结果
        if results:
            print("选股结果:")
            print("-" * 60)
            print(f"{'排名':<4} {'股票代码':<8} {'信号强度':<8} {'价格':<8} {'成交量':<12}")
            print("-" * 60)
            
            for i, result in enumerate(results):
                print(f"{i+1:<4} {result.symbol:<8} {result.signal_strength:<8.4f} "
                      f"{result.price:<8.2f} {result.volume:<12,}")
            
            print()
            
            # 显示详细信息（前3名）
            print("详细信息（前3名）:")
            for i, result in enumerate(results[:3]):
                print(f"{i+1}. {result.symbol}")
                print(f"   信号强度: {result.signal_strength:.4f}")
                print(f"   价格: {result.price:.2f}")
                print(f"   成交量: {result.volume:,}")
                print(f"   信号原因: {result.signal_reason}")
                
                # 显示满足的条件
                met_conditions = [k for k, v in result.conditions_met.items() if v]
                print(f"   满足条件: {', '.join(met_conditions[:5])}...")  # 只显示前5个
                print()
        
        # 6. 显示统计信息
        stats = screener.get_screening_statistics()
        print("筛选统计:")
        print(f"  总股票数: {stats['total_stocks']}")
        print(f"  成功分析数: {stats['analyzed_stocks']}")
        print(f"  符合条件数: {stats['qualified_stocks']}")
        print(f"  处理时间: {stats['processing_time']:.2f}秒")
        print(f"  成功率: {stats['success_rate']:.2%}")
        print(f"  入选率: {stats['qualification_rate']:.2%}")
        print()
        
    except Exception as e:
        print(f"批量选股失败: {str(e)}")
        print()


def demo_screening_report():
    """演示选股报告生成功能"""
    print("=" * 80)
    print("PVFRS选股报告演示")
    print("=" * 80)
    
    # 1. 创建报告生成器
    report_generator = ScreeningReportGenerator()
    
    # 2. 执行选股获取结果
    screener = StockScreener()
    stock_symbols = ["000001", "000002", "600000", "600036", "000858"]
    stock_data_dict = {}
    
    for symbol in stock_symbols:
        stock_data_dict[symbol] = create_sample_market_data(symbol, 25)
    
    screening_config = ScreeningConfig(min_signal_strength=0.5)  # 降低门槛以获得更多结果
    target_date = datetime.now().strftime('%Y-%m-%d')
    
    try:
        results = screener.screen_stocks(stock_data_dict, target_date, screening_config)
        screening_stats = screener.get_screening_statistics()
        
        print(f"获得 {len(results)} 个选股结果")
        print()
        
        # 3. 生成文本报告
        print("生成文本报告:")
        print("-" * 40)
        text_report = report_generator.generate_text_report(
            results, screening_config, screening_stats, target_date
        )
        print(text_report)
        
        # 4. 生成JSON报告（部分显示）
        print("\n" + "=" * 80)
        print("JSON报告摘要:")
        print("-" * 40)
        json_report = report_generator.generate_json_report(
            results, screening_config, screening_stats, target_date
        )
        
        # 只显示前500个字符
        print(json_report[:500] + "..." if len(json_report) > 500 else json_report)
        print()
        
        # 5. 生成CSV报告（部分显示）
        print("CSV报告预览:")
        print("-" * 40)
        csv_report = report_generator.generate_csv_report(results)
        csv_lines = csv_report.split('\n')
        
        # 显示表头和前几行
        for line in csv_lines[:min(5, len(csv_lines))]:
            if line.strip():
                print(line)
        
        if len(csv_lines) > 5:
            print("...")
        
        print()
        
    except Exception as e:
        print(f"报告生成失败: {str(e)}")
        print()


def main():
    """主演示函数"""
    print("PVFRS策略引擎和选股功能完整演示")
    print("=" * 80)
    print()
    
    # 演示1: 策略引擎分析
    demo_strategy_engine_analysis()
    
    # 演示2: 批量选股
    demo_stock_screening()
    
    # 演示3: 选股报告
    demo_screening_report()
    
    print("演示完成！")
    print("=" * 80)


if __name__ == "__main__":
    main()