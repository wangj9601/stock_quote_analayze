"""
测试重试机制 (retry_failed_push)
验证推送失败后的重试逻辑
"""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import Mock, MagicMock, patch
from backend_api.services.push_service import PushService, PushResult, ChannelResult
from backend_api.services.email_service import EmailService
from backend_api.services.config_service import ConfigService
from backend_api.services.report_service import ReportService, ReportInfo
from backend_api.services.record_repository import RecordRepository
from backend_core.wechat.wechat_service import WeChatService
from backend_api.models import User, UserPushConfig, PushRecord


@pytest.fixture
def mock_wechat_service():
    """Mock微信服务"""
    service = Mock(spec=WeChatService)
    service.send_text_message.return_value = True
    service.send_file_message.return_value = True
    service.config = Mock()
    service.config.is_configured.return_value = True
    return service


@pytest.fixture
def mock_email_service():
    """Mock邮件服务"""
    service = Mock(spec=EmailService)
    service.validate_email.return_value = True
    
    # Mock EmailSendResult
    mock_result = Mock()
    mock_result.success = True
    mock_result.error = None
    service.send_report_email.return_value = mock_result
    
    return service


@pytest.fixture
def mock_report_service():
    """Mock报告服务"""
    service = Mock(spec=ReportService)
    
    # Mock报告信息
    mock_info = ReportInfo(
        report_date="2024-01-15",
        stock_count=5,
        report_type="summary",
        file_size=1024,
        has_data=True,
        missing_data_stocks=[]
    )
    service.get_report_info.return_value = mock_info
    
    return service


@pytest.fixture
def mock_config_service():
    """Mock配置服务"""
    service = Mock(spec=ConfigService)
    
    # Mock用户配置
    mock_config = Mock(spec=UserPushConfig)
    mock_config.enabled = True
    mock_config.channels = ["wechat", "email"]
    mock_config.report_type = "summary"
    mock_config.stock_codes = None
    mock_config.wechat_notify_userids = None
    mock_config.wechat_app_profile = None

    service.get_user_config.return_value = mock_config
    service.get_config_by_user_and_report_type.return_value = mock_config

    return service


@pytest.fixture
def mock_record_repository():
    """Mock推送记录仓库"""
    repository = Mock(spec=RecordRepository)
    return repository


@pytest.fixture
def push_service(
    mock_wechat_service,
    mock_email_service,
    mock_report_service,
    mock_config_service,
    mock_record_repository
):
    """创建推送服务实例"""
    return PushService(
        wechat_service=mock_wechat_service,
        email_service=mock_email_service,
        report_service=mock_report_service,
        config_service=mock_config_service,
        record_repository=mock_record_repository
    )


def test_retry_failed_push_record_not_found(push_service, mock_record_repository):
    """测试：推送记录不存在"""
    # 设置mock
    mock_record_repository.get_record_by_id.return_value = None
    
    # 执行重试
    result = push_service.retry_failed_push(record_id=999)
    
    # 验证结果
    assert result.success is False
    assert "推送记录不存在" in result.error_message
    assert result.record_id == 999


def test_retry_failed_push_max_retries_reached(push_service, mock_record_repository):
    """测试：已达到最大重试次数"""
    # 创建已达到最大重试次数的记录
    mock_record = Mock(spec=PushRecord)
    mock_record.id = 1
    mock_record.user_id = 100
    mock_record.retry_count = 3
    mock_record.max_retries = 3
    mock_record.channel_status = {"wechat": "failed"}
    
    mock_record_repository.get_record_by_id.return_value = mock_record
    
    # 执行重试
    result = push_service.retry_failed_push(record_id=1)
    
    # 验证结果
    assert result.success is False
    assert "已达到最大重试次数" in result.error_message
    assert result.user_id == 100
    
    # 验证记录被标记为最终失败
    mock_record_repository.update_record_status.assert_called_once()
    call_args = mock_record_repository.update_record_status.call_args
    assert call_args[1]["status"] == "failed_final"


