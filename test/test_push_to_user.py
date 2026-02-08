"""
测试 PushService.push_to_user 方法
验证单用户推送逻辑的正确性
"""

import pytest
from datetime import datetime, date
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session

from backend_api.services.push_service import PushService, PushResult, ChannelResult
from backend_api.services.config_service import ConfigService
from backend_api.services.report_service import ReportService, ReportResult, ReportInfo
from backend_api.services.record_repository import RecordRepository
from backend_api.services.email_service import EmailService
from backend_core.wechat.wechat_service import WeChatService
from backend_api.models import User, UserPushConfig, PushRecord


@pytest.fixture
def mock_wechat_service():
    """Mock 微信服务"""
    service = Mock(spec=WeChatService)
    service.send_text_message.return_value = True
    service.send_file_message.return_value = True
    return service


@pytest.fixture
def mock_email_service():
    """Mock 邮件服务"""
    service = Mock(spec=EmailService)
    service.validate_email.return_value = True
    
    # Mock EmailSendResult
    mock_result = Mock()
    mock_result.success = True
    mock_result.error = None
    service.send_report_email.return_value = mock_result
    
    return service


@pytest.fixture
def mock_config_service():
    """Mock 配置服务"""
    service = Mock(spec=ConfigService)
    
    # 默认返回一个启用的配置
    mock_config = Mock(spec=UserPushConfig)
    mock_config.enabled = True
    mock_config.channels = ["wechat", "email"]
    mock_config.push_times = ["09:30", "15:30"]
    mock_config.report_type = "summary"
    mock_config.stock_codes = None
    
    service.get_user_config.return_value = mock_config
    
    return service


@pytest.fixture
def mock_report_service():
    """Mock 报告服务"""
    service = Mock(spec=ReportService)
    
    # 默认返回成功的报告结果
    mock_report_info = ReportInfo(
        stock_count=5,
        report_date="2024-01-15",
        report_type="summary",
        file_size=1024,
        has_data=True,
        missing_data_stocks=[]
    )
    
    mock_result = ReportResult(
        success=True,
        file_path="/tmp/report_test.csv",
        report_info=mock_report_info,
        error_message=None
    )
    
    service.generate_user_report.return_value = mock_result
    
    return service


@pytest.fixture
def mock_record_repository():
    """Mock 推送记录仓库"""
    repo = Mock(spec=RecordRepository)
    
    # Mock 创建记录
    mock_record = Mock(spec=PushRecord)
    mock_record.id = 1
    mock_record.user_id = 1
    mock_record.status = "pending"
    
    repo.create_record.return_value = mock_record
    repo.update_record_status.return_value = mock_record
    
    return repo


@pytest.fixture
def mock_user():
    """Mock 用户对象"""
    user = Mock(spec=User)
    user.id = 1
    user.username = "test_user"
    user.email = "test@example.com"
    user.wechat_openid = "test_openid_123"
    user.wechat_type = "personal"
    return user


@pytest.fixture
def push_service(mock_wechat_service, mock_email_service, mock_report_service, 
                 mock_config_service, mock_record_repository):
    """创建 PushService 实例"""
    return PushService(
        wechat_service=mock_wechat_service,
        email_service=mock_email_service,
        report_service=mock_report_service,
        config_service=mock_config_service,
        record_repository=mock_record_repository
    )


