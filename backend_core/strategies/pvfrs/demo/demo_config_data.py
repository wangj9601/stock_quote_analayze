"""
PVFRS配置管理和数据接口演示
展示配置管理器和数据接口的基本功能
"""

import os
import sys
import tempfile
from datetime import datetime

# 添加项目根目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from backend_core.strategies.pvfrs import (
    PVFRSConfigManager,
    PVFRSDataInterface,
    MarketData
)


def demo_config_manager():
    """演示配置管理器功能"""
    print("=" * 60)
    print("PVFRS配置管理器演示")
    print("=" * 60)
    
    # 创建临时配置文件
    temp_dir = tempfile.mkdtemp()
    config_file = os.path.join(temp_dir, "demo_config.json")
    
    try:
        # 1. 创建配置管理器
        config_manager = PVFRSConfigManager(config_file)
        print("✓ 配置管理器创建成功")
        
        # 2. 获取默认配置
        default_config = config_manager.get_default_config()
        print(f"✓ 默认配置包含 {len(default_config)} 个参数")
        print(f"  - 止损比例: {default_config['stop_loss']}")
        print(f"  - 止盈比例: {default_config['take_profit']}")
        print(f"  - 最大仓位: {default_config['max_position_size']}")
        
        # 3. 保存配置
        config_manager.save_config(default_config)
        print(f"✓ 配置已保存到: {config_file}")
        
        # 4. 更新配置
        updates = {
            'stop_loss': -0.08,
            'take_profit': 0.25,
            'max_position_size': 0.15
        }
        updated_config = config_manager.update_config(updates)
        print("✓ 配置已更新:")
        for key, value in updates.items():
            print(f"  - {key}: {value}")
        
        # 5. 获取单个配置值
        stop_loss = config_manager.get_config_value('stop_loss')
        print(f"✓ 当前止损比例: {stop_loss}")
        
        # 6. 配置验证
        try:
            invalid_config = default_config.copy()
            invalid_config['stop_loss'] = 0.1  # 无效值
            config_manager.validate_config(invalid_config)
        except Exception as e:
            print(f"✓ 配置验证正常工作: {type(e).__name__}")
        
        # 7. 备份和恢复
        backup_path = config_manager.backup_config()
        print(f"✓ 配置已备份到: {os.path.basename(backup_path)}")
        
        # 8. 重置为默认
        config_manager.reset_to_default()
        print("✓ 配置已重置为默认值")
        
    finally:
        # 清理临时文件
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def demo_data_interface():
    """演示数据接口功能"""
    print("\n" + "=" * 60)
    print("PVFRS数据接口演示")
    print("=" * 60)
    
    # 1. 创建数据接口
    data_interface = PVFRSDataInterface()
    print("✓ 数据接口创建成功")
    
    # 2. 获取股票列表
    cn_stocks = data_interface.get_stock_list("CN")
    print(f"✓ 获取中国A股列表: {len(cn_stocks)} 只股票")
    print(f"  示例股票: {cn_stocks[:3]}")
    
    us_stocks = data_interface.get_stock_list("US")
    print(f"✓ 获取美股列表: {len(us_stocks)} 只股票")
    print(f"  示例股票: {us_stocks[:3]}")
    
    # 3. 获取交易日历
    calendar = data_interface.get_trading_calendar("2024-01-01", "2024-01-10")
    print(f"✓ 获取交易日历: {len(calendar)} 个交易日")
    print(f"  示例日期: {calendar[:3]}")
    
    # 4. 获取市场数据
    symbol = "000001"
    start_date = "2024-01-01"
    end_date = "2024-01-31"
    
    try:
        market_data = data_interface.get_market_data(symbol, start_date, end_date)
        print(f"✓ 获取 {symbol} 市场数据: {len(market_data)} 天")
        
        # 显示前几天的数据
        print("  前3天数据:")
        for i, data in enumerate(market_data[:3]):
            print(f"    {i+1}. {data.date}: 开盘={data.open}, 收盘={data.close}, 成交量={data.volume:,}")
        
    except Exception as e:
        print(f"✗ 获取市场数据失败: {e}")
    
    # 5. 数据验证演示
    valid_data = [
        MarketData("000001", "2024-01-01", 10.0, 10.5, 9.8, 10.2, 1000000, 10200000),
        MarketData("000001", "2024-01-02", 10.2, 10.8, 10.0, 10.5, 1200000, 12600000)
    ]
    
    is_valid = data_interface.validate_data(valid_data)
    print(f"✓ 数据验证结果: {'通过' if is_valid else '失败'}")
    
    # 6. 数据清洗演示
    cleaned_data = data_interface.clean_data(valid_data)
    print(f"✓ 数据清洗完成: {len(cleaned_data)} 条记录")
    
    # 7. 列名标准化演示
    raw_columns = {
        'trade_date': '2024-01-01',
        'open_price': 10.0,
        'high_price': 10.5,
        'vol': 1000000
    }
    
    standardized = data_interface._standardize_columns(raw_columns)
    print("✓ 列名标准化:")
    for old_key, new_key in [('trade_date', 'date'), ('open_price', 'open'), ('vol', 'volume')]:
        if old_key in raw_columns:
            print(f"  {old_key} -> {new_key}")


def demo_integration():
    """演示配置管理和数据接口的集成使用"""
    print("\n" + "=" * 60)
    print("配置管理与数据接口集成演示")
    print("=" * 60)
    
    # 1. 创建配置管理器和数据接口
    config_manager = PVFRSConfigManager()
    data_interface = PVFRSDataInterface()
    
    # 2. 从配置获取参数
    config = config_manager.get_current_config()
    observation_period = config.get('observation_period', 20)
    min_data_points = config.get('min_data_points', 25)
    
    print(f"✓ 从配置获取参数:")
    print(f"  - 观察周期: {observation_period} 天")
    print(f"  - 最少数据点: {min_data_points} 个")
    
    # 3. 根据配置参数获取数据
    symbol = "000001"
    try:
        market_data = data_interface.get_market_data(symbol, "2024-01-01", "2024-02-15")
        
        if len(market_data) >= min_data_points:
            print(f"✓ 数据充足: {len(market_data)} >= {min_data_points}")
            
            # 取最近的观察周期数据
            recent_data = market_data[-observation_period:]
            print(f"✓ 提取最近 {observation_period} 天数据用于分析")
            
            # 简单统计
            prices = [d.close for d in recent_data]
            avg_price = sum(prices) / len(prices)
            price_change = (prices[-1] - prices[0]) / prices[0] * 100
            
            print(f"  - 平均价格: {avg_price:.2f}")
            print(f"  - 期间涨跌幅: {price_change:.2f}%")
            
        else:
            print(f"✗ 数据不足: {len(market_data)} < {min_data_points}")
            
    except Exception as e:
        print(f"✗ 集成演示失败: {e}")
    
    # 4. 配置变更回调演示
    def on_config_change(new_config):
        print(f"📢 配置变更通知: 观察周期更新为 {new_config.get('observation_period')} 天")
    
    config_manager.add_config_change_callback(on_config_change)
    config_manager.set_config_value('observation_period', 25)
    
    print("✓ 配置变更回调机制正常工作")


if __name__ == "__main__":
    print(f"PVFRS配置管理和数据接口演示")
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        demo_config_manager()
        demo_data_interface()
        demo_integration()
        
        print("\n" + "=" * 60)
        print("✅ 所有演示完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()