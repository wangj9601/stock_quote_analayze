"""
PushService 日志记录集成测试
验证结构化日志在推送服务中的集成使用
"""

import pytest
import logging
from unittest.mock import Mock, MagicMock, patch
from datetime import date

from backend_api.services.push_service import PushService
from backend_api.services.email_service import EmailService
from backend_api.services.config_service import ConfigService
from backend_api.services.report_service import ReportService, ReportResult, ReportInfo
from backend_api.services.record_repository import RecordRepository
from backend_core.wechat.wechat_service import WeChatService
from backend_api.models import User, UserPushConfig, PushRecord


def _push_task(user: Mock) -> tuple:
    cfg = Mock(spec=UserPushConfig)
    cfg.id = user.id
    cfg.enabled = True
    cfg.channels = ["wechat", "email"]
    cfg.report_type = "summary"
    cfg.stock_codes = None
    cfg.wechat_notify_userids = None
    cfg.wechat_app_profile = None
    return (cfg, user)


class TestPushServiceLogging:
    """测试 PushService 中的日志记录"""
    
    @pytest.fixture
    def mock_services(self):
        """创建模拟服务"""
        wechat_service = Mock(spec=WeChatService)
        wechat_service.config = Mock()
        wechat_service.config.is_configured.return_value = True
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
        """创建 PushService 实例"""
        return PushService(
            wechat_service=mock_services['wechat'],
            email_service=mock_services['email'],
            report_service=mock_services['report'],
            config_service=mock_services['config'],
            record_repository=mock_services['record']
        )
    
    def test_execute_scheduled_push_logs_batch_events(self, push_service, mock_services, caplog):
        """测试批量推送记录批量事件日志"""
        # 设置模拟数据
        mock_services['config'].get_configs_for_push_time.return_value = []
        
        with caplog.at_level(logging.INFO):
            result = push_service.execute_scheduled_push("09:30")
        
        # 验证批量推送开始日志
        log_messages = [record.message for record in caplog.records]
        assert any("批量推送开始" in msg for msg in log_messages)
        
        # 当没有任务时，不会记录批量推送完成事件，但会记录「没有需要推送的任务」
        assert any(
            "没有需要推送的任务" in msg or "没有需要推送的用户" in msg
            for msg in log_messages
        )
    
    def test_execute_scheduled_push_logs_duplicate_skip(self, push_service, mock_services, caplog):
        """测试批量推送记录重复跳过日志"""
        # 创建模拟用户
        user = Mock(spec=User)
        user.id = 123
        user.wechat_openid = "test_openid"
        user.email = "test@example.com"
        
        mock_services['config'].get_configs_for_push_time.return_value = [_push_task(user)]
        mock_services['record'].check_duplicate_push.return_value = True  # 模拟重复推送
        
        with caplog.at_level(logging.INFO):
            result = push_service.execute_scheduled_push("09:30")
        
        # 验证重复推送跳过日志
        log_messages = [record.message for record in caplog.records]
        assert any("重复推送跳过" in msg or "今日已推送" in msg for msg in log_messages)
    
    def test_push_to_user_logs_push_started(self, push_service, mock_services, caplog):
        """测试单用户推送记录开始事件"""
        # 设置模拟配置
        config = Mock(spec=UserPushConfig)
        config.enabled = False  # 禁用推送，快速返回
        
        mock_services['config'].get_user_config.return_value = config
        
        with caplog.at_level(logging.INFO):
            result = push_service.push_to_user(123, "09:30")
        
        # 验证推送开始日志
        log_messages = [record.message for record in caplog.records]
        assert any("推送开始" in msg for msg in log_messages)
    
    def test_push_to_user_logs_user_not_configured(self, push_service, mock_services, caplog):
        """测试推送记录用户未配置警告"""
        # 模拟没有配置
        mock_services['config'].get_user_config.return_value = None
        
        with caplog.at_level(logging.WARNING):
            result = push_service.push_to_user(123, "09:30")
        
        # 验证用户未配置日志
        log_messages = [record.message for record in caplog.records]
        assert any("用户未配置" in msg or "没有推送配置" in msg for msg in log_messages)
    
    def test_push_to_user_logs_report_generated(self, push_service, mock_services, caplog):
        """测试推送记录报告生成成功日志"""
        # 设置完整的模拟数据
        config = Mock(spec=UserPushConfig)
        config.enabled = True
        config.channels = ['wechat']
        config.report_type = 'summary'
        config.stock_codes = None
        
        user = Mock(spec=User)
        user.id = 123
        user.wechat_openid = "test_openid"
        user.email = None
        
        report_info = ReportInfo(
            report_type='summary',
            report_date='2024-01-01',
            stock_count=5,
            file_size=1024,
            has_data=True,
            missing_data_stocks=[]
        )
        
        report_result = ReportResult(
            success=True,
            file_path='/tmp/report.csv',
            report_info=report_info,
            error_message=None
        )
        
        record = Mock(spec=PushRecord)
        record.id = 456
        
        mock_services['config'].get_user_config.return_value = config
        mock_services['report'].generate_user_report.return_value = report_result
        mock_services['record'].create_record.return_value = record
        mock_services['wechat'].send_text_message.return_value = True
        mock_services['wechat'].send_file_message.return_value = True
        
        # 使用正确的导入路径
        with patch('backend_core.database.db.get_db') as mock_get_db:
            mock_session = MagicMock()
            mock_session.query.return_value.filter.return_value.first.return_value = user
            mock_get_db.return_value = iter([mock_session])
            
            with caplog.at_level(logging.INFO):
                result = push_service.push_to_user(123, "09:30", db_session=mock_session)
        
        # 验证报告生成成功日志
        log_messages = [record.message for record in caplog.records]
        assert any("报告生成成功" in msg for msg in log_messages)
    
    def test_push_to_user_logs_data_missing(self, push_service, mock_services, caplog):
        """测试推送记录数据缺失警告"""
        # 设置模拟数据
        config = Mock(spec=UserPushConfig)
        config.enabled = True
        config.channels = ['wechat']
        config.report_type = 'summary'
        config.stock_codes = None
        
        user = Mock(spec=User)
        user.id = 123
        user.wechat_openid = "test_openid"
        
        # 模拟没有数据的报告
        report_info = ReportInfo(
            report_type='summary',
            report_date='2024-01-01',
            stock_count=0,
            file_size=0,
            has_data=False,  # 没有数据
            missing_data_stocks=[]
        )
        
        report_result = ReportResult(
            success=True,
            file_path='/tmp/report.csv',
            report_info=report_info,
            error_message=None
        )
        
        mock_services['config'].get_user_config.return_value = config
        mock_services['report'].generate_user_report.return_value = report_result
        
        # 使用正确的导入路径
        with patch('backend_core.database.db.get_db') as mock_get_db:
            mock_session = MagicMock()
            mock_session.query.return_value.filter.return_value.first.return_value = user
            mock_get_db.return_value = iter([mock_session])
            
            with caplog.at_level(logging.WARNING):
                result = push_service.push_to_user(123, "09:30", db_session=mock_session)
        
        # 验证数据缺失日志
        log_messages = [record.message for record in caplog.records]
        assert any("数据缺失" in msg or "没有自选股数据" in msg for msg in log_messages)
    
    def test_push_to_user_logs_channel_success(self, push_service, mock_services, caplog):
        """测试推送记录渠道发送成功日志"""
        # 设置完整的模拟数据（与 test_push_to_user_logs_report_generated 类似）
        config = Mock(spec=UserPushConfig)
        config.enabled = True
        config.channels = ['wechat']
        config.report_type = 'summary'
        config.stock_codes = None
        
        user = Mock(spec=User)
        user.id = 123
        user.wechat_openid = "test_openid"
        user.email = None
        
        report_info = ReportInfo(
            report_type='summary',
            report_date='2024-01-01',
            stock_count=5,
            file_size=1024,
            has_data=True,
            missing_data_stocks=[]
        )
        
        report_result = ReportResult(
            success=True,
            file_path='/tmp/report.csv',
            report_info=report_info,
            error_message=None
        )
        
        record = Mock(spec=PushRecord)
        record.id = 456
        
        mock_services['config'].get_user_config.return_value = config
        mock_services['report'].generate_user_report.return_value = report_result
        mock_services['record'].create_record.return_value = record
        mock_services['wechat'].send_text_message.return_value = True
        mock_services['wechat'].send_file_message.return_value = True
        
        # 使用正确的导入路径
        with patch('backend_core.database.db.get_db') as mock_get_db:
            mock_session = MagicMock()
            mock_session.query.return_value.filter.return_value.first.return_value = user
            mock_get_db.return_value = iter([mock_session])
            
            with caplog.at_level(logging.INFO):
                result = push_service.push_to_user(123, "09:30", db_session=mock_session)
        
        # 验证渠道发送成功日志
        log_messages = [record.message for record in caplog.records]
        assert any("渠道发送成功" in msg or "微信推送成功" in msg for msg in log_messages)
    
    def test_push_to_user_logs_push_completed(self, push_service, mock_services, caplog):
        """测试推送记录完成事件"""
        # 设置完整的模拟数据
        config = Mock(spec=UserPushConfig)
        config.enabled = True
        config.channels = ['wechat']
        config.report_type = 'summary'
        config.stock_codes = None
        
        user = Mock(spec=User)
        user.id = 123
        user.wechat_openid = "test_openid"
        user.email = None
        
        report_info = ReportInfo(
            report_type='summary',
            report_date='2024-01-01',
            stock_count=5,
            file_size=1024,
            has_data=True,
            missing_data_stocks=[]
        )
        
        report_result = ReportResult(
            success=True,
            file_path='/tmp/report.csv',
            report_info=report_info,
            error_message=None
        )
        
        record = Mock(spec=PushRecord)
        record.id = 456
        
        mock_services['config'].get_user_config.return_value = config
        mock_services['report'].generate_user_report.return_value = report_result
        mock_services['record'].create_record.return_value = record
        mock_services['wechat'].send_text_message.return_value = True
        mock_services['wechat'].send_file_message.return_value = True
        
        # 使用正确的导入路径
        with patch('backend_core.database.db.get_db') as mock_get_db:
            mock_session = MagicMock()
            mock_session.query.return_value.filter.return_value.first.return_value = user
            mock_get_db.return_value = iter([mock_session])
            
            with caplog.at_level(logging.INFO):
                result = push_service.push_to_user(123, "09:30", db_session=mock_session)
        
        # 验证推送完成日志
        log_messages = [record.message for record in caplog.records]
        assert any("推送完成" in msg for msg in log_messages)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
