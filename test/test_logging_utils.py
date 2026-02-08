"""
日志记录工具测试
测试结构化日志记录功能
"""

import pytest
import logging
import json
from unittest.mock import Mock, patch, call
from datetime import datetime

from backend_api.services.logging_utils import (
    log_push_event, log_data_missing, log_service_unavailable,
    log_push_failure, log_user_not_configured,
    PushEventType, LogLevel, configure_structured_logging
)


class TestLogPushEvent:
    """测试 log_push_event 函数"""
    
    def test_log_push_event_basic(self, caplog):
        """测试基本的推送事件日志记录"""
        with caplog.at_level(logging.INFO):
            log_push_event(
                event_type=PushEventType.PUSH_STARTED,
                user_id=123,
                push_time="09:30"
            )
        
        # 验证日志被记录
        assert len(caplog.records) > 0
        
        # 验证日志消息包含关键信息
        log_message = caplog.records[0].message
        assert "推送开始" in log_message
        assert "用户ID=123" in log_message
        assert "推送时间=09:30" in log_message
        assert "JSON:" in log_message
    
    def test_log_push_event_with_all_fields(self, caplog):
        """测试包含所有字段的推送事件日志"""
        with caplog.at_level(logging.INFO):
            log_push_event(
                event_type=PushEventType.PUSH_COMPLETED,
                user_id=456,
                record_id=789,
                channel='wechat',
                push_time="15:30",
                status='success',
                error_message=None,
                details={"report_type": "summary", "stock_count": 10},
                log_level=LogLevel.INFO
            )
        
        assert len(caplog.records) > 0
        log_message = caplog.records[0].message
        
        # 验证所有字段都在日志中
        assert "推送完成" in log_message
        assert "用户ID=456" in log_message
        assert "记录ID=789" in log_message
        assert "渠道=wechat" in log_message
        assert "推送时间=15:30" in log_message
        assert "状态=success" in log_message
        
        # 验证JSON数据包含details
        assert "report_type" in log_message
        assert "summary" in log_message
    
    def test_log_push_event_error_level(self, caplog):
        """测试错误级别的日志记录"""
        with caplog.at_level(logging.ERROR):
            log_push_event(
                event_type=PushEventType.PUSH_FAILED,
                user_id=123,
                error_message="推送失败测试",
                log_level=LogLevel.ERROR
            )
        
        assert len(caplog.records) > 0
        assert caplog.records[0].levelname == "ERROR"
        assert "推送失败" in caplog.records[0].message
        assert "推送失败测试" in caplog.records[0].message
    
    def test_log_push_event_warning_level(self, caplog):
        """测试警告级别的日志记录"""
        with caplog.at_level(logging.WARNING):
            log_push_event(
                event_type=PushEventType.DATA_MISSING,
                user_id=123,
                log_level=LogLevel.WARNING
            )
        
        assert len(caplog.records) > 0
        assert caplog.records[0].levelname == "WARNING"
        assert "数据缺失" in caplog.records[0].message
    
    def test_log_push_event_auto_level(self, caplog):
        """测试自动确定日志级别"""
        # 错误事件应该使用ERROR级别
        with caplog.at_level(logging.ERROR):
            log_push_event(
                event_type=PushEventType.SERVICE_UNAVAILABLE,
                user_id=123
            )
        
        assert len(caplog.records) > 0
        assert caplog.records[0].levelname == "ERROR"
        
        caplog.clear()
        
        # 警告事件应该使用WARNING级别
        with caplog.at_level(logging.WARNING):
            log_push_event(
                event_type=PushEventType.USER_NOT_CONFIGURED,
                user_id=123
            )
        
        assert len(caplog.records) > 0
        assert caplog.records[0].levelname == "WARNING"
        
        caplog.clear()
        
        # 普通事件应该使用INFO级别
        with caplog.at_level(logging.INFO):
            log_push_event(
                event_type=PushEventType.PUSH_STARTED,
                user_id=123
            )
        
        assert len(caplog.records) > 0
        assert caplog.records[0].levelname == "INFO"


class TestLogHelperFunctions:
    """测试辅助日志函数"""
    
    def test_log_data_missing(self, caplog):
        """测试数据缺失日志记录"""
        with caplog.at_level(logging.WARNING):
            log_data_missing(
                user_id=123,
                missing_stocks=["000001", "600000"],
                context="report_generation"
            )
        
        assert len(caplog.records) > 0
        log_message = caplog.records[0].message
        
        assert "数据缺失" in log_message
        assert "用户ID=123" in log_message
        assert "000001" in log_message
        assert "600000" in log_message
        assert "missing_count" in log_message
    
    def test_log_service_unavailable(self, caplog):
        """测试服务不可用日志记录"""
        with caplog.at_level(logging.ERROR):
            log_service_unavailable(
                service_name='wechat',
                user_id=123,
                channel='wechat',
                error_message="微信API连接失败"
            )
        
        assert len(caplog.records) > 0
        log_message = caplog.records[0].message
        
        assert "服务不可用" in log_message
        assert "用户ID=123" in log_message
        assert "渠道=wechat" in log_message
        assert "微信API连接失败" in log_message
        assert caplog.records[0].levelname == "ERROR"
    
    def test_log_push_failure(self, caplog):
        """测试推送失败日志记录"""
        with caplog.at_level(logging.ERROR):
            log_push_failure(
                user_id=123,
                record_id=456,
                channel='email',
                error_message="SMTP连接失败",
                retry_count=2
            )
        
        assert len(caplog.records) > 0
        log_message = caplog.records[0].message
        
        assert "推送失败" in log_message
        assert "用户ID=123" in log_message
        assert "记录ID=456" in log_message
        assert "渠道=email" in log_message
        assert "SMTP连接失败" in log_message
        assert "retry_count" in log_message
        assert caplog.records[0].levelname == "ERROR"
    
    def test_log_user_not_configured(self, caplog):
        """测试用户未配置日志记录"""
        with caplog.at_level(logging.WARNING):
            log_user_not_configured(
                user_id=123,
                reason="未绑定推送渠道"
            )
        
        assert len(caplog.records) > 0
        log_message = caplog.records[0].message
        
        assert "用户未配置" in log_message
        assert "用户ID=123" in log_message
        assert "未绑定推送渠道" in log_message
        assert caplog.records[0].levelname == "WARNING"


