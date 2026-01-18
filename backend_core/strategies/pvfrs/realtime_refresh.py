"""
PVFRS策略实时数据刷新机制 - 工作版本
实现选股结果的实时更新功能，确保数据变化时前端能及时响应
"""

import threading
import time
import uuid
from typing import Dict, List, Optional, Callable, Any, Set
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from concurrent.futures import ThreadPoolExecutor

# 配置日志
logger = logging.getLogger(__name__)


class RefreshTriggerType(Enum):
    """刷新触发类型"""
    SCHEDULED = "scheduled"      # 定时刷新
    DATA_CHANGE = "data_change"  # 数据变化触发
    MANUAL = "manual"           # 手动触发
    MARKET_EVENT = "market_event"  # 市场事件触发


@dataclass
class RefreshEvent:
    """刷新事件数据结构"""
    event_id: str               # 事件ID
    trigger_type: RefreshTriggerType  # 触发类型
    timestamp: str             # 事件时间戳
    affected_symbols: List[str]  # 受影响的股票代码
    event_data: Dict[str, Any]  # 事件数据
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        result = asdict(self)
        result['trigger_type'] = self.trigger_type.value
        return result


@dataclass
class RefreshConfig:
    """刷新配置"""
    enabled: bool = True                    # 是否启用实时刷新
    scheduled_interval_seconds: int = 300   # 定时刷新间隔（秒）
    data_change_debounce_seconds: int = 30  # 数据变化防抖时间（秒）
    max_concurrent_refreshes: int = 3       # 最大并发刷新数量
    market_hours_only: bool = True          # 是否仅在交易时间刷新
    market_start_hour: int = 9              # 市场开始时间（小时）
    market_end_hour: int = 15               # 市场结束时间（小时）
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return asdict(self)


class RefreshStatus(Enum):
    """刷新状态"""
    IDLE = "idle"                    # 空闲
    RUNNING = "running"              # 运行中
    PAUSED = "paused"               # 暂停
    ERROR = "error"                 # 错误
    STOPPED = "stopped"             # 已停止


@dataclass
class RefreshMetrics:
    """刷新指标统计"""
    total_refreshes: int = 0        # 总刷新次数
    successful_refreshes: int = 0   # 成功刷新次数
    failed_refreshes: int = 0       # 失败刷新次数
    last_refresh_time: Optional[str] = None  # 最后刷新时间
    last_success_time: Optional[str] = None  # 最后成功时间
    last_error_time: Optional[str] = None    # 最后错误时间
    last_error_message: Optional[str] = None # 最后错误信息
    average_refresh_duration: float = 0.0    # 平均刷新耗时（秒）
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return asdict(self)


