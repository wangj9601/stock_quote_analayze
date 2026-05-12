"""
推送相关的API路由
提供配置管理、推送记录、推送控制和管理员API
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from pydantic import BaseModel, EmailStr
import logging

from backend_api.models import User, UserPushConfig, PushRecord, EmailSenderConfig, EmailSendLog
from backend_api.auth import get_current_user, get_current_admin
from backend_core.database.db import get_db
from backend_api.services.config_service import ConfigService, ConfigUpdate
from backend_api.services.record_repository import RecordRepository
from backend_api.services.push_service import PushService
from backend_api.services.email_service import EmailService, SMTPConfig, EmailSendException
from backend_api.services.report_service import ReportService
from backend_core.wechat.wechat_service import WeChatService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/push", tags=["push"])

VALID_PUSH_REPORT_TYPES = (
    "summary",
    "detailed",
    "gms_daily",
    "volume_aberration",
    "triple_volume_observe_scan",
    "triple_volume_observe_eval",
)


# ==================== Pydantic 模型定义 ====================

class UserPushConfigResponse(BaseModel):
    """用户推送配置响应模型"""
    id: int
    user_id: int
    enabled: bool
    channels: List[str]
    push_times: List[str]
    report_type: str
    stock_codes: Optional[List[str]]
    wechat_notify_userids: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ConfigUpdateRequest(BaseModel):
    """配置更新请求模型"""
    enabled: Optional[bool] = None
    channels: Optional[List[str]] = None
    push_times: Optional[List[str]] = None
    report_type: Optional[str] = None
    stock_codes: Optional[List[str]] = None
    wechat_notify_userids: Optional[List[str]] = None


class ConfigCreateRequest(BaseModel):
    """管理员创建推送配置请求模型（用户来源于 user 表，配置写入 user_push_configs 表）"""
    user_id: int
    enabled: Optional[bool] = True
    channels: Optional[List[str]] = None  # 不传则默认 ["email"]
    push_times: Optional[List[str]] = None  # 不传则默认 ["09:00", "15:00"]
    report_type: Optional[str] = None  # 不传则默认 "summary"
    wechat_notify_userids: Optional[List[str]] = None


class BindWeChatRequest(BaseModel):
    """绑定微信请求模型"""
    wechat_openid: str
    wechat_type: str  # 'personal' 或 'enterprise'


class BindEmailRequest(BaseModel):
    """绑定邮箱请求模型"""
    email: EmailStr


class PushRecordResponse(BaseModel):
    """推送记录响应模型"""
    id: int
    user_id: int
    push_date: date
    push_time: str
    report_type: str
    channel_status: Dict[str, str]
    status: str
    report_file_path: Optional[str]
    error_messages: Optional[Dict[str, str]]
    retry_count: int
    max_retries: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class TriggerPushResponse(BaseModel):
    """手动触发推送响应模型"""
    success: bool
    message: str
    record_id: Optional[int] = None


class PushStatusResponse(BaseModel):
    """推送系统状态响应模型"""
    pending_users_count: int
    last_push_time: Optional[datetime]
    total_records_today: int
    success_records_today: int
    failed_records_today: int


class GlobalControlRequest(BaseModel):
    """全局推送控制请求模型"""
    action: str  # 'pause' 或 'resume'


class PushStatisticsResponse(BaseModel):
    """推送统计数据响应模型"""
    total_users: int
    enabled_users: int
    total_records: int
    success_rate: float
    records_by_status: Dict[str, int]
    records_by_channel: Dict[str, int]


class EmailSenderConfigResponse(BaseModel):
    """发件邮箱配置响应（password 脱敏）"""
    id: int
    host: str
    port: int
    username: str
    password_masked: Optional[str] = None  # 仅显示占位或后几位
    from_email: str
    from_name: str
    use_tls: bool
    updated_at: Optional[datetime] = None


class EmailSenderConfigUpdateRequest(BaseModel):
    """发件邮箱配置更新请求"""
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None  # 不传则保留原密码
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    use_tls: Optional[bool] = None


class EmailSenderConfigTestRequest(BaseModel):
    """测试发信请求"""
    to_email: EmailStr


class EmailSendLogResponse(BaseModel):
    """邮件发送日志响应"""
    id: int
    user_id: int
    username: Optional[str] = None
    to_email: str
    subject: str
    report_type: str
    push_record_id: Optional[int] = None
    sent_at: datetime
    success: bool
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== 依赖注入函数 ====================

def get_config_service(db: Session = Depends(get_db)) -> ConfigService:
    """获取配置服务实例"""
    return ConfigService(db)


def get_record_repository(db: Session = Depends(get_db)) -> RecordRepository:
    """获取记录仓库实例"""
    return RecordRepository(db)


def get_smtp_config_from_db(db: Session) -> Optional[SMTPConfig]:
    """优先从数据库读取发件邮箱配置；无效则返回 None，调用方回退到环境变量。"""
    if EmailSenderConfig is None:
        return None
    row = db.query(EmailSenderConfig).filter(EmailSenderConfig.id == 1).first()
    if not row or not (row.host and row.username):
        return None
    return SMTPConfig(
        host=str(row.host),
        port=int(row.port),
        username=str(row.username),
        password=str(row.password) if row.password else "",
        use_tls=bool(row.use_tls),
        from_email=str(row.from_email) if row.from_email else str(row.username),
        from_name=str(row.from_name) if row.from_name else "股票分析系统",
    )


def get_push_service(db: Session = Depends(get_db)) -> PushService:
    """获取推送服务实例。发件邮箱优先使用 DB 中的 email_sender_config，否则回退到 SMTP_CONFIG。"""
    wechat_service = WeChatService()
    smtp_config = get_smtp_config_from_db(db)
    if smtp_config is None:
        from backend_api.config import SMTP_CONFIG
        smtp_config = SMTPConfig(
            host=SMTP_CONFIG["host"],
            port=SMTP_CONFIG["port"],
            username=SMTP_CONFIG["username"],
            password=SMTP_CONFIG["password"],
            use_tls=SMTP_CONFIG["use_tls"],
            from_email=SMTP_CONFIG["from_email"],
            from_name=SMTP_CONFIG["from_name"],
        )
    email_service = EmailService(smtp_config)
    report_service = ReportService(db)
    config_service = ConfigService(db)
    record_repository = RecordRepository(db)
    return PushService(
        wechat_service=wechat_service,
        email_service=email_service,
        report_service=report_service,
        config_service=config_service,
        record_repository=record_repository,
    )


# ==================== 配置管理API ====================

@router.get("/config", response_model=UserPushConfigResponse)
def get_push_config(
    current_user: User = Depends(get_current_user),
    config_service: ConfigService = Depends(get_config_service)
):
    """
    获取当前用户推送配置
    """
    try:
        config = config_service.get_user_config(current_user.id)
        
        if not config:
            # 如果配置不存在，创建默认配置
            config = config_service.create_default_config(current_user.id)
        
        return config
    
    except Exception as e:
        logger.error(f"获取推送配置失败: user_id={current_user.id}, error={str(e)}")
        raise HTTPException(status_code=500, detail=f"获取推送配置失败: {str(e)}")


@router.put("/config", response_model=UserPushConfigResponse)
def update_push_config(
    config_update: ConfigUpdateRequest,
    current_user: User = Depends(get_current_user),
    config_service: ConfigService = Depends(get_config_service)
):
    """
    更新当前用户推送配置
    """
    try:
        # 验证配置参数
        if config_update.channels is not None:
            valid_channels = ['wechat', 'email']
            for channel in config_update.channels:
                if channel not in valid_channels:
                    raise HTTPException(
                        status_code=400,
                        detail=f"无效的推送渠道: {channel}，有效值为: {valid_channels}"
                    )
        
        if config_update.report_type is not None:
            if config_update.report_type not in VALID_PUSH_REPORT_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail=f"无效的报告类型: {config_update.report_type}，有效值为: {list(VALID_PUSH_REPORT_TYPES)}"
                )
        
        # 更新配置
        config_update_obj = ConfigUpdate(
            enabled=config_update.enabled,
            channels=config_update.channels,
            push_times=config_update.push_times,
            report_type=config_update.report_type,
            stock_codes=config_update.stock_codes,
            wechat_notify_userids=config_update.wechat_notify_userids,
        )
        
        updated_config = config_service.update_user_config(
            user_id=current_user.id,
            config_update=config_update_obj
        )
        
        logger.info(f"更新推送配置成功: user_id={current_user.id}")
        return updated_config
    
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"更新推送配置失败: user_id={current_user.id}, error={str(e)}")
        raise HTTPException(status_code=500, detail=f"更新推送配置失败: {str(e)}")


@router.post("/config/bind-wechat")
def bind_wechat(
    request: BindWeChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    绑定微信
    """
    try:
        # 验证微信类型
        valid_types = ['personal', 'enterprise']
        if request.wechat_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"无效的微信类型: {request.wechat_type}，有效值为: {valid_types}"
            )
        
        # 更新用户的微信信息
        user = db.query(User).filter(User.id == current_user.id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        
        user.wechat_openid = request.wechat_openid
        user.wechat_type = request.wechat_type
        
        db.commit()
        
        logger.info(f"绑定微信成功: user_id={current_user.id}, wechat_type={request.wechat_type}")
        return {"success": True, "message": "微信绑定成功"}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"绑定微信失败: user_id={current_user.id}, error={str(e)}")
        raise HTTPException(status_code=500, detail=f"绑定微信失败: {str(e)}")