class TestPushToUser:
    """测试 push_to_user 方法"""
    
    def test_push_to_user_success_both_channels(
        self, push_service, mock_user, mock_config_service, 
        mock_report_service, mock_record_repository
    ):
        """测试：成功推送到两个渠道（微信和邮件）"""
        
        # Mock 数据库会话
        mock_db = Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        # 执行推送
        result = push_service.push_to_user(user_id=1, push_time="09:30", db_session=mock_db)
        
        # 验证结果
        assert result.success is True
        assert result.user_id == 1
        assert result.record_id == 1
        assert len(result.channel_results) == 2
        
        # 验证两个渠道都成功
        wechat_result = next((r for r in result.channel_results if r.channel == 'wechat'), None)
        email_result = next((r for r in result.channel_results if r.channel == 'email'), None)
        
        assert wechat_result is not None
        assert wechat_result.success is True
        assert email_result is not None
        assert email_result.success is True
        
        # 验证调用了配置服务
        mock_config_service.get_user_config.assert_called_once_with(1)
        
        # 验证调用了报告服务
        mock_report_service.generate_user_report.assert_called_once()
        
        # 验证创建了推送记录
        mock_record_repository.create_record.assert_called_once()
        
        # 验证更新了记录状态（至少2次：processing 和 success）
        assert mock_record_repository.update_record_status.call_count >= 2
    
    def test_push_to_user_no_config(self, push_service, mock_config_service):
        """测试：用户没有推送配置"""
        
        # 配置服务返回 None
        mock_config_service.get_user_config.return_value = None
        
        # 执行推送
        result = push_service.push_to_user(user_id=1, push_time="09:30")
        
        # 验证结果
        assert result.success is False
        assert result.user_id == 1
        assert result.record_id is None
        assert "没有推送配置" in result.error_message
        assert len(result.channel_results) == 0
    
    def test_push_to_user_disabled_config(self, push_service, mock_config_service):
        """测试：用户推送功能已禁用"""
        
        # 配置推送功能为禁用
        mock_config = mock_config_service.get_user_config.return_value
        mock_config.enabled = False
        
        # 执行推送
        result = push_service.push_to_user(user_id=1, push_time="09:30")
        
        # 验证结果
        assert result.success is False
        assert "推送功能已禁用" in result.error_message
    
    def test_push_to_user_no_channels_bound(
        self, push_service, mock_config_service
    ):
        """测试：用户没有绑定任何推送渠道"""
        
        # 创建一个没有绑定渠道的用户
        mock_user_no_channels = Mock(spec=User)
        mock_user_no_channels.id = 1
        mock_user_no_channels.username = "test_user"
        mock_user_no_channels.email = None  # 没有邮箱
        mock_user_no_channels.wechat_openid = None  # 没有微信
        
        # Mock 数据库会话
        mock_db = Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user_no_channels
        
        # 执行推送
        result = push_service.push_to_user(user_id=1, push_time="09:30", db_session=mock_db)
        
        # 验证结果
        assert result.success is False
        assert "没有绑定任何推送渠道" in result.error_message
    
    def test_push_to_user_report_generation_failed(
        self, push_service, mock_user, mock_report_service
    ):
        """测试：报告生成失败"""
        
        # 报告服务返回失败结果
        mock_report_service.generate_user_report.return_value = ReportResult(
            success=False,
            file_path=None,
            report_info=None,
            error_message="数据库连接失败"
        )
        
        # Mock 数据库会话
        mock_db = Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        # 执行推送
        result = push_service.push_to_user(user_id=1, push_time="09:30", db_session=mock_db)
        
        # 验证结果
        assert result.success is False
        assert "报告生成失败" in result.error_message
    
    def test_push_to_user_no_watchlist_data(
        self, push_service, mock_user, mock_report_service
    ):
        """测试：用户没有自选股数据"""
        
        # 报告服务返回没有数据的结果
        mock_report_info = ReportInfo(
            stock_count=0,
            report_date="2024-01-15",
            report_type="summary",
            file_size=0,
            has_data=False,
            missing_data_stocks=[]
        )
        
        mock_report_service.generate_user_report.return_value = ReportResult(
            success=True,
            file_path=None,
            report_info=mock_report_info,
            error_message="用户没有自选股"
        )
        
        # Mock 数据库会话
        mock_db = Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        # 执行推送
        result = push_service.push_to_user(user_id=1, push_time="09:30", db_session=mock_db)
        
        # 验证结果
        assert result.success is True  # 没有数据也算成功
        assert "没有自选股数据" in result.error_message
        assert len(result.channel_results) == 0
    
    def test_push_to_user_wechat_only(
        self, push_service, mock_config_service, mock_record_repository
    ):
        """测试：仅通过微信推送"""
        
        # 配置仅微信渠道
        mock_config = mock_config_service.get_user_config.return_value
        mock_config.channels = ["wechat"]
        
        # 创建只有微信的用户
        mock_user_wechat_only = Mock(spec=User)
        mock_user_wechat_only.id = 1
        mock_user_wechat_only.username = "test_user"
        mock_user_wechat_only.email = None
        mock_user_wechat_only.wechat_openid = "test_openid_123"
        
        # Mock 数据库会话
        mock_db = Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user_wechat_only
        
        # 执行推送
        result = push_service.push_to_user(user_id=1, push_time="09:30", db_session=mock_db)
        
        # 验证结果
        assert result.success is True
        assert len(result.channel_results) == 1
        assert result.channel_results[0].channel == 'wechat'
        assert result.channel_results[0].success is True
    
    def test_push_to_user_email_only(
        self, push_service, mock_config_service, mock_record_repository
    ):
        """测试：仅通过邮件推送"""
        
        # 配置仅邮件渠道
        mock_config = mock_config_service.get_user_config.return_value
        mock_config.channels = ["email"]
        
        # 创建只有邮箱的用户
        mock_user_email_only = Mock(spec=User)
        mock_user_email_only.id = 1
        mock_user_email_only.username = "test_user"
        mock_user_email_only.email = "test@example.com"
        mock_user_email_only.wechat_openid = None
        
        # Mock 数据库会话
        mock_db = Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user_email_only
        
        # 执行推送
        result = push_service.push_to_user(user_id=1, push_time="09:30", db_session=mock_db)
        
        # 验证结果
        assert result.success is True
        assert len(result.channel_results) == 1
        assert result.channel_results[0].channel == 'email'
        assert result.channel_results[0].success is True
    
    def test_push_to_user_partial_success(
        self, push_service, mock_user, mock_wechat_service, 
        mock_record_repository
    ):
        """测试：部分渠道成功（微信失败，邮件成功）"""
        
        # 微信发送失败
        mock_wechat_service.send_text_message.return_value = False
        
        # Mock 数据库会话
        mock_db = Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        # 执行推送
        result = push_service.push_to_user(user_id=1, push_time="09:30", db_session=mock_db)
        
        # 验证结果
        assert result.success is True  # 至少一个渠道成功
        assert len(result.channel_results) == 2
        
        # 验证微信失败
        wechat_result = next((r for r in result.channel_results if r.channel == 'wechat'), None)
        assert wechat_result is not None
        assert wechat_result.success is False
        
        # 验证邮件成功
        email_result = next((r for r in result.channel_results if r.channel == 'email'), None)
        assert email_result is not None
        assert email_result.success is True
        
        # 验证记录状态更新为 partial_success
        # 获取最后一次调用的参数
        last_call = mock_record_repository.update_record_status.call_args_list[-1]
        assert last_call[1]['status'] == 'partial_success'
    
    def test_push_to_user_all_channels_failed(
        self, push_service, mock_user, mock_wechat_service, 
        mock_email_service, mock_record_repository
    ):
        """测试：所有渠道都失败"""
        
        # 微信和邮件都失败
        mock_wechat_service.send_text_message.return_value = False
        
        mock_email_result = Mock()
        mock_email_result.success = False
        mock_email_result.error = "SMTP连接失败"
        mock_email_service.send_report_email.return_value = mock_email_result
        
        # Mock 数据库会话
        mock_db = Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        # 执行推送
        result = push_service.push_to_user(user_id=1, push_time="09:30", db_session=mock_db)
        
        # 验证结果
        assert result.success is False
        assert "所有渠道推送失败" in result.error_message
        assert len(result.channel_results) == 2
        
        # 验证所有渠道都失败
        for channel_result in result.channel_results:
            assert channel_result.success is False
        
        # 验证记录状态更新为 failed
        last_call = mock_record_repository.update_record_status.call_args_list[-1]
        assert last_call[1]['status'] == 'failed'
    
    def test_push_to_user_channel_isolation(
        self, push_service, mock_user, mock_wechat_service
    ):
        """测试：渠道失败隔离（一个渠道异常不影响其他渠道）"""
        
        # 微信发送抛出异常
        mock_wechat_service.send_text_message.side_effect = Exception("微信服务异常")
        
        # Mock 数据库会话
        mock_db = Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        # 执行推送
        result = push_service.push_to_user(user_id=1, push_time="09:30", db_session=mock_db)
        
        # 验证结果
        assert result.success is True  # 邮件渠道仍然成功
        assert len(result.channel_results) == 2
        
        # 验证微信失败但有错误信息
        wechat_result = next((r for r in result.channel_results if r.channel == 'wechat'), None)
        assert wechat_result is not None
        assert wechat_result.success is False
        assert "微信服务异常" in wechat_result.error_message or "推送异常" in wechat_result.error_message
        
        # 验证邮件仍然成功
        email_result = next((r for r in result.channel_results if r.channel == 'email'), None)
        assert email_result is not None
        assert email_result.success is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
