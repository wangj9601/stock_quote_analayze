"""
推送服务核心 (PushService)
负责协调报告生成、渠道选择、消息发送
"""

from datetime import datetime, date
from typing import List, Optional, Dict, Any, Set
from dataclasses import dataclass
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend_api.models import User
from backend_api.services.email_service import EmailService, EmailSendException
from backend_api.services.config_service import ConfigService
from backend_api.services.report_service import ReportService, ReportInfo
from backend_api.services.record_repository import RecordRepository
from backend_core.wechat.wechat_service import WeChatService
from backend_core.wechat.wechat_config import normalize_wechat_app_profile
from backend_api.services.logging_utils import (
    log_push_event, log_data_missing, log_service_unavailable,
    log_push_failure, log_user_not_configured,
    PushEventType, LogLevel
)

logger = logging.getLogger(__name__)

_wechat_service_lock = threading.Lock()
_wechat_service_by_key: Dict[str, WeChatService] = {}


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

    def _get_wechat_service_for_push_config(self, push_config: Any) -> WeChatService:
        """按推送任务 wechat_app_profile 返回 WeChatService；空 profile 复用注入的默认实例（与单测 Mock 一致）。"""
        raw = getattr(push_config, "wechat_app_profile", None)
        key = normalize_wechat_app_profile(raw) or ""
        if not key:
            return self.wechat_service
        with _wechat_service_lock:
            if key not in _wechat_service_by_key:
                _wechat_service_by_key[key] = WeChatService(app_profile=key)
            return _wechat_service_by_key[key]

    @staticmethod
    def _wechat_recipient_userids(user: User, config: Optional[Any] = None) -> List[str]:
        """企业微信接收人：优先 user_push_configs.wechat_notify_userids，否则用户绑定。"""
        raw = getattr(config, "wechat_notify_userids", None) if config is not None else None
        if raw is not None:
            if isinstance(raw, list):
                out = [str(x).strip() for x in raw if str(x).strip()]
                if out:
                    return out
            if isinstance(raw, str) and raw.strip():
                return [p.strip() for p in raw.replace("|", ",").split(",") if p.strip()]
        one = getattr(user, "wechat_userid", None) or getattr(user, "wechat_openid", None)
        return [one] if one else []
    
    def execute_scheduled_push(self, push_time: str, max_workers: int = 1) -> PushBatchResult:
        """
        执行定时推送任务（批量推送）
        
        ConfigService/ReportService/RecordRepository 共用同一 DB Session，非线程安全，
        因此默认 max_workers=1，避免多线程并发访问同一 Session 导致 InvalidRequestError。
        
        实现步骤:
        1. 查询指定时间点需要推送的用户(调用ConfigService.get_users_for_push_time)
        2. 使用RecordRepository.check_duplicate_push检查推送去重
        3. 串行或线程池处理各用户推送（默认串行）
        4. 处理单个用户失败不影响其他用户(异常捕获和隔离)
        5. 返回批量推送结果统计(成功数、失败数、跳过数)
        
        Args:
            push_time: 推送时间点 (如 "09:30")
            max_workers: 最大并发工作线程数，默认1（Session 非线程安全）
            
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
            # 1. 查询指定时间点需要推送的「任务」列表（同一用户可有多个任务，不同 report_type）
            tasks = self.config_service.get_configs_for_push_time(push_time)
            total_tasks = len(tasks)
            logger.info(f"找到 {total_tasks} 个需要推送的任务")
            if total_tasks == 0:
                logger.info("没有需要推送的任务，任务结束")
                return PushBatchResult(
                    total_users=0,
                    success_count=0,
                    failed_count=0,
                    skipped_count=0,
                    push_results=[]
                )
            push_date = date.today()

            # 2. 按 (user, report_type, push_time) 去重：已推送过的任务跳过
            tasks_to_push = []
            skipped_count = 0
            for config, user in tasks:
                # 3倍量观察股：关闭时跳过扫描/复核微信与邮件推送
                if config.report_type in (
                    "triple_volume_observe_scan",
                    "triple_volume_observe_eval",
                ):
                    try:
                        from backend_core.strategies.triple_volume_observe.env_config import (
                            is_triple_volume_observe_enabled,
                        )

                        tvo_on = is_triple_volume_observe_enabled()
                    except Exception:
                        tvo_on = False
                    if not tvo_on:
                        logger.info(
                            "用户 %s 任务 %s 跳过（TRIPLE_VOLUME_OBSERVE_ENABLED=false）",
                            user.id,
                            config.report_type,
                        )
                        skipped_count += 1
                        continue
                # GMS：按用户自选股涉及的 CN/HK 分别对照 trading_calendar，仅当持仓侧均为休市日才跳过
                if config.report_type == "gms_daily":
                    skip_gms, gms_skip_reason = False, ""
                    mkt: Set[str] = set()
                    try:
                        from backend_api.utils.trading_calendar_utils import (
                            should_skip_gms_scheduled_notification,
                        )

                        wl = self.report_service.get_user_watchlist(
                            user.id, config.stock_codes
                        )
                        mkt = {w["market"] for w in wl} if wl else set()
                        skip_gms, gms_skip_reason = (
                            should_skip_gms_scheduled_notification(
                                self.config_service.db, push_date, mkt
                            )
                        )
                    except Exception as e:
                        logger.warning(
                            "GMS 休市日判定异常 user=%s: %s", user.id, e
                        )
                    if skip_gms:
                        logger.info(
                            "用户 %s 任务 gms_daily 跳过（%s）",
                            user.id,
                            gms_skip_reason,
                        )
                        log_push_event(
                            event_type=PushEventType.GMS_NON_TRADING_SKIPPED,
                            user_id=user.id,
                            push_time=push_time,
                            details={
                                "push_date": str(push_date),
                                "report_type": "gms_daily",
                                "reason": gms_skip_reason,
                                "watchlist_markets": sorted(mkt),
                            },
                        )
                        skipped_count += 1
                        continue
                # URT：仅 A 股策略，A 股休市日跳过
                if config.report_type == "urt_daily":
                    skip_urt = False
                    urt_skip_reason = ""
                    try:
                        from backend_api.utils.trading_calendar_utils import (
                            is_market_session_closed,
                        )

                        if is_market_session_closed(
                            self.config_service.db, "CN", push_date
                        ):
                            skip_urt = True
                            urt_skip_reason = "A股休市日"
                    except Exception as e:
                        logger.warning(
                            "URT 休市日判定异常 user=%s: %s", user.id, e
                        )
                    if skip_urt:
                        logger.info(
                            "用户 %s 任务 urt_daily 跳过（%s）",
                            user.id,
                            urt_skip_reason,
                        )
                        log_push_event(
                            event_type=PushEventType.GMS_NON_TRADING_SKIPPED,
                            user_id=user.id,
                            push_time=push_time,
                            details={
                                "push_date": str(push_date),
                                "report_type": "urt_daily",
                                "reason": urt_skip_reason,
                            },
                        )
                        skipped_count += 1
                        continue
                is_duplicate = self.record_repository.check_duplicate_push(
                    user_id=user.id,
                    push_date=push_date,
                    push_time=push_time,
                    report_type=config.report_type,
                )
                if is_duplicate:
                    logger.info(f"用户 {user.id} 任务 {config.report_type} 今日已推送，跳过")
                    log_push_event(
                        event_type=PushEventType.DUPLICATE_PUSH_SKIPPED,
                        user_id=user.id,
                        push_time=push_time,
                        details={"push_date": str(push_date), "report_type": config.report_type}
                    )
                    skipped_count += 1
                else:
                    tasks_to_push.append((user.id, config.id))
            logger.info(f"去重后需要推送的任务数: {len(tasks_to_push)}, 跳过: {skipped_count}")
            if not tasks_to_push:
                return PushBatchResult(
                    total_users=total_tasks,
                    success_count=0,
                    failed_count=0,
                    skipped_count=skipped_count,
                    push_results=[],
                )
            # 3. 按任务执行推送（传入 config_id，worker 内再查 config）
            push_results = []
            success_count = 0
            failed_count = 0
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_key = {
                    executor.submit(self._push_to_user_safe, uid, push_time, cid): (uid, cid)
                    for uid, cid in tasks_to_push
                }
                for future in as_completed(future_to_key):
                    user_id, _ = future_to_key[future]
                    try:
                        result = future.result()
                        push_results.append(result)
                        if result.success:
                            success_count += 1
                            logger.info(f"用户 {user_id} 推送成功")
                        else:
                            failed_count += 1
                            logger.warning(f"用户 {user_id} 推送失败: {result.error_message}")
                    except Exception as e:
                        error_msg = f"获取用户 {user_id} 推送结果时异常: {str(e)}"
                        logger.error(error_msg, exc_info=True)
                        failed_count += 1
                        push_results.append(PushResult(
                            user_id=user_id,
                            success=False,
                            channel_results=[],
                            record_id=None,
                            error_message=error_msg
                        ))
            
            batch_result = PushBatchResult(
                total_users=total_tasks,
                success_count=success_count,
                failed_count=failed_count,
                skipped_count=skipped_count,
                push_results=push_results
            )
            logger.info(
                f"批量推送任务完成: 总任务数={total_tasks}, 成功={success_count}, 失败={failed_count}, 跳过={skipped_count}"
            )
            log_push_event(
                event_type=PushEventType.BATCH_PUSH_COMPLETED,
                push_time=push_time,
                status="completed",
                details={
                    "total_tasks": total_tasks,
                    "success_count": success_count,
                    "failed_count": failed_count,
                    "skipped_count": skipped_count
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
    
    def _push_to_user_safe(
        self, user_id: int, push_time: str, config_id: Optional[int] = None
    ) -> PushResult:
        """
        安全地向单个用户推送（捕获所有异常）。
        若传入 config_id 则按该任务配置推送；否则按用户当前一条配置推送（兼容）。
        """
        try:
            return self.push_to_user(user_id, push_time, config_id=config_id)
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
    
    def push_to_user(
        self,
        user_id: int,
        push_time: str,
        config_id: Optional[int] = None,
        db_session=None,
    ) -> PushResult:
        """
        向单个用户推送报告。若传入 config_id 则使用该任务配置，否则使用该用户的第一条配置（兼容）。
        """
        logger.info(f"开始向用户 {user_id} 推送报告，推送时间: {push_time}")
        log_push_event(
            event_type=PushEventType.PUSH_STARTED,
            user_id=user_id,
            push_time=push_time
        )
        try:
            if config_id is not None:
                config = self.config_service.get_config_by_id(config_id)
            else:
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

            if config.report_type in (
                "triple_volume_observe_scan",
                "triple_volume_observe_eval",
            ):
                try:
                    from backend_core.strategies.triple_volume_observe.env_config import (
                        is_triple_volume_observe_enabled,
                    )

                    tvo_on = is_triple_volume_observe_enabled()
                except Exception:
                    tvo_on = False
                if not tvo_on:
                    error_msg = (
                        f"用户 {user_id} 任务 {config.report_type} 已停用"
                        "（TRIPLE_VOLUME_OBSERVE_ENABLED=false）"
                    )
                    logger.info(error_msg)
                    return PushResult(
                        user_id=user_id,
                        success=False,
                        channel_results=[],
                        record_id=None,
                        error_message=error_msg,
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
            
            # 检查是否有可用的推送渠道（微信：user_push_configs.wechat_notify_userids 优先，否则 wechat_userid / wechat_openid）
            wechat_targets = self._wechat_recipient_userids(user, config)
            available_channels = []
            wechat_skipped_misconfig = False
            for channel in config.channels:
                if channel == 'wechat' and wechat_targets:
                    wx_svc = self._get_wechat_service_for_push_config(config)
                    if not wx_svc.config.is_configured():
                        prof_disp = getattr(config, "wechat_app_profile", None) or ""
                        logger.warning(
                            "用户 %s: 微信渠道已启用且已有接收人，但企业微信凭证不完整（wechat_app_profile=%s），跳过微信渠道",
                            user_id,
                            prof_disp if prof_disp else "(空=默认 WECHAT_CORP_ID 等)",
                        )
                        wechat_skipped_misconfig = True
                        continue
                    available_channels.append('wechat')
                elif channel == 'email' and user.email:
                    available_channels.append('email')
            
            if not available_channels:
                if wechat_skipped_misconfig and wechat_targets:
                    error_msg = (
                        f"用户 {user_id} 企业微信应用凭证未配置完整。"
                        f"wechat_app_profile={getattr(config, 'wechat_app_profile', None) or '(空=默认)'}；"
                        "默认需 WECHAT_CORP_ID/WECHAT_CORP_SECRET/WECHAT_AGENT_ID；"
                        "命名 profile 需 WECHAT_<PROFILE>_CORP_ID、WECHAT_<PROFILE>_CORP_SECRET、WECHAT_<PROFILE>_AGENT_ID。"
                    )
                    logger.warning(error_msg)
                    log_user_not_configured(user_id=user_id, reason="企业微信凭证不完整")
                    return PushResult(
                        user_id=user_id,
                        success=False,
                        channel_results=[],
                        record_id=None,
                        error_message=error_msg
                    )
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
                            report_info=report_result.report_info,
                            wechat_user_ids=self._wechat_recipient_userids(user, config),
                            push_config=config,
                        )
                    elif channel == 'email':
                        result = self._send_via_email(
                            user=user,
                            report_path=report_result.file_path,
                            report_info=report_result.report_info,
                            push_record_id=record.id,
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
        report_info: ReportInfo,
        wechat_user_ids: Optional[List[str]] = None,
        push_config: Optional[Any] = None,
    ) -> ChannelResult:
        """
        通过微信发送报告

        Args:
            user: 用户对象
            report_path: 报告文件路径
            report_info: 报告信息
            wechat_user_ids: 企业微信 userid 列表（已解析）；空则回退用户绑定
            push_config: 当前推送任务配置；非空时按 wechat_app_profile 选择企业微信应用凭证
        """
        try:
            wx = (
                self._get_wechat_service_for_push_config(push_config)
                if push_config is not None
                else self.wechat_service
            )
            if not wx.config.is_configured():
                prof = getattr(push_config, "wechat_app_profile", None) if push_config is not None else None
                error_msg = (
                    f"企业微信凭证未配置完整（wechat_app_profile={prof or '默认'}）。"
                    "请检查环境变量 WECHAT_* 或 WECHAT_<PROFILE>_*。"
                )
                logger.warning("用户 %s: %s", user.id, error_msg)
                return ChannelResult(channel="wechat", success=False, error_message=error_msg)

            if wechat_user_ids is not None:
                ids = [x for x in wechat_user_ids if x]
            else:
                ids = self._wechat_recipient_userids(user, push_config)
            if not ids:
                error_msg = f"用户 {user.id} 未绑定微信（未设置 wechat_userid 或 wechat_openid）"
                logger.warning(error_msg)
                return ChannelResult(
                    channel='wechat',
                    success=False,
                    error_message=error_msg
                )

            # 格式化推送消息
            text_message = self._format_push_message(user, report_info)

            # 1. 先发送文本消息
            logger.info(f"向用户 {user.id} 发送微信文本消息 -> {ids}")
            text_success = wx.send_text_message(
                user_ids=ids,
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
            file_success = wx.send_file_message(
                user_ids=ids,
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
        report_info: ReportInfo,
        push_record_id: Optional[int] = None,
    ) -> ChannelResult:
        """
        通过邮件发送报告；发送后写入邮件发送日志。
        """
        subject = (
            f"自选股GSM策略指标信号列表 - {report_info.report_date}"
            if report_info.report_type == "gms_daily"
            else f"自选股上升趋势策略信号列表 - {report_info.report_date}"
            if report_info.report_type == "urt_daily"
            else f"成交量异动榜 - {report_info.report_date}"
            if report_info.report_type == "volume_aberration"
            else f"3倍量观察股·爆量侦测 - {report_info.report_date}"
            if report_info.report_type == "triple_volume_observe_scan"
            else f"3倍量观察股·状态复核 - {report_info.report_date}"
            if report_info.report_type == "triple_volume_observe_eval"
            else f"股票报告推送 - {report_info.report_date}"
        )

        def _write_email_log(success: bool, err_msg: Optional[str] = None):
            try:
                self.record_repository.create_email_send_log(
                    user_id=user.id,
                    to_email=user.email or "",
                    subject=subject,
                    report_type=report_info.report_type,
                    success=success,
                    error_message=err_msg,
                    push_record_id=push_record_id,
                )
            except Exception as log_ex:
                logger.warning("写入邮件发送日志失败: %s", log_ex)

        try:
            if not user.email:
                error_msg = f"用户 {user.id} 未绑定邮箱"
                logger.warning(error_msg)
                return ChannelResult(channel="email", success=False, error_message=error_msg)
            if not self.email_service.validate_email(user.email):
                error_msg = f"用户 {user.id} 邮箱格式无效: {user.email}"
                logger.error(error_msg)
                return ChannelResult(channel="email", success=False, error_message=error_msg)

            content = self._format_email_content(user, report_info)
            logger.info("向用户 %s 发送邮件: %s", user.id, user.email)
            result = self.email_service.send_report_email(
                to_email=user.email,
                subject=subject,
                content=content,
                attachment_path=report_path,
            )

            if result.success:
                _write_email_log(success=True)
                log_push_event(
                    event_type=PushEventType.CHANNEL_SEND_SUCCESS,
                    user_id=user.id,
                    channel="email",
                    details={"to_email": user.email},
                )
                return ChannelResult(channel="email", success=True, error_message=None)
            else:
                _write_email_log(success=False, err_msg=result.error)
                log_push_event(
                    event_type=PushEventType.CHANNEL_SEND_FAILED,
                    user_id=user.id,
                    channel="email",
                    error_message=result.error,
                    details={"to_email": user.email},
                )
                return ChannelResult(
                    channel="email",
                    success=False,
                    error_message=result.error or "发送失败",
                )
        except EmailSendException as e:
            _write_email_log(success=False, err_msg=str(e))
            log_service_unavailable(
                service_name="email",
                user_id=user.id,
                channel="email",
                error_message=str(e),
            )
            return ChannelResult(channel="email", success=False, error_message=str(e))
        except Exception as e:
            _write_email_log(success=False, err_msg=str(e))
            log_push_event(
                event_type=PushEventType.CHANNEL_SEND_FAILED,
                user_id=user.id,
                channel="email",
                error_message=str(e),
            )
            return ChannelResult(channel="email", success=False, error_message=str(e))
    
    def _format_push_message(self, user: User, report_info: ReportInfo) -> str:
        """
        格式化推送消息内容（用于微信文本消息）
        
        Args:
            user: 用户对象
            report_info: 报告信息
            
        Returns:
            str: 格式化后的消息文本
        """
        if report_info.report_type == "gms_daily":
            report_type_name = "自选股GSM策略指标信号列表"
        elif report_info.report_type == "urt_daily":
            report_type_name = "自选股上升趋势策略信号列表"
        elif report_info.report_type == "volume_aberration":
            report_type_name = "成交量异动榜"
        elif report_info.report_type == "triple_volume_observe_scan":
            report_type_name = "3倍量观察股·爆量侦测"
        elif report_info.report_type == "triple_volume_observe_eval":
            report_type_name = "3倍量观察股·状态复核"
        elif report_info.report_type == "summary":
            report_type_name = "汇总报告"
        else:
            report_type_name = "详细报告"
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
        if report_info.report_type == "gms_daily":
            report_type_name = "自选股GSM策略指标信号列表"
        elif report_info.report_type == "urt_daily":
            report_type_name = "自选股上升趋势策略信号列表"
        elif report_info.report_type == "volume_aberration":
            report_type_name = "成交量异动榜"
        elif report_info.report_type == "triple_volume_observe_scan":
            report_type_name = "3倍量观察股·爆量侦测"
        elif report_info.report_type == "triple_volume_observe_eval":
            report_type_name = "3倍量观察股·状态复核"
        elif report_info.report_type == "summary":
            report_type_name = "汇总报告"
        else:
            report_type_name = "详细报告"

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
            
            # 获取用户配置（按推送记录上的 report_type 匹配任务，避免多任务用户重试错配）
            config_retry = self.config_service.get_config_by_user_and_report_type(
                user_id, record.report_type
            )
            if not config_retry:
                error_msg = f"用户配置不存在: user_id={user_id}, report_type={record.report_type}"
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
            if not config_retry.enabled:
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
                    # 检查用户是否仍然绑定了该渠道（微信：wechat_userid 或 wechat_openid）
                    wechat_targets = self._wechat_recipient_userids(user, config_retry)
                    if channel == 'wechat' and wechat_targets:
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
                            report_info=report_info,
                            wechat_user_ids=self._wechat_recipient_userids(user, config_retry),
                            push_config=config_retry,
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
