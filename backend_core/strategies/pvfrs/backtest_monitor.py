"""
PVFRS策略回测执行监控模块
负责回测任务的异步执行和进度监控
"""

from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
import logging
import threading
import time
import queue
from dataclasses import dataclass
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, Future, as_completed

from .models import PVFRSException

# 配置日志
logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


@dataclass
class ProgressUpdate:
    """进度更新数据结构"""
    task_id: str
    progress: int  # 0-100
    current_step: str
    timestamp: str
    details: Optional[Dict] = None


@dataclass
class TaskMetrics:
    """任务执行指标"""
    task_id: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    elapsed_seconds: float = 0.0
    estimated_total_seconds: Optional[float] = None
    estimated_remaining_seconds: Optional[float] = None
    steps_completed: int = 0
    total_steps: int = 0
    current_step_name: str = ""
    error_count: int = 0
    warning_count: int = 0


class BacktestExecutionMonitor:
    """回测执行监控器
    
    负责监控回测任务的执行状态和进度：
    - 异步任务执行管理
    - 实时进度监控
    - 任务状态跟踪
    - 性能指标收集
    - 错误和异常处理
    """
    
    def __init__(self, max_workers: int = 3):
        """初始化回测执行监控器
        
        Args:
            max_workers: 最大工作线程数
        """
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # 任务管理
        self.running_tasks: Dict[str, Future] = {}
        self.task_metrics: Dict[str, TaskMetrics] = {}
        self.task_status: Dict[str, TaskStatus] = {}
        
        # 进度监控
        self.progress_queue = queue.Queue()
        self.progress_callbacks: Dict[str, List[Callable]] = {}
        self.progress_history: Dict[str, List[ProgressUpdate]] = {}
        
        # 监控线程
        self.monitor_thread = None
        self.is_monitoring = False
        
        # 性能统计
        self.total_tasks_executed = 0
        self.total_execution_time = 0.0
        self.average_execution_time = 0.0
        
        logger.info(f"回测执行监控器初始化完成，最大工作线程数: {max_workers}")
    
    def start_monitoring(self) -> None:
        """启动监控线程"""
        if not self.is_monitoring:
            self.is_monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            logger.info("回测执行监控线程已启动")
    
    def stop_monitoring(self) -> None:
        """停止监控线程"""
        if self.is_monitoring:
            self.is_monitoring = False
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=5.0)
            logger.info("回测执行监控线程已停止")
    
    def submit_task(self, task_id: str, task_func: Callable, *args, **kwargs) -> bool:
        """提交回测任务
        
        Args:
            task_id: 任务ID
            task_func: 任务执行函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            bool: 是否成功提交
        """
        try:
            if task_id in self.running_tasks:
                logger.warning(f"任务 {task_id} 已在执行中")
                return False
            
            # 初始化任务指标
            self.task_metrics[task_id] = TaskMetrics(task_id=task_id)
            self.task_status[task_id] = TaskStatus.PENDING
            self.progress_history[task_id] = []
            
            # 包装任务函数以添加监控
            wrapped_func = self._wrap_task_function(task_id, task_func)
            
            # 提交任务
            future = self.executor.submit(wrapped_func, *args, **kwargs)
            self.running_tasks[task_id] = future
            
            # 启动监控（如果尚未启动）
            if not self.is_monitoring:
                self.start_monitoring()
            
            logger.info(f"任务 {task_id} 已提交执行")
            return True
            
        except Exception as e:
            logger.error(f"提交任务 {task_id} 失败: {str(e)}")
            return False
    
    def cancel_task(self, task_id: str) -> bool:
        """取消回测任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功取消
        """
        try:
            if task_id not in self.running_tasks:
                logger.warning(f"任务 {task_id} 不存在或未在执行")
                return False
            
            future = self.running_tasks[task_id]
            success = future.cancel()
            
            if success:
                self.task_status[task_id] = TaskStatus.CANCELLED
                self._update_task_metrics(task_id, end_time=datetime.now())
                del self.running_tasks[task_id]
                logger.info(f"任务 {task_id} 已取消")
            else:
                logger.warning(f"任务 {task_id} 无法取消（可能已开始执行）")
            
            return success
            
        except Exception as e:
            logger.error(f"取消任务 {task_id} 失败: {str(e)}")
            return False
    
    def pause_task(self, task_id: str) -> bool:
        """暂停回测任务（暂不实现，预留接口）
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功暂停
        """
        # 暂停功能需要任务函数的配合，暂不实现
        logger.warning(f"暂停功能暂未实现: {task_id}")
        return False
    
    def resume_task(self, task_id: str) -> bool:
        """恢复回测任务（暂不实现，预留接口）
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功恢复
        """
        # 恢复功能需要任务函数的配合，暂不实现
        logger.warning(f"恢复功能暂未实现: {task_id}")
        return False
    
    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[TaskStatus]: 任务状态，如果任务不存在则返回None
        """
        return self.task_status.get(task_id)
    
    def get_task_progress(self, task_id: str) -> Optional[Dict]:
        """获取任务进度信息
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[Dict]: 进度信息，如果任务不存在则返回None
        """
        if task_id not in self.task_metrics:
            return None
        
        metrics = self.task_metrics[task_id]
        status = self.task_status.get(task_id, TaskStatus.PENDING)
        
        # 获取最新进度
        latest_progress = None
        if task_id in self.progress_history and self.progress_history[task_id]:
            latest_progress = self.progress_history[task_id][-1]
        
        progress_info = {
            'task_id': task_id,
            'status': status.value,
            'progress_percentage': latest_progress.progress if latest_progress else 0,
            'current_step': latest_progress.current_step if latest_progress else "等待开始",
            'start_time': metrics.start_time.isoformat() if metrics.start_time else None,
            'end_time': metrics.end_time.isoformat() if metrics.end_time else None,
            'elapsed_seconds': metrics.elapsed_seconds,
            'estimated_total_seconds': metrics.estimated_total_seconds,
            'estimated_remaining_seconds': metrics.estimated_remaining_seconds,
            'steps_completed': metrics.steps_completed,
            'total_steps': metrics.total_steps,
            'error_count': metrics.error_count,
            'warning_count': metrics.warning_count
        }
        
        return progress_info
    
    def get_all_tasks_status(self) -> Dict[str, Dict]:
        """获取所有任务的状态信息
        
        Returns:
            Dict[str, Dict]: 所有任务的状态信息
        """
        all_status = {}
        
        for task_id in self.task_metrics:
            progress_info = self.get_task_progress(task_id)
            if progress_info:
                all_status[task_id] = progress_info
        
        return all_status
    
    def add_progress_callback(self, task_id: str, callback: Callable) -> None:
        """添加进度回调函数
        
        Args:
            task_id: 任务ID
            callback: 回调函数，签名为 callback(progress_update: ProgressUpdate)
        """
        if task_id not in self.progress_callbacks:
            self.progress_callbacks[task_id] = []
        
        self.progress_callbacks[task_id].append(callback)
        logger.debug(f"为任务 {task_id} 添加进度回调")
    
    def remove_progress_callback(self, task_id: str, callback: Callable) -> None:
        """移除进度回调函数
        
        Args:
            task_id: 任务ID
            callback: 要移除的回调函数
        """
        if task_id in self.progress_callbacks:
            try:
                self.progress_callbacks[task_id].remove(callback)
                logger.debug(f"为任务 {task_id} 移除进度回调")
            except ValueError:
                logger.warning(f"任务 {task_id} 的回调函数不存在")
    
    def update_progress(self, task_id: str, progress: int, current_step: str, 
                       details: Optional[Dict] = None) -> None:
        """更新任务进度
        
        Args:
            task_id: 任务ID
            progress: 进度百分比 (0-100)
            current_step: 当前步骤描述
            details: 可选的详细信息
        """
        try:
            # 创建进度更新对象
            progress_update = ProgressUpdate(
                task_id=task_id,
                progress=progress,
                current_step=current_step,
                timestamp=datetime.now().isoformat(),
                details=details
            )
            
            # 添加到进度队列
            self.progress_queue.put(progress_update)
            
        except Exception as e:
            logger.error(f"更新任务 {task_id} 进度失败: {str(e)}")
    
    def get_monitor_statistics(self) -> Dict:
        """获取监控统计信息
        
        Returns:
            Dict: 监控统计信息
        """
        active_tasks = len(self.running_tasks)
        total_tasks = len(self.task_metrics)
        
        # 计算状态分布
        status_counts = {}
        for status in self.task_status.values():
            status_counts[status.value] = status_counts.get(status.value, 0) + 1
        
        return {
            'monitor_status': 'active' if self.is_monitoring else 'inactive',
            'max_workers': self.max_workers,
            'active_tasks': active_tasks,
            'total_tasks': total_tasks,
            'total_tasks_executed': self.total_tasks_executed,
            'total_execution_time': self.total_execution_time,
            'average_execution_time': self.average_execution_time,
            'status_distribution': status_counts,
            'executor_info': {
                'max_workers': self.executor._max_workers,
                'threads_count': len(self.executor._threads) if hasattr(self.executor, '_threads') else 0
            }
        }
    
    def cleanup_completed_tasks(self, keep_recent_hours: int = 24) -> int:
        """清理已完成的任务记录
        
        Args:
            keep_recent_hours: 保留最近几小时的记录
            
        Returns:
            int: 清理的任务数量
        """
        cutoff_time = datetime.now() - timedelta(hours=keep_recent_hours)
        cleaned_count = 0
        
        tasks_to_remove = []
        for task_id, metrics in self.task_metrics.items():
            if (metrics.end_time and 
                metrics.end_time < cutoff_time and 
                task_id not in self.running_tasks):
                tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            # 清理相关数据
            if task_id in self.task_metrics:
                del self.task_metrics[task_id]
            if task_id in self.task_status:
                del self.task_status[task_id]
            if task_id in self.progress_history:
                del self.progress_history[task_id]
            if task_id in self.progress_callbacks:
                del self.progress_callbacks[task_id]
            
            cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"清理了 {cleaned_count} 个已完成的任务记录")
        
        return cleaned_count
    
    def _wrap_task_function(self, task_id: str, task_func: Callable) -> Callable:
        """包装任务函数以添加监控功能
        
        Args:
            task_id: 任务ID
            task_func: 原始任务函数
            
        Returns:
            Callable: 包装后的任务函数
        """
        def wrapped_func(*args, **kwargs):
            try:
                # 更新任务状态和指标
                self.task_status[task_id] = TaskStatus.RUNNING
                self._update_task_metrics(task_id, start_time=datetime.now())
                
                # 更新进度
                self.update_progress(task_id, 0, "任务开始执行")
                
                # 执行原始任务函数
                result = task_func(*args, **kwargs)
                
                # 任务成功完成
                self.task_status[task_id] = TaskStatus.COMPLETED
                self._update_task_metrics(task_id, end_time=datetime.now())
                self.update_progress(task_id, 100, "任务执行完成")
                
                # 更新统计信息
                self.total_tasks_executed += 1
                if task_id in self.task_metrics:
                    self.total_execution_time += self.task_metrics[task_id].elapsed_seconds
                    self.average_execution_time = self.total_execution_time / self.total_tasks_executed
                
                return result
                
            except Exception as e:
                # 任务执行失败
                self.task_status[task_id] = TaskStatus.FAILED
                self._update_task_metrics(task_id, end_time=datetime.now())
                self.update_progress(task_id, -1, f"任务执行失败: {str(e)}")
                
                logger.error(f"任务 {task_id} 执行失败: {str(e)}")
                raise
            
            finally:
                # 清理运行任务记录
                if task_id in self.running_tasks:
                    del self.running_tasks[task_id]
        
        return wrapped_func
    
    def _update_task_metrics(self, task_id: str, start_time: Optional[datetime] = None,
                           end_time: Optional[datetime] = None) -> None:
        """更新任务指标
        
        Args:
            task_id: 任务ID
            start_time: 开始时间
            end_time: 结束时间
        """
        if task_id not in self.task_metrics:
            return
        
        metrics = self.task_metrics[task_id]
        
        if start_time:
            metrics.start_time = start_time
        
        if end_time:
            metrics.end_time = end_time
        
        # 计算执行时间
        if metrics.start_time and metrics.end_time:
            metrics.elapsed_seconds = (metrics.end_time - metrics.start_time).total_seconds()
        elif metrics.start_time:
            metrics.elapsed_seconds = (datetime.now() - metrics.start_time).total_seconds()
    
    def _monitor_loop(self) -> None:
        """监控循环线程"""
        logger.info("监控循环线程开始运行")
        
        while self.is_monitoring:
            try:
                # 处理进度更新队列
                self._process_progress_queue()
                
                # 更新运行中任务的指标
                self._update_running_tasks_metrics()
                
                # 检查已完成的任务
                self._check_completed_tasks()
                
                # 短暂休眠
                time.sleep(1.0)
                
            except Exception as e:
                logger.error(f"监控循环异常: {str(e)}")
                time.sleep(5.0)  # 异常时休眠更长时间
        
        logger.info("监控循环线程结束运行")
    
    def _process_progress_queue(self) -> None:
        """处理进度更新队列"""
        try:
            while not self.progress_queue.empty():
                progress_update = self.progress_queue.get_nowait()
                
                # 添加到历史记录
                if progress_update.task_id not in self.progress_history:
                    self.progress_history[progress_update.task_id] = []
                
                self.progress_history[progress_update.task_id].append(progress_update)
                
                # 限制历史记录长度
                if len(self.progress_history[progress_update.task_id]) > 100:
                    self.progress_history[progress_update.task_id] = \
                        self.progress_history[progress_update.task_id][-50:]
                
                # 调用回调函数
                if progress_update.task_id in self.progress_callbacks:
                    for callback in self.progress_callbacks[progress_update.task_id]:
                        try:
                            callback(progress_update)
                        except Exception as e:
                            logger.warning(f"进度回调执行失败: {str(e)}")
                
                # 更新任务指标
                if progress_update.task_id in self.task_metrics:
                    metrics = self.task_metrics[progress_update.task_id]
                    if progress_update.progress >= 0:
                        metrics.steps_completed = progress_update.progress
                        metrics.current_step_name = progress_update.current_step
                        
                        # 估算剩余时间
                        if (metrics.start_time and progress_update.progress > 0 and 
                            progress_update.progress < 100):
                            elapsed = (datetime.now() - metrics.start_time).total_seconds()
                            estimated_total = elapsed * 100 / progress_update.progress
                            metrics.estimated_total_seconds = estimated_total
                            metrics.estimated_remaining_seconds = estimated_total - elapsed
                
        except queue.Empty:
            pass
        except Exception as e:
            logger.error(f"处理进度队列异常: {str(e)}")
    
    def _update_running_tasks_metrics(self) -> None:
        """更新运行中任务的指标"""
        for task_id in list(self.running_tasks.keys()):
            if task_id in self.task_metrics:
                self._update_task_metrics(task_id)
    
    def _check_completed_tasks(self) -> None:
        """检查已完成的任务"""
        completed_tasks = []
        
        for task_id, future in list(self.running_tasks.items()):
            if future.done():
                completed_tasks.append(task_id)
        
        # 处理已完成的任务
        for task_id in completed_tasks:
            if task_id in self.running_tasks:
                future = self.running_tasks[task_id]
                
                try:
                    # 检查任务结果
                    if future.cancelled():
                        self.task_status[task_id] = TaskStatus.CANCELLED
                    elif future.exception():
                        self.task_status[task_id] = TaskStatus.FAILED
                        if task_id in self.task_metrics:
                            self.task_metrics[task_id].error_count += 1
                    else:
                        # 任务正常完成的状态已在包装函数中设置
                        pass
                
                except Exception as e:
                    logger.error(f"检查任务 {task_id} 结果时异常: {str(e)}")
                    self.task_status[task_id] = TaskStatus.FAILED
                
                # 更新结束时间
                self._update_task_metrics(task_id, end_time=datetime.now())


# 便捷函数
def create_backtest_monitor(max_workers: int = 3) -> BacktestExecutionMonitor:
    """创建回测执行监控器实例
    
    Args:
        max_workers: 最大工作线程数
        
    Returns:
        BacktestExecutionMonitor: 监控器实例
    """
    return BacktestExecutionMonitor(max_workers)