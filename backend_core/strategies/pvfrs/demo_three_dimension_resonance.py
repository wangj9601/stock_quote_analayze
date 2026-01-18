"""
三维共振检测器演示脚本
展示PVFRS策略三维共振检测器的完整功能
"""

from datetime import datetime, timedelta
from .models import MarketData
from .three_dimension_resonance import ThreeDimensionResonanceEngine


def create_sample_data(symbol: str, days: int = 20, scenario: str = 'ideal') -> list:
    """创建示例数据
    
    Args:
        symbol: 股票代码
        days: 数据天数
        scenario: 场景类型 ('ideal', 'weak', 'mixed', 'poor')
    
    Returns:
        list: 市场数据列表
    """
    data = []
    base_date = datetime(2024, 1, 1)
    base_price = 15.0
    base_volume = 2000000
    
    for i in range(days):
        date = base_date + timedelta(days=i)
        
        if scenario == 'ideal':
            # 理想场景：价格稳步上涨，成交量放大，频率优势明显
            price_growth = 1 + (i * 0.015) + (0.01 if i % 2 == 0 else 0.005)
            volume_growth = 1 + (i * 0.08) + (0.1 if i % 3 == 0 else 0)
            
        elif scenario == 'weak':
            # 弱势场景：价格小幅上涨，成交量一般，频率优势不明显
            price_growth = 1 + (i * 0.005) + (0.003 if i % 3 == 0 else -0.002)
            volume_growth = 1 + (i * 0.02) + (0.05 if i % 4 == 0 else -0.03)
            
        elif scenario == 'mixed':
            # 混合场景：价格波动较大，成交量不稳定
            price_growth = 1 + (i * 0.01) + (0.02 if i % 2 == 0 else -0.015)
            volume_growth = 1 + (i * 0.04) + (0.15 if i % 2 == 0 else -0.1)
            
        else:  # poor
            # 差劲场景：价格下跌，成交量萎缩
            price_growth = max(0.7, 1 - (i * 0.01))
            volume_growth = max(0.5, 1 - (i * 0.03))
        
        current_price = base_price * price_growth
        current_volume = int(base_volume * volume_growth)
        
        # 创建OHLC数据
        open_price = current_price * 0.995
        high_price = current_price * 1.008
        low_price = current_price * 0.992
        close_price = current_price
        
        data.append(MarketData(
            symbol=symbol,
            date=date.strftime("%Y-%m-%d"),
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=current_volume,
            amount=current_volume * current_price
        ))
    
    return data


def demo_single_stock_analysis():
    """演示单只股票分析"""
    print("=" * 60)
    print("单只股票三维共振分析演示")
    print("=" * 60)
    
    engine = ThreeDimensionResonanceEngine()
    
    # 测试不同场景
    scenarios = {
        '理想场景': 'ideal',
        '弱势场景': 'weak', 
        '混合场景': 'mixed',
        '差劲场景': 'poor'
    }
    
    for scenario_name, scenario_code in scenarios.items():
        print(f"\n【{scenario_name}】")
        print("-" * 40)
        
        # 创建测试数据
        data = create_sample_data(f"TEST_{scenario_code.upper()}", 20, scenario_code)
        
        # 分析并生成信号
        signal = engine.analyze_and_generate_signal(f"TEST_{scenario_code.upper()}", data)
        
        # 获取详细分析结果
        details = engine.get_analysis_details(f"TEST_{scenario_code.upper()}", data)
        
        # 显示结果
        print(f"股票代码: {details['symbol']}")
        print(f"数据天数: {details['data_length']}")
        
        if signal:
            print(f"✅ 生成信号: {signal.signal_type.value}")
            print(f"   信号强度: {signal.strength:.3f}")
            print(f"   信号价格: {signal.price:.2f}")
            print(f"   信号原因: {signal.reason}")
        else:
            print("❌ 未生成信号")
            if 'filter_reason' in details and details['filter_reason']:
                print(f"   过滤原因: {details['filter_reason']}")
        
        # 显示各维度分析结果
        if 'resonance_result' in details:
            resonance = details['resonance_result']
            print(f"   价格维度: {'✅' if resonance.get('price_dimension_valid', False) else '❌'}")
            print(f"   频率维度: {'✅' if resonance.get('frequency_dimension_valid', False) else '❌'}")
            print(f"   成交量维度: {'✅' if resonance.get('volume_dimension_valid', False) else '❌'}")
            print(f"   三维共振: {'✅' if resonance.get('three_dimension_resonance', False) else '❌'}")
            print(f"   共振强度: {resonance.get('resonance_strength', 0):.3f}")