def test_retry_failed_push_delay_not_met(push_service, mock_record_repository):
    """测试：重试时间未到（指数退避策略）"""
    # 创建刚失败的记录（1秒前）
    mock_record = Mock(spec=PushRecord)
    mock_record.id = 1
    mock_record.user_id = 100
    mock_record.retry_count = 0
    mock_record.max_retries = 3
    mock_record.channel_status = {"wechat": "failed"}
    mock_record.completed_at = datetime.now() - timedelta(seconds=1)  # 1秒前完成
    
    mock_record_repository.get_record_by_id.return_value = mock_record
    
    # 执行重试
    result = push_service.retry_failed_push(record_id=1)
    
    # 验证结果
    assert result.success is False
    assert "重试时间未到" in result.error_message
    assert "还需等待" in result.error_message


@patch('backend_core.database.db.get_db')
def test_retry_failed_push_user_not_found(
    mock_get_db,
    push_service,
    mock_record_repository
):
    """测试：用户不存在"""
    # 创建可以重试的记录
    mock_record = Mock(spec=PushRecord)
    mock_record.id = 1
    mock_record.user_id = 100
    mock_record.retry_count = 0
    mock_record.max_retries = 3
    mock_record.channel_status = {"wechat": "failed"}
    mock_record.completed_at = datetime.now() - timedelta(minutes=2)  # 2分钟前完成
    mock_record.report_file_path = "/path/to/report.csv"
    mock_record.error_messages = {}
    
    mock_record_repository.get_record_by_id.return_value = mock_record
    
    # Mock数据库会话
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None  # 用户不存在
    mock_get_db.return_value = iter([mock_db])
    
    # 执行重试
    result = push_service.retry_failed_push(record_id=1)
    
    # 验证结果
    assert result.success is False
    assert "用户不存在" in result.error_message
    
    # 验证记录状态被更新为失败
    assert mock_record_repository.update_record_status.called


@patch('backend_core.database.db.get_db')
def test_retry_failed_push_user_disabled(
    mock_get_db,
    push_service,
    mock_record_repository,
    mock_config_service
):
    """测试：用户推送功能已禁用"""
    # 创建可以重试的记录
    mock_record = Mock(spec=PushRecord)
    mock_record.id = 1
    mock_record.user_id = 100
    mock_record.retry_count = 0
    mock_record.max_retries = 3
    mock_record.channel_status = {"wechat": "failed"}
    mock_record.completed_at = datetime.now() - timedelta(minutes=2)
    mock_record.report_file_path = "/path/to/report.csv"
    mock_record.error_messages = {}
    
    mock_record_repository.get_record_by_id.return_value = mock_record
    
    # Mock用户
    mock_user = Mock(spec=User)
    mock_user.id = 100
    mock_user.username = "test_user"
    mock_user.wechat_openid = "test_openid"
    mock_user.email = "test@example.com"
    
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_user
    mock_get_db.return_value = iter([mock_db])
    
    # Mock配置为禁用
    mock_config = Mock(spec=UserPushConfig)
    mock_config.enabled = False
    mock_config_service.get_user_config.return_value = mock_config
    mock_config_service.get_config_by_user_and_report_type.return_value = mock_config
    
    # 执行重试
    result = push_service.retry_failed_push(record_id=1)
    
    # 验证结果
    assert result.success is False
    assert "推送功能已禁用" in result.error_message


@patch('backend_core.database.db.get_db')
def test_retry_failed_push_no_channels_to_retry(
    mock_get_db,
    push_service,
    mock_record_repository,
    mock_config_service
):
    """测试：没有需要重试的渠道（用户已解绑）"""
    # 创建可以重试的记录
    mock_record = Mock(spec=PushRecord)
    mock_record.id = 1
    mock_record.user_id = 100
    mock_record.retry_count = 0
    mock_record.max_retries = 3
    mock_record.channel_status = {"wechat": "failed", "email": "success"}
    mock_record.completed_at = datetime.now() - timedelta(minutes=2)
    mock_record.report_file_path = "/path/to/report.csv"
    mock_record.error_messages = {}
    mock_record.report_type = "summary"
    
    mock_record_repository.get_record_by_id.return_value = mock_record
    
    # Mock用户（已解绑微信）
    mock_user = Mock(spec=User)
    mock_user.id = 100
    mock_user.username = "test_user"
    mock_user.wechat_openid = None  # 已解绑
    mock_user.wechat_userid = None
    mock_user.email = "test@example.com"
    
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_user
    mock_get_db.return_value = iter([mock_db])
    
    # 执行重试
    result = push_service.retry_failed_push(record_id=1)
    
    # 验证结果 - 没有需要重试的渠道，但email已经成功，所以标记为partial_success
    # 注意：由于没有实际重试任何渠道，success应该基于已有的成功渠道
    assert result.user_id == 100
    assert result.error_message and "没有需要重试的渠道" in result.error_message
    
    # 验证记录状态被更新为partial_success（因为email成功了）
    assert mock_record_repository.update_record_status.called
    last_call = mock_record_repository.update_record_status.call_args
    assert last_call[1]["status"] == "partial_success"


