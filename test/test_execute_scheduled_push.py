"""
测试批量推送逻辑 (execute_scheduled_push)
验证任务 7.4 的实现
"""

import pytest
from datetime import date, datetime
from unittest.mock import Mock, MagicMock, patch
from backend_api.services.push_service import PushService, PushResult, PushBatchResult, ChannelResult
from backend_api.services.config_service import ConfigService
from backend_api.services.report_service import ReportService
from backend_api.services.record_repository import RecordRepository
from backend_api.services.email_service import EmailService
from backend_core.wechat.wechat_service import WeChatService
from backend_api.models import User, UserPushConfig


class TestExecuteScheduledPush:
    """测试批量推送逻辑"""
    
    @pytest.fixture
    def mock_services(self):
        """创建模拟服务"""
        wechat_service = Mock(spec=WeChatService)
        email_service = Mock(spec=EmailService)
        report_service = Mock(spec=ReportService)
        config_service = Mock(spec=ConfigService)
        record_repository = Mock(spec=RecordRepository)
        
        return {
            'wechat': wechat_service,
            'email': email_service,
            'report': report_service,
            'config': config_service,
            'record': record_repository
        }
    
    @pytest.fixture
    def push_service(self, mock_services):
        """创建推送服务实例"""
        return PushService(
            wechat_service=mock_services['wechat'],
            email_service=mock_services['email'],
            report_service=mock_services['report'],
            config_service=mock_services['config'],
            record_repository=mock_services['record']
        )
    
    def test_execute_scheduled_push_no_users(self, push_service, mock_services):
        """测试：没有需要推送的用户"""
        # 设置：没有用户需要推送
        mock_services['config'].get_users_for_push_time.return_value = []
        
        # 执行
        result = push_service.execute_scheduled_push("09:30")
        
        # 验证
        assert result.total_users == 0
        assert result.success_count == 0
        assert result.failed_count == 0
        assert result.skipped_count == 0
        assert len(result.push_results) == 0
        
        # 验证调用
        mock_services['config'].get_users_for_push_time.assert_called_once_with("09:30")
    
    def test_execute_scheduled_push_all_duplicates(self, push_service, mock_services):
        """测试：所有用户今日已推送（去重）"""
        # 创建测试用户
        users = [
            Mock(spec=User, id=1, username="user1"),
            Mock(spec=User, id=2, username="user2"),
            Mock(spec=User, id=3, username="user3")
        ]
        
        # 设置：有3个用户需要推送
        mock_services['config'].get_users_for_push_time.return_value = users
        
        # 设置：所有用户都已推送过（去重检查返回True）
        mock_services['record'].check_duplicate_push.return_value = True
        
        # 执行
        result = push_service.execute_scheduled_push("09:30")
        
        # 验证
        assert result.total_users == 3
        assert result.success_count == 0
        assert result.failed_count == 0
        assert result.skipped_count == 3
        assert len(result.push_results) == 0
        
        # 验证去重检查被调用了3次
        assert mock_services['record'].check_duplicate_push.call_count == 3
    
    def test_execute_scheduled_push_single_user_success(self, push_service, mock_services):
        """测试：单个用户推送成功"""
        # 创建测试用户
        user = Mock(spec=User, id=1, username="user1", wechat_openid="openid1", email="user1@test.com")
        
        # 设置：有1个用户需要推送
        mock_services['config'].get_users_for_push_time.return_value = [user]
        
        # 设置：未推送过（去重检查返回False）
        mock_services['record'].check_duplicate_push.return_value = False
        
        # 模拟 push_to_user 返回成功结果
        with patch.object(push_service, 'push_to_user') as mock_push:
            mock_push.return_value = PushResult(
                user_id=1,
                success=True,
                channel_results=[
                    ChannelResult(channel='wechat', success=True)
                ],
                record_id=100
            )
            
            # 执行
            result = push_service.execute_scheduled_push("09:30")
        
        # 验证
        assert result.total_users == 1
        assert result.success_count == 1
        assert result.failed_count == 0
        assert result.skipped_count == 0
        assert len(result.push_results) == 1
        assert result.push_results[0].success is True
        assert result.push_results[0].user_id == 1
    
    def test_execute_scheduled_push_multiple_users_mixed_results(self, push_service, mock_services):
        """测试：多个用户推送，结果混合（成功、失败、跳过）"""
        # 创建测试用户
        users = [
            Mock(spec=User, id=1, username="user1"),
            Mock(spec=User, id=2, username="user2"),
            Mock(spec=User, id=3, username="user3"),
            Mock(spec=User, id=4, username="user4")
        ]
        
        # 设置：有4个用户需要推送
        mock_services['config'].get_users_for_push_time.return_value = users
        
        # 设置：user1已推送（跳过），其他未推送
        def check_duplicate_side_effect(user_id, push_date, push_time):
            return user_id == 1  # user1已推送
        
        mock_services['record'].check_duplicate_push.side_effect = check_duplicate_side_effect
        
        # 模拟 push_to_user 返回不同结果
        def push_to_user_side_effect(user_id, push_time):
            if user_id == 2:
                # user2 推送成功
                return PushResult(
                    user_id=user_id,
                    success=True,
                    channel_results=[ChannelResult(channel='wechat', success=True)],
                    record_id=200
                )
            elif user_id == 3:
                # user3 推送失败
                return PushResult(
                    user_id=user_id,
                    success=False,
                    channel_results=[ChannelResult(channel='wechat', success=False, error_message="发送失败")],
                    record_id=300,
                    error_message="推送失败"
                )
            elif user_id == 4:
                # user4 推送成功
                return PushResult(
                    user_id=user_id,
                    success=True,
                    channel_results=[ChannelResult(channel='email', success=True)],
                    record_id=400
                )
        
        with patch.object(push_service, 'push_to_user', side_effect=push_to_user_side_effect):
            # 执行
            result = push_service.execute_scheduled_push("09:30")
        
        # 验证
        assert result.total_users == 4
        assert result.success_count == 2  # user2, user4
        assert result.failed_count == 1  # user3
        assert result.skipped_count == 1  # user1
        assert len(result.push_results) == 3  # user2, user3, user4
        
        # 验证结果详情
        user_ids = [r.user_id for r in result.push_results]
        assert 2 in user_ids
        assert 3 in user_ids
        assert 4 in user_ids
        assert 1 not in user_ids  # user1被跳过
    
    def test_execute_scheduled_push_concurrent_processing(self, push_service, mock_services):
        """测试：并发处理多个用户"""
        # 创建10个测试用户
        users = [Mock(spec=User, id=i, username=f"user{i}") for i in range(1, 11)]
        
        # 设置：有10个用户需要推送
        mock_services['config'].get_users_for_push_time.return_value = users
        
        # 设置：都未推送过
        mock_services['record'].check_duplicate_push.return_value = False
        
        # 记录调用顺序和时间
        call_times = []
        
        def push_to_user_side_effect(user_id, push_time):
            import time
            call_times.append((user_id, datetime.now()))
            time.sleep(0.1)  # 模拟推送耗时
            return PushResult(
                user_id=user_id,
                success=True,
                channel_results=[ChannelResult(channel='wechat', success=True)],
                record_id=user_id * 100
            )
        
        with patch.object(push_service, 'push_to_user', side_effect=push_to_user_side_effect):
            # 执行（使用3个工作线程）
            result = push_service.execute_scheduled_push("09:30", max_workers=3)
        
        # 验证
        assert result.total_users == 10
        assert result.success_count == 10
        assert result.failed_count == 0
        assert result.skipped_count == 0
        assert len(result.push_results) == 10
        
        # 验证并发执行（所有调用都应该被记录）
        assert len(call_times) == 10
    
    def test_execute_scheduled_push_single_user_failure_isolation(self, push_service, mock_services):
        """测试：单个用户失败不影响其他用户"""
        # 创建测试用户
        users = [
            Mock(spec=User, id=1, username="user1"),
            Mock(spec=User, id=2, username="user2"),
            Mock(spec=User, id=3, username="user3")
        ]
        
        # 设置：有3个用户需要推送
        mock_services['config'].get_users_for_push_time.return_value = users
        
        # 设置：都未推送过
        mock_services['record'].check_duplicate_push.return_value = False
        
        # 模拟 push_to_user：user2抛出异常，其他正常
        def push_to_user_side_effect(user_id, push_time):
            if user_id == 2:
                raise Exception("模拟推送异常")
            return PushResult(
                user_id=user_id,
                success=True,
                channel_results=[ChannelResult(channel='wechat', success=True)],
                record_id=user_id * 100
            )
        
        with patch.object(push_service, 'push_to_user', side_effect=push_to_user_side_effect):
            # 执行
            result = push_service.execute_scheduled_push("09:30")
        
        # 验证：即使user2失败，user1和user3仍然成功
        assert result.total_users == 3
        assert result.success_count == 2  # user1, user3
        assert result.failed_count == 1  # user2
        assert result.skipped_count == 0
        assert len(result.push_results) == 3
        
        # 验证失败的用户
        failed_results = [r for r in result.push_results if not r.success]
        assert len(failed_results) == 1
        assert failed_results[0].user_id == 2
        assert "异常" in failed_results[0].error_message
    
    def test_execute_scheduled_push_exception_handling(self, push_service, mock_services):
        """测试：批量推送过程中的异常处理"""
        # 设置：get_users_for_push_time 抛出异常
        mock_services['config'].get_users_for_push_time.side_effect = Exception("数据库连接失败")
        
        # 执行
        result = push_service.execute_scheduled_push("09:30")
        
        # 验证：即使出现异常，也返回结果对象
        assert result.total_users == 0
        assert result.success_count == 0
        assert result.failed_count == 0
        assert result.skipped_count == 0
        assert len(result.push_results) == 0
    
    def test_push_to_user_safe_wrapper(self, push_service, mock_services):
        """测试：_push_to_user_safe 包装方法捕获异常"""
        # 模拟 push_to_user 抛出异常
        with patch.object(push_service, 'push_to_user', side_effect=Exception("未预期的异常")):
            # 执行
            result = push_service._push_to_user_safe(1, "09:30")
        
        # 验证：异常被捕获，返回失败结果
        assert result.success is False
        assert result.user_id == 1
        assert "未捕获异常" in result.error_message
        assert len(result.channel_results) == 0
        assert result.record_id is None


