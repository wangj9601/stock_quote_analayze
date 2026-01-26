"""
通用告警管理模块
负责告警的生成、处理、通知和生命周期管理
"""

import logging
import smtplib
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Callable
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass
from enum import Enum
from sqlalchemy import func, desc, and_, or_

from backend_api.database import SessionLocal
from backend_api.models import SystemAlert, SystemAlertRule, SystemServiceStatus

logger = logging.getLogger(__name__)

class NotificationChannel(Enum):
    """通知渠道"""
    EMAIL = "email"
    WEBHOOK = "webhook"
    SMS = "sms"
    DINGTALK = "dingtalk"
    WECHAT = "wechat"

class AlertStatus(Enum):
    """告警状态"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"

@dataclass
class NotificationConfig:
    """通知配置"""
    channel: NotificationChannel
    enabled: bool = True
    config: Dict[str, Any] = None
    filters: Dict[str, Any] = None  # 过滤条件

@dataclass
class AlertNotification:
    """告警通知"""
    alert_id: int
    title: str
    message: str
    level: str
    alert_type: str
    timestamp: datetime
    metadata: Dict[str, Any]

class AlertManager:
    """告警管理器"""
    
    _instance = None
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self.notification_configs: Dict[str, NotificationConfig] = {}
            self.notification_handlers: Dict[NotificationChannel, Callable] = {}
            self.alert_callbacks: List[Callable] = []
            self.suppression_rules: Dict[str, Dict] = {}
            self._init_default_handlers()
            logger.info("告警管理器单例初始化")

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AlertManager, cls).__new__(cls)
        return cls._instance

    def _init_default_handlers(self):
        """初始化默认通知处理器"""
        self.notification_handlers = {
            NotificationChannel.EMAIL: self._send_email_notification,
            NotificationChannel.WEBHOOK: self._send_webhook_notification,
            NotificationChannel.SMS: self._send_sms_notification,
            NotificationChannel.DINGTALK: self._send_dingtalk_notification,
            NotificationChannel.WECHAT: self._send_wechat_notification,
        }

    def add_notification_config(self, name: str, config: NotificationConfig):
        """添加通知配置"""
        self.notification_configs[name] = config
        logger.info(f"添加通知配置: {name}")

    def remove_notification_config(self, name: str):
        """移除通知配置"""
        if name in self.notification_configs:
            del self.notification_configs[name]
            logger.info(f"移除通知配置: {name}")

    def add_alert_callback(self, callback: Callable):
        """添加告警回调函数"""
        self.alert_callbacks.append(callback)

    def add_suppression_rule(self, rule_name: str, conditions: Dict, duration_minutes: int = 60):
        """添加告警抑制规则"""
        self.suppression_rules[rule_name] = {
            "conditions": conditions,
            "duration_minutes": duration_minutes,
            "created_at": datetime.now()
        }
        logger.info(f"添加告警抑制规则: {rule_name}")

    def create_alert(self, level: str, title: str, message: str, 
                   alert_type: str = "system", source: str = "alert_manager",
                   metadata: Optional[Dict] = None) -> Optional[int]:
        """创建告警"""
        try:
            # 检查抑制规则
            if self._is_suppressed(level, alert_type, source, metadata):
                logger.info(f"告警被抑制: {title}")
                return None
            
            with SessionLocal() as db:
                alert = SystemAlert(
                    level=level.upper(),
                    alert_type=alert_type,
                    title=title,
                    message=message,
                    source=source,
                    timestamp=datetime.now(),
                    acknowledged=False,
                    alert_metadata=metadata
                )
                db.add(alert)
                db.commit()
                db.refresh(alert)
                
                alert_id = alert.id
                
                # 触发通知
                self._trigger_notifications(alert_id, title, message, level, alert_type, metadata)
                
                # 触发回调
                self._trigger_callbacks(alert_id, title, message, level, alert_type, metadata)
                
                logger.info(f"成功创建告警: [{level}] {title} (ID: {alert_id})")
                return alert_id
                
        except Exception as e:
            logger.error(f"创建告警失败: {e}")
            return None

    def _is_suppressed(self, level: str, alert_type: str, source: str, metadata: Optional[Dict]) -> bool:
        """检查告警是否被抑制"""
        for rule_name, rule in self.suppression_rules.items():
            conditions = rule["conditions"]
            created_at = rule["created_at"]
            duration_minutes = rule["duration_minutes"]
            
            # 检查抑制时间是否过期
            if datetime.now() - created_at > timedelta(minutes=duration_minutes):
                continue
            
            # 检查条件匹配
            if self._match_conditions(conditions, level, alert_type, source, metadata):
                return True
        
        return False

    def _match_conditions(self, conditions: Dict, level: str, alert_type: str, source: str, metadata: Optional[Dict]) -> bool:
        """匹配抑制条件"""
        for key, value in conditions.items():
            if key == "level" and level != value:
                return False
            elif key == "alert_type" and alert_type != value:
                return False
            elif key == "source" and source != value:
                return False
            elif key.startswith("metadata.") and metadata:
                metadata_key = key[9:]  # 移除 "metadata." 前缀
                if metadata.get(metadata_key) != value:
                    return False
        
        return True

    def _trigger_notifications(self, alert_id: int, title: str, message: str, 
                              level: str, alert_type: str, metadata: Optional[Dict]):
        """触发通知"""
        notification = AlertNotification(
            alert_id=alert_id,
            title=title,
            message=message,
            level=level,
            alert_type=alert_type,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )
        
        for config_name, config in self.notification_configs.items():
            if not config.enabled:
                continue
            
            # 应用过滤条件
            if not self._apply_filters(config.filters, notification):
                continue
            
            try:
                handler = self.notification_handlers.get(config.channel)
                if handler:
                    handler(notification, config.config)
            except Exception as e:
                logger.error(f"发送通知失败 ({config_name}): {e}")

    def _apply_filters(self, filters: Optional[Dict], notification: AlertNotification) -> bool:
        """应用过滤条件"""
        if not filters:
            return True
        
        for key, value in filters.items():
            if key == "level" and notification.level not in value:
                return False
            elif key == "alert_type" and notification.alert_type not in value:
                return False
            elif key == "exclude_level" and notification.level in value:
                return False
        
        return True

    def _trigger_callbacks(self, alert_id: int, title: str, message: str, 
                         level: str, alert_type: str, metadata: Optional[Dict]):
        """触发回调函数"""
        for callback in self.alert_callbacks:
            try:
                callback(alert_id, title, message, level, alert_type, metadata)
            except Exception as e:
                logger.error(f"告警回调执行失败: {e}")

    def acknowledge_alert(self, alert_id: int, acknowledged_by: str = "system") -> bool:
        """确认告警"""
        try:
            with SessionLocal() as db:
                alert = db.query(SystemAlert).filter(SystemAlert.id == alert_id).first()
                if alert:
                    alert.acknowledged = True
                    alert.acknowledged_at = datetime.now()
                    alert.acknowledged_by = acknowledged_by
                    db.commit()
                    logger.info(f"告警已确认: {alert_id} by {acknowledged_by}")
                    return True
                return False
        except Exception as e:
            logger.error(f"确认告警失败: {e}")
            return False

    def resolve_alert(self, alert_id: int, resolved_by: str = "system") -> bool:
        """解决告警"""
        try:
            with SessionLocal() as db:
                alert = db.query(SystemAlert).filter(SystemAlert.id == alert_id).first()
                if alert:
                    # 这里可以添加解决状态字段，或者通过alert_metadata标记
                    if not alert.alert_metadata:
                        alert.alert_metadata = {}
                    alert.alert_metadata["resolved"] = True
                    alert.alert_metadata["resolved_by"] = resolved_by
                    alert.alert_metadata["resolved_at"] = datetime.now().isoformat()
                    db.commit()
                    logger.info(f"告警已解决: {alert_id} by {resolved_by}")
                    return True
                return False
        except Exception as e:
            logger.error(f"解决告警失败: {e}")
            return False

    def get_alerts(self, limit: int = 50, level: Optional[str] = None, 
                  alert_type: Optional[str] = None, acknowledged: Optional[bool] = None,
                  start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> List[Dict]:
        """获取告警列表"""
        try:
            with SessionLocal() as db:
                query = db.query(SystemAlert).order_by(desc(SystemAlert.timestamp))
                
                if level:
                    query = query.filter(SystemAlert.level == level.upper())
                if alert_type:
                    query = query.filter(SystemAlert.alert_type == alert_type)
                if acknowledged is not None:
                    query = query.filter(SystemAlert.acknowledged == acknowledged)
                if start_time:
                    query = query.filter(SystemAlert.timestamp >= start_time)
                if end_time:
                    query = query.filter(SystemAlert.timestamp <= end_time)
                
                alerts = query.limit(limit).all()
                
                result = []
                for alert in alerts:
                    result.append({
                        "id": str(alert.id),
                        "level": alert.level,
                        "type": alert.alert_type,
                        "title": alert.title,
                        "message": alert.message,
                        "timestamp": alert.timestamp.isoformat(),
                        "acknowledged": alert.acknowledged,
                        "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                        "acknowledged_by": alert.acknowledged_by,
                        "source": alert.source,
                        "metadata": alert.alert_metadata or {}
                    })
                return result
        except Exception as e:
            logger.error(f"获取告警列表失败: {e}")
            return []

    def get_alert_statistics(self, days: int = 7) -> Dict:
        """获取告警统计信息"""
        try:
            with SessionLocal() as db:
                start_time = datetime.now() - timedelta(days=days)
                
                # 总告警数
                total_alerts = db.query(SystemAlert)\
                    .filter(SystemAlert.timestamp >= start_time)\
                    .count()
                
                # 按级别统计
                level_stats = {}
                for level in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
                    count = db.query(SystemAlert)\
                        .filter(and_(
                            SystemAlert.timestamp >= start_time,
                            SystemAlert.level == level
                        ))\
                        .count()
                    level_stats[level.lower()] = count
                
                # 按类型统计
                type_stats = {}
                type_results = db.query(SystemAlert.alert_type, func.count(SystemAlert.id))\
                    .filter(SystemAlert.timestamp >= start_time)\
                    .group_by(SystemAlert.alert_type)\
                    .all()
                
                for alert_type, count in type_results:
                    type_stats[alert_type.lower()] = count
                
                # 未确认告警数
                unacknowledged_count = db.query(SystemAlert)\
                    .filter(and_(
                        SystemAlert.timestamp >= start_time,
                        SystemAlert.acknowledged == False
                    ))\
                    .count()
                
                # 今日告警趋势
                today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                hourly_stats = []
                for hour in range(24):
                    hour_start = today_start + timedelta(hours=hour)
                    hour_end = hour_start + timedelta(hours=1)
                    
                    count = db.query(SystemAlert)\
                        .filter(and_(
                            SystemAlert.timestamp >= hour_start,
                            SystemAlert.timestamp < hour_end
                        ))\
                        .count()
                    
                    hourly_stats.append({
                        "hour": hour,
                        "count": count
                    })
                
                return {
                    "period_days": days,
                    "total_alerts": total_alerts,
                    "level_distribution": level_stats,
                    "type_distribution": type_stats,
                    "unacknowledged_count": unacknowledged_count,
                    "hourly_trend": hourly_stats
                }
        except Exception as e:
            logger.error(f"获取告警统计失败: {e}")
            return {}

    def cleanup_old_alerts(self, days: int = 30) -> int:
        """清理旧告警"""
        try:
            with SessionLocal() as db:
                cutoff_time = datetime.now() - timedelta(days=days)
                
                # 只删除已确认且超过保留期的告警
                deleted_count = db.query(SystemAlert)\
                    .filter(and_(
                        SystemAlert.timestamp < cutoff_time,
                        SystemAlert.acknowledged == True
                    ))\
                    .delete()
                
                db.commit()
                logger.info(f"清理旧告警完成，删除 {deleted_count} 条记录")
                return deleted_count
        except Exception as e:
            logger.error(f"清理旧告警失败: {e}")
            return 0

    # 通知处理器实现
    def _send_email_notification(self, notification: AlertNotification, config: Dict):
        """发送邮件通知"""
        try:
            smtp_server = config.get("smtp_server")
            smtp_port = config.get("smtp_port", 587)
            username = config.get("username")
            password = config.get("password")
            from_email = config.get("from_email")
            to_emails = config.get("to_emails", [])
            
            if not all([smtp_server, username, password, from_email, to_emails]):
                logger.warning("邮件配置不完整，跳过发送")
                return
            
            msg = MIMEMultipart()
            msg['From'] = from_email
            msg['To'] = ', '.join(to_emails)
            msg['Subject'] = f"[{notification.level}] {notification.title}"
            
            body = f"""
