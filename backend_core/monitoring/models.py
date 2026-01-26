"""
系统监控相关的数据库模型
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class SystemMonitorMetric(Base):
    """系统监控指标表"""
    __tablename__ = "system_monitor_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_name = Column(String(100), nullable=False, index=True)  # 指标名称
    metric_value = Column(Float, nullable=False)  # 指标值
    tags = Column(JSON, nullable=True)  # 标签（JSON格式）
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

class SystemAlert(Base):
    """系统告警表"""
    __tablename__ = "system_alerts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(String(20), nullable=False, index=True)  # 告警级别：LOW, MEDIUM, HIGH, CRITICAL
    alert_type = Column(String(50), nullable=False, index=True)  # 告警类型：system, performance, business, security
    title = Column(String(200), nullable=False)  # 告警标题
    message = Column(Text, nullable=False)  # 告警消息
    source = Column(String(100), nullable=False, default="system")  # 告警来源
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    acknowledged = Column(Boolean, nullable=False, default=False)  # 是否已确认
    acknowledged_at = Column(DateTime, nullable=True)  # 确认时间
    acknowledged_by = Column(String(100), nullable=True)  # 确认人
    alert_metadata = Column(JSON, nullable=True)  # 额外元数据
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

class SystemServiceStatus(Base):
    """系统服务状态表"""
    __tablename__ = "system_service_status"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    service_name = Column(String(100), nullable=False, unique=True, index=True)  # 服务名称
    status = Column(String(20), nullable=False)  # 服务状态：healthy, degraded, unhealthy, unknown
    last_check = Column(DateTime, nullable=False, default=datetime.utcnow)  # 最后检查时间
    response_time = Column(Float, nullable=True)  # 响应时间（毫秒）
    error_message = Column(Text, nullable=True)  # 错误消息
    service_metadata = Column(JSON, nullable=True)  # 额外信息
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

class SystemAlertRule(Base):
    """系统告警规则表"""
    __tablename__ = "system_alert_rules"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, unique=True)  # 规则名称
    metric_name = Column(String(100), nullable=False)  # 监控指标名称
    condition = Column(String(10), nullable=False)  # 条件：>, <, >=, <=, ==
    threshold = Column(Float, nullable=False)  # 阈值
    level = Column(String(20), nullable=False)  # 告警级别
    alert_type = Column(String(50), nullable=False)  # 告警类型
    message_template = Column(Text, nullable=False)  # 消息模板
    enabled = Column(Boolean, nullable=False, default=True)  # 是否启用
    description = Column(Text, nullable=True)  # 规则描述
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

class SystemPerformanceReport(Base):
    """系统性能报告表"""
    __tablename__ = "system_performance_reports"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    report_name = Column(String(200), nullable=False)  # 报告名称
    report_type = Column(String(50), nullable=False)  # 报告类型：daily, weekly, monthly
    period_start = Column(DateTime, nullable=False)  # 报告周期开始时间
    period_end = Column(DateTime, nullable=False)  # 报告周期结束时间
    
    # 性能指标汇总
    avg_cpu_usage = Column(Float, nullable=True)  # 平均CPU使用率
    max_cpu_usage = Column(Float, nullable=True)  # 最大CPU使用率
    avg_memory_usage = Column(Float, nullable=True)  # 平均内存使用率
    max_memory_usage = Column(Float, nullable=True)  # 最大内存使用率
    avg_disk_usage = Column(Float, nullable=True)  # 平均磁盘使用率
    
    # 告警统计
    total_alerts = Column(Integer, nullable=False, default=0)  # 总告警数
    critical_alerts = Column(Integer, nullable=False, default=0)  # 严重告警数
    high_alerts = Column(Integer, nullable=False, default=0)  # 高级告警数
    medium_alerts = Column(Integer, nullable=False, default=0)  # 中级告警数
    low_alerts = Column(Integer, nullable=False, default=0)  # 低级告警数
    
    # 服务可用性
    service_uptime = Column(Float, nullable=True)  # 服务可用性百分比
    
    report_data = Column(JSON, nullable=True)  # 详细报告数据
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
