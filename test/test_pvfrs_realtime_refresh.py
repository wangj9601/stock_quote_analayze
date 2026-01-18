"""
PVFRS策略实时数据刷新机制测试
测试选股结果的实时更新功能
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from backend_core.strategies.pvfrs.realtime_refresh import (
    RealtimeRefreshManager,
    RefreshConfig,
    RefreshTriggerType,
    RefreshStatus,
    RefreshEvent,
    RefreshMetrics,
    create_realtime_refresh_manager
)
from backend_core.strategies.pvfrs.frontend_interface import FrontendInterface, SelectionResult
from backend_core.strategies.pvfrs.models import PVFRSIndicators


class TestRealtimeRefreshManager:
    """实时刷新管理器测试类"""
    
    def setup_method(self):
        """测试前置设置"""
        # 创建模拟的前端接口
        self.mock_frontend = Mock(spec=FrontendInterface)
        
        # 创建测试配置
        self.test_config = RefreshConfig(
            enabled=True,
            scheduled_interval_seconds=5,  # 短间隔用于测试
            data_change_debounce_seconds=1,
            max_concurrent_refreshes=2,
            market_hours_only=False  # 测试时不限制交易时间
        )
        
        # 创建刷新管理器
        self.refresh_manager = RealtimeRefreshManager(
            self.mock_frontend,
            self.test_config
        )
    
    def teardown_method(self):
        """测试后清理"""
        if self.refresh_manager:
            self.refresh_manager.stop()
    
    def test_initialization(self):
        """测试初始化"""
        assert self.refresh_manager.frontend_interface == self.mock_frontend
        assert self.refresh_manager.config == self.test_config
        assert self.refresh_manager.status == RefreshStatus.IDLE
        assert isinstance(self.refresh_manager.metrics, RefreshMetrics)
    
    def test_start_and_stop_service(self):
        """测试启动和停止服务"""
        # 测试启动
        assert self.refresh_manager.start() == True
        assert self.refresh_manager.status == RefreshStatus.RUNNING
        
        # 等待一小段时间确保线程启动
        time.sleep(0.1)
        
        # 测试停止
        assert self.refresh_manager.stop() == True
        assert self.refresh_manager.status == RefreshStatus.STOPPED
    
    def test_pause_and_resume_service(self):
        """测试暂停和恢复服务"""
        # 先启动服务
        self.refresh_manager.start()
        
        # 测试暂停
        assert self.refresh_manager.pause() == True
        assert self.refresh_manager.status == RefreshStatus.PAUSED
        
        # 测试恢复
        assert self.refresh_manager.resume() == True
        assert self.refresh_manager.status == RefreshStatus.RUNNING
        
        # 清理
        self.refresh_manager.stop()
    
    def test_manual_refresh_trigger(self):
        """测试手动刷新触发"""
        # 设置模拟返回值
        self.mock_frontend.refresh_results.return_value = True
        self.mock_frontend.get_selection_results.return_value = []
        
        # 触发手动刷新
        result = self.refresh_manager.trigger_manual_refresh(['000001', '000002'])
        
        assert result == True
        assert self.mock_frontend.refresh_results.called
        assert self.refresh_manager.metrics.total_refreshes > 0
    
    def test_data_change_notification(self):
        """测试数据变化通知"""
        # 设置模拟返回值
        self.mock_frontend.refresh_results.return_value = True
        self.mock_frontend.get_selection_results.return_value = []
        
        # 通知数据变化
        self.refresh_manager.notify_data_change(['000001'], 'price_update')
        
        # 等待防抖时间
        time.sleep(1.5)
        
        # 验证刷新被触发
        assert self.mock_frontend.refresh_results.called
    
    def test_event_subscription(self):
        """测试事件订阅"""
        events_received = []
        
        def event_callback(event: RefreshEvent):
            events_received.append(event)
        
        # 订阅事件
        self.refresh_manager.subscribe_to_events(event_callback)
        
        # 触发手动刷新
        self.mock_frontend.refresh_results.return_value = True
        self.mock_frontend.get_selection_results.return_value = []
        self.refresh_manager.trigger_manual_refresh()
        
        # 验证事件被接收
        assert len(events_received) > 0
        assert events_received[0].trigger_type == RefreshTriggerType.MANUAL
        
        # 取消订阅
        self.refresh_manager.unsubscribe_from_events(event_callback)
    
    def test_config_update(self):
        """测试配置更新"""
        new_config = RefreshConfig(
            enabled=False,
            scheduled_interval_seconds=10
        )
        
        result = self.refresh_manager.update_config(new_config)
        
        assert result == True
        assert self.refresh_manager.config.enabled == False
        assert self.refresh_manager.config.scheduled_interval_seconds == 10
    
    def test_status_reporting(self):
        """测试状态报告"""
        status = self.refresh_manager.get_status()
        
        assert 'service_status' in status
        assert 'config' in status
        assert 'metrics' in status
        assert 'is_market_hours' in status
        assert status['service_status'] == RefreshStatus.IDLE.value
    
    def test_results_change_detection(self):
        """测试结果变化检测"""
        # 创建测试选股结果
        old_results = [
            SelectionResult(
                symbol='000001',
                name='测试股票1',
                signal_strength=0.8,
                conditions_met={},
                indicators=PVFRSIndicators(
                    macro_displacement=1.0, instant_deviation=0.5, avg_price_20d=10.0,
                    rising_days=12, falling_days=8, frequency_advantage=True,
                    avg_volume_20d=1000000, current_volume=1200000, efficiency_ratio=1.2,
                    amplitude_ratio=0.1, resonance_strength=0.8
                ),
                timestamp=datetime.now().isoformat(),
                price=10.5,
                signal_reason='三维共振'
            )
        ]
        
        new_results = [
            SelectionResult(
                symbol='000001',
                name='测试股票1',
                signal_strength=0.9,  # 信号强度变化
                conditions_met={},
                indicators=PVFRSIndicators(
                    macro_displacement=1.0, instant_deviation=0.5, avg_price_20d=10.0,
                    rising_days=12, falling_days=8, frequency_advantage=True,
                    avg_volume_20d=1000000, current_volume=1200000, efficiency_ratio=1.2,
                    amplitude_ratio=0.1, resonance_strength=0.9
                ),
                timestamp=datetime.now().isoformat(),
                price=10.8,
                signal_reason='三维共振'
            )
        ]
        
        # 设置初始结果
        self.refresh_manager._last_selection_results = old_results
        
        # 检测变化
        has_changes = self.refresh_manager._check_results_changes(new_results)
        
        assert has_changes == True  # 信号强度变化超过5%
    
    def test_market_hours_check(self):
        """测试交易时间检查"""
        # 创建限制交易时间的配置
        market_config = RefreshConfig(
            market_hours_only=True,
            market_start_hour=9,
            market_end_hour=15
        )
        
        manager = RealtimeRefreshManager(self.mock_frontend, market_config)
        
        # 模拟不同时间
        with patch('backend_core.strategies.pvfrs.realtime_refresh.datetime') as mock_datetime:
            # 模拟交易时间内（周一上午10点）
            mock_now = Mock()
            mock_now.weekday.return_value = 0  # 周一
            mock_now.hour = 10
            mock_datetime.now.return_value = mock_now
            
            assert manager._is_market_hours() == True
            
            # 模拟非交易时间（周六）
            mock_now.weekday.return_value = 5  # 周六
            assert manager._is_market_hours() == False
            
            # 模拟非交易时间（晚上）
            mock_now.weekday.return_value = 0  # 周一
            mock_now.hour = 20
            assert manager._is_market_hours() == False
        
        manager.stop()
    
    def test_metrics_tracking(self):
        """测试指标统计"""
        # 设置模拟返回值
        self.mock_frontend.refresh_results.return_value = True
        self.mock_frontend.get_selection_results.return_value = []
        
        # 执行几次刷新
        self.refresh_manager.trigger_manual_refresh()
        self.refresh_manager.trigger_manual_refresh()
        
        # 验证指标统计
        metrics = self.refresh_manager.metrics
        assert metrics.total_refreshes >= 2
        assert metrics.successful_refreshes >= 2
        assert metrics.last_refresh_time is not None
        assert metrics.last_success_time is not None
    
    def test_error_handling(self):
        """测试错误处理"""
        # 设置模拟抛出异常
        self.mock_frontend.refresh_results.side_effect = Exception("测试异常")
        
        # 触发刷新
        result = self.refresh_manager.trigger_manual_refresh()
        
        # 验证错误处理
        assert result == True  # 触发成功，但执行失败
        assert self.refresh_manager.metrics.failed_refreshes > 0
        assert self.refresh_manager.metrics.last_error_message == "测试异常"
    
    def test_concurrent_refresh_limit(self):
        """测试并发刷新限制"""
        # 设置较慢的刷新操作
        def slow_refresh():
            time.sleep(0.5)
            return True
        
        self.mock_frontend.refresh_results.side_effect = slow_refresh
        self.mock_frontend.get_selection_results.return_value = []
        
        # 启动多个并发刷新
        threads = []
        for i in range(5):
            thread = threading.Thread(
                target=self.refresh_manager.trigger_manual_refresh
            )
            threads.append(thread)
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        # 验证刷新次数（应该受到并发限制）
        assert self.refresh_manager.metrics.total_refreshes <= 5
    
    def test_event_queue_management(self):
        """测试事件队列管理"""
        # 触发多个刷新事件
        for i in range(10):
            self.mock_frontend.refresh_results.return_value = True
            self.mock_frontend.get_selection_results.return_value = []
            self.refresh_manager.trigger_manual_refresh()
        
        # 获取最近事件
        recent_events = self.refresh_manager.get_recent_events(5)
        
        assert len(recent_events) <= 5
        assert all('event_id' in event for event in recent_events)
        assert all('trigger_type' in event for event in recent_events)
    
    def test_clear_metrics(self):
        """测试清除统计指标"""
        # 先执行一些操作产生统计数据
        self.mock_frontend.refresh_results.return_value = True
        self.mock_frontend.get_selection_results.return_value = []
        self.refresh_manager.trigger_manual_refresh()
        
        # 验证有统计数据
        assert self.refresh_manager.metrics.total_refreshes > 0
        
        # 清除统计
        self.refresh_manager.clear_metrics()
        
        # 验证统计被清除
        assert self.refresh_manager.metrics.total_refreshes == 0
        assert self.refresh_manager.metrics.successful_refreshes == 0
        assert self.refresh_manager.metrics.failed_refreshes == 0


class TestRefreshConfig:
    """刷新配置测试类"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = RefreshConfig()
        
        assert config.enabled == True
        assert config.scheduled_interval_seconds == 300
        assert config.data_change_debounce_seconds == 30
        assert config.max_concurrent_refreshes == 3
        assert config.market_hours_only == True
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = RefreshConfig(
            enabled=False,
            scheduled_interval_seconds=600,
            data_change_debounce_seconds=60,
            max_concurrent_refreshes=5,
            market_hours_only=False
        )
        
        assert config.enabled == False
        assert config.scheduled_interval_seconds == 600
        assert config.data_change_debounce_seconds == 60
        assert config.max_concurrent_refreshes == 5
        assert config.market_hours_only == False
    
    def test_config_to_dict(self):
        """测试配置转换为字典"""
        config = RefreshConfig()
        config_dict = config.to_dict()
        
        assert isinstance(config_dict, dict)
        assert 'enabled' in config_dict
        assert 'scheduled_interval_seconds' in config_dict
        assert 'market_hours_only' in config_dict


