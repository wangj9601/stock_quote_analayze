"""
通用系统监控服务
负责整个系统的性能监控、指标收集和告警管理
"""

import logging
import psutil
import threading
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Callable
from sqlalchemy import func, desc, and_, text
from dataclasses import dataclass
from enum import Enum

from backend_api.database import SessionLocal
from backend_api.models import (
    SystemAlert, 
    SystemMonitorMetric, 
    SystemServiceStatus
)

logger = logging.getLogger(__name__)

class AlertLevel(Enum):
    """告警级别"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class AlertType(Enum):
    """告警类型"""
    SYSTEM = "system"
    PERFORMANCE = "performance"
    BUSINESS = "business"
    SECURITY = "security"

class ServiceStatus(Enum):
    """服务状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

@dataclass
class SystemHealth:
    """系统健康状态"""
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_io: Dict[str, float]
    service_status: Dict[str, ServiceStatus]
    timestamp: datetime

@dataclass
class AlertRule:
    """告警规则"""
    name: str
    metric_name: str
    condition: str  # >, <, >=, <=, ==
    threshold: float
    level: AlertLevel
    alert_type: AlertType
    message_template: str
    enabled: bool = True

class SystemMonitor:
    """系统监控服务类"""
    
    _instance = None
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self.stop_event = threading.Event()
            self.monitor_thread = None
            self.alert_rules: Dict[str, AlertRule] = {}
            self.metric_callbacks: Dict[str, List[Callable]] = {}
            self._init_default_rules()
            logger.info("系统监控服务单例初始化")

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SystemMonitor, cls).__new__(cls)
        return cls._instance

    def _init_default_rules(self):
        """初始化默认告警规则"""
        default_rules = [
            AlertRule(
                name="CPU使用率过高",
                metric_name="cpu_usage",
                condition=">",
                threshold=80.0,
                level=AlertLevel.HIGH,
                alert_type=AlertType.SYSTEM,
                message_template="CPU使用率过高: {value:.1f}%"
            ),
            AlertRule(
                name="内存使用率过高",
                metric_name="memory_usage",
                condition=">",
                threshold=85.0,
                level=AlertLevel.HIGH,
                alert_type=AlertType.SYSTEM,
                message_template="内存使用率过高: {value:.1f}%"
            ),
            AlertRule(
                name="磁盘使用率过高",
                metric_name="disk_usage",
                condition=">",
                threshold=90.0,
                level=AlertLevel.CRITICAL,
                alert_type=AlertType.SYSTEM,
                message_template="磁盘使用率过高: {value:.1f}%"
            ),
            AlertRule(
                name="系统响应时间过长",
                metric_name="response_time",
                condition=">",
                threshold=2.0,
                level=AlertLevel.MEDIUM,
                alert_type=AlertType.PERFORMANCE,
                message_template="系统响应时间过长: {value:.2f}秒"
            )
        ]
        
        for rule in default_rules:
            self.alert_rules[rule.name] = rule

    def start_background_monitoring(self):
        """启动后台监控线程"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            return
        
        self.stop_event.clear()
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("系统后台监控线程已启动")

    def stop_background_monitoring(self):
        """停止后台监控线程"""
        self.stop_event.set()
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("系统后台监控线程已停止")

    def _monitoring_loop(self):
        """核心监控循环"""
        while not self.stop_event.is_set():
            try:
                # 1. 采集系统指标
                system_metrics = self._collect_system_metrics()
                
                # 2. 记录指标
                for metric_name, value in system_metrics.items():
                    self.record_metric(metric_name, value)
                
                # 3. 检查告警规则
                self._check_alert_rules(system_metrics)
                
                # 4. 采集数据库指标
                db_metrics = self._collect_database_metrics()
                for table_name, size_mb in db_metrics.items():
                    self.record_metric(f"db_table_size_{table_name}", size_mb, {"unit": "MB"})
                
                # 5. 更新服务状态
                self._update_service_status()
                
                # 休眠30分钟 (1800秒)
                for _ in range(1800):
                    if self.stop_event.is_set():
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"监控循环异常: {e}")
                time.sleep(10)

    def _collect_system_metrics(self) -> Dict[str, float]:
        """采集系统指标"""
        try:
            metrics = {}
            
            # CPU指标
            metrics['cpu_usage'] = psutil.cpu_percent(interval=1)
            metrics['cpu_count'] = psutil.cpu_count()
            
            # 内存指标
            memory = psutil.virtual_memory()
            metrics['memory_usage'] = memory.percent
            metrics['memory_available'] = memory.available / (1024**3)  # GB
            metrics['memory_total'] = memory.total / (1024**3)  # GB
            
            # 磁盘指标
            disk = psutil.disk_usage('/')
            metrics['disk_usage'] = disk.percent
            metrics['disk_free'] = disk.free / (1024**3)  # GB
            metrics['disk_total'] = disk.total / (1024**3)  # GB
            
            # 网络指标
            net_io = psutil.net_io_counters()
            metrics['network_bytes_sent'] = net_io.bytes_sent
            metrics['network_bytes_recv'] = net_io.bytes_recv
            
            # 进程指标
            metrics['process_count'] = len(psutil.pids())
            
            return metrics
        except Exception as e:
            logger.error(f"采集系统指标失败: {e}")
            return {}

    def _collect_database_metrics(self) -> Dict[str, float]:
        """采集数据库表大小指标 (单位: MB)"""
        try:
            db_metrics = {}
            sql = """
            SELECT 
                relname as table_name,
                pg_total_relation_size(relid) / (1024.0 * 1024.0) as size_mb
            FROM pg_catalog.pg_statio_user_tables;
            """
            with SessionLocal() as db:
                result = db.execute(text(sql))
                for row in result:
                    # row[0] 是表名, row[1] 是大小(MB)
                    db_metrics[row[0]] = float(row[1])
            return db_metrics
        except Exception as e:
            logger.error(f"采集数据库指标失败: {e}")
            return {}

    def _check_alert_rules(self, metrics: Dict[str, float]):
        """检查告警规则"""
        for rule_name, rule in self.alert_rules.items():
            if not rule.enabled:
                continue
                
            if rule.metric_name not in metrics:
                continue
                
            value = metrics[rule.metric_name]
            
            # 检查条件
            triggered = False
            if rule.condition == ">":
                triggered = value > rule.threshold
            elif rule.condition == "<":
                triggered = value < rule.threshold
            elif rule.condition == ">=":
                triggered = value >= rule.threshold
            elif rule.condition == "<=":
                triggered = value <= rule.threshold
            elif rule.condition == "==":
                triggered = value == rule.threshold
            
            if triggered:
                message = rule.message_template.format(value=value)
                self.add_alert(
                    level=rule.level.value,
                    title=rule.name,
                    message=message,
                    alert_type=rule.alert_type.value,
                    source="system_monitor"
                )

    def _update_service_status(self):
        """更新服务状态"""
        try:
            services = {
                'database': self._check_database_status(),
                'api_server': self._check_api_server_status(),
                'scheduler': self._check_scheduler_status(),
            }
            
            with SessionLocal() as db:
                for service_name, status in services.items():
                    # 更新或创建服务状态记录
                    service_status = db.query(SystemServiceStatus)\
                        .filter(SystemServiceStatus.service_name == service_name)\
                        .first()
                    
                    if not service_status:
                        service_status = SystemServiceStatus(
                            service_name=service_name,
                            status=status.value,
                            last_check=datetime.now()
                        )
                        db.add(service_status)
                    else:
                        service_status.status = status.value
                        service_status.last_check = datetime.now()
                    
                    db.commit()
                    
        except Exception as e:
            logger.error(f"更新服务状态失败: {e}")

    def _check_database_status(self) -> ServiceStatus:
        """检查数据库状态"""
        try:
            with SessionLocal() as db:
                db.execute(text("SELECT 1"))
                return ServiceStatus.HEALTHY
        except Exception as e:
            logger.error(f"数据库连接检查失败: {e}")
            return ServiceStatus.UNHEALTHY

    def _check_api_server_status(self) -> ServiceStatus:
        """检查API服务器状态"""
        # 这里可以添加更详细的API健康检查
        try:
            # 简单的内部检查
            return ServiceStatus.HEALTHY
        except Exception:
            return ServiceStatus.UNHEALTHY

    def _check_scheduler_status(self) -> ServiceStatus:
        """检查调度器状态"""
        # 这里可以添加调度器状态检查
        return ServiceStatus.HEALTHY

    def get_system_health(self) -> SystemHealth:
        """获取系统健康状态"""
        try:
            metrics = self._collect_system_metrics()
            
            # 获取服务状态
            services = {}
            with SessionLocal() as db:
                service_statuses = db.query(SystemServiceStatus).all()
                for service in service_statuses:
                    services[service.service_name] = ServiceStatus(service.status)
            
            # 网络IO
            net_io = psutil.net_io_counters()
            network_io = {
                'bytes_sent': net_io.bytes_sent,
                'bytes_recv': net_io.bytes_recv,
                'packets_sent': net_io.packets_sent,
                'packets_recv': net_io.packets_recv
            }
            
            return SystemHealth(
                cpu_usage=metrics.get('cpu_usage', 0),
                memory_usage=metrics.get('memory_usage', 0),
                disk_usage=metrics.get('disk_usage', 0),
                network_io=network_io,
                service_status=services,
                timestamp=datetime.now()
            )
        except Exception as e:
            logger.error(f"获取系统健康状态失败: {e}")
            return SystemHealth(
                cpu_usage=0, memory_usage=0, disk_usage=0,
                network_io={}, service_status={}, timestamp=datetime.now()
            )

    def get_monitoring_data(self) -> Dict:
        """获取监控概览数据"""
        try:
            health = self.get_system_health()
            
            # 获取最近的告警数量
            with SessionLocal() as db:
                recent_alerts = db.query(SystemAlert)\
                    .filter(SystemAlert.timestamp >= datetime.now() - timedelta(hours=24))\
                    .count()
                
                critical_alerts = db.query(SystemAlert)\
                    .filter(and_(
                        SystemAlert.timestamp >= datetime.now() - timedelta(hours=24),
                        SystemAlert.level == AlertLevel.CRITICAL.value
                    ))\
                    .count()
            
            return {
                "status": "running",
                "last_update": datetime.now().isoformat(),
                "system_health": {
                    "cpu_usage": health.cpu_usage,
                    "memory_usage": health.memory_usage,
                    "disk_usage": health.disk_usage,
                    "network_io": health.network_io
                },
                "services": {name: status.value for name, status in health.service_status.items()},
                "alerts": {
                    "total_24h": recent_alerts,
                    "critical_24h": critical_alerts
                },
                "performance": {
                    "uptime": self._get_system_uptime(),
                    "process_count": len(psutil.pids()),
                    "load_average": self._get_load_average()
                },
                "database_size": self._collect_database_metrics()
            }
        except Exception as e:
            logger.error(f"获取监控数据失败: {e}")
            return {"status": "error", "message": str(e)}

    def _get_system_uptime(self) -> float:
        """获取系统运行时间（小时）"""
        try:
            return time.time() - psutil.boot_time()
        except:
            return 0.0

    def _get_load_average(self) -> List[float]:
        """获取系统负载平均值"""
        try:
            return list(psutil.getloadavg())
        except:
            return [0.0, 0.0, 0.0]

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
                    query = query.filter(SystemAlert.alert_type == alert_type.lower())
                
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
                        "source": alert.source,
                        "metadata": alert.alert_metadata or {}
                    })
                return result
        except Exception as e:
            logger.error(f"获取告警列表失败: {e}")
            return []

    def acknowledge_alert(self, alert_id: int, acknowledged_by: str = "admin") -> bool:
        """确认告警"""
        try:
            with SessionLocal() as db:
                alert = db.query(SystemAlert).filter(SystemAlert.id == alert_id).first()
                if alert:
                    alert.acknowledged = True
                    alert.acknowledged_at = datetime.now()
                    alert.acknowledged_by = acknowledged_by
                    db.commit()
                    return True
                return False
        except Exception as e:
            logger.error(f"确认告警失败: {e}")
            return False

    def get_performance_metrics(self, time_range: str = "1h", interval: str = "1m") -> Dict:
        """获取性能指标时间序列数据"""
        try:
            # 根据 timeRange 确定起始时间
            now = datetime.now()
            if time_range == "1h":
                start_time = now - timedelta(hours=1)
            elif time_range == "6h":
                start_time = now - timedelta(hours=6)
            elif time_range == "12h":
                start_time = now - timedelta(hours=12)
            elif time_range == "1d":
                start_time = now - timedelta(days=1)
            else:
                start_time = now - timedelta(hours=1)

            with SessionLocal() as db:
                # 查询指标
                metrics = db.query(SystemMonitorMetric)\
                    .filter(SystemMonitorMetric.timestamp >= start_time)\
                    .order_by(SystemMonitorMetric.timestamp.asc())\
                    .all()
                
                # 分组组织数据
                data_by_ts = {}
                for m in metrics:
                    # 格式化时间戳，这里可以根据 interval 进一步处理，但目前保持原样
                    ts = m.timestamp.isoformat()
                    if ts not in data_by_ts:
                        data_by_ts[ts] = {"cpu": None, "memory": None, "disk": None}
                    
                    if m.metric_name == 'cpu_usage':
                        data_by_ts[ts]["cpu"] = m.metric_value
                    elif m.metric_name == 'memory_usage':
                        data_by_ts[ts]["memory"] = m.metric_value
                    elif m.metric_name == 'disk_usage':
                        data_by_ts[ts]["disk"] = m.metric_value
                
                # 转换回平坦列表，按时间排序，确保所有列表长度一致
                sorted_ts = sorted(data_by_ts.keys())
                timestamps = sorted_ts
                cpu_usage = [data_by_ts[ts]["cpu"] for ts in sorted_ts]
                memory_usage = [data_by_ts[ts]["memory"] for ts in sorted_ts]
                disk_usage = [data_by_ts[ts]["disk"] for ts in sorted_ts]
                
                return {
                    "timestamps": timestamps,
                    "cpuUsage": cpu_usage,
                    "memoryUsage": memory_usage,
                    "diskUsage": disk_usage
                }
        except Exception as e:
            logger.error(f"获取性能指标失败: {e}")
            return {"error": str(e)}

    def record_metric(self, name: str, value: float, tags: Optional[Dict] = None):
        """记录监控指标"""
        try:
            with SessionLocal() as db:
                metric = SystemMonitorMetric(
                    metric_name=name,
                    metric_value=value,
                    tags=tags,
                    timestamp=datetime.now()
                )
                db.add(metric)
                db.commit()
                
                # 触发回调
                if name in self.metric_callbacks:
                    for callback in self.metric_callbacks[name]:
                        try:
                            callback(name, value, tags)
                        except Exception as e:
                            logger.error(f"指标回调执行失败: {e}")
                            
        except Exception as e:
            logger.error(f"记录指标失败 {name}: {e}")

    def add_alert(self, level: str, title: str, message: str, 
                  alert_type: str = "system", source: str = "monitor", 
                  metadata: Optional[Dict] = None) -> Optional[int]:
        """生成告警"""
        try:
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
                logger.info(f"成功生成告警: [{level}] {title}")
                return alert.id
        except Exception as e:
            logger.error(f"生成告警失败: {e}")
            return None

    def add_metric_callback(self, metric_name: str, callback: Callable):
        """添加指标回调函数"""
        if metric_name not in self.metric_callbacks:
            self.metric_callbacks[metric_name] = []
        self.metric_callbacks[metric_name].append(callback)

    def add_alert_rule(self, rule: AlertRule):
        """添加告警规则"""
        self.alert_rules[rule.name] = rule

    def remove_alert_rule(self, rule_name: str):
        """移除告警规则"""
        if rule_name in self.alert_rules:
            del self.alert_rules[rule_name]

    def get_alert_rules(self) -> List[Dict]:
        """获取告警规则列表"""
        return [
            {
                "name": rule.name,
                "metric_name": rule.metric_name,
                "condition": rule.condition,
                "threshold": rule.threshold,
                "level": rule.level.value,
                "alert_type": rule.alert_type.value,
                "message_template": rule.message_template,
                "enabled": rule.enabled
            }
            for rule in self.alert_rules.values()
        ]

# 单例导出
system_monitor = SystemMonitor()
