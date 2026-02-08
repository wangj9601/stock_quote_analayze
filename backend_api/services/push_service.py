"""
推送服务核心 (PushService)
负责协调报告生成、渠道选择、消息发送
"""

from datetime import datetime, date
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend_api.models import User
from backend_api.services.email_service import EmailService, EmailSendException
from backend_api.services.config_service import ConfigService
from backend_api.services.report_service import ReportService, ReportInfo
from backend_api.services.record_repository import RecordRepository
from backend_core.wechat.wechat_service import WeChatService
from backend_api.services.logging_utils import (
    log_push_event, log_data_missing, log_service_unavailable,
    log_push_failure, log_user_not_configured,
    PushEventType, LogLevel
)

logger = logging.getLogger(__name__)


@dataclass
class ChannelResult:
    """单个渠道的推送结果"""
    channel: str  # 渠道名称 ('wechat' 或 'email')
    success: bool  # 是否成功
    error_message: Optional[str] = None  # 错误信息


@dataclass
class PushResult:
    """单个用户的推送结果"""
    user_id: int
    success: bool  # 整体是否成功
    channel_results: List[ChannelResult]  # 各渠道推送结果
    record_id: Optional[int] = None  # 推送记录ID
    error_message: Optional[str] = None  # 整体错误信息


@dataclass
class PushBatchResult:
    """批量推送结果"""
    total_users: int  # 总用户数
    success_count: int  # 成功数
    failed_count: int  # 失败数
    skipped_count: int  # 跳过数
    push_results: List[PushResult]  # 各用户推送结果