class TestRefreshEvent:
    """刷新事件测试类"""
    
    def test_event_creation(self):
        """测试事件创建"""
        event = RefreshEvent(
            event_id='test-123',
            trigger_type=RefreshTriggerType.MANUAL,
            timestamp=datetime.now().isoformat(),
            affected_symbols=['000001', '000002'],
            event_data={'test': 'data'}
        )
        
        assert event.event_id == 'test-123'
        assert event.trigger_type == RefreshTriggerType.MANUAL
        assert event.affected_symbols == ['000001', '000002']
        assert event.event_data == {'test': 'data'}
    
    def test_event_to_dict(self):
        """测试事件转换为字典"""
        event = RefreshEvent(
            event_id='test-123',
            trigger_type=RefreshTriggerType.SCHEDULED,
            timestamp=datetime.now().isoformat(),
            affected_symbols=[],
            event_data={}
        )
        
        event_dict = event.to_dict()
        
        assert isinstance(event_dict, dict)
        assert event_dict['event_id'] == 'test-123'
        assert event_dict['trigger_type'] == 'scheduled'
        assert 'timestamp' in event_dict
        assert 'affected_symbols' in event_dict


class TestConvenienceFunctions:
    """便捷函数测试类"""
    
    def test_create_realtime_refresh_manager(self):
        """测试创建实时刷新管理器"""
        mock_frontend = Mock(spec=FrontendInterface)
        config = RefreshConfig(enabled=False)
        
        manager = create_realtime_refresh_manager(mock_frontend, config)
        
        assert isinstance(manager, RealtimeRefreshManager)
        assert manager.frontend_interface == mock_frontend
        assert manager.config == config
        
        # 清理
        manager.stop()


if __name__ == '__main__':
    pytest.main([__file__])