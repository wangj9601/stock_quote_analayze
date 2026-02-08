"""
日志记录工具 (Logging Utils)
提供结构化日志记录功能，用于记录推送事件、错误和警告信息
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum


class PushEventType(Enum):
    """推送事件类型"""
    PUSH_STARTED = "push_started"  # 推送开始
    PUSH_COMPLETED = "push_completed"  # 推送完成
    PUSH_FAILED = "push_failed"  # 推送失败
    REPORT_GENERATED = "report_generated"  # 报告生成
    REPORT_GENERATION_FAILED = "report_generation_failed"  # 报告生成失败
    CHANNEL_SEND_SUCCESS = "channel_send_success"  # 渠道发送成功
    CHANNEL_SEND_FAILED = "channel_send_failed"  # 渠道发送失败
    RETRY_STARTED = "retry_started"  # 重试开始
    RETRY_COMPLETED = "retry_completed"  # 重试完成
    BATCH_PUSH_STARTED = "batch_push_started"  # 批量推送开始
    BATCH_PUSH_COMPLETED = "batch_push_completed"  # 批量推送完成
    DATA_MISSING = "data_missing"  # 数据缺失
    SERVICE_UNAVAILABLE = "service_unavailable"  # 服务不可用
    USER_NOT_CONFIGURED = "user_not_configured"  # 用户未配置
    DUPLICATE_PUSH_SKIPPED = "duplicate_push_skipped"  # 重复推送跳过


class LogLevel(Enum):
    """日志级别"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


def log_push_event(
    event_type: PushEventType,
    user_id: Optional[int] = None,
    record_id: Optional[int] = None,
    channel: Optional[str] = None,
    push_time: Optional[str] = None,
    status: Optional[str] = None,
    error_message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    log_level: Optional[LogLevel] = None
):
    """
    记录推送事件（结构化日志）
    
    使用JSON格式记录结构化日志，包含事件类型、用户信息、时间戳等关键信息。
    
    Args:
        event_type: 事件类型
        user_id: 用户ID（可选）
        record_id: 推送记录ID（可选）
        channel: 推送渠道（可选，如 'wechat', 'email'）
        push_time: 推送时间点（可选，如 '09:30'）
        status: 状态（可选，如 'success', 'failed', 'processing'）
        error_message: 错误信息（可选）
        details: 额外的详细信息（可选）
        log_level: 日志级别（可选，如果不提供则根据事件类型自动确定）
    
    Example:
        log_push_event(
            event_type=PushEventType.PUSH_STARTED,
            user_id=123,
            push_time="09:30",
            details={"report_type": "summary"}
        )
    """
    logger = logging.getLogger(__name__)
    
    # 构建结构化日志数据
    log_data = {
        "event_type": event_type.value,
        "timestamp": datetime.now().isoformat(),
    }
    
    # 添加可选字段
    if user_id is not None:
        log_data["user_id"] = user_id
    
    if record_id is not None:
        log_data["record_id"] = record_id
    
    if channel is not None:
        log_data["channel"] = channel
    
    if push_time is not None:
        log_data["push_time"] = push_time
    
    if status is not None:
        log_data["status"] = status
    
    if error_message is not None:
        log_data["error_message"] = error_message
    
    # 合并额外的详细信息
    if details:
        log_data["details"] = details
    
    # 确定日志级别
    if log_level is None:
        log_level = _get_default_log_level(event_type)
    
    # 格式化日志消息
    log_message = _format_log_message(event_type, log_data)
    
    # 记录日志
    _write_log(logger, log_level, log_message, log_data)


def log_data_missing(
    user_id: int,
    missing_stocks: List[str],
    context: str = "report_generation"
):
    """
    记录数据缺失警告
    
    Args:
        user_id: 用户ID
        missing_stocks: 缺失数据的股票代码列表
        context: 上下文信息（默认为 'report_generation'）
    """
    log_push_event(
        event_type=PushEventType.DATA_MISSING,
        user_id=user_id,
        details={
            "missing_stocks": missing_stocks,
            "missing_count": len(missing_stocks),
            "context": context
        },
        log_level=LogLevel.WARNING
    )


def log_service_unavailable(
    service_name: str,
    user_id: Optional[int] = None,
    channel: Optional[str] = None,
    error_message: Optional[str] = None
):
    """
    记录服务不可用错误
    
    Args:
        service_name: 服务名称（如 'wechat', 'email', 'database'）
        user_id: 用户ID（可选）
        channel: 推送渠道（可选）
        error_message: 错误信息（可选）
    """
    log_push_event(
        event_type=PushEventType.SERVICE_UNAVAILABLE,
        user_id=user_id,
        channel=channel,
        error_message=error_message,
        details={
            "service_name": service_name
        },
        log_level=LogLevel.ERROR
    )


def log_push_failure(
    user_id: int,
    record_id: Optional[int] = None,
    channel: Optional[str] = None,
    error_message: Optional[str] = None,
    retry_count: int = 0
):
    """
    记录推送失败
    
    Args:
        user_id: 用户ID
        record_id: 推送记录ID（可选）
        channel: 推送渠道（可选）
        error_message: 错误信息（可选）
        retry_count: 重试次数（默认为0）
    """
    log_push_event(
        event_type=PushEventType.PUSH_FAILED,
        user_id=user_id,
        record_id=record_id,
        channel=channel,
        status="failed",
        error_message=error_message,
        details={
            "retry_count": retry_count
        },
        log_level=LogLevel.ERROR
    )