@router.post("/config/unbind-wechat")
def unbind_wechat(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    解绑微信
    """
    try:
        # 清空用户的微信信息
        user = db.query(User).filter(User.id == current_user.id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        
        user.wechat_openid = None
        user.wechat_type = None
        
        db.commit()
        
        logger.info(f"解绑微信成功: user_id={current_user.id}")
        return {"success": True, "message": "微信解绑成功"}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"解绑微信失败: user_id={current_user.id}, error={str(e)}")
        raise HTTPException(status_code=500, detail=f"解绑微信失败: {str(e)}")


@router.post("/config/bind-email")
def bind_email(
    request: BindEmailRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    绑定邮箱
    """
    try:
        # 更新用户的邮箱信息
        user = db.query(User).filter(User.id == current_user.id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        
        # 检查邮箱是否已被其他用户使用
        existing_user = db.query(User).filter(
            User.email == request.email,
            User.id != current_user.id
        ).first()
        
        if existing_user:
            raise HTTPException(status_code=400, detail="该邮箱已被其他用户使用")
        
        user.email = request.email
        
        db.commit()
        
        logger.info(f"绑定邮箱成功: user_id={current_user.id}, email={request.email}")
        return {"success": True, "message": "邮箱绑定成功"}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"绑定邮箱失败: user_id={current_user.id}, error={str(e)}")
        raise HTTPException(status_code=500, detail=f"绑定邮箱失败: {str(e)}")


@router.post("/config/unbind-email")
def unbind_email(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    解绑邮箱
    
    注意：由于email字段在User模型中是必填的，这里不能直接设置为None
    实际应用中可能需要设置为一个特殊值或者修改数据库模型
    """
    try:
        user = db.query(User).filter(User.id == current_user.id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        
        # 由于email是必填字段，这里设置为一个特殊的占位符
        # 实际应用中应该修改数据库模型使email可为空
        placeholder_email = f"unbound_{current_user.id}@placeholder.local"
        user.email = placeholder_email
        
        db.commit()
        
        logger.info(f"解绑邮箱成功: user_id={current_user.id}")
        return {"success": True, "message": "邮箱解绑成功"}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"解绑邮箱失败: user_id={current_user.id}, error={str(e)}")
        raise HTTPException(status_code=500, detail=f"解绑邮箱失败: {str(e)}")


# ==================== 推送记录API ====================

@router.get("/records", response_model=List[PushRecordResponse])
def get_push_records(
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    status: Optional[str] = Query(None, description="推送状态"),
    limit: int = Query(50, ge=1, le=200, description="返回记录数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    current_user: User = Depends(get_current_user),
    record_repository: RecordRepository = Depends(get_record_repository)
):
    """
    查询当前用户推送记录（支持日期范围和状态筛选）
    """
    try:
        records = record_repository.get_user_records(
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
            status=status,
            limit=limit,
            offset=offset
        )
        
        return records
    
    except Exception as e:
        logger.error(f"查询推送记录失败: user_id={current_user.id}, error={str(e)}")
        raise HTTPException(status_code=500, detail=f"查询推送记录失败: {str(e)}")


@router.get("/records/{record_id}", response_model=PushRecordResponse)
def get_push_record(
    record_id: int,
    current_user: User = Depends(get_current_user),
    record_repository: RecordRepository = Depends(get_record_repository)
):
    """
    获取单条推送记录详情
    """
    try:
        record = record_repository.get_record_by_id(record_id)
        
        if not record:
            raise HTTPException(status_code=404, detail="推送记录不存在")
        
        # 验证记录是否属于当前用户
        if record.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问该推送记录")
        
        return record
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取推送记录失败: record_id={record_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail=f"获取推送记录失败: {str(e)}")


@router.post("/records/{record_id}/retry", response_model=TriggerPushResponse)
def retry_push_record(
    record_id: int,
    current_user: User = Depends(get_current_user),
    record_repository: RecordRepository = Depends(get_record_repository),
    push_service: PushService = Depends(get_push_service)
):
    """
    手动重发失败的推送
    """
    try:
        # 获取推送记录
        record = record_repository.get_record_by_id(record_id)
        
        if not record:
            raise HTTPException(status_code=404, detail="推送记录不存在")
        
        # 验证记录是否属于当前用户
        if record.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权操作该推送记录")
        
        # 检查记录状态
        if record.status == "success":
            raise HTTPException(status_code=400, detail="该推送已成功，无需重试")
        
        # 执行重试
        result = push_service.retry_failed_push(record_id)
        
        if result.success:
            return TriggerPushResponse(
                success=True,
                message="推送重试成功",
                record_id=record_id
            )
        else:
            return TriggerPushResponse(
                success=False,
                message=f"推送重试失败: {result.error_message}",
                record_id=record_id
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重试推送失败: record_id={record_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail=f"重试推送失败: {str(e)}")


# ==================== 推送控制API ====================

@router.post("/trigger", response_model=TriggerPushResponse)
def trigger_push(
    current_user: User = Depends(get_current_user),
    push_service: PushService = Depends(get_push_service)
):
    """
    手动触发当前用户的推送
    """
    try:
        # 使用当前时间作为推送时间
        from datetime import datetime
        push_time = datetime.now().strftime("%H:%M")
        
        # 执行推送
        result = push_service.push_to_user(
            user_id=current_user.id,
            push_time=push_time
        )
        
        if result.success:
            return TriggerPushResponse(
                success=True,
                message="推送触发成功",
                record_id=result.record_id
            )
        else:
            return TriggerPushResponse(
                success=False,
                message=f"推送触发失败: {result.error_message}",
                record_id=result.record_id
            )
    
    except Exception as e:
        logger.error(f"触发推送失败: user_id={current_user.id}, error={str(e)}")
        raise HTTPException(status_code=500, detail=f"触发推送失败: {str(e)}")


@router.get("/status", response_model=PushStatusResponse)
def get_push_status(
    current_user: User = Depends(get_current_user),
    record_repository: RecordRepository = Depends(get_record_repository),
    config_service: ConfigService = Depends(get_config_service)
):
    """
    查询推送系统状态
    """
    try:
        today = date.today()
        
        # 获取今日推送记录
        today_records = record_repository.get_user_records(
            user_id=current_user.id,
            start_date=today,
            end_date=today
        )
        
        # 统计今日推送情况
        total_records_today = len(today_records)
        success_records_today = sum(1 for r in today_records if r.status == "success")
        failed_records_today = sum(1 for r in today_records if r.status in ["failed", "failed_final"])
        
        # 获取最近一次推送时间
        last_push_time = None
        if today_records:
            last_record = max(today_records, key=lambda r: r.created_at)
            last_push_time = last_record.created_at
        
        # 获取用户配置，计算待推送用户数（这里只返回当前用户的状态）
        config = config_service.get_user_config(current_user.id)
        pending_users_count = 1 if (config and config.enabled) else 0
        
        return PushStatusResponse(
            pending_users_count=pending_users_count,
            last_push_time=last_push_time,
            total_records_today=total_records_today,
            success_records_today=success_records_today,
            failed_records_today=failed_records_today
        )
    
    except Exception as e:
        logger.error(f"查询推送状态失败: user_id={current_user.id}, error={str(e)}")
        raise HTTPException(status_code=500, detail=f"查询推送状态失败: {str(e)}")


# ==================== 管理员API ====================

# 创建管理员路由
admin_router = APIRouter(prefix="/api/admin/push", tags=["admin-push"])


@admin_router.get("/configs", response_model=List[UserPushConfigResponse])
def get_all_push_configs(
    limit: int = Query(50, ge=1, le=500, description="返回记录数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    查看所有用户配置（支持分页）
    """
    try:
        configs = db.query(UserPushConfig).offset(offset).limit(limit).all()
        return configs
    
    except Exception as e:
        logger.error(f"查询所有用户配置失败: error={str(e)}")
        raise HTTPException(status_code=500, detail=f"查询所有用户配置失败: {str(e)}")


@admin_router.post("/configs", response_model=UserPushConfigResponse)
def admin_create_push_config(
    body: ConfigCreateRequest,
    current_admin: User = Depends(get_current_admin),
    config_service: ConfigService = Depends(get_config_service),
):
    """管理员创建推送配置（同一用户可有多条，按 report_type 区分）。"""
    if body.report_type is not None and body.report_type not in VALID_PUSH_REPORT_TYPES:
        raise HTTPException(status_code=400, detail=f"report_type 有效值为: {list(VALID_PUSH_REPORT_TYPES)}")
    try:
        config = config_service.create_config(
            user_id=body.user_id,
            enabled=body.enabled if body.enabled is not None else True,
            channels=body.channels or ["email"],
            push_times=body.push_times or ["09:00", "15:00"],
            report_type=body.report_type or "summary",
            wechat_notify_userids=body.wechat_notify_userids,
        )
        return config
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"管理员创建用户 {body.user_id} 推送任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.put("/configs/{config_id}", response_model=UserPushConfigResponse)
def admin_update_push_config_by_id(
    config_id: int,
    config_update: ConfigUpdateRequest,
    current_admin: User = Depends(get_current_admin),
    config_service: ConfigService = Depends(get_config_service),
):
    """管理员按任务 id 修改一条推送配置"""
    if config_update.report_type is not None and config_update.report_type not in VALID_PUSH_REPORT_TYPES:
        raise HTTPException(status_code=400, detail=f"report_type 有效值为: {list(VALID_PUSH_REPORT_TYPES)}")
    update_obj = ConfigUpdate(
        enabled=config_update.enabled,
        channels=config_update.channels,
        push_times=config_update.push_times,
        report_type=config_update.report_type,
        stock_codes=config_update.stock_codes,
        wechat_notify_userids=config_update.wechat_notify_userids,
    )
    try:
        updated = config_service.update_config_by_id(config_id, update_obj)
        if updated is None:
            raise HTTPException(status_code=404, detail="推送配置不存在")
        return updated
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"管理员更新推送配置 {config_id} 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 兼容某些生产环境/代理不允许 PUT 的情况：同时支持 POST/PATCH 更新
@admin_router.post("/configs/{config_id}", response_model=UserPushConfigResponse)
def admin_update_push_config_by_id_post(
    config_id: int,
    config_update: ConfigUpdateRequest,
    current_admin: User = Depends(get_current_admin),
    config_service: ConfigService = Depends(get_config_service),
):
    return admin_update_push_config_by_id(
        config_id=config_id,
        config_update=config_update,
        current_admin=current_admin,
        config_service=config_service,
    )


@admin_router.patch("/configs/{config_id}", response_model=UserPushConfigResponse)
def admin_update_push_config_by_id_patch(
    config_id: int,
    config_update: ConfigUpdateRequest,
    current_admin: User = Depends(get_current_admin),
    config_service: ConfigService = Depends(get_config_service),
):
    return admin_update_push_config_by_id(
        config_id=config_id,
        config_update=config_update,
        current_admin=current_admin,
        config_service=config_service,
    )


@admin_router.delete("/configs/{config_id}")
def admin_delete_push_config_by_id(
    config_id: int,
    current_admin: User = Depends(get_current_admin),
    config_service: ConfigService = Depends(get_config_service),
):
    """管理员按任务 id 删除一条推送配置"""
    try:
        deleted = config_service.delete_config_by_id(config_id)
        return {"success": True, "deleted": deleted, "message": "已删除该推送任务" if deleted else "推送任务不存在"}
    except Exception as e:
        logger.error(f"管理员删除推送配置 {config_id} 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 兼容某些生产环境/代理不允许 DELETE 的情况：使用 POST 删除
@admin_router.post("/configs/{config_id}/delete")
def admin_delete_push_config_by_id_post(
    config_id: int,
    current_admin: User = Depends(get_current_admin),
    config_service: ConfigService = Depends(get_config_service),
):
    return admin_delete_push_config_by_id(
        config_id=config_id,
        current_admin=current_admin,
        config_service=config_service,
    )


# ---------- 发件邮箱参数配置 ----------

@admin_router.get("/email-sender-config", response_model=EmailSenderConfigResponse)
def get_email_sender_config(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """获取发件邮箱配置（password 脱敏）"""
    if EmailSenderConfig is None:
        raise HTTPException(status_code=503, detail="发件邮箱配置模型未就绪")
    row = db.query(EmailSenderConfig).filter(EmailSenderConfig.id == 1).first()
    if not row:
        return EmailSenderConfigResponse(
            id=1,
            host="",
            port=587,
            username="",
            password_masked="",
            from_email="",
            from_name="股票分析系统",
            use_tls=True,
            updated_at=None,
        )
    return EmailSenderConfigResponse(
        id=row.id,
        host=str(row.host),
        port=int(row.port),
        username=str(row.username),
        password_masked="********" if row.password else "",
        from_email=str(row.from_email),
        from_name=str(row.from_name),
        use_tls=bool(row.use_tls),
        updated_at=row.updated_at,
    )


def _update_email_sender_config_impl(
    body: EmailSenderConfigUpdateRequest,
    db: Session,
) -> "EmailSenderConfigResponse":
    """更新发件邮箱配置实现；不传 password 则保留原密码。供 PUT/POST 共用。"""
    if EmailSenderConfig is None:
        raise HTTPException(status_code=503, detail="发件邮箱配置模型未就绪")
    row = db.query(EmailSenderConfig).filter(EmailSenderConfig.id == 1).first()
    if not row:
        row = EmailSenderConfig(id=1)
        db.add(row)
        db.flush()
    if body.host is not None:
        row.host = body.host
    if body.port is not None:
        row.port = body.port
    if body.username is not None:
        row.username = body.username
    if body.password is not None and body.password != "":
        row.password = body.password
    if body.from_email is not None:
        row.from_email = body.from_email
    if body.from_name is not None:
        row.from_name = body.from_name
    if body.use_tls is not None:
        row.use_tls = body.use_tls
    row.updated_at = datetime.now()
    db.commit()
    db.refresh(row)
    return EmailSenderConfigResponse(
        id=row.id,
        host=str(row.host),
        port=int(row.port),
        username=str(row.username),
        password_masked="********" if row.password else "",
        from_email=str(row.from_email),
        from_name=str(row.from_name),
        use_tls=bool(row.use_tls),
        updated_at=row.updated_at,
    )


@admin_router.put("/email-sender-config", response_model=EmailSenderConfigResponse)
def update_email_sender_config_put(
    body: EmailSenderConfigUpdateRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """更新发件邮箱配置（PUT）；不传 password 则保留原密码。"""
    return _update_email_sender_config_impl(body, db)


@admin_router.post("/email-sender-config", response_model=EmailSenderConfigResponse)
def update_email_sender_config_post(
    body: EmailSenderConfigUpdateRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """更新发件邮箱配置（POST）；与 PUT 行为一致，用于生产环境对 PUT 有限制时。"""
    return _update_email_sender_config_impl(body, db)


@admin_router.post("/email-sender-config/test")
def test_email_sender_config(
    body: EmailSenderConfigTestRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """使用当前发件配置向指定邮箱发送测试邮件"""
    smtp_config = get_smtp_config_from_db(db)
    if smtp_config is None:
        from backend_api.config import SMTP_CONFIG
        smtp_config = SMTPConfig(
            host=SMTP_CONFIG["host"],
            port=SMTP_CONFIG["port"],
            username=SMTP_CONFIG["username"],
            password=SMTP_CONFIG["password"],
            use_tls=SMTP_CONFIG["use_tls"],
            from_email=SMTP_CONFIG["from_email"],
            from_name=SMTP_CONFIG["from_name"],
        )
    email_service = EmailService(smtp_config)
    import tempfile
    import os
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
    tmp.write("test,test\n")
    tmp.close()
    try:
        result = email_service.send_report_email(
            to_email=body.to_email,
            subject="【测试】股票分析系统发件配置测试",
            content="<p>这是一封测试邮件，说明发件邮箱配置正常。</p>",
            attachment_path=tmp.name,
        )
        return {"success": result.success, "message": result.message}
    except EmailSendException as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


@admin_router.get("/email-logs", response_model=List[EmailSendLogResponse])
def get_email_send_logs(
    user_id: Optional[int] = Query(None, description="用户ID"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    success: Optional[bool] = Query(None, description="是否成功"),
    limit: int = Query(50, ge=1, le=200, description="返回记录数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """查询邮件发送日志（管理端）"""
    if EmailSendLog is None:
        raise HTTPException(status_code=503, detail="邮件发送日志模型未就绪")
    query = db.query(EmailSendLog)
    if user_id is not None:
        query = query.filter(EmailSendLog.user_id == user_id)
    if start_date is not None:
        query = query.filter(EmailSendLog.sent_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date is not None:
        query = query.filter(EmailSendLog.sent_at <= datetime.combine(end_date, datetime.max.time()))
    if success is not None:
        query = query.filter(EmailSendLog.success == success)
    query = query.order_by(EmailSendLog.sent_at.desc())
    logs = query.offset(offset).limit(limit).all()
    # 补全 username
    out = []
    for log in logs:
        u = db.query(User).filter(User.id == log.user_id).first()
        out.append(EmailSendLogResponse(
            id=log.id,
            user_id=log.user_id,
            username=u.username if u else None,
            to_email=log.to_email,
            subject=log.subject,
            report_type=log.report_type,
            push_record_id=log.push_record_id,
            sent_at=log.sent_at,
            success=log.success,
            error_message=log.error_message,
            created_at=log.created_at,
        ))
    return out


@admin_router.get("/records", response_model=List[PushRecordResponse])
def get_all_push_records(
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    status: Optional[str] = Query(None, description="推送状态"),
    user_id: Optional[int] = Query(None, description="用户ID"),
    limit: int = Query(50, ge=1, le=200, description="返回记录数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    查看所有推送记录（支持筛选和分页）
    """
    try:
        query = db.query(PushRecord)
        
        # 应用筛选条件
        if user_id is not None:
            query = query.filter(PushRecord.user_id == user_id)
        
        if start_date is not None:
            query = query.filter(PushRecord.push_date >= start_date)
        
        if end_date is not None:
            query = query.filter(PushRecord.push_date <= end_date)
        
        if status is not None:
            query = query.filter(PushRecord.status == status)
        
        # 按创建时间倒序排列
        query = query.order_by(PushRecord.created_at.desc())
        
        # 分页
        records = query.offset(offset).limit(limit).all()
        
        return records
    
    except Exception as e:
        logger.error(f"查询所有推送记录失败: error={str(e)}")
        raise HTTPException(status_code=500, detail=f"查询所有推送记录失败: {str(e)}")


# 全局推送开关状态（存储在内存中，实际应用中应该存储在数据库或Redis中）
_global_push_enabled = True


@admin_router.post("/global-control")
def global_push_control(
    request: GlobalControlRequest,
    current_admin: User = Depends(get_current_admin)
):
    """
    全局暂停/恢复推送功能
    """
    global _global_push_enabled
    
    try:
        if request.action == "pause":
            _global_push_enabled = False
            logger.info(f"管理员暂停全局推送: admin_id={current_admin.id}")
            return {"success": True, "message": "全局推送已暂停", "enabled": False}
        
        elif request.action == "resume":
            _global_push_enabled = True
            logger.info(f"管理员恢复全局推送: admin_id={current_admin.id}")
            return {"success": True, "message": "全局推送已恢复", "enabled": True}
        
        else:
            raise HTTPException(
                status_code=400,
                detail=f"无效的操作: {request.action}，有效值为: pause, resume"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"全局推送控制失败: error={str(e)}")
        raise HTTPException(status_code=500, detail=f"全局推送控制失败: {str(e)}")


@admin_router.get("/statistics", response_model=PushStatisticsResponse)
def get_push_statistics(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    获取推送统计数据
    """
    try:
        # 统计用户数
        total_users = db.query(User).count()
        
        # 统计启用推送的用户数
        enabled_users = db.query(UserPushConfig).filter(
            UserPushConfig.enabled == True
        ).count()
        
        # 统计推送记录总数
        total_records = db.query(PushRecord).count()
        
        # 统计各状态的记录数
        records_by_status = {}
        status_list = ['pending', 'processing', 'success', 'partial_success', 'failed', 'failed_final']
        for status in status_list:
            count = db.query(PushRecord).filter(PushRecord.status == status).count()
            if count > 0:
                records_by_status[status] = count
        
        # 统计各渠道的记录数（这里简化处理，实际需要解析JSON字段）
        records_by_channel = {
            "wechat": 0,
            "email": 0
        }
        
        # 计算成功率
        success_count = records_by_status.get('success', 0) + records_by_status.get('partial_success', 0)
        success_rate = (success_count / total_records * 100) if total_records > 0 else 0.0
        
        return PushStatisticsResponse(
            total_users=total_users,
            enabled_users=enabled_users,
            total_records=total_records,
            success_rate=round(success_rate, 2),
            records_by_status=records_by_status,
            records_by_channel=records_by_channel
        )
    
    except Exception as e:
        logger.error(f"获取推送统计数据失败: error={str(e)}")
        raise HTTPException(status_code=500, detail=f"获取推送统计数据失败: {str(e)}")


# 导出全局推送开关状态的访问函数
def is_global_push_enabled() -> bool:
    """检查全局推送是否启用"""
    return _global_push_enabled
