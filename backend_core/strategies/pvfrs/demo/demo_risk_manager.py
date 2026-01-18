"""
PVFRS风险管理模块演示
展示风险管理器的主要功能和使用方法
"""

from datetime import datetime, timedelta
from .risk_manager import RiskManager
from .models import MarketData, Trade


def create_sample_data():
    """创建示例市场数据"""
    data = []
    base_date = datetime(2024, 1, 1)
    base_price = 10.0
    base_volume = 1000000
    
    # 创建25天的市场数据，模拟上涨趋势
    for i in range(25):
        date = (base_date + timedelta(days=i)).strftime('%Y-%m-%d')
        price = base_price + i * 0.08 + (i % 4 - 1.5) * 0.03  # 带波动的上涨
        volume = base_volume + i * 8000 + (i % 3) * 30000
        
        market_data = MarketData(
            symbol='DEMO001',
            date=date,
            open=price - 0.01,
            high=price + 0.02,
            low=price - 0.02,
            close=price,
            volume=int(volume),
            amount=price * volume
        )
        data.append(market_data)
    
    return data


def demo_basic_risk_checks():
    """演示基本风险检查功能"""
    print("=== PVFRS风险管理模块演示 ===\n")
    
    # 创建风险管理器
    risk_manager = RiskManager()
    
    print("1. 基本风险检查演示")
    print("-" * 40)
    
    # 止损检查
    entry_price = 10.0
    current_prices = [9.5, 9.3, 10.5, 12.6]
    
    for price in current_prices:
        stop_loss = risk_manager.check_stop_loss(price, entry_price)
        take_profit = risk_manager.check_take_profit(price, entry_price)
        profit_pct = (price - entry_price) / entry_price
        
        print(f"价格: {price:.2f}, 盈亏: {profit_pct:+.1%}, "
              f"止损: {'是' if stop_loss else '否'}, "
              f"止盈: {'是' if take_profit else '否'}")
    
    print()


def demo_time_management():
    """演示时间管理功能"""
    print("2. 时间管理演示")
    print("-" * 40)
    
    risk_manager = RiskManager()
    entry_date = '2024-01-01'
    
    # 测试不同持有天数和盈利情况
    test_cases = [
        ('2024-01-20', 0.05),   # 19天，5%盈利
        ('2024-02-10', 0.02),   # 40天，2%盈利
        ('2024-02-20', 0.15),   # 50天，15%盈利
        ('2024-03-01', -0.03),  # 60天，-3%亏损
    ]
    
    for current_date, profit_pct in test_cases:
        # 检查最大持有期
        max_holding = risk_manager.check_max_holding_period(entry_date, current_date)
        
        # 动态最大持有天数
        dynamic_max = risk_manager.get_dynamic_max_holding_days(profit_pct)
        
        # 基于时间的退出检查
        time_exit, reason = risk_manager.check_time_based_exit(entry_date, current_date, profit_pct)
        
        holding_days = (datetime.strptime(current_date, '%Y-%m-%d') - 
                       datetime.strptime(entry_date, '%Y-%m-%d')).days
        
        print(f"持有{holding_days}天, 盈利{profit_pct:+.1%}: "
              f"超期={'是' if max_holding else '否'}, "
              f"动态限制{dynamic_max}天, "
              f"时间退出={'是' if time_exit else '否'}")
        
        if time_exit and reason:
            print(f"  退出原因: {reason}")
    
    print()


def demo_trend_analysis():
    """演示趋势分析功能"""
    print("3. 趋势分析演示")
    print("-" * 40)
    
    risk_manager = RiskManager()
    sample_data = create_sample_data()
    
    # 趋势反转检测
    is_reversal = risk_manager.detect_trend_reversal(sample_data)
    print(f"趋势反转检测: {'检测到反转' if is_reversal else '趋势正常'}")
    
    # 基于盈利的趋势反转检测
    profit_levels = [0.05, 0.20]  # 5%和20%盈利
    
    for profit_pct in profit_levels:
        is_reversal, details = risk_manager.detect_trend_reversal_with_profit(
            sample_data, profit_pct
        )
        
        print(f"盈利{profit_pct:.0%}时反转检测: {'反转' if is_reversal else '正常'}, "
              f"需要{details['required_conditions']}个条件, "
              f"满足{details['reversal_count']}个")
    
    # 趋势弱化检测
    is_weakening, weak_details = risk_manager.detect_trend_weakening(sample_data)
    print(f"趋势弱化检测: {'检测到弱化' if is_weakening else '趋势强劲'}, "
          f"弱化信号{weak_details.get('weakening_count', 0)}个")
    
    print()


