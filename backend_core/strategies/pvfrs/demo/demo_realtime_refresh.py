"""
PVFRS策略实时数据刷新机制使用示例
演示如何使用实时刷新功能确保数据变化时前端能及时响应
"""

import sys
import os
import time
import logging
from typing import List, Dict
from unittest.mock import Mock

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from backend_core.strategies.pvfrs.realtime_refresh import (
    RealtimeRefreshManager,
    RefreshConfig,
    RefreshEvent,
    RefreshTriggerType,
    create_realtime_refresh_manager
)
from backend_core.strategies.pvfrs.models import PVFRSIndicators

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# 简化的SelectionResult类用于演示
class SelectionResult:
    def __init__(self, symbol, name, signal_strength, conditions_met, indicators, timestamp, price, signal_reason):
        self.symbol = symbol
        self.name = name
        self.signal_strength = signal_strength
        self.conditions_met = conditions_met
        self.indicators = indicators
        self.timestamp = timestamp
        self.price = price
        self.signal_reason = signal_reason


class MockFrontendInterface:
    """模拟前端接口，用于演示"""
    
    def __init__(self):
        self.refresh_count = 0
        self.selection_results = []
        
    def refresh_results(self) -> bool:
        """模拟刷新操作"""
        self.refresh_count += 1
        logger.info(f"执行刷新操作 #{self.refresh_count}")
        
        # 模拟刷新成功
        return True
    
    def get_selection_results(self) -> List[SelectionResult]:
        """模拟获取选股结果"""
        # 模拟动态变化的选股结果
        mock_results = []
        
        if self.refresh_count % 3 == 0:
            # 每3次刷新添加一个新股票
            mock_results.append(SelectionResult(
                symbol=f'00000{self.refresh_count}',
                name=f'测试股票{self.refresh_count}',
                signal_strength=0.8 + (self.refresh_count % 10) * 0.01,
                conditions_met={'price_dimension': True, 'frequency_dimension': True, 'volume_dimension': True},
                indicators=PVFRSIndicators(
                    macro_displacement=1.0, instant_deviation=0.5, avg_price_20d=10.0,
                    rising_days=12, falling_days=8, frequency_advantage=True,
                    avg_volume_20d=1000000, current_volume=1200000, efficiency_ratio=1.2,
                    amplitude_ratio=0.1, resonance_strength=0.8
                ),
                timestamp=time.strftime('%Y-%m-%d %H:%M:%S'),
                price=10.5,
                signal_reason='三维共振'
            ))
        
        self.selection_results = mock_results
        return mock_results


def demo_basic_refresh_functionality():
    """演示基本刷新功能"""
    print("\n=== 演示基本刷新功能 ===")
    
    # 创建模拟前端接口
    mock_frontend = MockFrontendInterface()
    
    # 创建刷新配置
    config = RefreshConfig(
        enabled=True,
        scheduled_interval_seconds=2,  # 2秒间隔用于演示
        data_change_debounce_seconds=1,
        market_hours_only=False  # 演示时不限制交易时间
    )
    
    # 创建刷新管理器
    refresh_manager = create_realtime_refresh_manager(mock_frontend, config)
    
    print(f"初始状态: {refresh_manager.get_status()['service_status']}")
    
    # 启动刷新服务
    success = refresh_manager.start()
    print(f"启动刷新服务: {'成功' if success else '失败'}")
    
    # 等待几次定时刷新
    print("等待定时刷新...")
    time.sleep(6)
    
    # 触发手动刷新
    print("触发手动刷新...")
    refresh_manager.trigger_manual_refresh(['000001', '000002'])
    
    # 等待一段时间
    time.sleep(2)
    
    # 获取状态信息
    status = refresh_manager.get_status()
    print(f"刷新统计: 总次数={status['metrics']['total_refreshes']}, "
          f"成功次数={status['metrics']['successful_refreshes']}")
    
    # 停止服务
    refresh_manager.stop()
    print("刷新服务已停止")


def demo_data_change_notification():
    """演示数据变化通知功能"""
    print("\n=== 演示数据变化通知功能 ===")
    
    mock_frontend = MockFrontendInterface()
    
    config = RefreshConfig(
        enabled=True,
        data_change_debounce_seconds=2,  # 2秒防抖
        market_hours_only=False
    )
    
    refresh_manager = RealtimeRefreshManager(mock_frontend, config)
    refresh_manager.start()
    
    print("发送数据变化通知...")
    
    # 发送多个数据变化通知（测试防抖功能）
    refresh_manager.notify_data_change(['000001'], 'price_update')
    time.sleep(0.5)
    refresh_manager.notify_data_change(['000002'], 'price_update')
    time.sleep(0.5)
    refresh_manager.notify_data_change(['000003'], 'volume_update')
    
    print("等待防抖时间...")
    time.sleep(3)
    
    # 检查刷新是否被触发
    status = refresh_manager.get_status()
    print(f"防抖后刷新次数: {status['metrics']['total_refreshes']}")
    
    refresh_manager.stop()


