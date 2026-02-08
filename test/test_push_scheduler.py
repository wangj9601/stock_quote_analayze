"""
PushScheduler 单元测试
测试定时调度器的各项功能
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
import time

from backend_core.scheduler.push_scheduler import PushScheduler, JobInfo
from backend_api.services.push_service import PushBatchResult


class TestPushScheduler:
    """PushScheduler 测试类"""
    
    @pytest.fixture
    def mock_push_service(self):
        """创建Mock推送服务"""
        service = Mock()
        service.execute_scheduled_push.return_value = PushBatchResult(
            total_users=10,
            success_count=8,
            failed_count=2,
            skipped_count=0,
            push_results=[]
        )
        return service
    
    @pytest.fixture
    def scheduler(self, mock_push_service):
        """创建调度器实例"""
        return PushScheduler(
            push_service=mock_push_service,
            default_push_times=["09:30", "15:30"]
        )
    
    def test_init_scheduler(self, mock_push_service):
        """测试调度器初始化"""
        scheduler = PushScheduler(
            push_service=mock_push_service,
            default_push_times=["10:00", "16:00"]
        )
        
        assert scheduler.push_service == mock_push_service
        assert scheduler.default_push_times == ["10:00", "16:00"]
        assert not scheduler.is_running()
    
    def test_init_scheduler_with_default_times(self, mock_push_service):
        """测试使用默认推送时间初始化"""
        scheduler = PushScheduler(push_service=mock_push_service)
        
        assert scheduler.default_push_times == ["09:30", "15:30"]
    
    def test_start_scheduler(self, scheduler):
        """测试启动调度器"""
        scheduler.start()
        
        assert scheduler.is_running()
        
        # 验证默认任务已添加
        jobs = scheduler.get_scheduled_jobs()
        assert len(jobs) == 2
        
        job_times = [job.push_time for job in jobs]
        assert "09:30" in job_times
        assert "15:30" in job_times
        
        # 清理
        scheduler.stop()
    
    def test_start_scheduler_twice(self, scheduler):
        """测试重复启动调度器"""
        scheduler.start()
        assert scheduler.is_running()
        
        # 第二次启动应该被忽略
        scheduler.start()
        assert scheduler.is_running()
        
        # 清理
        scheduler.stop()
    
    def test_stop_scheduler(self, scheduler):
        """测试停止调度器"""
        scheduler.start()
        assert scheduler.is_running()
        
        scheduler.stop()
        assert not scheduler.is_running()
    
    def test_stop_scheduler_not_running(self, scheduler):
        """测试停止未运行的调度器"""
        assert not scheduler.is_running()
        
        # 应该不会抛出异常
        scheduler.stop()
        assert not scheduler.is_running()
    
    def test_add_push_job(self, scheduler):
        """测试添加推送任务"""
        scheduler.start()
        
        # 添加新任务
        scheduler.add_push_job("12:00")
        
        # 验证任务已添加
        jobs = scheduler.get_scheduled_jobs()
        job_times = [job.push_time for job in jobs]
        assert "12:00" in job_times
        
        # 清理
        scheduler.stop()
    
    def test_add_push_job_invalid_format(self, scheduler):
        """测试添加无效格式的推送任务"""
        scheduler.start()
        
        # 无效格式应该抛出异常
        with pytest.raises(ValueError, match="无效的时间格式"):
            scheduler.add_push_job("25:00")  # 小时超出范围
        
        with pytest.raises(ValueError, match="无效的时间格式"):
            scheduler.add_push_job("12:60")  # 分钟超出范围
        
        with pytest.raises(ValueError, match="无效的时间格式"):
            scheduler.add_push_job("12-00")  # 错误的分隔符
        
        with pytest.raises(ValueError, match="无效的时间格式"):
            scheduler.add_push_job("invalid")  # 完全无效
        
        # 清理
        scheduler.stop()
    
    def test_add_push_job_duplicate(self, scheduler):
        """测试添加重复的推送任务"""
        scheduler.start()
        
        # 第一次添加
        scheduler.add_push_job("14:00")
        jobs_before = len(scheduler.get_scheduled_jobs())
        
        # 第二次添加相同时间（应该被忽略）
        scheduler.add_push_job("14:00")
        jobs_after = len(scheduler.get_scheduled_jobs())
        
        # 任务数量不应该增加
        assert jobs_after == jobs_before
        
        # 清理
        scheduler.stop()
    
    def test_remove_push_job(self, scheduler):
        """测试移除推送任务"""
        scheduler.start()
        
        # 添加任务
        scheduler.add_push_job("13:00")
        jobs_before = scheduler.get_scheduled_jobs()
        assert any(job.push_time == "13:00" for job in jobs_before)
        
        # 移除任务
        scheduler.remove_push_job("13:00")
        jobs_after = scheduler.get_scheduled_jobs()
        assert not any(job.push_time == "13:00" for job in jobs_after)
        
        # 清理
        scheduler.stop()
    
    def test_remove_push_job_not_exists(self, scheduler):
        """测试移除不存在的推送任务"""
        scheduler.start()
        
        # 移除不存在的任务（不应该抛出异常）
        scheduler.remove_push_job("99:99")
        
        # 清理
        scheduler.stop()
    
    def test_get_scheduled_jobs(self, scheduler):
        """测试获取已调度任务列表"""
        scheduler.start()
        
        # 获取任务列表
        jobs = scheduler.get_scheduled_jobs()
        
        # 应该有2个默认任务
        assert len(jobs) == 2
        
        # 验证任务信息
        for job in jobs:
            assert isinstance(job, JobInfo)
            assert job.job_id is not None
            assert job.push_time in ["09:30", "15:30"]
            assert job.next_run_time is not None
        
        # 清理
        scheduler.stop()
    
    def test_get_scheduled_jobs_empty(self, mock_push_service):
        """测试获取空任务列表"""
        # 创建没有默认任务的调度器
        scheduler = PushScheduler(
            push_service=mock_push_service,
            default_push_times=[]
        )
        scheduler.start()
        
        # 清除所有现有任务（可能来自之前的测试）
        for job in scheduler.scheduler.get_jobs():
            scheduler.scheduler.remove_job(job.id)
        
        jobs = scheduler.get_scheduled_jobs()
        assert len(jobs) == 0
        
        # 清理
        scheduler.stop()
        
        # 清理
        scheduler.stop()
    
    def test_job_info_to_dict(self):
        """测试JobInfo转换为字典"""
        next_run = datetime(2024, 1, 15, 9, 30, 0)
        job_info = JobInfo(
            job_id="push_job_0930",
            push_time="09:30",
            next_run_time=next_run
        )
        
        result = job_info.to_dict()
        
        assert result["job_id"] == "push_job_0930"
        assert result["push_time"] == "09:30"
        assert result["next_run_time"] == next_run.isoformat()
    
    def test_job_info_to_dict_no_next_run(self):
        """测试JobInfo转换为字典（无下次运行时间）"""
        job_info = JobInfo(
            job_id="push_job_0930",
            push_time="09:30",
            next_run_time=None
        )
        
        result = job_info.to_dict()
        
        assert result["next_run_time"] is None
    
    def test_validate_time_format(self, scheduler):
        """测试时间格式验证"""
        # 有效格式
        assert scheduler._validate_time_format("09:30")
        assert scheduler._validate_time_format("00:00")
        assert scheduler._validate_time_format("23:59")
        assert scheduler._validate_time_format("12:00")
        
        # 无效格式
        assert not scheduler._validate_time_format("25:00")  # 小时超出范围
        assert not scheduler._validate_time_format("12:60")  # 分钟超出范围
        assert not scheduler._validate_time_format("-1:30")  # 负数
        assert not scheduler._validate_time_format("12-30")  # 错误分隔符
        assert not scheduler._validate_time_format("12:30:00")  # 包含秒
        assert not scheduler._validate_time_format("invalid")  # 完全无效
        assert not scheduler._validate_time_format("")  # 空字符串
    
    def test_execute_push_job_success(self, scheduler, mock_push_service):
        """测试执行推送任务成功"""
        scheduler.start()
        
        # 手动触发推送任务
        scheduler._execute_push_job("09:30")
        
        # 验证推送服务被调用
        mock_push_service.execute_scheduled_push.assert_called_once_with("09:30")
        
        # 清理
        scheduler.stop()
    
    def test_execute_push_job_exception(self, scheduler, mock_push_service):
        """测试执行推送任务异常"""
        scheduler.start()
        
        # 模拟推送服务抛出异常
        mock_push_service.execute_scheduled_push.side_effect = Exception("推送失败")
        
        # 执行任务（不应该抛出异常）
        scheduler._execute_push_job("09:30")
        
        # 验证推送服务被调用
        mock_push_service.execute_scheduled_push.assert_called_once_with("09:30")
        
        # 清理
        scheduler.stop()
    
    def test_scheduler_persistence_after_restart(self, mock_push_service):
        """测试系统重启后任务恢复"""
        # 第一次启动
        scheduler1 = PushScheduler(
            push_service=mock_push_service,
            default_push_times=["09:30", "15:30"]
        )
        scheduler1.start()
        
        jobs1 = scheduler1.get_scheduled_jobs()
        assert len(jobs1) == 2
        
        scheduler1.stop()
        
        # 模拟系统重启 - 创建新的调度器实例
        scheduler2 = PushScheduler(
            push_service=mock_push_service,
            default_push_times=["09:30", "15:30"]
        )
        scheduler2.start()
        
        # 验证任务已恢复
        jobs2 = scheduler2.get_scheduled_jobs()
        assert len(jobs2) == 2
        
        job_times = [job.push_time for job in jobs2]
        assert "09:30" in job_times
        assert "15:30" in job_times
        
        scheduler2.stop()
    
    def test_multiple_jobs_different_times(self, scheduler):
        """测试添加多个不同时间的任务"""
        scheduler.start()
        
        # 添加多个任务
        times = ["08:00", "10:00", "12:00", "14:00", "16:00"]
        for time_str in times:
            scheduler.add_push_job(time_str)
        
        # 验证所有任务都已添加
        jobs = scheduler.get_scheduled_jobs()
        job_times = [job.push_time for job in jobs]
        
        # 应该包含默认任务和新添加的任务
        for time_str in times:
            assert time_str in job_times
        
        # 清理
        scheduler.stop()
    
    def test_scheduler_timezone(self, scheduler):
        """测试调度器使用正确的时区"""
        scheduler.start()
        
        # 验证调度器使用Asia/Shanghai时区
        assert str(scheduler.scheduler.timezone) == "Asia/Shanghai"
        
        # 清理
        scheduler.stop()


class TestPushSchedulerIntegration:
    """PushScheduler 集成测试"""
    
    @pytest.fixture
    def mock_push_service(self):
        """创建Mock推送服务"""
        service = Mock()
        service.execute_scheduled_push.return_value = PushBatchResult(
            total_users=5,
            success_count=5,
            failed_count=0,
            skipped_count=0,
            push_results=[]
        )
        return service
    
    def test_scheduler_lifecycle(self, mock_push_service):
        """测试调度器完整生命周期"""
        # 1. 创建调度器
        scheduler = PushScheduler(
            push_service=mock_push_service,
            default_push_times=["09:30"]
        )
        assert not scheduler.is_running()
        
        # 2. 启动调度器
        scheduler.start()
        assert scheduler.is_running()
        
        # 3. 添加任务
        scheduler.add_push_job("14:00")
        jobs = scheduler.get_scheduled_jobs()
        assert len(jobs) == 2  # 1个默认 + 1个新增
        
        # 4. 移除任务
        scheduler.remove_push_job("14:00")
        jobs = scheduler.get_scheduled_jobs()
        assert len(jobs) == 1  # 只剩默认任务
        
        # 5. 停止调度器
        scheduler.stop()
        assert not scheduler.is_running()
    
    def test_add_and_remove_multiple_jobs(self, mock_push_service):
        """测试批量添加和移除任务"""
        scheduler = PushScheduler(
            push_service=mock_push_service,
            default_push_times=[]
        )
        scheduler.start()
        
        # 清除所有现有任务（可能来自之前的测试）
        for job in scheduler.scheduler.get_jobs():
            scheduler.scheduler.remove_job(job.id)
        
        # 批量添加任务
        times = ["08:00", "10:00", "12:00", "14:00", "16:00", "18:00"]
        for time_str in times:
            scheduler.add_push_job(time_str)
        
        assert len(scheduler.get_scheduled_jobs()) == 6
        
        # 批量移除任务
        for time_str in times[:3]:  # 移除前3个
            scheduler.remove_push_job(time_str)
        
        assert len(scheduler.get_scheduled_jobs()) == 3
        
        # 验证剩余的任务
        remaining_jobs = scheduler.get_scheduled_jobs()
        remaining_times = [job.push_time for job in remaining_jobs]
        assert "14:00" in remaining_times
        assert "16:00" in remaining_times
        assert "18:00" in remaining_times
        
        scheduler.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