@patch('backend_core.database.db.get_db')
def test_retry_failed_push_success_wechat(
    mock_get_db,
    push_service,
    mock_record_repository,
    mock_config_service,
    mock_wechat_service,
    mock_report_service
):
    """测试：微信渠道重试成功"""
    # 创建可以重试的记录
    mock_record = Mock(spec=PushRecord)
    mock_record.id = 1
    mock_record.user_id = 100
    mock_record.retry_count = 0
    mock_record.max_retries = 3
    mock_record.channel_status = {"wechat": "failed"}
    mock_record.completed_at = datetime.now() - timedelta(minutes=2)
    mock_record.report_file_path = "/path/to/report.csv"
    mock_record.error_messages = {"wechat": "Network error"}
    
    mock_record_repository.get_record_by_id.return_value = mock_record
    
    # Mock用户
    mock_user = Mock(spec=User)
    mock_user.id = 100
    mock_user.username = "test_user"
    mock_user.wechat_openid = "test_openid"
    mock_user.email = None
    
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_user
    mock_get_db.return_value = iter([mock_db])
    
    # 执行重试
    result = push_service.retry_failed_push(record_id=1)
    
    # 验证结果
    assert result.success is True
    assert result.user_id == 100
    assert result.record_id == 1
    assert len(result.channel_results) == 1
    assert result.channel_results[0].channel == "wechat"
    assert result.channel_results[0].success is True
    
    # 验证微信服务被调用
    assert mock_wechat_service.send_text_message.called
    assert mock_wechat_service.send_file_message.called
    
    # 验证记录状态被更新
    assert mock_record_repository.update_record_status.called
    # 检查最后一次调用（完成时的更新）
    last_call = mock_record_repository.update_record_status.call_args_list[-1]
    assert last_call[1]["status"] == "success"
    assert last_call[1]["channel_status"]["wechat"] == "success"


@patch('backend_core.database.db.get_db')
def test_retry_failed_push_partial_success(
    mock_get_db,
    push_service,
    mock_record_repository,
    mock_config_service,
    mock_wechat_service,
    mock_email_service,
    mock_report_service
):
    """测试：部分渠道重试成功"""
    # 创建可以重试的记录
    mock_record = Mock(spec=PushRecord)
    mock_record.id = 1
    mock_record.user_id = 100
    mock_record.retry_count = 0
    mock_record.max_retries = 3
    mock_record.channel_status = {"wechat": "failed", "email": "failed"}
    mock_record.completed_at = datetime.now() - timedelta(minutes=2)
    mock_record.report_file_path = "/path/to/report.csv"
    mock_record.error_messages = {}
    
    mock_record_repository.get_record_by_id.return_value = mock_record
    
    # Mock用户
    mock_user = Mock(spec=User)
    mock_user.id = 100
    mock_user.username = "test_user"
    mock_user.wechat_openid = "test_openid"
    mock_user.email = "test@example.com"
    
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_user
    mock_get_db.return_value = iter([mock_db])
    
    # 设置微信成功，邮件失败
    mock_wechat_service.send_text_message.return_value = True
    mock_wechat_service.send_file_message.return_value = True
    
    mock_email_result = Mock()
    mock_email_result.success = False
    mock_email_result.error = "SMTP connection failed"
    mock_email_service.send_report_email.return_value = mock_email_result
    
    # 执行重试
    result = push_service.retry_failed_push(record_id=1)
    
    # 验证结果
    assert result.success is True  # 有成功的渠道
    assert len(result.channel_results) == 2
    
    # 验证记录状态被更新为partial_success
    last_call = mock_record_repository.update_record_status.call_args_list[-1]
    assert last_call[1]["status"] == "partial_success"
    assert last_call[1]["channel_status"]["wechat"] == "success"
    assert last_call[1]["channel_status"]["email"] == "failed"