def demo_comprehensive_risk_management():
    """演示综合风险管理功能"""
    print("4. 综合风险管理演示")
    print("-" * 40)
    
    risk_manager = RiskManager()
    sample_data = create_sample_data()
    
    # 创建示例交易
    trade = Trade(
        symbol='DEMO001',
        entry_date='2024-01-01',
        exit_date=None,
        entry_price=10.0,
        exit_price=None,
        quantity=1000,
        position_size=10000.0
    )
    
    # 测试不同日期的风险管理信号
    test_dates = ['2024-01-15', '2024-01-20', '2024-01-25']
    
    for date in test_dates:
        # 找到对应日期的数据
        current_data = None
        for data in sample_data:
            if data.date == date:
                current_data = data
                break
        
        if current_data:
            # 生成风险管理信号
            risk_signal = risk_manager.generate_risk_management_signal(
                'DEMO001', current_data, trade, sample_data
            )
            
            # 获取风险状态
            risk_status = risk_manager.get_risk_status(
                'DEMO001', current_data.close, trade.entry_price, 
                trade.entry_date, current_data.date
            )
            
            print(f"日期: {date}, 价格: {current_data.close:.2f}, "
                  f"盈利: {risk_status['profit_pct']:+.1%}, "
                  f"风险等级: {risk_status['risk_level']}")
            
            if risk_signal:
                print(f"  风险信号: {risk_signal.signal_type.value}, "
                      f"强度: {risk_signal.strength:.2f}, "
                      f"原因: {risk_signal.reason}")
            else:
                print("  无风险信号")
    
    print()


def demo_trailing_stop():
    """演示移动止损功能"""
    print("5. 移动止损演示")
    print("-" * 40)
    
    # 启用移动止损
    config = {'trailing_stop_enabled': True, 'trailing_stop_pct': 0.10}
    risk_manager = RiskManager(config)
    
    symbol = 'DEMO001'
    entry_price = 10.0
    
    # 模拟价格变化
    price_sequence = [10.5, 11.0, 12.0, 11.5, 11.0, 10.5]
    
    print(f"入场价格: {entry_price:.2f}, 移动止损: {risk_manager.trailing_stop_pct:.0%}")
    print("价格变化过程:")
    
    for i, price in enumerate(price_sequence):
        triggered, reason = risk_manager.check_trailing_stop(symbol, price, entry_price)
        
        highest_price = risk_manager.highest_price_since_entry.get(symbol, entry_price)
        stop_price = highest_price * (1 - risk_manager.trailing_stop_pct)
        
        print(f"  步骤{i+1}: 价格{price:.2f}, 最高价{highest_price:.2f}, "
              f"止损价{stop_price:.2f}, 触发: {'是' if triggered else '否'}")
        
        if triggered:
            print(f"    触发原因: {reason}")
            break
    
    print()


def main():
    """主演示函数"""
    try:
        demo_basic_risk_checks()
        demo_time_management()
        demo_trend_analysis()
        demo_comprehensive_risk_management()
        demo_trailing_stop()
        
        print("=== 演示完成 ===")
        print("\n风险管理模块主要功能:")
        print("✓ 止损止盈检查")
        print("✓ 时间管理（最大持有期、动态调整）")
        print("✓ 趋势反转检测")
        print("✓ 趋势弱化分析")
        print("✓ 移动止损")
        print("✓ 综合风险评估")
        print("✓ 风险信号生成")
        
    except Exception as e:
        print(f"演示过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()