class PushService:
    """推送服务核心"""
    
    def __init__(
        self,
        wechat_service: WeChatService,
        email_service: EmailService,
        report_service: ReportService,
        config_service: ConfigService,
        record_repository: RecordRepository
    ):
        """
        初始化推送服务
        
        Args:
            wechat_service: 微信服务
            email_service: 邮件服务
            report_service: 报告服务
            config_service: 配置服务
            record_repository: 推送记录仓库
        """
        self.wechat_service = wechat_service
        self.email_service = email_service
        self.report_service = report_service
        self.config_service = config_service
        self.record_repository = record_repository
        
        logger.info("PushService 初始化完成")
    
    def execute_scheduled_push(self, push_time: str, max_workers: int = 5) -> PushBatchResult:
        """
        执行定时推送任务（批量推送）
        
        实现步骤:
        1. 查询指定时间点需要推送的用户(调用ConfigService.get_users_for_push_time)
        2. 使用RecordRepository.check_duplicate_push检查推送去重
        3. 使用线程池或异步方式并发处理多个用户推送
        4. 处理单个用户失败不影响其他用户(异常捕获和隔离)
        5. 返回批量推送结果统计(成功数、失败数、跳过数)
        
        Args:
            push_time: 推送时间点 (如 "09:30")
            max_workers: 最大并发工作线程数，默认5
            
        Returns:
            PushBatchResult: 批量推送结果
        """
        logger.info(f"开始执行定时推送任务: push_time={push_time}")
        
        # 记录批量推送开始事件
        log_push_event(
            event_type=PushEventType.BATCH_PUSH_STARTED,
            push_time=push_time,
            details={"max_workers": max_workers}
        )
        
        try:
            # 1. 查询指定时间点需要推送的用户
            users = self.config_service.get_users_for_push_time(push_time)
            total_users = len(users)
            
            logger.info(f"找到 {total_users} 个需要推送的用户")
            
            if total_users == 0:
                logger.info("没有需要推送的用户，任务结束")
                return PushBatchResult(
                    total_users=0,
                    success_count=0,
                    failed_count=0,
                    skipped_count=0,
                    push_results=[]
                )
            
            # 2. 检查推送去重，筛选出需要推送的用户
            push_date = date.today()
            users_to_push = []
            skipped_users = []
            
            for user in users:
                # 检查是否已经推送过
                is_duplicate = self.record_repository.check_duplicate_push(
                    user_id=user.id,
                    push_date=push_date,
                    push_time=push_time
                )
                
                if is_duplicate:
                    logger.info(f"用户 {user.id} 今日已推送，跳过")
                    # 记录重复推送跳过事件
                    log_push_event(
                        event_type=PushEventType.DUPLICATE_PUSH_SKIPPED,
                        user_id=user.id,
                        push_time=push_time,
                        details={"push_date": str(push_date)}
                    )
                    skipped_users.append(user.id)
                else:
                    users_to_push.append(user)
            
            logger.info(f"去重后需要推送的用户数: {len(users_to_push)}, 跳过: {len(skipped_users)}")
            
            # 如果所有用户都已推送，直接返回
            if not users_to_push:
                logger.info("所有用户今日已推送，任务结束")
                return PushBatchResult(
                    total_users=total_users,
                    success_count=0,
                    failed_count=0,
                    skipped_count=len(skipped_users),
                    push_results=[]
                )
            
            # 3. 使用线程池并发处理多个用户推送
            # 4. 处理单个用户失败不影响其他用户(异常捕获和隔离)
            push_results = []
            success_count = 0
            failed_count = 0
            
            # 使用线程池并发执行推送
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有推送任务
                future_to_user = {
                    executor.submit(self._push_to_user_safe, user.id, push_time): user
                    for user in users_to_push
                }
                
                # 收集结果
                for future in as_completed(future_to_user):
                    user = future_to_user[future]
                    try:
                        result = future.result()
                        push_results.append(result)
                        
                        if result.success:
                            success_count += 1
                            logger.info(f"用户 {user.id} 推送成功")
                        else:
                            failed_count += 1
                            logger.warning(f"用户 {user.id} 推送失败: {result.error_message}")
                    
                    except Exception as e:
                        # 即使获取结果时出错，也不影响其他用户
                        error_msg = f"获取用户 {user.id} 推送结果时异常: {str(e)}"
                        logger.error(error_msg, exc_info=True)
                        
                        failed_count += 1
                        push_results.append(PushResult(
                            user_id=user.id,
                            success=False,
                            channel_results=[],
                            record_id=None,
                            error_message=error_msg
                        ))
            
            # 5. 返回批量推送结果统计
            batch_result = PushBatchResult(
                total_users=total_users,
                success_count=success_count,
                failed_count=failed_count,
                skipped_count=len(skipped_users),
                push_results=push_results
            )
            
            logger.info(
                f"批量推送任务完成: "
                f"总用户数={total_users}, "
                f"成功={success_count}, "
                f"失败={failed_count}, "
                f"跳过={len(skipped_users)}"
            )
            
            # 记录批量推送完成事件
            log_push_event(
                event_type=PushEventType.BATCH_PUSH_COMPLETED,
                push_time=push_time,
                status="completed",
                details={
                    "total_users": total_users,
                    "success_count": success_count,
                    "failed_count": failed_count,
                    "skipped_count": len(skipped_users)
                }
            )
            
            return batch_result
        
        except Exception as e:
            error_msg = f"批量推送任务异常: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # 记录批量推送失败事件
            log_push_event(
                event_type=PushEventType.PUSH_FAILED,
                push_time=push_time,
                status="failed",
                error_message=error_msg,
                log_level=LogLevel.ERROR
            )
            
            # 即使出现异常，也返回结果对象
            return PushBatchResult(
                total_users=0,
                success_count=0,
                failed_count=0,
                skipped_count=0,
                push_results=[]
            )
    
    def _push_to_user_safe(self, user_id: int, push_time: str) -> PushResult:
        """
        安全地向单个用户推送（捕获所有异常）
        
        这是一个包装方法，确保单个用户的推送失败不会影响其他用户
        
        Args:
            user_id: 用户ID
            push_time: 推送时间点
            
        Returns:
            PushResult: 推送结果
        """
        try:
            return self.push_to_user(user_id, push_time)
        except Exception as e:
            error_msg = f"推送过程发生未捕获异常: {str(e)}"
            logger.error(f"用户 {user_id}: {error_msg}", exc_info=True)
            
            return PushResult(
                user_id=user_id,
                success=False,
                channel_results=[],
                record_id=None,
                error_message=error_msg
            )
    
    def push_to_user(self, user_id: int, push_time: str, db_session=None) -> PushResult:
        """
        向单个用户推送报告
        
        实现步骤:
        1. 获取用户配置
        2. 验证用户是否绑定了推送渠道
        3. 生成报告(调用ReportService)
        4. 根据配置选择推送渠道
        5. 创建推送记录(状态为processing)
        6. 处理多渠道推送(并行发送)
        7. 处理渠道失败隔离(一个渠道失败不影响其他渠道)
        8. 更新推送记录状态(success/partial_success/failed)
        
        Args:
            user_id: 用户ID
            push_time: 推送时间点 (如 "09:30")
            db_session: 数据库会话（可选，用于测试）
            
        Returns:
            PushResult: 推送结果
        """
        logger.info(f"开始向用户 {user_id} 推送报告，推送时间: {push_time}")
        
        # 记录推送开始事件
        log_push_event(
            event_type=PushEventType.PUSH_STARTED,
            user_id=user_id,
            push_time=push_time
        )
        
        try:
            # 1. 获取用户配置
            config = self.config_service.get_user_config(user_id)
            if not config:
                error_msg = f"用户 {user_id} 没有推送配置"
                logger.error(error_msg)
                # 记录用户未配置事件
                log_user_not_configured(user_id=user_id, reason="没有推送配置")
                return PushResult(
                    user_id=user_id,
                    success=False,
                    channel_results=[],
                    record_id=None,
                    error_message=error_msg
                )
            
            # 检查推送是否启用
            if not config.enabled:
                error_msg = f"用户 {user_id} 推送功能已禁用"
                logger.warning(error_msg)
                # 记录用户未配置事件
                log_user_not_configured(user_id=user_id, reason="推送功能已禁用")
                return PushResult(
                    user_id=user_id,
                    success=False,
                    channel_results=[],
                    record_id=None,
                    error_message=error_msg
                )
            
            # 2. 验证用户是否绑定了推送渠道
            # 获取用户信息
            if db_session is None:
                from backend_core.database.db import get_db
                db_session = next(get_db())
            
            user = db_session.query(User).filter(User.id == user_id).first()
            
            if not user:
                error_msg = f"用户 {user_id} 不存在"
                logger.error(error_msg)
                return PushResult(
                    user_id=user_id,
                    success=False,
                    channel_results=[],
                    record_id=None,
                    error_message=error_msg
                )
            
            # 检查是否有可用的推送渠道
            available_channels = []
            for channel in config.channels:
                if channel == 'wechat' and user.wechat_openid:
                    available_channels.append('wechat')
                elif channel == 'email' and user.email:
                    available_channels.append('email')
            
            if not available_channels:
                error_msg = f"用户 {user_id} 没有绑定任何推送渠道"
                logger.warning(error_msg)
                # 记录用户未配置事件
                log_user_not_configured(user_id=user_id, reason="没有绑定任何推送渠道")
                return PushResult(
                    user_id=user_id,
                    success=False,
                    channel_results=[],
                    record_id=None,
                    error_message=error_msg
                )
            
            logger.info(f"用户 {user_id} 可用推送渠道: {available_channels}")
            
            # 3. 生成报告
            logger.info(f"开始为用户 {user_id} 生成报告，类型: {config.report_type}")
            report_result = self.report_service.generate_user_report(
                user_id=user_id,
                report_type=config.report_type,
                stock_codes=config.stock_codes
            )
            
            if not report_result.success:
                error_msg = f"报告生成失败: {report_result.error_message}"
                logger.error(f"用户 {user_id}: {error_msg}")
                # 记录报告生成失败事件
                log_push_event(
                    event_type=PushEventType.REPORT_GENERATION_FAILED,
                    user_id=user_id,
                    error_message=report_result.error_message,
                    details={"report_type": config.report_type}
                )
                return PushResult(
                    user_id=user_id,
                    success=False,
                    channel_results=[],
                    record_id=None,
                    error_message=error_msg
                )
            
            # 如果用户没有自选股，返回成功但不推送
            if not report_result.report_info.has_data:
                logger.warning(f"用户 {user_id} 没有自选股数据，跳过推送")
                # 记录数据缺失事件
                log_data_missing(
                    user_id=user_id,
                    missing_stocks=[],
                    context="no_watchlist_data"
                )
                return PushResult(
                    user_id=user_id,
                    success=True,
                    channel_results=[],
                    record_id=None,
                    error_message="用户没有自选股数据"
                )
            
            logger.info(f"用户 {user_id} 报告生成成功: {report_result.file_path}")
            
            # 记录报告生成成功事件
            log_push_event(
                event_type=PushEventType.REPORT_GENERATED,
                user_id=user_id,
                details={
                    "report_type": config.report_type,
                    "file_path": report_result.file_path,
                    "stock_count": report_result.report_info.stock_count
                }
            )
            
            # 如果有数据缺失的股票，记录警告
            if report_result.report_info.missing_data_stocks:
                log_data_missing(
                    user_id=user_id,
                    missing_stocks=report_result.report_info.missing_data_stocks,
                    context="report_generation"
                )
            
            # 5. 创建推送记录(状态为processing)
            push_date = date.today()
            
            # 初始化渠道状态
            initial_channel_status = {channel: "pending" for channel in available_channels}
            
            record = self.record_repository.create_record(
                user_id=user_id,
                push_date=push_date,
                push_time=push_time,
                report_type=config.report_type,
                channel_status=initial_channel_status,
                report_file_path=report_result.file_path,
                max_retries=3
            )
            
            logger.info(f"创建推送记录成功: record_id={record.id}")
            
            # 更新记录状态为processing
            self.record_repository.update_record_status(
                record_id=record.id,
                status="processing",
                started_at=datetime.now()
            )
            
            # 6. 处理多渠道推送(并行发送)
            # 7. 处理渠道失败隔离(一个渠道失败不影响其他渠道)
            channel_results = []
            channel_status = {}
            error_messages = {}
            
            for channel in available_channels:
                try:
                    if channel == 'wechat':
                        result = self._send_via_wechat(
                            user=user,
                            report_path=report_result.file_path,
                            report_info=report_result.report_info
                        )
                    elif channel == 'email':
                        result = self._send_via_email(
                            user=user,
                            report_path=report_result.file_path,
                            report_info=report_result.report_info
                        )
                    else:
                        result = ChannelResult(
                            channel=channel,
                            success=False,
                            error_message=f"不支持的推送渠道: {channel}"
                        )
                    
                    channel_results.append(result)
                    channel_status[channel] = "success" if result.success else "failed"
                    error_messages[channel] = result.error_message
                    
                    logger.info(f"用户 {user_id} 渠道 {channel} 推送结果: {result.success}")
                    
                except Exception as e:
                    error_msg = f"渠道 {channel} 推送异常: {str(e)}"
                    logger.error(f"用户 {user_id}: {error_msg}")
                    
                    result = ChannelResult(
                        channel=channel,
                        success=False,
                        error_message=error_msg
                    )
                    channel_results.append(result)
                    channel_status[channel] = "failed"
                    error_messages[channel] = error_msg
            
            # 8. 更新推送记录状态(success/partial_success/failed)
            success_count = sum(1 for r in channel_results if r.success)
            total_count = len(channel_results)
            
            if success_count == total_count:
                final_status = "success"
            elif success_count > 0:
                final_status = "partial_success"
            else:
                final_status = "failed"
            
            self.record_repository.update_record_status(
                record_id=record.id,
                status=final_status,
                channel_status=channel_status,
                error_messages=error_messages,
                completed_at=datetime.now()
            )
            
            logger.info(f"用户 {user_id} 推送完成，最终状态: {final_status}, 成功渠道: {success_count}/{total_count}")
            
            # 记录推送完成事件
            log_push_event(
                event_type=PushEventType.PUSH_COMPLETED,
                user_id=user_id,
                record_id=record.id,
                push_time=push_time,
                status=final_status,
                details={
                    "success_channels": success_count,
                    "total_channels": total_count,
                    "channel_status": channel_status
                }
            )
            
            return PushResult(
                user_id=user_id,
                success=(success_count > 0),
                channel_results=channel_results,
                record_id=record.id,
                error_message=None if success_count > 0 else "所有渠道推送失败"
            )
            
        except Exception as e:
            error_msg = f"推送过程异常: {str(e)}"
            logger.error(f"用户 {user_id}: {error_msg}", exc_info=True)
            # 记录推送失败事件
            log_push_failure(
                user_id=user_id,
                error_message=error_msg
            )
            return PushResult(
                user_id=user_id,
                success=False,
                channel_results=[],
                record_id=None,
                error_message=error_msg
            )
    
    def _send_via_wechat(
        self, 
        user: User, 
        report_path: str, 
        report_info: ReportInfo
    ) -> ChannelResult:
        """
        通过微信发送报告
        
        Args:
            user: 用户对象
            report_path: 报告文件路径
            report_info: 报告信息
            
        Returns:
            ChannelResult: 微信推送结果
        """
        try:
            # 检查用户是否绑定了微信
            if not user.wechat_openid:
                error_msg = f"用户 {user.id} 未绑定微信"
                logger.warning(error_msg)
                return ChannelResult(
                    channel='wechat',
                    success=False,
                    error_message=error_msg
                )
            
            # 格式化推送消息
            text_message = self._format_push_message(user, report_info)
            
            # 1. 先发送文本消息
            logger.info(f"向用户 {user.id} 发送微信文本消息")
            text_success = self.wechat_service.send_text_message(
                user_ids=[user.wechat_openid],
                content=text_message
            )
            
            if not text_success:
                error_msg = "微信文本消息发送失败"
                logger.error(f"用户 {user.id}: {error_msg}")
                # 记录渠道发送失败事件
                log_push_event(
                    event_type=PushEventType.CHANNEL_SEND_FAILED,
                    user_id=user.id,
                    channel='wechat',
                    error_message=error_msg,
                    details={"step": "text_message"}
                )
                return ChannelResult(
                    channel='wechat',
                    success=False,
                    error_message=error_msg
                )
            
            # 2. 然后发送CSV文件
            logger.info(f"向用户 {user.id} 发送微信文件消息")
            import os
            file_name = os.path.basename(report_path)
            file_success = self.wechat_service.send_file_message(
                user_ids=[user.wechat_openid],
                file_path=report_path,
                file_name=file_name
            )
            
            if not file_success:
                error_msg = "微信文件消息发送失败"
                logger.error(f"用户 {user.id}: {error_msg}")
                # 记录渠道发送失败事件
                log_push_event(
                    event_type=PushEventType.CHANNEL_SEND_FAILED,
                    user_id=user.id,
                    channel='wechat',
                    error_message=error_msg,
                    details={"step": "file_message"}
                )
                return ChannelResult(
                    channel='wechat',
                    success=False,
                    error_message=error_msg
                )
            
            logger.info(f"用户 {user.id} 微信推送成功")
            # 记录渠道发送成功事件
            log_push_event(
                event_type=PushEventType.CHANNEL_SEND_SUCCESS,
                user_id=user.id,
                channel='wechat'
            )
            return ChannelResult(
                channel='wechat',
                success=True,
                error_message=None
            )
            
        except Exception as e:
            error_msg = f"微信推送异常: {str(e)}"
            logger.error(f"用户 {user.id}: {error_msg}")
            return ChannelResult(
                channel='wechat',
                success=False,
                error_message=error_msg
            )
    
    def _send_via_email(
        self, 
        user: User, 
        report_path: str, 
        report_info: ReportInfo
    ) -> ChannelResult:
        """
        通过邮件发送报告
        
        Args:
            user: 用户对象
            report_path: 报告文件路径
            report_info: 报告信息
            
        Returns:
            ChannelResult: 邮件推送结果
        """
        try:
            # 检查用户是否绑定了邮箱
            if not user.email:
                error_msg = f"用户 {user.id} 未绑定邮箱"
                logger.warning(error_msg)
                return ChannelResult(
                    channel='email',
                    success=False,
                    error_message=error_msg
                )
            
            # 验证邮箱格式
            if not self.email_service.validate_email(user.email):
                error_msg = f"用户 {user.id} 邮箱格式无效: {user.email}"
                logger.error(error_msg)
                return ChannelResult(
                    channel='email',
                    success=False,
                    error_message=error_msg
                )
            
            # 构建邮件主题
            subject = f"股票报告推送 - {report_info.report_date}"
            
            # 构建HTML邮件正文
            content = self._format_email_content(user, report_info)
            
            # 发送邮件
            logger.info(f"向用户 {user.id} 发送邮件: {user.email}")
            result = self.email_service.send_report_email(
                to_email=user.email,
                subject=subject,
                content=content,
                attachment_path=report_path
            )
            
            if result.success:
                logger.info(f"用户 {user.id} 邮件推送成功")
                # 记录渠道发送成功事件
                log_push_event(
                    event_type=PushEventType.CHANNEL_SEND_SUCCESS,
                    user_id=user.id,
                    channel='email',
                    details={"to_email": user.email}
                )
                return ChannelResult(
                    channel='email',
                    success=True,
                    error_message=None
                )
            else:
                error_msg = f"邮件发送失败: {result.error}"
                logger.error(f"用户 {user.id}: {error_msg}")
                # 记录渠道发送失败事件
                log_push_event(
                    event_type=PushEventType.CHANNEL_SEND_FAILED,
                    user_id=user.id,
                    channel='email',
                    error_message=result.error,
                    details={"to_email": user.email}
                )
                return ChannelResult(
                    channel='email',
                    success=False,
                    error_message=error_msg
                )
            
        except EmailSendException as e:
            error_msg = f"邮件发送异常: {str(e)}"
            logger.error(f"用户 {user.id}: {error_msg}")
            # 记录服务不可用事件
            log_service_unavailable(
                service_name='email',
                user_id=user.id,
                channel='email',
                error_message=error_msg
            )
            return ChannelResult(
                channel='email',
                success=False,
                error_message=error_msg
            )
        except Exception as e:
            error_msg = f"邮件推送异常: {str(e)}"
            logger.error(f"用户 {user.id}: {error_msg}")
            # 记录渠道发送失败事件
            log_push_event(
                event_type=PushEventType.CHANNEL_SEND_FAILED,
                user_id=user.id,
                channel='email',
                error_message=error_msg
            )
            return ChannelResult(
                channel='email',
                success=False,
                error_message=error_msg
            )
    
    def _format_push_message(self, user: User, report_info: ReportInfo) -> str:
        """
        格式化推送消息内容（用于微信文本消息）
        
        Args:
            user: 用户对象
            report_info: 报告信息
            
        Returns:
            str: 格式化后的消息文本
        """
        report_type_name = "汇总报告" if report_info.report_type == "summary" else "详细报告"
        
        message = f"""【股票报告推送】

尊敬的 {user.username}，您好！

您的股票{report_type_name}已生成：

📅 报告日期: {report_info.report_date}
📊 股票数量: {report_info.stock_count} 只
📄 报告类型: {report_type_name}
"""
        
        # 如果有数据缺失，添加提示
        if report_info.missing_data_stocks:
            message += f"\n⚠️ 数据缺失股票: {len(report_info.missing_data_stocks)} 只"
        
        message += "\n\n报告文件将在下一条消息中发送，请注意查收。"
        
        return message
    
    def _format_email_content(self, user: User, report_info: ReportInfo) -> str:
        """
        格式化邮件HTML内容
        
        Args:
            user: 用户对象
            report_info: 报告信息
            
        Returns:
            str: HTML格式的邮件正文
        """
        report_type_name = "汇总报告" if report_info.report_type == "summary" else "详细报告"
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background-color: #4CAF50;
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 5px 5px 0 0;
        }}
        .content {{
            background-color: #f9f9f9;
            padding: 20px;
            border: 1px solid #ddd;
            border-radius: 0 0 5px 5px;
        }}
        .info-item {{
            margin: 10px 0;
            padding: 10px;
            background-color: white;
            border-left: 4px solid #4CAF50;
        }}
        .warning {{
            background-color: #fff3cd;
            border-left-color: #ffc107;
            color: #856404;
        }}
        .footer {{
            margin-top: 20px;
            text-align: center;
            color: #666;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>📊 股票报告推送</h2>
        </div>
        <div class="content">
            <p>尊敬的 <strong>{user.username}</strong>，您好！</p>
            <p>您的股票{report_type_name}已生成，详细信息如下：</p>
            
            <div class="info-item">
                <strong>📅 报告日期:</strong> {report_info.report_date}
            </div>
            
            <div class="info-item">
                <strong>📊 股票数量:</strong> {report_info.stock_count} 只
            </div>
            
            <div class="info-item">
                <strong>📄 报告类型:</strong> {report_type_name}
            </div>
            
            <div class="info-item">
                <strong>📦 文件大小:</strong> {report_info.file_size / 1024:.2f} KB
            </div>
"""
        
        # 如果有数据缺失，添加警告
        if report_info.missing_data_stocks:
            html_content += f"""
            <div class="info-item warning">
                <strong>⚠️ 数据缺失提示:</strong> 有 {len(report_info.missing_data_stocks)} 只股票的数据缺失，
                已在报告中标注。
            </div>
"""
        
        html_content += """
            <p style="margin-top: 20px;">报告文件已作为附件发送，请下载查看。</p>
        </div>
        <div class="footer">
            <p>此邮件由系统自动发送，请勿回复。</p>
        </div>
    </div>
</body>
</html>
"""
        
        return html_content
    
    def retry_failed_push(self, record_id: int) -> PushResult:
        """
        重试失败的推送
        
        实现步骤:
        1. 根据record_id获取推送记录
        2. 检查是否已达到最大重试次数
        3. 实现指数退避策略(1分钟、5分钟、15分钟)
        4. 更新重试次数
        5. 重新执行推送流程
        6. 更新推送记录状态和重试结果
        7. 如果达到最大重试次数,标记为最终失败
        
        Args:
            record_id: 推送记录ID
            
        Returns:
            PushResult: 重试结果
        """
        logger.info(f"开始重试推送记录: record_id={record_id}")
        
        # 记录重试开始事件
        log_push_event(
            event_type=PushEventType.RETRY_STARTED,
            record_id=record_id
        )
        
        try:
            # 1. 根据record_id获取推送记录
            record = self.record_repository.get_record_by_id(record_id)
            
            if not record:
                error_msg = f"推送记录不存在: record_id={record_id}"
                logger.error(error_msg)
                return PushResult(
                    user_id=0,
                    success=False,
                    channel_results=[],
                    record_id=record_id,
                    error_message=error_msg
                )
            
            user_id = record.user_id
            logger.info(f"找到推送记录: user_id={user_id}, 当前重试次数={record.retry_count}, 最大重试次数={record.max_retries}")
            
            # 2. 检查是否已达到最大重试次数
            if record.retry_count >= record.max_retries:
                error_msg = f"已达到最大重试次数 ({record.max_retries})，无法继续重试"
                logger.warning(f"记录 {record_id}: {error_msg}")
                
                # 7. 如果达到最大重试次数，标记为最终失败
                self.record_repository.update_record_status(
                    record_id=record_id,
                    status="failed_final",
                    completed_at=datetime.now()
                )
                
                return PushResult(
                    user_id=user_id,
                    success=False,
                    channel_results=[],
                    record_id=record_id,
                    error_message=error_msg
                )
            
            # 3. 实现指数退避策略(1分钟、5分钟、15分钟)
            # 计算应该等待的时间（秒）
            retry_delays = [60, 300, 900]  # 1分钟、5分钟、15分钟
            expected_delay = retry_delays[min(record.retry_count, len(retry_delays) - 1)]
            
            # 检查是否已经等待足够的时间
            if record.completed_at:
                elapsed_seconds = (datetime.now() - record.completed_at).total_seconds()
                if elapsed_seconds < expected_delay:
                    remaining_seconds = expected_delay - elapsed_seconds
                    error_msg = f"重试时间未到，还需等待 {remaining_seconds:.0f} 秒"
                    logger.warning(f"记录 {record_id}: {error_msg}")
                    return PushResult(
                        user_id=user_id,
                        success=False,
                        channel_results=[],
                        record_id=record_id,
                        error_message=error_msg
                    )
            
            # 4. 更新重试次数
            new_retry_count = record.retry_count + 1
            logger.info(f"记录 {record_id}: 开始第 {new_retry_count} 次重试")
            
            # 更新记录状态为processing
            self.record_repository.update_record_status(
                record_id=record_id,
                status="processing",
                retry_count=new_retry_count,
                started_at=datetime.now()
            )
            
            # 5. 重新执行推送流程
            # 获取用户信息
            from backend_core.database.db import get_db
            db_session = next(get_db())
            
            user = db_session.query(User).filter(User.id == user_id).first()
            
            if not user:
                error_msg = f"用户不存在: user_id={user_id}"
                logger.error(error_msg)
                
                # 6. 更新推送记录状态和重试结果
                self.record_repository.update_record_status(
                    record_id=record_id,
                    status="failed",
                    error_messages={"system": error_msg},
                    completed_at=datetime.now()
                )
                
                return PushResult(
                    user_id=user_id,
                    success=False,
                    channel_results=[],
                    record_id=record_id,
                    error_message=error_msg
                )
            
            # 获取用户配置
            config = self.config_service.get_user_config(user_id)
            if not config:
                error_msg = f"用户配置不存在: user_id={user_id}"
                logger.error(error_msg)
                
                self.record_repository.update_record_status(
                    record_id=record_id,
                    status="failed",
                    error_messages={"system": error_msg},
                    completed_at=datetime.now()
                )
                
                return PushResult(
                    user_id=user_id,
                    success=False,
                    channel_results=[],
                    record_id=record_id,
                    error_message=error_msg
                )
            
            # 检查推送是否启用
            if not config.enabled:
                error_msg = f"用户推送功能已禁用: user_id={user_id}"
                logger.warning(error_msg)
                
                self.record_repository.update_record_status(
                    record_id=record_id,
                    status="failed",
                    error_messages={"system": error_msg},
                    completed_at=datetime.now()
                )
                
                return PushResult(
                    user_id=user_id,
                    success=False,
                    channel_results=[],
                    record_id=record_id,
                    error_message=error_msg
                )
            
            # 确定需要重试的渠道（只重试失败的渠道）
            channels_to_retry = []
            for channel, status in record.channel_status.items():
                if status == "failed" or status == "pending":
                    # 检查用户是否仍然绑定了该渠道
                    if channel == 'wechat' and user.wechat_openid:
                        channels_to_retry.append('wechat')
                    elif channel == 'email' and user.email:
                        channels_to_retry.append('email')
            
            if not channels_to_retry:
                error_msg = "没有需要重试的渠道或用户已解绑所有失败渠道"
                logger.warning(f"记录 {record_id}: {error_msg}")
                
                # 如果所有渠道都已成功或用户已解绑，标记为成功
                all_success = all(status == "success" for status in record.channel_status.values())
                final_status = "success" if all_success else "partial_success"
                
                self.record_repository.update_record_status(
                    record_id=record_id,
                    status=final_status,
                    completed_at=datetime.now()
                )
                
                return PushResult(
                    user_id=user_id,
                    success=all_success,
                    channel_results=[],
                    record_id=record_id,
                    error_message=error_msg if not all_success else None
                )
            
            logger.info(f"记录 {record_id}: 需要重试的渠道: {channels_to_retry}")
            
            # 获取报告信息
            if not record.report_file_path:
                error_msg = "推送记录中没有报告文件路径"
                logger.error(f"记录 {record_id}: {error_msg}")
                
                self.record_repository.update_record_status(
                    record_id=record_id,
                    status="failed",
                    error_messages={"system": error_msg},
                    completed_at=datetime.now()
                )
                
                return PushResult(
                    user_id=user_id,
                    success=False,
                    channel_results=[],
                    record_id=record_id,
                    error_message=error_msg
                )
            
            # 获取报告信息
            report_info = self.report_service.get_report_info(record.report_file_path)
            
            # 重试各个失败的渠道
            channel_results = []
            updated_channel_status = dict(record.channel_status)  # 复制现有状态
            updated_error_messages = dict(record.error_messages) if record.error_messages else {}
            
            for channel in channels_to_retry:
                try:
                    if channel == 'wechat':
                        result = self._send_via_wechat(
                            user=user,
                            report_path=record.report_file_path,
                            report_info=report_info
                        )
                    elif channel == 'email':
                        result = self._send_via_email(
                            user=user,
                            report_path=record.report_file_path,
                            report_info=report_info
                        )
                    else:
                        result = ChannelResult(
                            channel=channel,
                            success=False,
                            error_message=f"不支持的推送渠道: {channel}"
                        )
                    
                    channel_results.append(result)
                    updated_channel_status[channel] = "success" if result.success else "failed"
                    updated_error_messages[channel] = result.error_message
                    
                    logger.info(f"记录 {record_id} 渠道 {channel} 重试结果: {result.success}")
                    
                except Exception as e:
                    error_msg = f"渠道 {channel} 重试异常: {str(e)}"
                    logger.error(f"记录 {record_id}: {error_msg}", exc_info=True)
                    
                    result = ChannelResult(
                        channel=channel,
                        success=False,
                        error_message=error_msg
                    )
                    channel_results.append(result)
                    updated_channel_status[channel] = "failed"
                    updated_error_messages[channel] = error_msg
            
            # 6. 更新推送记录状态和重试结果
            # 计算最终状态
            success_count = sum(1 for status in updated_channel_status.values() if status == "success")
            total_count = len(updated_channel_status)
            
            if success_count == total_count:
                final_status = "success"
            elif success_count > 0:
                final_status = "partial_success"
            else:
                # 如果仍然全部失败，检查是否达到最大重试次数
                if new_retry_count >= record.max_retries:
                    final_status = "failed_final"
                    logger.warning(f"记录 {record_id}: 达到最大重试次数，标记为最终失败")
                else:
                    final_status = "failed"
            
            self.record_repository.update_record_status(
                record_id=record_id,
                status=final_status,
                channel_status=updated_channel_status,
                error_messages=updated_error_messages,
                completed_at=datetime.now()
            )
            
            logger.info(
                f"记录 {record_id} 重试完成: "
                f"最终状态={final_status}, "
                f"成功渠道={success_count}/{total_count}, "
                f"重试次数={new_retry_count}/{record.max_retries}"
            )
            
            # 记录重试完成事件
            log_push_event(
                event_type=PushEventType.RETRY_COMPLETED,
                user_id=user_id,
                record_id=record_id,
                status=final_status,
                details={
                    "success_channels": success_count,
                    "total_channels": total_count,
                    "retry_count": new_retry_count,
                    "max_retries": record.max_retries,
                    "channel_status": updated_channel_status
                }
            )
            
            return PushResult(
                user_id=user_id,
                success=(success_count > 0),
                channel_results=channel_results,
                record_id=record_id,
                error_message=None if success_count > 0 else "所有渠道重试失败"
            )
            
        except Exception as e:
            error_msg = f"重试过程异常: {str(e)}"
            logger.error(f"记录 {record_id}: {error_msg}", exc_info=True)
            
            # 尝试更新记录状态
            try:
                self.record_repository.update_record_status(
                    record_id=record_id,
                    status="failed",
                    error_messages={"system": error_msg},
                    completed_at=datetime.now()
                )
            except Exception as update_error:
                logger.error(f"更新记录状态失败: {str(update_error)}")
            
            return PushResult(
                user_id=0,
                success=False,
                channel_results=[],
                record_id=record_id,
                error_message=error_msg
            )