class RealtimeRefreshManager:
    """实时数据刷新管理器
    
    负责管理PVFRS选股结果的实时更新功能：
    - 定时刷新机制
    - 数据变化监听
    - 手动刷新触发
    - 市场事件响应
    - 刷新状态管理
    - 性能监控和统计
    """
    
    def __init__(self, frontend_interface, config: Optional[RefreshConfig] = None):
        """初始化实时刷新管理器
        
        Args:
            frontend_interface: 前端接口实例
            config: 刷新配置，如果不提供则使用默认配置
        """
        self.frontend_interface = frontend_interface
        self.config = config or RefreshConfig()
        
        # 状态管理
        self.status = RefreshStatus.IDLE
        self.metrics = RefreshMetrics()
        
        # 线程和任务管理
        self._refresh_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._executor = ThreadPoolExecutor(max_workers=self.config.max_concurrent_refreshes)
        
        # 事件管理
        self._event_queue: List[RefreshEvent] = []
        self._event_lock = threading.Lock()
        self._subscribers: List[Callable[[RefreshEvent], None]] = []
        
        # 数据变化监听
        self._pending_data_changes: Set[str] = set()
        self._debounce_timer: Optional[threading.Timer] = None
        
        # 缓存管理
        self._last_selection_results: List = []
        self._last_refresh_duration: float = 0.0
        
        logger.info("实时刷新管理器初始化完成")
    
    def start(self) -> bool:
        """启动实时刷新服务"""
        try:
            if self.status == RefreshStatus.RUNNING:
                logger.warning("实时刷新服务已在运行中")
                return True
            
            if not self.config.enabled:
                logger.info("实时刷新功能已禁用")
                return False
            
            logger.info("启动实时刷新服务")
            
            # 重置停止事件
            self._stop_event.clear()
            
            # 启动刷新线程
            self._refresh_thread = threading.Thread(
                target=self._refresh_loop,
                name="PVFRS-RealtimeRefresh",
                daemon=True
            )
            self._refresh_thread.start()
            
            self.status = RefreshStatus.RUNNING
            
            # 触发启动事件
            self._emit_event(RefreshEvent(
                event_id=str(uuid.uuid4()),
                trigger_type=RefreshTriggerType.MANUAL,
                timestamp=datetime.now().isoformat(),
                affected_symbols=[],
                event_data={'action': 'service_started'}
            ))
            
            logger.info("实时刷新服务启动成功")
            return True
            
        except Exception as e:
            logger.error(f"启动实时刷新服务失败: {str(e)}")
            self.status = RefreshStatus.ERROR
            self.metrics.last_error_time = datetime.now().isoformat()
            self.metrics.last_error_message = str(e)
            return False
    
    def stop(self) -> bool:
        """停止实时刷新服务"""
        try:
            logger.info("停止实时刷新服务")
            
            # 设置停止事件
            self._stop_event.set()
            
            # 取消防抖定时器
            if self._debounce_timer:
                self._debounce_timer.cancel()
                self._debounce_timer = None
            
            # 等待刷新线程结束
            if self._refresh_thread and self._refresh_thread.is_alive():
                self._refresh_thread.join(timeout=5.0)
            
            # 关闭线程池
            self._executor.shutdown(wait=True)
            
            self.status = RefreshStatus.STOPPED
            
            # 触发停止事件
            self._emit_event(RefreshEvent(
                event_id=str(uuid.uuid4()),
                trigger_type=RefreshTriggerType.MANUAL,
                timestamp=datetime.now().isoformat(),
                affected_symbols=[],
                event_data={'action': 'service_stopped'}
            ))
            
            logger.info("实时刷新服务停止成功")
            return True
            
        except Exception as e:
            logger.error(f"停止实时刷新服务失败: {str(e)}")
            return False
    
    def pause(self) -> bool:
        """暂停实时刷新服务"""
        if self.status == RefreshStatus.RUNNING:
            self.status = RefreshStatus.PAUSED
            logger.info("实时刷新服务已暂停")
            return True
        return False
    
    def resume(self) -> bool:
        """恢复实时刷新服务"""
        if self.status == RefreshStatus.PAUSED:
            self.status = RefreshStatus.RUNNING
            logger.info("实时刷新服务已恢复")
            return True
        return False
    
    def trigger_manual_refresh(self, symbols: Optional[List[str]] = None) -> bool:
        """触发手动刷新"""
        try:
            logger.info(f"触发手动刷新，股票: {symbols or '全部'}")
            
            # 创建刷新事件
            event = RefreshEvent(
                event_id=str(uuid.uuid4()),
                trigger_type=RefreshTriggerType.MANUAL,
                timestamp=datetime.now().isoformat(),
                affected_symbols=symbols or [],
                event_data={'manual_trigger': True}
            )
            
            # 添加到事件队列
            with self._event_lock:
                self._event_queue.append(event)
            
            # 立即执行刷新
            self._execute_refresh(event)
            
            return True
            
        except Exception as e:
            logger.error(f"触发手动刷新失败: {str(e)}")
            return False
    
    def notify_data_change(self, symbols: List[str], change_type: str = "price_update") -> None:
        """通知数据变化"""
        try:
            logger.debug(f"收到数据变化通知: {symbols}, 类型: {change_type}")
            
            # 添加到待处理变化集合
            self._pending_data_changes.update(symbols)
            
            # 取消之前的防抖定时器
            if self._debounce_timer:
                self._debounce_timer.cancel()
            
            # 设置新的防抖定时器
            self._debounce_timer = threading.Timer(
                self.config.data_change_debounce_seconds,
                self._process_data_changes
            )
            self._debounce_timer.start()
            
        except Exception as e:
            logger.error(f"处理数据变化通知失败: {str(e)}")
    
    def subscribe_to_events(self, callback: Callable[[RefreshEvent], None]) -> None:
        """订阅刷新事件"""
        self._subscribers.append(callback)
        logger.info(f"添加事件订阅者，当前订阅者数量: {len(self._subscribers)}")
    
    def unsubscribe_from_events(self, callback: Callable[[RefreshEvent], None]) -> None:
        """取消订阅刷新事件"""
        if callback in self._subscribers:
            self._subscribers.remove(callback)
            logger.info(f"移除事件订阅者，当前订阅者数量: {len(self._subscribers)}")
    
    def get_status(self) -> Dict:
        """获取刷新服务状态"""
        return {
            'service_status': self.status.value,
            'config': self.config.to_dict(),
            'metrics': self.metrics.to_dict(),
            'is_market_hours': self._is_market_hours(),
            'pending_changes_count': len(self._pending_data_changes),
            'event_queue_size': len(self._event_queue),
            'subscribers_count': len(self._subscribers),
            'last_selection_count': len(self._last_selection_results),
            'last_refresh_duration': self._last_refresh_duration
        }
    
    def update_config(self, new_config: RefreshConfig) -> bool:
        """更新刷新配置"""
        try:
            old_enabled = self.config.enabled
            self.config = new_config
            
            logger.info("刷新配置已更新")
            
            # 如果启用状态发生变化，相应地启动或停止服务
            if old_enabled != new_config.enabled:
                if new_config.enabled and self.status == RefreshStatus.STOPPED:
                    return self.start()
                elif not new_config.enabled and self.status == RefreshStatus.RUNNING:
                    return self.stop()
            
            return True
            
        except Exception as e:
            logger.error(f"更新刷新配置失败: {str(e)}")
            return False
    
    def get_recent_events(self, limit: int = 10) -> List[Dict]:
        """获取最近的刷新事件"""
        with self._event_lock:
            recent_events = self._event_queue[-limit:] if self._event_queue else []
            return [event.to_dict() for event in recent_events]
    
    def clear_metrics(self) -> None:
        """清除统计指标"""
        self.metrics = RefreshMetrics()
        logger.info("刷新统计指标已清除")
    
    def _refresh_loop(self) -> None:
        """刷新循环主函数"""
        logger.info("刷新循环开始")
        
        while not self._stop_event.is_set():
            try:
                # 检查是否暂停
                if self.status == RefreshStatus.PAUSED:
                    time.sleep(1)
                    continue
                
                # 检查是否在交易时间
                if self.config.market_hours_only and not self._is_market_hours():
                    time.sleep(60)  # 非交易时间每分钟检查一次
                    continue
                
                # 执行定时刷新
                self._execute_scheduled_refresh()
                
                # 等待下次刷新
                self._stop_event.wait(timeout=self.config.scheduled_interval_seconds)
                
            except Exception as e:
                logger.error(f"刷新循环异常: {str(e)}")
                self.status = RefreshStatus.ERROR
                self.metrics.last_error_time = datetime.now().isoformat()
                self.metrics.last_error_message = str(e)
                time.sleep(30)  # 错误后等待30秒再重试
        
        logger.info("刷新循环结束")
    
    def _execute_scheduled_refresh(self) -> None:
        """执行定时刷新"""
        event = RefreshEvent(
            event_id=str(uuid.uuid4()),
            trigger_type=RefreshTriggerType.SCHEDULED,
            timestamp=datetime.now().isoformat(),
            affected_symbols=[],
            event_data={'scheduled_refresh': True}
        )
        
        self._execute_refresh(event)
    
    def _process_data_changes(self) -> None:
        """处理数据变化（防抖后执行）"""
        try:
            if not self._pending_data_changes:
                return
            
            symbols = list(self._pending_data_changes)
            self._pending_data_changes.clear()
            
            logger.info(f"处理数据变化，影响股票: {symbols}")
            
            event = RefreshEvent(
                event_id=str(uuid.uuid4()),
                trigger_type=RefreshTriggerType.DATA_CHANGE,
                timestamp=datetime.now().isoformat(),
                affected_symbols=symbols,
                event_data={'data_change_symbols': symbols}
            )
            
            self._execute_refresh(event)
            
        except Exception as e:
            logger.error(f"处理数据变化失败: {str(e)}")
    
    def _execute_refresh(self, event: RefreshEvent) -> None:
        """执行刷新操作"""
        start_time = time.time()
        
        try:
            logger.info(f"执行刷新操作，事件ID: {event.event_id}, 类型: {event.trigger_type.value}")
            
            # 更新统计
            self.metrics.total_refreshes += 1
            self.metrics.last_refresh_time = event.timestamp
            
            # 执行实际刷新
            success = self.frontend_interface.refresh_results()
            
            if success:
                # 获取最新选股结果
                new_results = self.frontend_interface.get_selection_results()
                
                # 检查结果是否有变化
                has_changes = self._check_results_changes(new_results)
                
                # 更新缓存
                self._last_selection_results = new_results
                
                # 更新成功统计
                self.metrics.successful_refreshes += 1
                self.metrics.last_success_time = event.timestamp
                
                # 更新事件数据
                event.event_data.update({
                    'success': True,
                    'results_count': len(new_results),
                    'has_changes': has_changes,
                    'refresh_duration': time.time() - start_time
                })
                
                logger.info(f"刷新成功，获取到 {len(new_results)} 只股票，有变化: {has_changes}")
                
            else:
                # 更新失败统计
                self.metrics.failed_refreshes += 1
                self.metrics.last_error_time = event.timestamp
                self.metrics.last_error_message = "刷新操作返回失败"
                
                event.event_data.update({
                    'success': False,
                    'error': '刷新操作返回失败'
                })
                
                logger.warning("刷新操作失败")
            
        except Exception as e:
            # 更新失败统计
            self.metrics.failed_refreshes += 1
            self.metrics.last_error_time = event.timestamp
            self.metrics.last_error_message = str(e)
            
            event.event_data.update({
                'success': False,
                'error': str(e)
            })
            
            logger.error(f"执行刷新操作异常: {str(e)}")
        
        finally:
            # 更新刷新耗时
            duration = time.time() - start_time
            self._last_refresh_duration = duration
            
            # 更新平均耗时
            if self.metrics.total_refreshes > 0:
                self.metrics.average_refresh_duration = (
                    (self.metrics.average_refresh_duration * (self.metrics.total_refreshes - 1) + duration) /
                    self.metrics.total_refreshes
                )
            
            # 发送事件通知
            self._emit_event(event)
    
    def _check_results_changes(self, new_results: List) -> bool:
        """检查选股结果是否有变化"""
        try:
            # 如果是第一次获取结果
            if not self._last_selection_results:
                return True
            
            # 比较结果数量
            if len(new_results) != len(self._last_selection_results):
                return True
            
            # 简单比较：如果结果列表长度不同或为空，认为有变化
            if not new_results and not self._last_selection_results:
                return False
            
            # 如果有结果，检查第一个结果的属性（简化版本）
            if new_results and self._last_selection_results:
                try:
                    # 尝试比较股票代码
                    old_symbols = {getattr(r, 'symbol', str(r)) for r in self._last_selection_results}
                    new_symbols = {getattr(r, 'symbol', str(r)) for r in new_results}
                    
                    if old_symbols != new_symbols:
                        return True
                        
                    # 尝试比较信号强度
                    old_strengths = {getattr(r, 'symbol', str(r)): getattr(r, 'signal_strength', 0.0) 
                                   for r in self._last_selection_results}
                    new_strengths = {getattr(r, 'symbol', str(r)): getattr(r, 'signal_strength', 0.0) 
                                   for r in new_results}
                    
                    for symbol in new_symbols:
                        old_strength = old_strengths.get(symbol, 0.0)
                        new_strength = new_strengths.get(symbol, 0.0)
                        
                        # 如果信号强度变化超过5%，认为有变化
                        if abs(new_strength - old_strength) > 0.05:
                            return True
                            
                except (AttributeError, TypeError):
                    # 如果对象结构不符合预期，认为有变化
                    return True
            
            return False
            
        except Exception as e:
            logger.warning(f"检查结果变化失败: {str(e)}")
            return True  # 出错时认为有变化，确保刷新
    
    def _emit_event(self, event: RefreshEvent) -> None:
        """发送事件通知"""
        try:
            # 添加到事件队列
            with self._event_lock:
                self._event_queue.append(event)
                
                # 限制事件队列大小
                if len(self._event_queue) > 100:
                    self._event_queue = self._event_queue[-50:]  # 保留最近50个事件
            
            # 通知订阅者
            for subscriber in self._subscribers:
                try:
                    subscriber(event)
                except Exception as e:
                    logger.warning(f"通知事件订阅者失败: {str(e)}")
            
        except Exception as e:
            logger.error(f"发送事件通知失败: {str(e)}")
    
    def _is_market_hours(self) -> bool:
        """检查是否在交易时间"""
        try:
            now = datetime.now()
            
            # 检查是否是工作日（周一到周五）
            if now.weekday() >= 5:  # 周六、周日
                return False
            
            # 检查时间范围
            current_hour = now.hour
            return self.config.market_start_hour <= current_hour < self.config.market_end_hour
            
        except Exception as e:
            logger.warning(f"检查交易时间失败: {str(e)}")
            return True  # 出错时默认认为在交易时间
    
    def __del__(self):
        """析构函数，确保资源清理"""
        try:
            self.stop()
        except:
            pass


# 便捷函数
def create_realtime_refresh_manager(frontend_interface, config: Optional[RefreshConfig] = None) -> RealtimeRefreshManager:
    """创建实时刷新管理器实例"""
    return RealtimeRefreshManager(frontend_interface, config)