class TestStructuredLogging:
    """测试结构化日志配置"""
    
    def test_configure_structured_logging_console_only(self):
        """测试只配置控制台日志"""
        configure_structured_logging(
            log_level="INFO",
            json_format=False
        )
        
        root_logger = logging.getLogger()
        
        # 验证日志级别
        assert root_logger.level == logging.INFO
        
        # 验证至少有一个处理器（控制台）
        assert len(root_logger.handlers) >= 1
    
    def test_configure_structured_logging_with_file(self, tmp_path):
        """测试配置文件日志"""
        log_file = tmp_path / "test.log"
        
        configure_structured_logging(
            log_file=str(log_file),
            log_level="DEBUG",
            json_format=False
        )
        
        root_logger = logging.getLogger()
        
        # 验证日志级别
        assert root_logger.level == logging.DEBUG
        
        # 验证有多个处理器（控制台 + 文件）
        assert len(root_logger.handlers) >= 2
        
        # 写入一条日志
        logging.info("测试日志消息")
        
        # 验证文件被创建
        assert log_file.exists()
    
    def test_configure_structured_logging_json_format(self):
        """测试JSON格式日志配置"""
        configure_structured_logging(
            log_level="INFO",
            json_format=True
        )
        
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO


class TestEventTypes:
    """测试事件类型枚举"""
    
    def test_all_event_types_exist(self):
        """测试所有事件类型都已定义"""
        expected_events = [
            "PUSH_STARTED",
            "PUSH_COMPLETED",
            "PUSH_FAILED",
            "REPORT_GENERATED",
            "REPORT_GENERATION_FAILED",
            "CHANNEL_SEND_SUCCESS",
            "CHANNEL_SEND_FAILED",
            "RETRY_STARTED",
            "RETRY_COMPLETED",
            "BATCH_PUSH_STARTED",
            "BATCH_PUSH_COMPLETED",
            "DATA_MISSING",
            "SERVICE_UNAVAILABLE",
            "USER_NOT_CONFIGURED",
            "DUPLICATE_PUSH_SKIPPED"
        ]
        
        for event_name in expected_events:
            assert hasattr(PushEventType, event_name)
    
    def test_event_type_values(self):
        """测试事件类型的值"""
        assert PushEventType.PUSH_STARTED.value == "push_started"
        assert PushEventType.PUSH_COMPLETED.value == "push_completed"
        assert PushEventType.PUSH_FAILED.value == "push_failed"


class TestLogLevels:
    """测试日志级别枚举"""
    
    def test_all_log_levels_exist(self):
        """测试所有日志级别都已定义"""
        expected_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        
        for level_name in expected_levels:
            assert hasattr(LogLevel, level_name)
    
    def test_log_level_values(self):
        """测试日志级别的值"""
        assert LogLevel.DEBUG.value == "debug"
        assert LogLevel.INFO.value == "info"
        assert LogLevel.WARNING.value == "warning"
        assert LogLevel.ERROR.value == "error"
        assert LogLevel.CRITICAL.value == "critical"


class TestJSONFormatting:
    """测试JSON格式化"""
    
    def test_json_data_in_log_message(self, caplog):
        """测试日志消息中包含有效的JSON数据"""
        with caplog.at_level(logging.INFO):
            log_push_event(
                event_type=PushEventType.PUSH_STARTED,
                user_id=123,
                push_time="09:30",
                details={"test_key": "test_value"}
            )
        
        assert len(caplog.records) > 0
        log_message = caplog.records[0].message
        
        # 提取JSON部分
        if "JSON:" in log_message:
            json_part = log_message.split("JSON:")[1].strip()
            
            # 验证可以解析为JSON
            try:
                json_data = json.loads(json_part)
                
                # 验证关键字段
                assert json_data["event_type"] == "push_started"
                assert json_data["user_id"] == 123
                assert json_data["push_time"] == "09:30"
                assert "timestamp" in json_data
                assert json_data["details"]["test_key"] == "test_value"
            except json.JSONDecodeError:
                pytest.fail("日志中的JSON数据无法解析")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
