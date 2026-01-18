"""
频率维度分析器演示
展示频率维度分析器的各项功能
"""

from backend_core.strategies.pvfrs.analyzers import FrequencyDimensionAnalyzer
from backend_core.strategies.pvfrs.models import MarketData


def create_test_data(prices, symbol="DEMO"):
    """创建测试数据"""
    data = []
    for i, price in enumerate(prices):
        data.append(MarketData(
            symbol=symbol,
            date=f"2024-01-{i+1:02d}",
            open=price,
            high=price * 1.02,
            low=price * 0.98,
            close=price,
            volume=1000000,
            amount=price * 1000000
        ))
    return data


def demo_frequency_analyzer():
    """演示频率维度分析器"""
    analyzer = FrequencyDimensionAnalyzer()
    
    print("=" * 60)
    print("频率维度分析器演示")
    print("=" * 60)
    
    # 案例1: 稳定上涨趋势
    print("\n案例1: 稳定上涨趋势")
    print("-" * 30)
    prices1 = [100 + i * 0.5 for i in range(20)]  # 稳定上涨
    data1 = create_test_data(prices1, "STABLE_UP")
    
    result1 = analyzer.analyze(data1)
    print(f"股票代码: STABLE_UP")
    print(f"价格序列: {[round(p, 1) for p in prices1[:5]]} ... {[round(p, 1) for p in prices1[-5:]]}")
    print(f"上涨天数: {result1['rising_days']}")
    print(f"下跌天数: {result1['falling_days']}")
    print(f"频率优势: {result1['frequency_advantage']}")
    print(f"虚假繁荣: {result1['has_false_prosperity']}")
    print(f"频率维度有效: {result1['frequency_dimension_valid']}")
    
    # 案例2: 包含单日暴涨的情况
    print("\n案例2: 包含单日暴涨（虚假繁荣）")
    print("-" * 30)
    prices2 = [100] * 10 + [125] + [126] * 9  # 第11天暴涨25%
    data2 = create_test_data(prices2, "FALSE_BOOM")
    
    result2 = analyzer.analyze(data2)
    print(f"股票代码: FALSE_BOOM")
    print(f"价格序列: {prices2[:5]} ... {prices2[-5:]}")
    print(f"第10天到第11天涨幅: {(125-100)/100*100:.1f}%")
    print(f"上涨天数: {result2['rising_days']}")
    print(f"下跌天数: {result2['falling_days']}")
    print(f"频率优势: {result2['frequency_advantage']}")
    print(f"虚假繁荣: {result2['has_false_prosperity']}")
    print(f"频率维度有效: {result2['frequency_dimension_valid']}")
    
    # 案例3: 震荡行情
    print("\n案例3: 震荡行情")
    print("-" * 30)
    prices3 = []
    for i in range(20):
        if i % 2 == 0:
            prices3.append(100 + i * 0.1)  # 偶数天上涨
        else:
            prices3.append(100 + (i-1) * 0.1 - 0.05)  # 奇数天下跌
    data3 = create_test_data(prices3, "VOLATILE")
    
    result3 = analyzer.analyze(data3)
    print(f"股票代码: VOLATILE")
    print(f"价格序列: {[round(p, 2) for p in prices3[:5]]} ... {[round(p, 2) for p in prices3[-5:]]}")
    print(f"上涨天数: {result3['rising_days']}")
    print(f"下跌天数: {result3['falling_days']}")
    print(f"频率优势: {result3['frequency_advantage']}")
    print(f"虚假繁荣: {result3['has_false_prosperity']}")
    print(f"频率维度有效: {result3['frequency_dimension_valid']}")
    
    # 案例4: 下跌趋势
    print("\n案例4: 下跌趋势")
    print("-" * 30)
    prices4 = [120 - i * 0.8 for i in range(20)]  # 持续下跌
    data4 = create_test_data(prices4, "DOWNTREND")
    
    result4 = analyzer.analyze(data4)
    print(f"股票代码: DOWNTREND")
    print(f"价格序列: {[round(p, 1) for p in prices4[:5]]} ... {[round(p, 1) for p in prices4[-5:]]}")
    print(f"上涨天数: {result4['rising_days']}")
    print(f"下跌天数: {result4['falling_days']}")
    print(f"频率优势: {result4['frequency_advantage']}")
    print(f"虚假繁荣: {result4['has_false_prosperity']}")
    print(f"频率维度有效: {result4['frequency_dimension_valid']}")
    
    print("\n" + "=" * 60)
    print("演示完成")
    print("=" * 60)


if __name__ == "__main__":
    demo_frequency_analyzer()