def demo_batch_analysis():
    """演示批量分析"""
    print("\n" + "=" * 60)
    print("批量股票三维共振分析演示")
    print("=" * 60)
    
    engine = ThreeDimensionResonanceEngine()
    
    # 创建多只股票的测试数据
    stock_data = {
        'STOCK001': create_sample_data('STOCK001', 20, 'ideal'),
        'STOCK002': create_sample_data('STOCK002', 20, 'weak'),
        'STOCK003': create_sample_data('STOCK003', 20, 'mixed'),
        'STOCK004': create_sample_data('STOCK004', 20, 'poor'),
        'STOCK005': create_sample_data('STOCK005', 15, 'ideal'),  # 数据不足
    }
    
    # 批量分析
    results = engine.batch_analyze_stocks(stock_data)
    
    # 显示结果
    print(f"\n分析股票数量: {len(stock_data)}")
    print("-" * 40)
    
    for symbol, result in results.items():
        signal = result['signal']
        has_signal = result['has_signal']
        
        print(f"\n{symbol}:")
        if has_signal and signal:
            print(f"  ✅ {signal.signal_type.value} 信号 (强度: {signal.strength:.3f})")
        else:
            print(f"  ❌ 无信号")
    
    # 显示汇总统计
    summary = engine.get_dimension_summary(results)
    print(f"\n汇总统计:")
    print(f"  总股票数: {summary['total_stocks']}")
    print(f"  有信号股票数: {summary['stocks_with_signals']}")
    print(f"  信号生成率: {summary['signal_rate']:.1%}")
    
    print(f"\n各维度通过率:")
    for dimension, rate in summary['dimension_pass_rates'].items():
        print(f"  {dimension}: {rate:.1%}")


def demo_detailed_analysis():
    """演示详细分析过程"""
    print("\n" + "=" * 60)
    print("详细分析过程演示")
    print("=" * 60)
    
    engine = ThreeDimensionResonanceEngine()
    
    # 创建理想场景数据
    data = create_sample_data('DETAIL_DEMO', 20, 'ideal')
    
    # 获取详细分析结果
    details = engine.get_analysis_details('DETAIL_DEMO', data)
    
    print(f"股票代码: {details['symbol']}")
    print(f"分析日期: {details.get('analysis_date', 'N/A')}")
    
    # 价格维度详情
    if 'price_indicators' in details:
        price = details['price_indicators']
        print(f"\n【价格维度分析】")
        print(f"  宏观位移: {price.get('macro_displacement', 0):.4f}")
        print(f"  即时强度: {price.get('instant_deviation', 0):.4f}")
        print(f"  20日均价: {price.get('avg_price_20d', 0):.2f}")
        print(f"  维度有效: {'✅' if price.get('price_dimension_valid', False) else '❌'}")
    
    # 频率维度详情
    if 'frequency_indicators' in details:
        freq = details['frequency_indicators']
        print(f"\n【频率维度分析】")
        print(f"  上涨天数: {freq.get('rising_days', 0)}")
        print(f"  下跌天数: {freq.get('falling_days', 0)}")
        print(f"  频率优势: {'✅' if freq.get('frequency_advantage', False) else '❌'}")
        print(f"  虚假繁荣: {'❌' if freq.get('has_false_prosperity', True) else '✅'}")
        print(f"  维度有效: {'✅' if freq.get('frequency_dimension_valid', False) else '❌'}")
    
    # 成交量维度详情
    if 'volume_indicators' in details:
        vol = details['volume_indicators']
        print(f"\n【成交量维度分析】")
        print(f"  当前成交量: {vol.get('current_volume', 0):,}")
        print(f"  20日均量: {vol.get('avg_volume_20d', 0):,.0f}")
        print(f"  效率比: {vol.get('efficiency_ratio', 0):.2f}")
        print(f"  量价共振: {'✅' if vol.get('volume_price_resonance', False) else '❌'}")
        print(f"  资金支撑: {'✅' if vol.get('strong_fund_support', False) else '❌'}")
        print(f"  维度有效: {'✅' if vol.get('volume_dimension_valid', False) else '❌'}")
    
    # 共振分析详情
    if 'resonance_result' in details:
        resonance = details['resonance_result']
        print(f"\n【三维共振分析】")
        print(f"  三维共振: {'✅' if resonance.get('three_dimension_resonance', False) else '❌'}")
        print(f"  高效轨道: {'✅' if resonance.get('high_efficiency_trajectory', False) else '❌'}")
        print(f"  共振强度: {resonance.get('resonance_strength', 0):.3f}")
        
        if 'conditions_met' in resonance:
            conditions = resonance['conditions_met']
            print(f"\n  满足的条件:")
            for condition, met in conditions.items():
                status = '✅' if met else '❌'
                print(f"    {condition}: {status}")


def main():
    """主演示函数"""
    print("PVFRS策略三维共振检测器演示")
    print("=" * 60)
    
    try:
        # 单只股票分析演示
        demo_single_stock_analysis()
        
        # 批量分析演示
        demo_batch_analysis()
        
        # 详细分析演示
        demo_detailed_analysis()
        
        print("\n" + "=" * 60)
        print("演示完成！")
        
    except Exception as e:
        print(f"演示过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()