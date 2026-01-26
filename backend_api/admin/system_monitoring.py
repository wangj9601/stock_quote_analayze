"""
系统监控API路由
提供系统监控、告警管理和性能指标查询接口
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend_api.database import get_db
from backend_api.models import SystemAlert, SystemAlertRule, SystemServiceStatus
from backend_core.monitoring import system_monitor, alert_manager
from backend_core.monitoring.system_monitor import AlertLevel, AlertType
from backend_core.monitoring.alert_manager import NotificationChannel, NotificationConfig

router = APIRouter(prefix="/system/monitoring", tags=["系统监控"])

# Pydantic 模型
class AlertCreateRequest(BaseModel):
    """创建告警请求"""
    level: str
    title: str
    message: str
    alert_type: str = "system"
    source: str = "api"
    metadata: Optional[Dict] = None

class AlertAcknowledgeRequest(BaseModel):
    """告警确认请求"""
    acknowledged_by: str = "admin"

class AlertRuleCreateRequest(BaseModel):
    """创建告警规则请求"""
    name: str
    metric_name: str
    condition: str
    threshold: float
    level: str
    alert_type: str
    message_template: str
    enabled: bool = True
    description: Optional[str] = None

class NotificationConfigRequest(BaseModel):
    """通知配置请求"""
    name: str
    channel: str
    enabled: bool = True
    config: Dict[str, Any]
    filters: Optional[Dict[str, Any]] = None

@router.get("/overview")
async def get_monitoring_overview():
    """获取监控概览"""
    try:
        data = system_monitor.get_monitoring_data()
        return {
            "success": True,
            "data": data,
            "message": "获取监控概览成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取监控概览失败: {str(e)}")

@router.get("/system-health")
async def get_system_health():
    """获取系统健康状态"""
    try:
        health = system_monitor.get_system_health()
        return {
            "success": True,
            "data": {
                "cpu_usage": health.cpu_usage,
                "memory_usage": health.memory_usage,
                "disk_usage": health.disk_usage,
                "network_io": health.network_io,
                "services": {name: status.value for name, status in health.service_status.items()},
                "timestamp": health.timestamp.isoformat()
            },
            "message": "获取系统健康状态成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取系统健康状态失败: {str(e)}")

@router.get("/metrics")
async def get_performance_metrics(
    time_range: str = Query("1h", description="时间范围: 1h, 6h, 12h, 1d"),
    interval: str = Query("1m", description="间隔时间")
):
    """获取性能指标"""
    try:
        metrics = system_monitor.get_performance_metrics(time_range, interval)
        return {
            "success": True,
            "data": metrics,
            "message": "获取性能指标成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取性能指标失败: {str(e)}")

@router.get("/alerts")
async def get_alerts(
    limit: int = Query(50, ge=1, le=1000, description="返回数量限制"),
    level: Optional[str] = Query(None, description="告警级别过滤"),
    alert_type: Optional[str] = Query(None, description="告警类型过滤"),
    acknowledged: Optional[bool] = Query(None, description="是否已确认过滤"),
    start_time: Optional[str] = Query(None, description="开始时间 (ISO格式)"),
    end_time: Optional[str] = Query(None, description="结束时间 (ISO格式)")
):
    """获取告警列表"""
    try:
        # 转换时间参数
        start_dt = None
        end_dt = None
        if start_time:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        if end_time:
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        
        alerts = system_monitor.get_alerts(
            limit=limit,
            level=level,
            alert_type=alert_type,
            acknowledged=acknowledged,
            start_time=start_dt,
            end_time=end_dt
        )
        
        return {
            "success": True,
            "data": alerts,
            "message": "获取告警列表成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取告警列表失败: {str(e)}")

@router.post("/alerts")
async def create_alert(request: AlertCreateRequest):
    """创建告警"""
    try:
        alert_id = system_monitor.add_alert(
            level=request.level,
            title=request.title,
            message=request.message,
            alert_type=request.alert_type,
            source=request.source,
            metadata=request.metadata
        )
        
        if alert_id:
            return {
                "success": True,
                "data": {"alert_id": alert_id},
                "message": "创建告警成功"
            }
        else:
            raise HTTPException(status_code=500, detail="创建告警失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建告警失败: {str(e)}")

@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: int, request: AlertAcknowledgeRequest):
    """确认告警"""
    try:
        success = system_monitor.acknowledge_alert(alert_id, request.acknowledged_by)
        
        if success:
            return {
                "success": True,
                "message": "告警确认成功"
            }
        else:
            raise HTTPException(status_code=404, detail="告警不存在")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"确认告警失败: {str(e)}")

@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: int, resolved_by: str = "admin"):
    """解决告警"""
    try:
        success = alert_manager.resolve_alert(alert_id, resolved_by)
        
        if success:
            return {
                "success": True,
                "message": "告警解决成功"
            }
        else:
            raise HTTPException(status_code=404, detail="告警不存在")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解决告警失败: {str(e)}")

@router.get("/alerts/statistics")
async def get_alert_statistics(days: int = Query(7, ge=1, le=365, description="统计天数")):
    """获取告警统计信息"""
    try:
        stats = alert_manager.get_alert_statistics(days)
        return {
            "success": True,
            "data": stats,
            "message": "获取告警统计成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取告警统计失败: {str(e)}")

@router.get("/services")
async def get_service_status():
    """获取服务状态"""
    try:
        with SessionLocal() as db:
            services = db.query(SystemServiceStatus).all()
            
            result = []
            for service in services:
                result.append({
                    "service_name": service.service_name,
                    "status": service.status,
                    "last_check": service.last_check.isoformat(),
                    "response_time": service.response_time,
                    "error_message": service.error_message,
                    "metadata": service.metadata or {}
                })
            
            return {
                "success": True,
                "data": result,
                "message": "获取服务状态成功"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取服务状态失败: {str(e)}")

@router.get("/rules")
async def get_alert_rules():
    """获取告警规则"""
    try:
        rules = system_monitor.get_alert_rules()
        return {
            "success": True,
            "data": rules,
            "message": "获取告警规则成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取告警规则失败: {str(e)}")

@router.post("/rules")
async def create_alert_rule(request: AlertRuleCreateRequest):
    """创建告警规则"""
    try:
        from backend_core.monitoring.system_monitor import AlertRule as SystemAlertRule
        
        rule = SystemAlertRule(
            name=request.name,
            metric_name=request.metric_name,
            condition=request.condition,
            threshold=request.threshold,
            level=AlertLevel(request.level.upper()),
            alert_type=AlertType(request.alert_type.upper()),
            message_template=request.message_template,
            enabled=request.enabled
        )
        
        system_monitor.add_alert_rule(rule)
        
        return {
            "success": True,
            "message": "创建告警规则成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建告警规则失败: {str(e)}")

@router.delete("/rules/{rule_name}")
async def delete_alert_rule(rule_name: str):
    """删除告警规则"""
    try:
        system_monitor.remove_alert_rule(rule_name)
        return {
            "success": True,
            "message": "删除告警规则成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除告警规则失败: {str(e)}")

@router.get("/notifications/configs")
async def get_notification_configs():
    """获取通知配置"""
    try:
        configs = []
        for name, config in alert_manager.notification_configs.items():
            configs.append({
                "name": name,
                "channel": config.channel.value,
                "enabled": config.enabled,
                "config": config.config or {},
                "filters": config.filters or {}
            })
        
        return {
            "success": True,
            "data": configs,
            "message": "获取通知配置成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取通知配置失败: {str(e)}")

@router.post("/notifications/configs")
async def create_notification_config(request: NotificationConfigRequest):
    """创建通知配置"""
    try:
        config = NotificationConfig(
            channel=NotificationChannel(request.channel),
            enabled=request.enabled,
            config=request.config,
            filters=request.filters
        )
        
        alert_manager.add_notification_config(request.name, config)
        
        return {
            "success": True,
            "message": "创建通知配置成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建通知配置失败: {str(e)}")

@router.delete("/notifications/configs/{config_name}")
async def delete_notification_config(config_name: str):
    """删除通知配置"""
    try:
        alert_manager.remove_notification_config(config_name)
        return {
            "success": True,
            "message": "删除通知配置成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除通知配置失败: {str(e)}")

@router.post("/maintenance/cleanup-alerts")
async def cleanup_old_alerts(days: int = Query(30, ge=1, le=365, description="保留天数")):
    """清理旧告警"""
    try:
        deleted_count = alert_manager.cleanup_old_alerts(days)
        return {
            "success": True,
            "data": {"deleted_count": deleted_count},
            "message": f"清理完成，删除 {deleted_count} 条旧告警"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清理旧告警失败: {str(e)}")

@router.post("/monitoring/start")
async def start_monitoring():
    """启动监控"""
    try:
        system_monitor.start_background_monitoring()
        return {
            "success": True,
            "message": "监控已启动"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动监控失败: {str(e)}")

@router.post("/monitoring/stop")
async def stop_monitoring():
    """停止监控"""
    try:
        system_monitor.stop_background_monitoring()
        return {
            "success": True,
            "message": "监控已停止"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"停止监控失败: {str(e)}")

@router.get("/monitoring/status")
async def get_monitoring_status():
    """获取监控状态"""
    try:
        is_running = system_monitor.monitor_thread and system_monitor.monitor_thread.is_alive()
        return {
            "success": True,
            "data": {
                "is_running": is_running,
                "stop_event_set": system_monitor.stop_event.is_set()
            },
            "message": "获取监控状态成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取监控状态失败: {str(e)}")
