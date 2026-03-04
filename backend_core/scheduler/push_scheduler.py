"""
定时推送调度器 (PushScheduler)
使用APScheduler实现定时任务管理
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class JobInfo:
    """任务信息"""
    
    def __init__(self, job_id: str, push_time: str, next_run_time: Optional[datetime] = None):
        """
        初始化任务信息
        
        Args:
            job_id: 任务ID
            push_time: 推送时间 (如 "09:30")
            next_run_time: 下次运行时间
        """
        self.job_id = job_id
        self.push_time = push_time
        self.next_run_time = next_run_time
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "job_id": self.job_id,
            "push_time": self.push_time,
            "next_run_time": self.next_run_time.isoformat() if self.next_run_time else None
        }


class PushScheduler:
    """定时任务调度器。推送时间以 user_push_configs 表中启用配置的 push_times 为准。"""

    def __init__(self, push_service, default_push_times: Optional[List[str]] = None):
        """
        初始化调度器

        Args:
            push_service: 推送服务实例 (PushService)，其 config_service 用于读取表内推送时间
            default_push_times: 仅当无法从表读取时使用的兜底时间（可为空）
        """
        self.push_service = push_service
        self.fallback_push_times = default_push_times or []
        self.scheduler = BackgroundScheduler(timezone='Asia/Shanghai')
        self._is_running = False
        logger.info("PushScheduler 初始化完成，推送时间以 user_push_configs 表为准")

    def _get_push_times_from_config(self) -> List[str]:
        """从 user_push_configs 表读取所有需要调度的推送时间点（去重）。"""
        try:
            if getattr(self.push_service, 'config_service', None) is not None:
                return self.push_service.config_service.get_all_distinct_push_times()
        except Exception as e:
            logger.warning(f"从 user_push_configs 读取推送时间失败，使用兜底: {e}")
        return list(self.fallback_push_times)

    def start(self):
        """
        启动调度器。
        从 user_push_configs 表读取启用配置的 push_times，为每个时间点添加定时任务。
        """
        if self._is_running:
            logger.warning("调度器已经在运行中")
            return

        try:
            self.scheduler.start()
            self._is_running = True
            logger.info("调度器已启动")

            push_times = self._get_push_times_from_config()
            if not push_times:
                logger.warning("user_push_configs 中暂无推送时间配置，未添加任何定时任务")
            else:
                for push_time in push_times:
                    try:
                        self.add_push_job(push_time)
                        logger.info(f"已添加推送任务（来自表配置）: {push_time}")
                    except Exception as e:
                        logger.error(f"添加推送任务失败 ({push_time}): {str(e)}")

            logger.info(f"调度器启动完成，已调度 {len(self.get_scheduled_jobs())} 个任务")
            
        except Exception as e:
            logger.error(f"启动调度器失败: {str(e)}", exc_info=True)
            self._is_running = False
            raise
    
    def stop(self):
        """
        停止调度器
        
        停止后会清除所有已调度的任务
        """
        if not self._is_running:
            logger.warning("调度器未运行")
            return
        
        try:
            # 停止调度器
            self.scheduler.shutdown(wait=True)
            self._is_running = False
            
            logger.info("调度器已停止")
            
        except Exception as e:
            logger.error(f"停止调度器失败: {str(e)}", exc_info=True)
            raise
    
    def add_push_job(self, push_time: str):
        """
        添加推送任务
        
        Args:
            push_time: 推送时间 (如 "09:30")
            
        Raises:
            ValueError: 如果时间格式无效
        """
        # 验证时间格式
        if not self._validate_time_format(push_time):
            raise ValueError(f"无效的时间格式: {push_time}，应为 HH:MM 格式")
        
        # 解析时间
        hour, minute = push_time.split(":")
        hour = int(hour)
        minute = int(minute)
        
        # 生成任务ID
        job_id = f"push_job_{push_time.replace(':', '')}"
        
        # 检查任务是否已存在
        existing_job = self.scheduler.get_job(job_id)
        if existing_job:
            logger.warning(f"推送任务已存在: {push_time} (job_id={job_id})")
            return
        
        try:
            # 创建Cron触发器 (每天在指定时间执行)
            trigger = CronTrigger(
                hour=hour,
                minute=minute,
                timezone='Asia/Shanghai'
            )
            
            # 添加任务
            self.scheduler.add_job(
                func=self._execute_push_job,
                trigger=trigger,
                args=[push_time],
                id=job_id,
                name=f"推送任务 {push_time}",
                replace_existing=False
            )
            
            logger.info(f"成功添加推送任务: {push_time} (job_id={job_id})")
            
        except Exception as e:
            logger.error(f"添加推送任务失败 ({push_time}): {str(e)}", exc_info=True)
            raise
    
    def remove_push_job(self, push_time: str):
        """
        移除推送任务
        
        Args:
            push_time: 推送时间 (如 "09:30")
        """
        # 生成任务ID
        job_id = f"push_job_{push_time.replace(':', '')}"
        
        try:
            # 移除任务
            self.scheduler.remove_job(job_id)
            logger.info(f"成功移除推送任务: {push_time} (job_id={job_id})")
            
        except Exception as e:
            logger.warning(f"移除推送任务失败 ({push_time}): {str(e)}")
            # 不抛出异常，因为任务可能不存在
    
    def get_scheduled_jobs(self) -> List[JobInfo]:
        """
        获取所有已调度的任务
        
        Returns:
            List[JobInfo]: 任务信息列表
        """
        jobs = []
        
        try:
            for job in self.scheduler.get_jobs():
                # 从job_id中提取推送时间
                # job_id格式: push_job_0930
                if job.id.startswith("push_job_"):
                    time_str = job.id.replace("push_job_", "")
                    # 将0930转换为09:30
                    if len(time_str) == 4:
                        push_time = f"{time_str[:2]}:{time_str[2:]}"
                    else:
                        push_time = "unknown"
                    
                    job_info = JobInfo(
                        job_id=job.id,
                        push_time=push_time,
                        next_run_time=job.next_run_time
                    )
                    jobs.append(job_info)
            
            logger.debug(f"当前已调度任务数: {len(jobs)}")
            
        except Exception as e:
            logger.error(f"获取已调度任务失败: {str(e)}", exc_info=True)
        
        return jobs
    
    def is_running(self) -> bool:
        """
        检查调度器是否正在运行
        
        Returns:
            bool: 是否正在运行
        """
        return self._is_running and self.scheduler.running
    
    def _execute_push_job(self, push_time: str):
        """
        执行推送任务（内部方法）
        
        这个方法会被调度器在指定时间调用
        
        Args:
            push_time: 推送时间 (如 "09:30")
        """
        logger.info(f"[{datetime.now()}] 开始执行定时推送任务: push_time={push_time}")
        
        try:
            # 调用推送服务执行批量推送
            result = self.push_service.execute_scheduled_push(push_time)
            
            logger.info(
                f"定时推送任务完成: push_time={push_time}, "
                f"总用户数={result.total_users}, "
                f"成功={result.success_count}, "
                f"失败={result.failed_count}, "
                f"跳过={result.skipped_count}"
            )
            
        except Exception as e:
            logger.error(
                f"执行定时推送任务异常: push_time={push_time}, error={str(e)}",
                exc_info=True
            )
    
    def _validate_time_format(self, time_str: str) -> bool:
        """
        验证时间格式是否为 HH:MM
        
        Args:
            time_str: 时间字符串
            
        Returns:
            bool: 是否有效
        """
        try:
            parts = time_str.split(":")
            if len(parts) != 2:
                return False
            
            hour = int(parts[0])
            minute = int(parts[1])
            
            # 验证范围
            if hour < 0 or hour > 23:
                return False
            if minute < 0 or minute > 59:
                return False
            
            return True
            
        except (ValueError, AttributeError):
            return False
