"""
PushService 基础结构测试
测试 PushService 类的初始化和基础方法
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, date
import os
import tempfile

from backend_api.services.push_service import (
    PushService, 
    ChannelResult, 
    PushResult,
    PushBatchResult
)
from backend_api.services.email_service import EmailService, SMTPConfig, EmailSendResult
from backend_api.services.config_service import ConfigService
from backend_api.services.report_service import ReportService, ReportInfo
from backend_api.services.record_repository import RecordRepository
from backend_core.wechat.wechat_service import WeChatService
from backend_api.models import User


class TestPushServiceBasic:
    """测试 PushService 基础结构"""
    
    @pytest.fixture
    def mock_wechat_service(self):
        """Mock 微信服务"""
        service = Mock(spec=WeChatService)
        service.send_text_message.return_value = True
        service.send_file_message.return_value = True
        service.config = Mock()
        service.config.is_configured.return_value = True
        return service
    
    @pytest.fixture
    def mock_email_service(self):
        """Mock 邮件服务"""
        service = Mock(spec=EmailService)
        service.validate_email.return_value = True
        service.send_report_email.return_value = EmailSendResult(success=True)
        return service
    
    @pytest.fixture
    def mock_report_service(self):
        """Mock 报告服务"""
        service = Mock(spec=ReportService)
        return service
    
    @pytest.fixture
    def mock_config_service(self):
        """Mock 配置服务"""
        service = Mock(spec=ConfigService)
        return service
    
    @pytest.fixture
    def mock_record_repository(self):
        """Mock 推送记录仓库"""
        repository = Mock(spec=RecordRepository)
        return repository
    
    @pytest.fixture
    def push_service(
        self, 
        mock_wechat_service, 
        mock_email_service, 
        mock_report_service,
        mock_config_service,
        mock_record_repository
    ):
        """创建 PushService 实例"""
        return PushService(
            wechat_service=mock_wechat_service,
            email_service=mock_email_service,
            report_service=mock_report_service,
            config_service=mock_config_service,
            record_repository=mock_record_repository
        )
    
    @pytest.fixture
    def sample_user(self):
        """创建示例用户"""
        user = Mock(spec=User)
        user.id = 1
        user.username = "test_user"
        user.email = "test@example.com"
        user.wechat_openid = "test_openid"
        user.wechat_userid = None
        user.wechat_type = "personal"
        return user
    
    @pytest.fixture
    def sample_report_info(self):
        """创建示例报告信息"""
        return ReportInfo(
            stock_count=5,
            report_date="2024-01-15",
            report_type="summary",
            file_size=1024,
            has_data=True,
            missing_data_stocks=[]
        )
    
    @pytest.fixture
    def temp_report_file(self):
        """创建临时报告文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("股票代码,股票名称,当前价格\n")
            f.write("000001,平安银行,10.50\n")
            temp_path = f.name
        
        yield temp_path
        
        # 清理临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)
    
    def test_push_service_initialization(self, push_service):
        """测试 PushService 初始化"""
        assert push_service is not None
        assert push_service.wechat_service is not None
        assert push_service.email_service is not None
        assert push_service.report_service is not None
        assert push_service.config_service is not None
        assert push_service.record_repository is not None
    
    def test_send_via_wechat_success(
        self, 
        push_service, 
        sample_user, 
        sample_report_info,
        temp_report_file
    ):
        """测试通过微信发送报告 - 成功场景"""
        result = push_service._send_via_wechat(
            user=sample_user,
            report_path=temp_report_file,
            report_info=sample_report_info
        )
        
        assert result.channel == 'wechat'
        assert result.success is True
        assert result.error_message is None
        
        # 验证调用了微信服务
        push_service.wechat_service.send_text_message.assert_called_once()
        push_service.wechat_service.send_file_message.assert_called_once()
    
    def test_send_via_wechat_no_openid(
        self, 
        push_service, 
        sample_user, 
        sample_report_info,
        temp_report_file
    ):
        """测试通过微信发送报告 - 用户未绑定微信"""
        sample_user.wechat_openid = None
        sample_user.wechat_userid = None
        
        result = push_service._send_via_wechat(
            user=sample_user,
            report_path=temp_report_file,
            report_info=sample_report_info
        )
        
        assert result.channel == 'wechat'
        assert result.success is False
        assert "未绑定微信" in result.error_message
        
        # 验证没有调用微信服务
        push_service.wechat_service.send_text_message.assert_not_called()
        push_service.wechat_service.send_file_message.assert_not_called()
    
    def test_send_via_wechat_text_message_failed(
        self, 
        push_service, 
        sample_user, 
        sample_report_info,
        temp_report_file
    ):
        """测试通过微信发送报告 - 文本消息发送失败"""
        push_service.wechat_service.send_text_message.return_value = False
        
        result = push_service._send_via_wechat(
            user=sample_user,
            report_path=temp_report_file,
            report_info=sample_report_info
        )
        
        assert result.channel == 'wechat'
        assert result.success is False
        assert "文本消息发送失败" in result.error_message
        
        # 验证只调用了文本消息，没有调用文件消息
        push_service.wechat_service.send_text_message.assert_called_once()
        push_service.wechat_service.send_file_message.assert_not_called()
    
    def test_send_via_wechat_file_message_failed(
        self, 
        push_service, 
        sample_user, 
        sample_report_info,
        temp_report_file
    ):
        """测试通过微信发送报告 - 文件消息发送失败"""
        push_service.wechat_service.send_text_message.return_value = True
        push_service.wechat_service.send_file_message.return_value = False
        
        result = push_service._send_via_wechat(
            user=sample_user,
            report_path=temp_report_file,
            report_info=sample_report_info
        )
        
        assert result.channel == 'wechat'
        assert result.success is False
        assert "文件消息发送失败" in result.error_message
        
        # 验证两个方法都被调用了
        push_service.wechat_service.send_text_message.assert_called_once()
        push_service.wechat_service.send_file_message.assert_called_once()
    
    def test_send_via_email_success(
        self, 
        push_service, 
        sample_user, 
        sample_report_info,
        temp_report_file
    ):
        """测试通过邮件发送报告 - 成功场景"""
        result = push_service._send_via_email(
            user=sample_user,
            report_path=temp_report_file,
            report_info=sample_report_info
        )
        
        assert result.channel == 'email'
        assert result.success is True
        assert result.error_message is None
        
        # 验证调用了邮件服务
        push_service.email_service.validate_email.assert_called_once_with(sample_user.email)
        push_service.email_service.send_report_email.assert_called_once()
    
    def test_send_via_email_no_email(
        self, 
        push_service, 
        sample_user, 
        sample_report_info,
        temp_report_file
    ):
        """测试通过邮件发送报告 - 用户未绑定邮箱"""
        sample_user.email = None
        
        result = push_service._send_via_email(
            user=sample_user,
            report_path=temp_report_file,
            report_info=sample_report_info
        )
        
        assert result.channel == 'email'
        assert result.success is False
        assert "未绑定邮箱" in result.error_message
        
        # 验证没有调用邮件服务
        push_service.email_service.send_report_email.assert_not_called()
    
    def test_send_via_email_invalid_email(
        self, 
        push_service, 
        sample_user, 
        sample_report_info,
        temp_report_file
    ):
        """测试通过邮件发送报告 - 邮箱格式无效"""
        push_service.email_service.validate_email.return_value = False
        
        result = push_service._send_via_email(
            user=sample_user,
            report_path=temp_report_file,
            report_info=sample_report_info
        )
        
        assert result.channel == 'email'
        assert result.success is False
        assert "邮箱格式无效" in result.error_message
        
        # 验证调用了验证但没有发送
        push_service.email_service.validate_email.assert_called_once()
        push_service.email_service.send_report_email.assert_not_called()
    
    def test_send_via_email_send_failed(
        self, 
        push_service, 
        sample_user, 
        sample_report_info,
        temp_report_file
    ):
        """测试通过邮件发送报告 - 发送失败"""
        push_service.email_service.send_report_email.return_value = EmailSendResult(
            success=False,
            error="SMTP connection failed"
        )
        
        result = push_service._send_via_email(
            user=sample_user,
            report_path=temp_report_file,
            report_info=sample_report_info
        )
        
        assert result.channel == 'email'
        assert result.success is False
        assert "SMTP connection failed" in (result.error_message or "")
    
    def test_format_push_message(self, push_service, sample_user, sample_report_info):
        """测试格式化推送消息"""
        message = push_service._format_push_message(sample_user, sample_report_info)
        
        assert "股票报告推送" in message
        assert sample_user.username in message
        assert sample_report_info.report_date in message
        assert str(sample_report_info.stock_count) in message
        assert "汇总报告" in message
    
    def test_format_push_message_with_missing_data(
        self, 
        push_service, 
        sample_user, 
        sample_report_info
    ):
        """测试格式化推送消息 - 包含数据缺失"""
        sample_report_info.missing_data_stocks = ["000001", "600000"]
        
        message = push_service._format_push_message(sample_user, sample_report_info)
        
        assert "数据缺失股票" in message
        assert "2" in message
    
    def test_format_email_content(self, push_service, sample_user, sample_report_info):
        """测试格式化邮件内容"""
        content = push_service._format_email_content(sample_user, sample_report_info)
        
        assert "<!DOCTYPE html>" in content
        assert sample_user.username in content
        assert sample_report_info.report_date in content
        assert str(sample_report_info.stock_count) in content
        assert "汇总报告" in content
    
    def test_format_email_content_with_missing_data(
        self, 
        push_service, 
        sample_user, 
        sample_report_info
    ):
        """测试格式化邮件内容 - 包含数据缺失"""
        sample_report_info.missing_data_stocks = ["000001", "600000"]
        
        content = push_service._format_email_content(sample_user, sample_report_info)
        
        assert "数据缺失提示" in content
        assert "2" in content

    def test_format_push_message_volume_aberration(self, push_service, sample_user):
        """测试 report_type 为 volume_aberration 时推送消息展示名为「成交量异动榜」"""
        report_info = ReportInfo(
            stock_count=100,
            report_date="2026-01-01",
            report_type="volume_aberration",
            file_size=2048,
            has_data=True,
            missing_data_stocks=[],
        )
        message = push_service._format_push_message(sample_user, report_info)
        assert "成交量异动榜" in message
        assert "股票报告推送" in message

    def test_format_email_content_volume_aberration(self, push_service, sample_user):
        """测试 report_type 为 volume_aberration 时邮件正文展示名为「成交量异动榜」"""
        report_info = ReportInfo(
            stock_count=100,
            report_date="2026-01-01",
            report_type="volume_aberration",
            file_size=2048,
            has_data=True,
            missing_data_stocks=[],
        )
        content = push_service._format_email_content(sample_user, report_info)
        assert "成交量异动榜" in content
        assert "<!DOCTYPE html>" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