def demo_event_subscription():
    """演示事件订阅功能"""
    print("\n=== 演示事件订阅功能 ===")
    
    mock_frontend = MockFrontendInterface()
    refresh_manager = RealtimeRefreshManager(mock_frontend)
    
    # 事件收集器
    received_events = []
    
    def event_handler(event: RefreshEvent):
        """事件处理函数"""
        received_events.append(event)
        print(f"收到事件: {event.trigger_type.value}, ID: {event.event_id}")
    
    # 订阅事件
    refresh_manager.subscribe_to_events(event_handler)
    
    # 触发一些操作
    refresh_manager.trigger_manual_refresh()
    refresh_manager.notify_data_change(['000001'])
    
    # 等待事件处理
    time.sleep(2)
    
    print(f"总共收到 {len(received_events)} 个事件")
    
    # 取消订阅
    refresh_manager.unsubscribe_from_events(event_handler)
    
    refresh_manager.stop()


def demo_market_hours_control():
    """演示交易时间控制功能"""
    print("\n=== 演示交易时间控制功能 ===")
    
    mock_frontend = MockFrontendInterface()
    
    # 配置仅在交易时间刷新
    config = RefreshConfig(
        enabled=True,
        market_hours_only=True,
        market_start_hour=9,
        market_end_hour=15,
        scheduled_interval_seconds=1
    )
    
    refresh_manager = RealtimeRefreshManager(mock_frontend, config)
    
    # 检查当前是否在交易时间
    status = refresh_manager.get_status()
    is_market_hours = status['is_market_hours']
    print(f"当前是否在交易时间: {is_market_hours}")
    
    # 启动服务
    refresh_manager.start()
    
    if is_market_hours:
        print("在交易时间内，刷新服务将正常运行")
        time.sleep(3)
    else:
        print("不在交易时间内，刷新服务将暂停定时刷新")
        time.sleep(2)
        
        # 但手动刷新仍然可以工作
        print("测试手动刷新...")
        refresh_manager.trigger_manual_refresh()
        time.sleep(1)
    
    final_status = refresh_manager.get_status()
    print(f"最终刷新次数: {final_status['metrics']['total_refreshes']}")
    
    refresh_manager.stop()


def demo_pause_resume_functionality():
    """演示暂停和恢复功能"""
    print("\n=== 演示暂停和恢复功能 ===")
    
    mock_frontend = MockFrontendInterface()
    
    config = RefreshConfig(
        enabled=True,
        scheduled_interval_seconds=1,
        market_hours_only=False
    )
    
    refresh_manager = RealtimeRefreshManager(mock_frontend, config)
    
    # 启动服务
    refresh_manager.start()
    print("服务已启动，等待2秒...")
    time.sleep(2)
    
    # 暂停服务
    refresh_manager.pause()
    print("服务已暂停，等待2秒...")
    pause_count = refresh_manager.metrics.total_refreshes
    time.sleep(2)
    
    # 检查暂停期间是否有刷新
    after_pause_count = refresh_manager.metrics.total_refreshes
    print(f"暂停期间刷新次数变化: {pause_count} -> {after_pause_count}")
    
    # 恢复服务
    refresh_manager.resume()
    print("服务已恢复，等待2秒...")
    time.sleep(2)
    
    final_count = refresh_manager.metrics.total_refreshes
    print(f"恢复后总刷新次数: {final_count}")
    
    refresh_manager.stop()


def demo_error_handling():
    """演示错误处理功能"""
    print("\n=== 演示错误处理功能 ===")
    
    # 创建会抛出异常的模拟接口
    mock_frontend = Mock()
    mock_frontend.refresh_results.side_effect = Exception("模拟刷新异常")
    mock_frontend.get_selection_results.return_value = []
    
    refresh_manager = RealtimeRefreshManager(mock_frontend)
    
    # 触发刷新（会产生异常）
    print("触发会产生异常的刷新...")
    refresh_manager.trigger_manual_refresh()
    
    # 检查错误统计
    metrics = refresh_manager.metrics
    print(f"失败次数: {metrics.failed_refreshes}")
    print(f"最后错误信息: {metrics.last_error_message}")
    
    refresh_manager.stop()


def demo_performance_metrics():
    """演示性能指标统计"""
    print("\n=== 演示性能指标统计 ===")
    
    mock_frontend = MockFrontendInterface()
    refresh_manager = RealtimeRefreshManager(mock_frontend)
    
    # 执行多次刷新
    print("执行多次刷新操作...")
    for i in range(5):
        refresh_manager.trigger_manual_refresh()
        time.sleep(0.1)  # 短暂间隔
    
    # 获取性能指标
    metrics = refresh_manager.metrics
    print(f"总刷新次数: {metrics.total_refreshes}")
    print(f"成功次数: {metrics.successful_refreshes}")
    print(f"失败次数: {metrics.failed_refreshes}")
    print(f"平均耗时: {metrics.average_refresh_duration:.4f}秒")
    print(f"最后成功时间: {metrics.last_success_time}")
    
    # 获取最近事件
    recent_events = refresh_manager.get_recent_events(3)
    print(f"最近3个事件:")
    for event in recent_events:
        print(f"  - {event['trigger_type']}: {event['event_id'][:8]}...")
    
    refresh_manager.stop()


def main():
    """主演示函数"""
    print("PVFRS策略实时数据刷新机制演示")
    print("=" * 50)
    
    try:
        # 运行各种演示
        demo_basic_refresh_functionality()
        demo_data_change_notification()
        demo_event_subscription()
        demo_market_hours_control()
        demo_pause_resume_functionality()
        demo_error_handling()
        demo_performance_metrics()
        
        print("\n" + "=" * 50)
        print("所有演示完成！")
        
    except KeyboardInterrupt:
        print("\n演示被用户中断")
    except Exception as e:
        print(f"\n演示过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()