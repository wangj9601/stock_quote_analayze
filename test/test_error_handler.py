"""
ErrorHandler 单元测试
测试错误处理器的各种功能
"""

import pytest
from backend_api.services.error_handler import (
    ErrorHandler, 
    ErrorCategory, 
    PushContext,
    ErrorHandlingResult
)


class TestErrorHandler:
    """ErrorHandler 测试类"""
    
    @pytest.fixture
    def error_handler(self):
        """创建ErrorHandler实例"""
        return ErrorHandler()
    
    @pytest.fixture
    def sample_context(self):
        """创建示例推送上下文"""
        return PushContext(
            user_id=1,
            push_time="09:30",
            record_id=100,
            channel="wechat",
            retry_count=0
        )
    
    # ==================== 错误分类测试 ====================
    
    def test_classify_user_input_error_invalid_email(self, error_handler):
        """测试用户输入错误分类 - 无效邮箱"""
        error = ValueError("Invalid email format")
        category = error_handler._classify_error(error)
        assert category == ErrorCategory.USER_INPUT_ERROR
    
    def test_classify_user_input_error_validation(self, error_handler):
        """测试用户输入错误分类 - 验证失败"""
        error = ValueError("Validation error: invalid format")
        category = error_handler._classify_error(error)
        assert category == ErrorCategory.USER_INPUT_ERROR
    
    def test_classify_data_error_no_data(self, error_handler):
        """测试数据错误分类 - 没有数据"""
        error = Exception("No data found for user")
        category = error_handler._classify_error(error)
        assert category == ErrorCategory.DATA_ERROR
    
    def test_classify_data_error_empty_watchlist(self, error_handler):
        """测试数据错误分类 - 空自选股"""
        error = Exception("Empty watchlist")
        category = error_handler._classify_error(error)
        assert category == ErrorCategory.DATA_ERROR
    
    def test_classify_service_unavailable_connection(self, error_handler):
        """测试服务不可用错误分类 - 连接错误"""
        error = ConnectionError("Connection refused")
        category = error_handler._classify_error(error)
        assert category == ErrorCategory.SERVICE_UNAVAILABLE
    
    def test_classify_service_unavailable_timeout(self, error_handler):
        """测试服务不可用错误分类 - 超时"""
        error = TimeoutError("Request timeout")
        category = error_handler._classify_error(error)
        assert category == ErrorCategory.SERVICE_UNAVAILABLE
    
    def test_classify_service_unavailable_smtp(self, error_handler):
        """测试服务不可用错误分类 - SMTP错误"""
        error = Exception("SMTP connection failed")
        category = error_handler._classify_error(error)
        assert category == ErrorCategory.SERVICE_UNAVAILABLE
    
    def test_classify_system_error_default(self, error_handler):
        """测试系统错误分类 - 默认分类"""
        error = Exception("Unknown error occurred")
        category = error_handler._classify_error(error)
        assert category == ErrorCategory.SYSTEM_ERROR
    
    # ==================== 重试判断测试 ====================
    
    def test_should_retry_service_unavailable(self, error_handler):
        """测试服务不可用错误应该重试"""
        error = ConnectionError("Connection refused")
        assert error_handler.should_retry(error) is True
    
    def test_should_retry_timeout(self, error_handler):
        """测试超时错误应该重试"""
        error = Exception("Request timeout")
        assert error_handler.should_retry(error) is True
    
    def test_should_not_retry_user_input_error(self, error_handler):
        """测试用户输入错误不应该重试"""
        error = ValueError("Invalid email format")
        assert error_handler.should_retry(error) is False
    
    def test_should_not_retry_data_error(self, error_handler):
        """测试数据错误不应该重试"""
        error = Exception("No data found")
        assert error_handler.should_retry(error) is False
    
    def test_should_retry_temporary_system_error(self, error_handler):
        """测试临时性系统错误应该重试"""
        error = Exception("System temporarily unavailable")
        assert error_handler.should_retry(error) is True
    
    def test_should_not_retry_permanent_system_error(self, error_handler):
        """测试永久性系统错误不应该重试"""
        error = Exception("File system error")
        assert error_handler.should_retry(error) is False
    
    # ==================== 重试延迟测试 ====================
    
    def test_get_retry_delay_first_retry(self, error_handler):
        """测试第一次重试延迟 - 1分钟"""
        delay = error_handler.get_retry_delay(0)
        assert delay == 60
    
    def test_get_retry_delay_second_retry(self, error_handler):
        """测试第二次重试延迟 - 5分钟"""
        delay = error_handler.get_retry_delay(1)
        assert delay == 300
    
    def test_get_retry_delay_third_retry(self, error_handler):
        """测试第三次重试延迟 - 15分钟"""
        delay = error_handler.get_retry_delay(2)
        assert delay == 900
    
    def test_get_retry_delay_max_retry(self, error_handler):
        """测试超过最大重试次数后的延迟 - 保持15分钟"""
        delay = error_handler.get_retry_delay(5)
        assert delay == 900
    
    # ==================== 错误处理测试 ====================
    
    def test_handle_push_error_service_unavailable(self, error_handler, sample_context):
        """测试处理服务不可用错误"""
        error = ConnectionError("SMTP connection failed")
        result = error_handler.handle_push_error(error, sample_context)
        
        assert isinstance(result, ErrorHandlingResult)
        assert result.error_category == ErrorCategory.SERVICE_UNAVAILABLE
        assert result.should_retry is True
        assert result.retry_delay == 60  # 第一次重试延迟1分钟
        assert result.log_level == "error"
        assert "ConnectionError" in result.error_message
    
    def test_handle_push_error_user_input(self, error_handler, sample_context):
        """测试处理用户输入错误"""
        error = ValueError("Invalid email format")
        result = error_handler.handle_push_error(error, sample_context)
        
        assert result.error_category == ErrorCategory.USER_INPUT_ERROR
        assert result.should_retry is False
        assert result.retry_delay == 0
        assert result.log_level == "warning"
    
    def test_handle_push_error_data_error(self, error_handler, sample_context):
        """测试处理数据错误"""
        error = Exception("Empty watchlist")
        result = error_handler.handle_push_error(error, sample_context)
        
        assert result.error_category == ErrorCategory.DATA_ERROR
        assert result.should_retry is False
        assert result.retry_delay == 0
        assert result.log_level == "warning"
    
    def test_handle_push_error_with_retry_count(self, error_handler):
        """测试处理错误时考虑重试次数"""
        context = PushContext(
            user_id=1,
            push_time="09:30",
            retry_count=2  # 第三次重试
        )
        error = ConnectionError("Network error")
        result = error_handler.handle_push_error(error, context)
        
        assert result.should_retry is True
        assert result.retry_delay == 900  # 第三次重试延迟15分钟
    
    # ==================== 错误消息格式化测试 ====================
    
    def test_format_error_message_basic(self, error_handler, sample_context):
        """测试基本错误消息格式化"""
        error = ValueError("Test error")
        message = error_handler._format_error_message(error, sample_context)
        
        assert "ValueError" in message
        assert "Test error" in message
        assert "用户ID=1" in message
        assert "推送时间=09:30" in message
        assert "渠道=wechat" in message
        assert "记录ID=100" in message
    
    def test_format_error_message_with_retry(self, error_handler):
        """测试包含重试次数的错误消息格式化"""
        context = PushContext(
            user_id=1,
            push_time="09:30",
            retry_count=2
        )
        error = Exception("Test error")
        message = error_handler._format_error_message(error, context)
        
        assert "重试次数=2" in message
    
    def test_format_error_message_without_optional_fields(self, error_handler):
        """测试不包含可选字段的错误消息格式化"""
        context = PushContext(
            user_id=1,
            push_time="09:30"
        )
        error = Exception("Test error")
        message = error_handler._format_error_message(error, context)
        
        assert "用户ID=1" in message
        assert "推送时间=09:30" in message
        assert "渠道=" not in message  # 没有渠道信息
        assert "记录ID=" not in message  # 没有记录ID
    
    # ==================== 用户友好消息测试 ====================
    
    def test_get_user_friendly_message_user_input_error(self, error_handler):
        """测试用户输入错误的友好消息"""
        error = ValueError("Invalid email")
        message = error_handler.get_user_friendly_message(error)
        
        assert "输入信息有误" in message
        assert "配置信息" in message
    
    def test_get_user_friendly_message_data_error(self, error_handler):
        """测试数据错误的友好消息"""
        error = Exception("No data found")
        message = error_handler.get_user_friendly_message(error)
        
        assert "数据不完整" in message
        assert "自选股" in message
    
    def test_get_user_friendly_message_service_unavailable(self, error_handler):
        """测试服务不可用的友好消息"""
        error = ConnectionError("Connection failed")
        message = error_handler.get_user_friendly_message(error)
        
        assert "服务暂时不可用" in message
        assert "自动重试" in message
    
    def test_get_user_friendly_message_system_error(self, error_handler):
        """测试系统错误的友好消息"""
        error = Exception("Unknown system error")
        message = error_handler.get_user_friendly_message(error)
        
        assert "系统发生错误" in message
    
    def test_get_user_friendly_message_with_category(self, error_handler):
        """测试指定错误分类的友好消息"""
        error = Exception("Some error")
        message = error_handler.get_user_friendly_message(
            error, 
            category=ErrorCategory.SERVICE_UNAVAILABLE
        )
        
        assert "服务暂时不可用" in message
    
    # ==================== 错误分类名称测试 ====================
    
    def test_get_category_name_user_input(self, error_handler):
        """测试获取用户输入错误的中文名称"""
        name = error_handler._get_category_name(ErrorCategory.USER_INPUT_ERROR)
        assert name == "用户输入错误"
    
    def test_get_category_name_data_error(self, error_handler):
        """测试获取数据错误的中文名称"""
        name = error_handler._get_category_name(ErrorCategory.DATA_ERROR)
        assert name == "数据错误"
    
    def test_get_category_name_service_unavailable(self, error_handler):
        """测试获取服务不可用的中文名称"""
        name = error_handler._get_category_name(ErrorCategory.SERVICE_UNAVAILABLE)
        assert name == "服务不可用"
    
    def test_get_category_name_system_error(self, error_handler):
        """测试获取系统错误的中文名称"""
        name = error_handler._get_category_name(ErrorCategory.SYSTEM_ERROR)
        assert name == "系统错误"
    
    # ==================== 日志级别测试 ====================
    
    def test_get_log_level_user_input_error(self, error_handler):
        """测试用户输入错误的日志级别"""
        level = error_handler._get_log_level(ErrorCategory.USER_INPUT_ERROR)
        assert level == "warning"
    
    def test_get_log_level_data_error(self, error_handler):
        """测试数据错误的日志级别"""
        level = error_handler._get_log_level(ErrorCategory.DATA_ERROR)
        assert level == "warning"
    
    def test_get_log_level_service_unavailable(self, error_handler):
        """测试服务不可用的日志级别"""
        level = error_handler._get_log_level(ErrorCategory.SERVICE_UNAVAILABLE)
        assert level == "error"
    
    def test_get_log_level_system_error(self, error_handler):
        """测试系统错误的日志级别"""
        level = error_handler._get_log_level(ErrorCategory.SYSTEM_ERROR)
        assert level == "error"
    
    # ==================== 边界情况测试 ====================
    
    def test_handle_empty_error_message(self, error_handler, sample_context):
        """测试处理空错误消息"""
        error = Exception("")
        result = error_handler.handle_push_error(error, sample_context)
        
        assert isinstance(result, ErrorHandlingResult)
        assert result.error_message is not None
    
    def test_handle_unicode_error_message(self, error_handler, sample_context):
        """测试处理包含Unicode字符的错误消息"""
        error = Exception("错误：连接失败 🔥")
        result = error_handler.handle_push_error(error, sample_context)
        
        assert isinstance(result, ErrorHandlingResult)
        assert "错误" in result.error_message
    
    def test_handle_very_long_error_message(self, error_handler, sample_context):
        """测试处理非常长的错误消息"""
        long_message = "Error: " + "x" * 1000
        error = Exception(long_message)
        result = error_handler.handle_push_error(error, sample_context)
        
        assert isinstance(result, ErrorHandlingResult)
        assert len(result.error_message) > 0
    
    # ==================== 多种错误类型测试 ====================
    
    def test_classify_multiple_error_types(self, error_handler):
        """测试分类多种不同的错误类型"""
        errors = [
            (ValueError("Invalid format"), ErrorCategory.USER_INPUT_ERROR),
            (ConnectionError("Network error"), ErrorCategory.SERVICE_UNAVAILABLE),
            (Exception("No data"), ErrorCategory.DATA_ERROR),
            (RuntimeError("System failure"), ErrorCategory.SYSTEM_ERROR),
        ]
        
        for error, expected_category in errors:
            category = error_handler._classify_error(error)
            assert category == expected_category, f"错误 {error} 分类不正确"
    
    def test_retry_decision_for_multiple_errors(self, error_handler):
        """测试多种错误的重试决策"""
        should_retry_errors = [
            ConnectionError("Connection failed"),
            TimeoutError("Timeout"),
            Exception("Network temporarily unavailable"),
        ]
        
        should_not_retry_errors = [
            ValueError("Invalid input"),
            Exception("No data found"),
            Exception("File system error"),
        ]
        
        for error in should_retry_errors:
            assert error_handler.should_retry(error) is True, \
                f"错误 {error} 应该重试但判断为不重试"
        
        for error in should_not_retry_errors:
            assert error_handler.should_retry(error) is False, \
                f"错误 {error} 不应该重试但判断为重试"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
