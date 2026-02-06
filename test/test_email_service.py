"""
EmailService 单元测试
测试邮件服务的核心功能
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import smtplib

from backend_api.services.email_service import (
    EmailService, 
    SMTPConfig, 
    EmailSendResult, 
    EmailSendException
)


class TestEmailService:
    """EmailService 测试类"""
    
    @pytest.fixture
    def smtp_config(self):
        """创建测试用的SMTP配置"""
        return SMTPConfig(
            host="smtp.test.com",
            port=587,
            username="test@test.com",
            password="test_password",
            use_tls=True,
            from_email="test@test.com",
            from_name="测试系统"
        )
    
    @pytest.fixture
    def email_service(self, smtp_config):
        """创建EmailService实例"""
        return EmailService(smtp_config)
    
    @pytest.fixture
    def temp_csv_file(self):
        """创建临时CSV文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("股票代码,股票名称,日期,收盘价\n")
            f.write("000001,平安银行,2024-01-01,10.50\n")
            temp_path = f.name
        
        yield temp_path
        
        # 清理临时文件
        Path(temp_path).unlink(missing_ok=True)
    
    def test_validate_email_valid(self, email_service):
        """测试有效邮箱验证"""
        valid_emails = [
            "user@example.com",
            "user.name@example.com",
            "user+tag@example.co.uk",
            "user_name@example-domain.com",
            "123@example.com"
        ]
        
        for email in valid_emails:
            assert email_service.validate_email(email), f"应该接受有效邮箱: {email}"
    
    def test_validate_email_invalid(self, email_service):
        """测试无效邮箱拒绝"""
        invalid_emails = [
            "",
            "invalid",
            "@example.com",
            "user@",
            "user@.com",
            "user @example.com",
            "user@example",
            None,
            123
        ]
        
        for email in invalid_emails:
            assert not email_service.validate_email(email), f"应该拒绝无效邮箱: {email}"
    
    @patch('smtplib.SMTP')
    def test_send_report_email_success(self, mock_smtp, email_service, temp_csv_file):
        """测试成功发送邮件"""
        # 配置mock
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        # 发送邮件
        result = email_service.send_report_email(
            to_email="recipient@example.com",
            subject="测试报告",
            content="<html><body><h1>测试内容</h1></body></html>",
            attachment_path=temp_csv_file
        )
        
        # 验证结果
        assert result.success
        assert "发送成功" in result.message
        
        # 验证SMTP调用
        mock_smtp.assert_called_once()
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("test@test.com", "test_password")
        mock_server.send_message.assert_called_once()
    
    def test_send_report_email_invalid_email(self, email_service, temp_csv_file):
        """测试发送到无效邮箱"""
        with pytest.raises(EmailSendException) as exc_info:
            email_service.send_report_email(
                to_email="invalid_email",
                subject="测试报告",
                content="<html><body>测试</body></html>",
                attachment_path=temp_csv_file
            )
        
        assert "无效的邮箱地址" in str(exc_info.value)
    
    def test_send_report_email_missing_attachment(self, email_service):
        """测试附件文件不存在"""
        with pytest.raises(EmailSendException) as exc_info:
            email_service.send_report_email(
                to_email="recipient@example.com",
                subject="测试报告",
                content="<html><body>测试</body></html>",
                attachment_path="/nonexistent/file.csv"
            )
        
        assert "附件文件不存在" in str(exc_info.value)
    
    @patch('smtplib.SMTP')
    def test_send_report_email_smtp_auth_error(self, mock_smtp, email_service, temp_csv_file):
        """测试SMTP认证失败"""
        # 配置mock抛出认证错误
        mock_server = MagicMock()
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Authentication failed")
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        # 验证抛出异常
        with pytest.raises(EmailSendException) as exc_info:
            email_service.send_report_email(
                to_email="recipient@example.com",
                subject="测试报告",
                content="<html><body>测试</body></html>",
                attachment_path=temp_csv_file
            )
        
        assert "SMTP认证失败" in str(exc_info.value)
    
    @patch('smtplib.SMTP')
    def test_send_report_email_smtp_connect_error(self, mock_smtp, email_service, temp_csv_file):
        """测试SMTP连接失败"""
        # 配置mock抛出连接错误
        mock_smtp.side_effect = smtplib.SMTPConnectError(421, b"Service not available")
        
        # 验证抛出异常
        with pytest.raises(EmailSendException) as exc_info:
            email_service.send_report_email(
                to_email="recipient@example.com",
                subject="测试报告",
                content="<html><body>测试</body></html>",
                attachment_path=temp_csv_file
            )
        
        assert "SMTP连接失败" in str(exc_info.value)
    
    @patch('smtplib.SMTP_SSL')
    def test_send_report_email_ssl_connection(self, mock_smtp_ssl, temp_csv_file):
        """测试SSL连接（端口465）"""
        # 创建使用SSL的配置
        ssl_config = SMTPConfig(
            host="smtp.test.com",
            port=465,
            username="test@test.com",
            password="test_password",
            use_tls=False,  # 端口465使用SSL而不是TLS
            from_email="test@test.com",
            from_name="测试系统"
        )
        email_service = EmailService(ssl_config)
        
        # 配置mock
        mock_server = MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server
        
        # 发送邮件
        result = email_service.send_report_email(
            to_email="recipient@example.com",
            subject="测试报告",
            content="<html><body>测试</body></html>",
            attachment_path=temp_csv_file
        )
        
        # 验证结果
        assert result.success
        
        # 验证使用了SMTP_SSL
        mock_smtp_ssl.assert_called_once()
        mock_server.login.assert_called_once()
        mock_server.send_message.assert_called_once()
    
    def test_smtp_config_creation(self):
        """测试SMTPConfig创建"""
        config = SMTPConfig(
            host="smtp.gmail.com",
            port=587,
            username="user@gmail.com",
            password="password",
            use_tls=True,
            from_email="user@gmail.com",
            from_name="测试用户"
        )
        
        assert config.host == "smtp.gmail.com"
        assert config.port == 587
        assert config.use_tls is True
        assert config.from_name == "测试用户"
    
    def test_email_send_result_creation(self):
        """测试EmailSendResult创建"""
        # 成功结果
        success_result = EmailSendResult(success=True, message="发送成功")
        assert success_result.success
        assert success_result.message == "发送成功"
        assert success_result.error is None
        
        # 失败结果
        fail_result = EmailSendResult(success=False, error="发送失败")
        assert not fail_result.success
        assert fail_result.error == "发送失败"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
