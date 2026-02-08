"""
错误处理器 (ErrorHandler)
负责统一错误处理、错误分类和重试策略
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """错误分类"""
    USER_INPUT_ERROR = "user_input_error"  # 用户输入错误
    DATA_ERROR = "data_error"  # 数据错误
    SERVICE_UNAVAILABLE = "service_unavailable"  # 服务不可用错误
    SYSTEM_ERROR = "system_error"  # 系统错误


@dataclass
class PushContext:
    """推送上下文信息"""
    user_id: int
    push_time: str
    record_id: Optional[int] = None
    channel: Optional[str] = None
    retry_count: int = 0


@dataclass
class ErrorHandlingResult:
    """错误处理结果"""
    error_category: ErrorCategory
    should_retry: bool
    retry_delay: int  # 重试延迟时间（秒）
    error_message: str
    log_level: str  # 日志级别: 'error', 'warning', 'info'


class ErrorHandler:
    """统一错误处理器"""
    
    def __init__(self):
        """初始化错误处理器"""
        logger.info("ErrorHandler 初始化完成")
    
    def handle_push_error(
        self, 
        error: Exception, 
        context: PushContext
    ) -> ErrorHandlingResult:
        """
        处理推送错误
        
        策略:
        1. 记录详细错误信息到日志
        2. 根据错误类型进行分类
        3. 决定是否应该重试
        4. 计算重试延迟时间
        
        Args:
            error: 异常对象
            context: 推送上下文信息
            
        Returns:
            ErrorHandlingResult: 错误处理结果
        """
        # 分类错误
        error_category = self._classify_error(error)
        
        # 判断是否应该重试
        should_retry = self.should_retry(error)
        
        # 计算重试延迟
        retry_delay = self.get_retry_delay(context.retry_count) if should_retry else 0
        
        # 格式化错误消息
        error_message = self._format_error_message(error, context)
        
        # 确定日志级别
        log_level = self._get_log_level(error_category)
        
        # 记录日志
        self._log_error(error, context, error_category, log_level)
        
        return ErrorHandlingResult(
            error_category=error_category,
            should_retry=should_retry,
            retry_delay=retry_delay,
            error_message=error_message,
            log_level=log_level
        )
    
    def should_retry(self, error: Exception) -> bool:
        """
        判断错误是否应该重试
        
        重试策略:
        - 网络错误、服务暂时不可用 -> 重试
        - 数据错误、配置错误 -> 不重试
        - 用户输入错误 -> 不重试
        - 系统错误 -> 根据具体情况决定
        
        Args:
            error: 异常对象
            
        Returns:
            bool: 是否应该重试
        """
        error_category = self._classify_error(error)
        
        # 服务不可用错误应该重试
        if error_category == ErrorCategory.SERVICE_UNAVAILABLE:
            return True
        
        # 用户输入错误不应该重试
        if error_category == ErrorCategory.USER_INPUT_ERROR:
            return False
        
        # 数据错误不应该重试（数据缺失、格式错误等）
        if error_category == ErrorCategory.DATA_ERROR:
            return False
        
        # 系统错误根据具体类型决定
        if error_category == ErrorCategory.SYSTEM_ERROR:
            # 文件系统错误、内存错误等不应该重试
            error_str = str(error).lower()
            
            # 临时性错误可以重试
            temporary_errors = [
                'timeout', 'connection', 'network', 
                'temporarily', 'unavailable', 'busy'
            ]
            
            for temp_error in temporary_errors:
                if temp_error in error_str:
                    return True
            
            # 其他系统错误不重试
            return False
        
        # 默认不重试
        return False
    
    def get_retry_delay(self, retry_count: int) -> int:
        """
        获取重试延迟时间（秒）
        
        指数退避策略:
        - 第1次重试: 1分钟 (60秒)
        - 第2次重试: 5分钟 (300秒)
        - 第3次重试: 15分钟 (900秒)
        - 第4次及以后: 15分钟 (900秒)
        
        Args:
            retry_count: 当前重试次数（0表示第一次尝试）
            
        Returns:
            int: 重试延迟时间（秒）
        """
        delays = [60, 300, 900]  # 1分钟、5分钟、15分钟
        
        # 如果重试次数超过预定义的延迟列表，使用最后一个延迟值
        if retry_count >= len(delays):
            return delays[-1]
        
        return delays[retry_count]
    
    def _classify_error(self, error: Exception) -> ErrorCategory:
        """
        对错误进行分类
        
        分类规则:
        1. 用户输入错误: 无效的邮箱格式、无效的微信OpenID、无效的推送时间格式
        2. 数据错误: 用户没有自选股、历史行情数据缺失
        3. 服务不可用错误: 微信API不可用、SMTP服务器不可用、数据库连接失败
        4. 系统错误: CSV生成失败、文件系统错误
        
        Args:
            error: 异常对象
            
        Returns:
            ErrorCategory: 错误分类
        """
        error_type = type(error).__name__
        error_str = str(error).lower()
        
        # 1. 用户输入错误
        user_input_keywords = [
            'invalid email', 'invalid format', 'validation error',
            '邮箱格式', '格式无效', '验证失败', 'invalid openid'
        ]
        
        for keyword in user_input_keywords:
            if keyword in error_str:
                return ErrorCategory.USER_INPUT_ERROR
        
        # 检查特定的异常类型
        if error_type in ['ValueError', 'ValidationError']:
            return ErrorCategory.USER_INPUT_ERROR
        
        # 2. 数据错误
        data_error_keywords = [
            'no data', 'data not found', 'missing data', 
            'empty watchlist', '没有数据', '数据缺失', 
            '没有自选股', 'no stocks'
        ]
        
        for keyword in data_error_keywords:
            if keyword in error_str:
                return ErrorCategory.DATA_ERROR
        
        # 3. 服务不可用错误
        service_unavailable_keywords = [
            'connection', 'timeout', 'network', 'unavailable',
            'smtp', 'wechat api', 'database', 'connection refused',
            '连接失败', '服务不可用', '超时', '网络错误'
        ]
        
        for keyword in service_unavailable_keywords:
            if keyword in error_str:
                return ErrorCategory.SERVICE_UNAVAILABLE
        
        # 检查特定的异常类型
        if error_type in [
            'ConnectionError', 'TimeoutError', 'SMTPException',
            'DatabaseError', 'OperationalError'
        ]:
            return ErrorCategory.SERVICE_UNAVAILABLE
        
        # 导入EmailSendException（如果存在）
        try:
            from backend_api.services.email_service import EmailSendException
            if isinstance(error, EmailSendException):
                return ErrorCategory.SERVICE_UNAVAILABLE
        except ImportError:
            pass
        
        # 4. 系统错误（默认分类）
        return ErrorCategory.SYSTEM_ERROR
    
    def _format_error_message(
        self, 
        error: Exception, 
        context: PushContext
    ) -> str:
        """
        格式化错误消息
        
        Args:
            error: 异常对象
            context: 推送上下文
            
        Returns:
            str: 格式化后的错误消息
        """
        error_category = self._classify_error(error)
        
        # 基础错误信息
        base_message = f"{type(error).__name__}: {str(error)}"
        
        # 添加上下文信息
        context_info = f"用户ID={context.user_id}, 推送时间={context.push_time}"
        
        if context.channel:
            context_info += f", 渠道={context.channel}"
        
        if context.record_id:
            context_info += f", 记录ID={context.record_id}"
        
        if context.retry_count > 0:
            context_info += f", 重试次数={context.retry_count}"
        
        # 添加错误分类
        category_name = self._get_category_name(error_category)
        
        # 组合完整消息
        full_message = f"[{category_name}] {base_message} ({context_info})"
        
        return full_message
    
    def _get_category_name(self, category: ErrorCategory) -> str:
        """
        获取错误分类的中文名称
        
        Args:
            category: 错误分类
            
        Returns:
            str: 中文名称
        """
        category_names = {
            ErrorCategory.USER_INPUT_ERROR: "用户输入错误",
            ErrorCategory.DATA_ERROR: "数据错误",
            ErrorCategory.SERVICE_UNAVAILABLE: "服务不可用",
            ErrorCategory.SYSTEM_ERROR: "系统错误"
        }
        
        return category_names.get(category, "未知错误")
    
    def _get_log_level(self, category: ErrorCategory) -> str:
        """
        根据错误分类确定日志级别
        
        Args:
            category: 错误分类
            
        Returns:
            str: 日志级别
        """
        log_levels = {
            ErrorCategory.USER_INPUT_ERROR: "warning",
            ErrorCategory.DATA_ERROR: "warning",
            ErrorCategory.SERVICE_UNAVAILABLE: "error",
            ErrorCategory.SYSTEM_ERROR: "error"
        }
        
        return log_levels.get(category, "error")
    
    def _log_error(
        self,
        error: Exception,
        context: PushContext,
        category: ErrorCategory,
        log_level: str
    ):
        """
        记录错误日志
        
        Args:
            error: 异常对象
            context: 推送上下文
            category: 错误分类
            log_level: 日志级别
        """
        error_message = self._format_error_message(error, context)
        
        # 构建结构化日志数据
        log_data = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "error_category": category.value,
            "user_id": context.user_id,
            "push_time": context.push_time,
            "channel": context.channel,
            "record_id": context.record_id,
            "retry_count": context.retry_count,
            "should_retry": self.should_retry(error)
        }
        
        # 根据日志级别记录
        if log_level == "error":
            logger.error(error_message, extra=log_data, exc_info=True)
        elif log_level == "warning":
            logger.warning(error_message, extra=log_data)
        else:
            logger.info(error_message, extra=log_data)
    
    def get_user_friendly_message(
        self, 
        error: Exception, 
        category: Optional[ErrorCategory] = None
    ) -> str:
        """
        获取用户友好的错误消息
        
        Args:
            error: 异常对象
            category: 错误分类（可选，如果不提供则自动分类）
            
        Returns:
            str: 用户友好的错误消息
        """
        if category is None:
            category = self._classify_error(error)
        
        # 根据错误分类返回友好消息
        if category == ErrorCategory.USER_INPUT_ERROR:
            return "输入信息有误，请检查您的配置信息（邮箱、微信等）是否正确。"
        
        elif category == ErrorCategory.DATA_ERROR:
            return "数据不完整，请确保您已添加自选股并且有相关的历史数据。"
        
        elif category == ErrorCategory.SERVICE_UNAVAILABLE:
            return "服务暂时不可用，系统将自动重试。如果问题持续，请联系管理员。"
        
        elif category == ErrorCategory.SYSTEM_ERROR:
            return "系统发生错误，请稍后再试或联系管理员。"
        
        else:
            return "发生未知错误，请联系管理员。"
