"""
成交量维度分析器演示脚本
展示VolumeDimensionAnalyzer的各项功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_core.strategies.pvfrs.models import MarketData
from backend_core.strategies.pvfrs.analyzers import VolumeDimensionAnalyzer


def create_sample_data():
    """创建示例数据"""
    print("创建示例市场数据...")
    
    # 创建20天的示例数据，模拟一个上涨趋势
    data = []
    base_price = 10.0
    base_volume = 1000000
    
    for i in range(20):
        # 模拟价格逐步上涨
        price = base_price + i * 0.15
        # 模拟成交量逐步放大
        volume = base_volume + i * 80000
        
        market_data = MarketData(
            symbol="000001",
            date=f"2024-01-{i+1:02d}",
            open=price - 0.05,
            high=price + 0.1,
            low=price - 0.1,
            close=price,
            volume=volume,
            amount=volume * price
        )
        data.append(market_data)
    
    print(f"创建了{len(data)}天的市场数据")
    print(f"价格范围: {data[0].close:.2f} -> {data[-1].close:.2f}")
    print(f"成交量范围: {data[0].volume:,} -> {data[-1].volume:,}")
    return data


def demo_basic_calculations():
    """演示基础计算功能"""
    print("\n" + "="*60)
    print("演示基础计算功能")
    print("="*60)
    
    analyzer = VolumeDimensionAnalyzer()
    data = create_sample_data()
    
    # 计算20日平均成交量
    avg_volume = analyzer.calculate_avg_volume_20d(data)
    current_volume = data[-1].volume
    
    print(f"\n20日平均成交量: {avg_volume:,.0f}")
    print(f"当前成交量: {current_volume:,.0f}")
    
    # 计算效率指标
    efficiency_ratio = analyzer.calculate_efficiency_ratio(current_volume, avg_volume)
    efficiency_indicator = analyzer.calculate_efficiency_indicator(current_volume, avg_volume)
    
    print(f"效率比 (m₂₀/m): {efficiency_ratio:.2f}")
    print(f"效率指标 (m₂₀-m): {efficiency_indicator:,.0f}")
    
    # 检查成交量效率条件
    volume_efficiency = analyzer.check_volume_efficiency(current_volume, avg_volume)
    print(f"成交量效率条件满足: {volume_efficiency}")


def demo_resonance_analysis():
    """演示量价共振分析"""
    print("\n" + "="*60)
    print("演示量价共振分析")
    print("="*60)
    
    analyzer = VolumeDimensionAnalyzer()
    data = create_sample_data()
    
    # 分析量价共振状态
    resonance_result = analyzer.analyze_volume_price_resonance(data)
    
    print(f"\n价格上涨: {resonance_result['price_rising']}")
    print(f"成交量放大: {resonance_result['volume_increasing']}")
    print(f"量价共振状态: {resonance_result['volume_price_resonance']}")
    print(f"当前价格: {resonance_result['current_price']:.2f}")
    print(f"前一日价格: {resonance_result['previous_price']:.2f}")
    
    if resonance_result['volume_price_resonance']:
        print("✅ 检测到量价共振，价格上涨且成交量放大")
    else:
        print("❌ 未检测到量价共振")


def demo_fund_support_analysis():
    """演示资金支撑分析"""
    print("\n" + "="*60)
    print("演示资金支撑分析")
    print("="*60)
    
    analyzer = VolumeDimensionAnalyzer()
    data = create_sample_data()
    
    # 分析资金支撑质量
    fund_result = analyzer.analyze_fund_support_quality(data)
    
    print(f"\n强劲资金支撑: {fund_result['strong_fund_support']}")
    print(f"高质量信号: {fund_result['is_high_quality_signal']}")
    print(f"成交量倍数: {fund_result['volume_multiplier']:.2f}")
    print(f"资金支撑质量: {fund_result['fund_support_quality']}")
    
    if fund_result['fund_support_quality']:
        print("✅ 具有强劲资金支撑，信号质量高")
    else:
        print("❌ 资金支撑不足或信号质量低")


def demo_complete_analysis():
    """演示完整的成交量维度分析"""
    print("\n" + "="*60)
    print("演示完整的成交量维度分析")
    print("="*60)
    
    analyzer = VolumeDimensionAnalyzer()
    data = create_sample_data()
    
    # 执行完整分析
    result = analyzer.analyze(data)
    
    print(f"\n📊 成交量维度分析结果:")
    print(f"   20日平均成交量: {result['avg_volume_20d']:,.0f}")
    print(f"   当前成交量: {result['current_volume']:,.0f}")
    print(f"   效率比: {result['efficiency_ratio']:.2f}")
    print(f"   效率指标: {result['efficiency_indicator']:,.0f}")
    
    print(f"\n📈 量价共振分析:")
    print(f"   价格上涨: {result['price_rising']}")
    print(f"   成交量放大: {result['volume_increasing']}")
    print(f"   量价共振: {result['volume_price_resonance']}")
    
    print(f"\n💰 资金支撑分析:")
    print(f"   强劲资金支撑: {result['strong_fund_support']}")
    print(f"   高质量信号: {result['is_high_quality_signal']}")
    print(f"   成交量倍数: {result['volume_multiplier']:.2f}")
    
    print(f"\n✅ 成交量维度条件满足: {result['volume_dimension_valid']}")
    
    if result['volume_dimension_valid']:
        print("🎉 成交量维度分析通过，满足PVFRS策略条件！")
    else:
        print("⚠️  成交量维度分析未通过，不满足PVFRS策略条件")


def demo_edge_cases():
    """演示边界情况处理"""
    print("\n" + "="*60)
    print("演示边界情况处理")
    print("="*60)
    
    analyzer = VolumeDimensionAnalyzer()
    
    # 测试不同的成交量倍数情况
    test_cases = [
        (1000000, 1000000, "成交量相等"),
        (1400000, 1000000, "成交量略微放大(1.4倍)"),
        (1600000, 1000000, "成交量适度放大(1.6倍)"),
        (3000000, 1000000, "成交量显著放大(3倍)"),
        (6000000, 1000000, "成交量过度放大(6倍)"),
        (700000, 1000000, "成交量不足(0.7倍)"),
    ]
    
    print(f"\n测试不同成交量情况的资金支撑判定:")
    for current_vol, avg_vol, description in test_cases:
        strong_support = analyzer.confirm_strong_fund_support(current_vol, avg_vol)
        high_quality = analyzer.filter_low_quality_signals(current_vol, avg_vol)
        
        print(f"   {description}: 强劲支撑={strong_support}, 高质量={high_quality}")


if __name__ == "__main__":
    print("PVFRS成交量维度分析器演示")
    print("="*60)
    
    try:
        demo_basic_calculations()
        demo_resonance_analysis()
        demo_fund_support_analysis()
        demo_complete_analysis()
        demo_edge_cases()
        
        print("\n" + "="*60)
        print("演示完成！")
        print("="*60)
        
    except Exception as e:
        print(f"演示过程中发生错误: {e}")
        import traceback
        traceback.print_exc()