"""
入场时机优化器演示脚本
展示价格穿越监控、成交量突破确认和幅度校验系数计算功能
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from datetime import datetime, timedelta
from backend_core.strategies.pvfrs.entry_timing_optimizer import EntryTimingOptimizer
from backend_core.strategies.pvfrs.models import MarketData, PVFRSIndicators


def create_demo_data():
    """创建演示数据"""
    base_date = datetime(2024, 1, 1)
    data = []
    
    # 创建一个价格逐步上涨并在最后两天发生穿越的场景
    prices = [9.8, 9.9, 9.85, 9.95, 10.0, 10.05, 9.98, 10.1, 10.15, 10.2]
    volumes = [800000, 900000, 850000, 950000, 1000000, 1100000, 900000, 1200000, 1300000, 1500000]
    
    for i, (price, volume) in enumerate(zip(prices, volumes)):
        date = (base_date + timedelta(days=i)).strftime('%Y-%m-%d')
        
        market_data = MarketData(
            symbol='DEMO001',
            date=date,
            open=price * 0.995,
            high=price * 1.01,
            low=price * 0.99,
            close=price,
            volume=volume,
            amount=price * volume
        )
        data.append(market_data)
    
    return data


def create_demo_indicators():
    """创建演示PVFRS指标"""
    return PVFRSIndicators(
        macro_displacement=0.4,  # 4%的宏观位移
        instant_deviation=0.15,
        avg_price_20d=10.0,
        rising_days=12,
        falling_days=7,
        frequency_advantage=True,
        avg_volume_20d=1000000,
        current_volume=1500000,
        efficiency_ratio=1.5,
        amplitude_ratio=0.04,  # 4%的幅度系数
        resonance_strength=0.75
    )


def demo_price_breakthrough_monitoring():
    """演示价格穿越监控"""
    print("=" * 60)
    print("价格穿越监控演示")
    print("=" * 60)
    
    optimizer = EntryTimingOptimizer()
    data = create_demo_data()
    
    # 使用最后两天数据演示穿越
    recent_data = data[-2:]
    avg_price = 10.0
    
    result = optimizer.monitor_price_breakthrough(recent_data, avg_price)
    
    print(f"当前价格: {result['current_price']:.2f}")
    print(f"前一日价格: {result['previous_price']:.2f}")
    print(f"平均价格: {result['avg_price_20d']:.2f}")
    print(f"是否发生穿越: {result['has_breakthrough']}")
    print(f"穿越类型: {result['breakthrough_type']}")
    print(f"穿越幅度: {result['breakthrough_margin']:.3f}")
    print(f"穿越强度: {result['breakthrough_strength']:.3f}")
    print(f"入场机会: {result['entry_opportunity']}")
    print(f"监控状态: {result['monitoring_status']}")
    print()


def demo_volume_breakthrough_confirmation():
    """演示成交量突破确认"""
    print("=" * 60)
    print("成交量突破确认演示")
    print("=" * 60)
    
    optimizer = EntryTimingOptimizer()
    data = create_demo_data()
    
    # 使用最后一天数据
    current_data = data[-1]
    avg_volume = 1000000
    
    result = optimizer.confirm_volume_breakthrough(current_data, avg_volume)
    
    print(f"当前成交量: {result['current_volume']:,}")
    print(f"平均成交量: {result['avg_volume_20d']:,}")
    print(f"成交量倍数: {result['volume_multiplier']:.2f}")
    print(f"是否突破: {result['has_breakthrough']}")
    print(f"突破级别: {result['breakthrough_level']}")
    print(f"突破强度: {result['breakthrough_intensity']:.3f}")
    print(f"入场时机评分: {result['entry_timing_score']:.3f}")
    print(f"最佳入场时机: {result['optimal_entry_timing']}")
    print(f"确认状态: {result['confirmation_status']}")
    print()


def demo_amplitude_coefficient_calculation():
    """演示幅度校验系数计算"""
    print("=" * 60)
    print("幅度校验系数计算演示")
    print("=" * 60)
    
    optimizer = EntryTimingOptimizer()
    
    # 测试不同的幅度系数场景
    scenarios = [
        {"displacement": 0.4, "avg_price": 10.0, "desc": "正常幅度(4%)"},
        {"displacement": 0.05, "avg_price": 10.0, "desc": "幅度过小(0.5%)"},
        {"displacement": 3.5, "avg_price": 10.0, "desc": "幅度过大(35%)"},
        {"displacement": -0.3, "avg_price": 10.0, "desc": "负幅度(-3%)"},
    ]
    
    for scenario in scenarios:
        print(f"\n场景: {scenario['desc']}")
        print("-" * 40)
        
        result = optimizer.calculate_amplitude_coefficient(
            scenario['displacement'], scenario['avg_price']
        )
        
        print(f"幅度系数: {result['amplitude_coefficient']:.3f} ({result['coefficient_percentage']:.1f}%)")
        print(f"是否有效: {result['is_valid']}")
        print(f"验证状态: {result['validation_status']}")
        print(f"系数质量: {result['coefficient_quality']['quality_level']}")
        print(f"是否需要等待: {result['should_wait']}")
        if result['should_wait']:
            print(f"等待原因: {result['wait_reason']}")
        print(f"入场准备度: {result['entry_readiness']['recommendation']}")
    
    print()


def demo_comprehensive_optimization():
    """演示综合入场时机优化"""
    print("=" * 60)
    print("综合入场时机优化演示")
    print("=" * 60)
    
    optimizer = EntryTimingOptimizer()
    data = create_demo_data()
    indicators = create_demo_indicators()
    
    result = optimizer.optimize_entry_timing_comprehensive(data, indicators)
    
    print("价格分析:")
    print(f"  价格穿越: {result['price_analysis']['has_breakthrough']}")
    print(f"  穿越强度: {result['price_analysis']['breakthrough_strength']:.3f}")
    print(f"  监控状态: {result['price_analysis']['monitoring_status']}")
    
    print("\n成交量分析:")
    print(f"  成交量突破: {result['volume_analysis']['has_breakthrough']}")
    print(f"  时机评分: {result['volume_analysis']['entry_timing_score']:.3f}")
    print(f"  确认状态: {result['volume_analysis']['confirmation_status']}")
    
    print("\n幅度分析:")
    print(f"  系数有效: {result['amplitude_analysis']['is_valid']}")
    print(f"  幅度系数: {result['amplitude_analysis']['amplitude_coefficient']:.3f}")
    print(f"  是否等待: {result['amplitude_analysis']['should_wait']}")
    
    print(f"\n综合评估:")
    print(f"  综合评分: {result['comprehensive_score']:.3f}")
    print(f"  最佳时机: {result['optimal_entry_timing']}")
    print(f"  良好时机: {result['good_entry_timing']}")
    print(f"  综合建议: {result['recommendation']}")
    
    print(f"\n时机总结:")
    summary = result['timing_summary']
    print(f"  价格状态: {summary['price_status']}")
    print(f"  成交量状态: {summary['volume_status']}")
    print(f"  幅度状态: {summary['amplitude_status']}")
    
    key_conditions = summary['key_conditions']
    print(f"\n关键条件:")
    print(f"  价格穿越: {key_conditions['price_breakthrough']}")
    print(f"  成交量突破: {key_conditions['volume_breakthrough']}")
    print(f"  幅度有效: {key_conditions['amplitude_valid']}")
    
    if summary['waiting_required']:
        print(f"\n等待建议: {summary['wait_reason']}")
    
    print()


def main():
    """主演示函数"""
    print("PVFRS入场时机优化器演示")
    print("=" * 80)
    
    try:
        # 演示各个功能模块
        demo_price_breakthrough_monitoring()
        demo_volume_breakthrough_confirmation()
        demo_amplitude_coefficient_calculation()
        demo_comprehensive_optimization()
        
        print("演示完成！")
        
    except Exception as e:
        print(f"演示过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()