告警级别: {notification.level}
告警类型: {notification.alert_type}
告警标题: {notification.title}
告警消息: {notification.message}
时间: {notification.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
来源: {notification.metadata.get('source', 'unknown')}
            """
            
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(username, password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"邮件通知发送成功: {notification.title}")
            
        except Exception as e:
            logger.error(f"发送邮件通知失败: {e}")

    def _send_webhook_notification(self, notification: AlertNotification, config: Dict):
        """发送Webhook通知"""
        try:
            import requests
            
            url = config.get("url")
            headers = config.get("headers", {})
            timeout = config.get("timeout", 10)
            
            if not url:
                logger.warning("Webhook URL未配置，跳过发送")
                return
            
            payload = {
                "alert_id": notification.alert_id,
                "title": notification.title,
                "message": notification.message,
                "level": notification.level,
                "alert_type": notification.alert_type,
                "timestamp": notification.timestamp.isoformat(),
                "metadata": notification.metadata
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            response.raise_for_status()
            
            logger.info(f"Webhook通知发送成功: {notification.title}")
            
        except Exception as e:
            logger.error(f"发送Webhook通知失败: {e}")

    def _send_sms_notification(self, notification: AlertNotification, config: Dict):
        """发送短信通知"""
        # 这里需要根据具体的短信服务商API实现
        logger.info(f"短信通知暂未实现: {notification.title}")

    def _send_dingtalk_notification(self, notification: AlertNotification, config: Dict):
        """发送钉钉通知"""
        # 这里需要根据钉钉机器人API实现
        logger.info(f"钉钉通知暂未实现: {notification.title}")

    def _send_wechat_notification(self, notification: AlertNotification, config: Dict):
        """发送微信通知"""
        # 这里需要根据企业微信API实现
        logger.info(f"微信通知暂未实现: {notification.title}")

# 单例导出
alert_manager = AlertManager()