class TestExecuteScheduledPushIntegration:
    """集成测试：测试批量推送与实际服务的集成"""
    
    @pytest.fixture
    def mock_services(self):
        """创建模拟服务"""
        wechat_service = Mock(spec=WeChatService)
        email_service = Mock(spec=EmailService)
        report_service = Mock(spec=ReportService)
        config_service = Mock(spec=ConfigService)
        record_repository = Mock(spec=RecordRepository)
        
        return {
            'wechat': wechat_service,
            'email': email_service,
            'report': report_service,
            'config': config_service,
            'record': record_repository
        }
    
    @pytest.fixture
    def push_service(self, mock_services):
        """创建推送服务实例"""
        return PushService(
            wechat_service=mock_services['wechat'],
            email_service=mock_services['email'],
            report_service=mock_services['report'],
            config_service=mock_services['config'],
            record_repository=mock_services['record']
        )
    
    def test_execute_scheduled_push_with_duplicate_check(self, push_service, mock_services):
        """集成测试：验证去重逻辑正确调用"""
        # 创建测试用户
        users = [
            Mock(spec=User, id=1, username="user1"),
            Mock(spec=User, id=2, username="user2")
        ]
        
        # 设置
        mock_services['config'].get_users_for_push_time.return_value = users
        
        # 记录 check_duplicate_push 的调用
        duplicate_checks = []
        
        def check_duplicate_side_effect(user_id, push_date, push_time):
            duplicate_checks.append({
                'user_id': user_id,
                'push_date': push_date,
                'push_time': push_time
            })
            return False  # 都未推送过
        
        mock_services['record'].check_duplicate_push.side_effect = check_duplicate_side_effect
        
        # 模拟推送成功
        with patch.object(push_service, 'push_to_user') as mock_push:
            mock_push.return_value = PushResult(
                user_id=1,
                success=True,
                channel_results=[ChannelResult(channel='wechat', success=True)],
                record_id=100
            )
            
            # 执行
            result = push_service.execute_scheduled_push("09:30")
        
        # 验证：check_duplicate_push 被正确调用
        assert len(duplicate_checks) == 2
        assert duplicate_checks[0]['user_id'] == 1
        assert duplicate_checks[0]['push_time'] == "09:30"
        assert duplicate_checks[0]['push_date'] == date.today()
        assert duplicate_checks[1]['user_id'] == 2
        assert duplicate_checks[1]['push_time'] == "09:30"
        assert duplicate_checks[1]['push_date'] == date.today()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