def log_user_not_configured(
    user_id: int,
    reason: str
):
    """
    记录用户未配置警告
    
    Args:
        user_id: 用户ID
        reason: 原因说明（如 '未绑定推送渠道', '推送功能已禁用'）
    """
    log_push_event(
        event_type=PushEventType.USER_NOT_CONFIGURED,
        user_id=user_id,
        details={
            "reason": reason
        },
        log_level=LogLevel.WARNING
    )


def _get_default_log_level(event_type: PushEventType) -> LogLevel:
    """
    根据事件类型确定默认日志级别
    
    Args:
        event_type: 事件类型
        
    Returns:
        LogLevel: 日志级别
    """
    # 错误级别事件
    error_events = [
        PushEventType.PUSH_FAILED,
        PushEventType.REPORT_GENERATION_FAILED,
        PushEventType.CHANNEL_SEND_FAILED,
        PushEventType.SERVICE_UNAVAILABLE
    ]
    
    # 警告级别事件
    warning_events = [
        PushEventType.DATA_MISSING,
        PushEventType.USER_NOT_CONFIGURED,
        PushEventType.DUPLICATE_PUSH_SKIPPED
    ]
    
    if event_type in error_events:
        return LogLevel.ERROR
    elif event_type in warning_events:
        return LogLevel.WARNING
    else:
        return LogLevel.INFO


def _format_log_message(event_type: PushEventType, log_data: Dict[str, Any]) -> str:
    """
    格式化日志消息
    
    Args:
        event_type: 事件类型
        log_data: 日志数据
        
    Returns:
        str: 格式化后的日志消息
    """
    # 事件类型的中文描述
    event_descriptions = {
        PushEventType.PUSH_STARTED: "推送开始",
        PushEventType.PUSH_COMPLETED: "推送完成",
        PushEventType.PUSH_FAILED: "推送失败",
        PushEventType.REPORT_GENERATED: "报告生成成功",
        PushEventType.REPORT_GENERATION_FAILED: "报告生成失败",
        PushEventType.CHANNEL_SEND_SUCCESS: "渠道发送成功",
        PushEventType.CHANNEL_SEND_FAILED: "渠道发送失败",
        PushEventType.RETRY_STARTED: "重试开始",
        PushEventType.RETRY_COMPLETED: "重试完成",
        PushEventType.BATCH_PUSH_STARTED: "批量推送开始",
        PushEventType.BATCH_PUSH_COMPLETED: "批量推送完成",
        PushEventType.DATA_MISSING: "数据缺失",
        PushEventType.SERVICE_UNAVAILABLE: "服务不可用",
        PushEventType.USER_NOT_CONFIGURED: "用户未配置",
        PushEventType.DUPLICATE_PUSH_SKIPPED: "重复推送跳过"
    }
    
    description = event_descriptions.get(event_type, event_type.value)
    
    # 构建基础消息
    message_parts = [f"[推送事件] {description}"]
    
    # 添加用户信息
    if "user_id" in log_data:
        message_parts.append(f"用户ID={log_data['user_id']}")
    
    # 添加记录ID
    if "record_id" in log_data:
        message_parts.append(f"记录ID={log_data['record_id']}")
    
    # 添加渠道信息
    if "channel" in log_data:
        message_parts.append(f"渠道={log_data['channel']}")
    
    # 添加推送时间
    if "push_time" in log_data:
        message_parts.append(f"推送时间={log_data['push_time']}")
    
    # 添加状态
    if "status" in log_data:
        message_parts.append(f"状态={log_data['status']}")
    
    # 添加错误信息
    if "error_message" in log_data:
        message_parts.append(f"错误={log_data['error_message']}")
    
    return " | ".join(message_parts)


def _write_log(
    logger: logging.Logger,
    log_level: LogLevel,
    message: str,
    log_data: Dict[str, Any]
):
    """
    写入日志
    
    Args:
        logger: 日志记录器
        log_level: 日志级别
        message: 日志消息
        log_data: 结构化日志数据
    """
    # 将结构化数据转换为JSON字符串（用于某些日志处理器）
    json_data = json.dumps(log_data, ensure_ascii=False, default=str)
    
    # 根据日志级别写入
    if log_level == LogLevel.DEBUG:
        logger.debug(f"{message} | JSON: {json_data}")
    elif log_level == LogLevel.INFO:
        logger.info(f"{message} | JSON: {json_data}")
    elif log_level == LogLevel.WARNING:
        logger.warning(f"{message} | JSON: {json_data}")
    elif log_level == LogLevel.ERROR:
        logger.error(f"{message} | JSON: {json_data}")
    elif log_level == LogLevel.CRITICAL:
        logger.critical(f"{message} | JSON: {json_data}")
    else:
        logger.info(f"{message} | JSON: {json_data}")


def configure_structured_logging(
    log_file: Optional[str] = None,
    log_level: str = "INFO",
    json_format: bool = False
):
    """
    配置结构化日志记录
    
    Args:
        log_file: 日志文件路径（可选，如果不提供则只输出到控制台）
        log_level: 日志级别（默认为 'INFO'）
        json_format: 是否使用纯JSON格式（默认为False，使用混合格式）
    """
    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # 清除现有的处理器
    root_logger.handlers.clear()
    
    # 创建格式化器
    if json_format:
        # 纯JSON格式
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
            '"logger": "%(name)s", "message": "%(message)s"}'
        )
    else:
        # 混合格式（更易读）
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    # 添加控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # 如果指定了日志文件，添加文件处理器
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    logging.info(f"结构化日志记录已配置: log_level={log_level}, log_file={log_file}, json_format={json_format}")
