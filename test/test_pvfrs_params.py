"""
测试PVFRS策略参数是否正确加载
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_core.strategies.pvfrs.pvfrs_strategy import PVFRSStrategy

def test_params():
    """测试策略参数"""
    print("=" * 80)
    print("测试PVFRS策略参数")
    print("=" * 80)
    
    # 创建策略实例
    strategy = PVFRSStrategy()
    
    # 打印关键参数
    print("\n买入条件参数:")
    print(f"  buy_instant_deviation_min: {strategy.params.get('buy_instant_deviation_min')}")
    print(f"  buy_bias_min: {strategy.params.get('buy_bias_min')}")
    print(f"  buy_relative_displacement_min: {strategy.params.get('buy_relative_displacement_min')}")
    print(f"  buy_price_above_ma5: {strategy.params.get('buy_price_above_ma5')}")
    print(f"  buy_ma5_above_ma20: {strategy.params.get('buy_ma5_above_ma20')}")
    print(f"  buy_consecutive_days: {strategy.params.get('buy_consecutive_days')}")
    
    print("\n卖出条件参数:")
    print(f"  stop_loss_initial: {strategy.params.get('stop_loss_initial')}")
    print(f"  stop_loss_breakeven: {strategy.params.get('stop_loss_breakeven')}")
    print(f"  trailing_stop_activation: {strategy.params.get('trailing_stop_activation')}")
    print(f"  trailing_stop_distance: {strategy.params.get('trailing_stop_distance')}")
    print(f"  max_holding_days: {strategy.params.get('max_holding_days')}")
    
    print("\n" + "=" * 80)
    print("参数验证:")
    
    # 验证关键参数
    checks = [
        ("买入即时偏离最小值应为0", strategy.params.get('buy_instant_deviation_min') == 0),
        ("买入bias最小值应为0.02", strategy.params.get('buy_bias_min') == 0.02),
        ("不要求价格在5日均线之上", strategy.params.get('buy_price_above_ma5') == False),
        ("不要求5日均线在20日均线之上", strategy.params.get('buy_ma5_above_ma20') == False),
        ("初始止损应为-0.05", strategy.params.get('stop_loss_initial') == -0.05),
    ]
    
    all_passed = True
    for desc, result in checks:
        status = "✓" if result else "✗"
        print(f"  {status} {desc}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✓ 所有参数验证通过！策略配置正确。")
    else:
        print("✗ 部分参数验证失败！请检查策略配置。")
    print("=" * 80)
    
    return all_passed

if __name__ == "__main__":
    test_params()