@patch('backend_core.database.db.get_db')
def test_retry_failed_push_all_failed_final(
    mock_get_db,
    push_service,
    mock_record_repository,
    mock_config_service,
    mock_wechat_service,
    mock_report_service
):
    """测试：所有渠道重试失败且达到最大重试次数"""
    # 创建已重试2次的记录
    mock_record = Mock(spec=PushRecord)
    mock_record.id = 1
    mock_record.user_id = 100
    mock_record.retry_count = 2  # 已重试2次
    mock_record.max_retries = 3
    mock_record.channel_status = {"wechat": "failed"}
    mock_record.completed_at = datetime.now() - timedelta(minutes=20)
    mock_record.report_file_path = "/path/to/report.csv"
    mock_record.error_messages = {}
    
    mock_record_repository.get_record_by_id.return_value = mock_record
    
    # Mock用户
    mock_user = Mock(spec=User)
    mock_user.id = 100
    mock_user.username = "test_user"
    mock_user.wechat_openid = "test_openid"
    mock_user.email = None
    
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_user
    mock_get_db.return_value = iter([mock_db])
    
    # 设置微信失败
    mock_wechat_service.send_text_message.return_value = False
    
    # 执行重试（第3次，也是最后一次）
    result = push_service.retry_failed_push(record_id=1)
    
    # 验证结果
    assert result.success is False
    assert len(result.channel_results) == 1
    assert result.channel_results[0].success is False
    
    # 验证记录状态被更新为failed_final
    last_call = mock_record_repository.update_record_status.call_args_list[-1]
    assert last_call[1]["status"] == "failed_final"


@patch('backend_core.database.db.get_db')
def test_retry_failed_push_exponential_backoff(
    mock_get_db,
    push_service,
    mock_record_repository
):
    """测试：指数退避策略的时间间隔"""
    # 测试第1次重试（应等待60秒）
    mock_record = Mock(spec=PushRecord)
    mock_record.id = 1
    mock_record.user_id = 100
    mock_record.retry_count = 0
    mock_record.max_retries = 3
    mock_record.channel_status = {"wechat": "failed"}
    mock_record.completed_at = datetime.now() - timedelta(seconds=30)  # 只过了30秒
    
    mock_record_repository.get_record_by_id.return_value = mock_record
    
    result = push_service.retry_failed_push(record_id=1)
    assert result.success is False
    assert "重试时间未到" in result.error_message
    
    # 测试第2次重试（应等待300秒）
    mock_record.retry_count = 1
    mock_record.completed_at = datetime.now() - timedelta(seconds=200)  # 只过了200秒
    
    result = push_service.retry_failed_push(record_id=1)
    assert result.success is False
    assert "重试时间未到" in result.error_message
    
    # 测试第3次重试（应等待900秒）
    mock_record.retry_count = 2
    mock_record.completed_at = datetime.now() - timedelta(seconds=600)  # 只过了600秒
    
    result = push_service.retry_failed_push(record_id=1)
    assert result.success is False
    assert "重试时间未到" in result.error_message


def test_retry_failed_push_no_report_file(
    push_service,
    mock_record_repository,
    mock_config_service
):
    """测试：推送记录中没有报告文件路径"""
    # 创建没有报告文件的记录
    mock_record = Mock(spec=PushRecord)
    mock_record.id = 1
    mock_record.user_id = 100
    mock_record.retry_count = 0
    mock_record.max_retries = 3
    mock_record.channel_status = {"wechat": "failed"}
    mock_record.completed_at = datetime.now() - timedelta(minutes=2)
    mock_record.report_file_path = None  # 没有报告文件
    mock_record.error_messages = {}
    
    mock_record_repository.get_record_by_id.return_value = mock_record
    
    # Mock用户
    with patch('backend_core.database.db.get_db') as mock_get_db:
        mock_user = Mock(spec=User)
        mock_user.id = 100
        mock_user.wechat_openid = "test_openid"
        
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        mock_get_db.return_value = iter([mock_db])
        
        # 执行重试
        result = push_service.retry_failed_push(record_id=1)
        
        # 验证结果
        assert result.success is False
        assert "没有报告文件路径" in result.error_message


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
