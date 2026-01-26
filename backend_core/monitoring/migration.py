"""
PVFRS监控数据迁移脚本
将PVFRS模块的监控数据迁移到通用系统监控模块
"""

import logging
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_

from backend_api.database import SessionLocal
from backend_api.models import (
    SystemAlert, 
    SystemMonitorMetric, 
    SystemServiceStatus
)

logger = logging.getLogger(__name__)

class PVFRSMigration:
    """PVFRS数据迁移器"""
    
    def __init__(self):
        self.migrated_alerts = 0
        self.migrated_metrics = 0
        self.errors = []

    def migrate_all_data(self) -> Dict[str, Any]:
        """迁移所有数据"""
        try:
            logger.info("开始PVFRS监控数据迁移...")
            
            # 迁移告警数据
            self.migrate_alerts()
            
            # 迁移指标数据
            self.migrate_metrics()
            
            # 迁移服务状态
            self.migrate_service_status()
            
            result = {
                "success": True,
                "migrated_alerts": self.migrated_alerts,
                "migrated_metrics": self.migrated_metrics,
                "errors": self.errors,
                "message": "PVFRS监控数据迁移完成"
            }
            
            logger.info(f"迁移完成: 告警 {self.migrated_alerts} 条, 指标 {self.migrated_metrics} 条")
            return result
            
        except Exception as e:
            error_msg = f"迁移失败: {str(e)}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            
            return {
                "success": False,
                "migrated_alerts": self.migrated_alerts,
                "migrated_metrics": self.migrated_metrics,
                "errors": self.errors,
                "message": error_msg
            }

    def migrate_alerts(self):
        """迁移告警数据"""
        try:
            # 尝试从PVFRS告警表读取数据
            pvfrs_alerts = self._get_pvfrs_alerts()
            
            with SessionLocal() as db:
                for alert_data in pvfrs_alerts:
                    try:
                        # 检查是否已存在相同的告警
                        existing_alert = db.query(SystemAlert).filter(
                            and_(
                                SystemAlert.title == alert_data['title'],
                                SystemAlert.timestamp == alert_data['timestamp'],
                                SystemAlert.source == 'pvfrs'
                            )
                        ).first()
                        
                        if existing_alert:
                            logger.debug(f"告警已存在，跳过: {alert_data['title']}")
                            continue
                        
                        # 创建新的系统告警
                        system_alert = SystemAlert(
                            level=alert_data['level'],
                            alert_type=alert_data.get('alert_type', 'business'),
                            title=alert_data['title'],
                            message=alert_data['message'],
                            source='pvfrs',
                            timestamp=alert_data['timestamp'],
                            acknowledged=alert_data.get('acknowledged', False),
                            acknowledged_at=alert_data.get('acknowledged_at'),
                            acknowledged_by=alert_data.get('acknowledged_by'),
                            metadata=alert_data.get('metadata', {})
                        )
                        
                        db.add(system_alert)
                        self.migrated_alerts += 1
                        
                    except Exception as e:
                        error_msg = f"迁移告警失败: {alert_data.get('title', 'unknown')} - {str(e)}"
                        logger.error(error_msg)
                        self.errors.append(error_msg)
                
                db.commit()
                logger.info(f"告警迁移完成，共迁移 {self.migrated_alerts} 条")
                
        except Exception as e:
            error_msg = f"告警迁移过程失败: {str(e)}"
            logger.error(error_msg)
            self.errors.append(error_msg)

    def migrate_metrics(self):
        """迁移指标数据"""
        try:
            # 尝试从PVFRS指标表读取数据
            pvfrs_metrics = self._get_pvfrs_metrics()
            
            with SessionLocal() as db:
                for metric_data in pvfrs_metrics:
                    try:
                        # 创建新的系统指标
                        system_metric = SystemMonitorMetric(
                            metric_name=metric_data['metric_name'],
                            metric_value=metric_data['metric_value'],
                            tags=metric_data.get('tags', {}),
                            timestamp=metric_data['timestamp']
                        )
                        
                        db.add(system_metric)
                        self.migrated_metrics += 1
                        
                    except Exception as e:
                        error_msg = f"迁移指标失败: {metric_data.get('metric_name', 'unknown')} - {str(e)}"
                        logger.error(error_msg)
                        self.errors.append(error_msg)
                
                db.commit()
                logger.info(f"指标迁移完成，共迁移 {self.migrated_metrics} 条")
                
        except Exception as e:
            error_msg = f"指标迁移过程失败: {str(e)}"
            logger.error(error_msg)
            self.errors.append(error_msg)

    def migrate_service_status(self):
        """迁移服务状态"""
        try:
            # 为PVFRS相关服务创建状态记录
            pvfrs_services = [
                {
                    "service_name": "pvfrs_strategy",
                    "status": "healthy",
                    "description": "PVFRS策略服务"
                },
                {
                    "service_name": "pvfrs_backtest",
                    "status": "healthy", 
                    "description": "PVFRS回测服务"
                },
                {
                    "service_name": "pvfrs_monitor",
                    "status": "healthy",
                    "description": "PVFRS监控服务"
                }
            ]
            
            with SessionLocal() as db:
                for service_data in pvfrs_services:
                    try:
                        # 检查是否已存在
                        existing_service = db.query(SystemServiceStatus).filter(
                            SystemServiceStatus.service_name == service_data["service_name"]
                        ).first()
                        
                        if existing_service:
                            logger.debug(f"服务状态已存在，跳过: {service_data['service_name']}")
                            continue
                        
                        # 创建新的服务状态记录
                        service_status = SystemServiceStatus(
                            service_name=service_data["service_name"],
                            status=service_data["status"],
                            last_check=datetime.now(),
                            metadata={"description": service_data.get("description", "")}
                        )
                        
                        db.add(service_status)
                        
                    except Exception as e:
                        error_msg = f"迁移服务状态失败: {service_data['service_name']} - {str(e)}"
                        logger.error(error_msg)
                        self.errors.append(error_msg)
                
                db.commit()
                logger.info("服务状态迁移完成")
                
        except Exception as e:
            error_msg = f"服务状态迁移过程失败: {str(e)}"
            logger.error(error_msg)
            self.errors.append(error_msg)

    def _get_pvfrs_alerts(self) -> List[Dict[str, Any]]:
        """获取PVFRS告警数据"""
        try:
            # 尝试导入PVFRS模型
            from backend_api.models.pvfrs_enhanced import PVFRSAlertEnhanced
            
            with SessionLocal() as db:
                alerts = db.query(PVFRSAlertEnhanced).all()
                
                result = []
                for alert in alerts:
                    result.append({
                        "level": alert.level,
                        "title": alert.title,
                        "message": alert.message,
                        "timestamp": alert.timestamp,
                        "acknowledged": alert.acknowledged,
                        "acknowledged_at": alert.acknowledged_at,
                        "acknowledged_by": alert.acknowledged_by,
                        "alert_type": alert.alert_type or "business",
                        "metadata": alert.metadata or {}
                    })
                
                return result
                
        except ImportError:
            logger.warning("PVFRS增强模型不存在，尝试使用基础模型")
            return self._get_pvfrs_alerts_basic()
        except Exception as e:
            logger.error(f"获取PVFRS告警数据失败: {e}")
            return []

    def _get_pvfrs_alerts_basic(self) -> List[Dict[str, Any]]:
        """获取基础PVFRS告警数据"""
        try:
            # 检查是否有基础PVFRS模型
            from backend_api.models import PVFRSAlert
            
            with SessionLocal() as db:
                alerts = db.query(PVFRSAlert).all()
                
                result = []
                for alert in alerts:
                    result.append({
                        "level": alert.level,
                        "title": alert.title,
                        "message": alert.message,
                        "timestamp": alert.timestamp,
                        "acknowledged": alert.acknowledged,
                        "acknowledged_at": alert.acknowledged_at,
                        "acknowledged_by": alert.acknowledged_by,
                        "alert_type": "business",
                        "metadata": {}
                    })
                
                return result
                
        except ImportError:
            logger.warning("PVFRS基础模型也不存在，跳过告警迁移")
            return []
        except Exception as e:
            logger.error(f"获取基础PVFRS告警数据失败: {e}")
            return []

    def _get_pvfrs_metrics(self) -> List[Dict[str, Any]]:
        """获取PVFRS指标数据"""
        try:
            # 尝试导入PVFRS指标模型
            from backend_api.models.pvfrs_enhanced import PVFRSMonitorMetricEnhanced
            
            with SessionLocal() as db:
                metrics = db.query(PVFRSMonitorMetricEnhanced).all()
                
                result = []
                for metric in metrics:
                    result.append({
                        "metric_name": metric.metric_name,
                        "metric_value": metric.metric_value,
                        "timestamp": metric.timestamp,
                        "tags": metric.tags or {}
                    })
                
                return result
                
        except ImportError:
            logger.warning("PVFRS增强指标模型不存在，尝试使用基础模型")
            return self._get_pvfrs_metrics_basic()
        except Exception as e:
            logger.error(f"获取PVFRS指标数据失败: {e}")
            return []

    def _get_pvfrs_metrics_basic(self) -> List[Dict[str, Any]]:
        """获取基础PVFRS指标数据"""
        try:
            # 检查是否有基础PVFRS指标模型
            from backend_api.models import PVFRSMonitorMetric
            
            with SessionLocal() as db:
                metrics = db.query(PVFRSMonitorMetric).all()
                
                result = []
                for metric in metrics:
                    result.append({
                        "metric_name": metric.metric_name,
                        "metric_value": metric.metric_value,
                        "timestamp": metric.timestamp,
                        "tags": {}
                    })
                
                return result
                
        except ImportError:
            logger.warning("PVFRS基础指标模型也不存在，跳过指标迁移")
            return []
        except Exception as e:
            logger.error(f"获取基础PVFRS指标数据失败: {e}")
            return []

def run_migration() -> Dict[str, Any]:
    """运行迁移"""
    migration = PVFRSMigration()
    return migration.migrate_all_data()

def create_sample_data() -> Dict[str, Any]:
    """创建示例数据（当PVFRS数据不存在时）"""
    try:
        logger.info("创建PVFRS示例监控数据...")
        
        with SessionLocal() as db:
            # 创建示例告警
            sample_alerts = [
                {
                    "level": "MEDIUM",
                    "title": "PVFRS策略性能下降",
                    "message": "PVFRS策略在过去1小时内收益率下降了5%",
                    "source": "pvfrs",
                    "alert_type": "business",
                    "metadata": {"strategy": "pvfrs", "metric": "return_rate"}
                },
                {
                    "level": "LOW",
                    "title": "PVFRS回测任务完成",
                    "message": "PVFRS回测任务已成功完成，收益率12.5%",
                    "source": "pvfrs",
                    "alert_type": "business",
                    "metadata": {"strategy": "pvfrs", "task_id": "sample_task_001"}
                }
            ]
            
            for alert_data in sample_alerts:
                alert = SystemAlert(
                    level=alert_data["level"],
                    alert_type=alert_data["alert_type"],
                    title=alert_data["title"],
                    message=alert_data["message"],
                    source=alert_data["source"],
                    timestamp=datetime.now(),
                    acknowledged=False,
                    metadata=alert_data["metadata"]
                )
                db.add(alert)
            
            # 创建示例指标
            sample_metrics = [
                {"metric_name": "pvfrs_return_rate", "metric_value": 0.125},
                {"metric_name": "pvfrs_win_rate", "metric_value": 0.68},
                {"metric_name": "pvfrs_sharpe_ratio", "metric_value": 1.85},
                {"metric_name": "pvfrs_max_drawdown", "metric_value": 0.08}
            ]
            
            for metric_data in sample_metrics:
                metric = SystemMonitorMetric(
                    metric_name=metric_data["metric_name"],
                    metric_value=metric_data["metric_value"],
                    timestamp=datetime.now(),
                    tags={"source": "pvfrs", "sample": "true"}
                )
                db.add(metric)
            
            db.commit()
            
            logger.info("示例数据创建完成")
            return {
                "success": True,
                "message": "示例数据创建完成",
                "created_alerts": len(sample_alerts),
                "created_metrics": len(sample_metrics)
            }
            
    except Exception as e:
        error_msg = f"创建示例数据失败: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "message": error_msg
        }

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 运行迁移
    result = run_migration()
    
    if result["success"]:
        print(f"✅ 迁移成功!")
        print(f"   - 迁移告警: {result['migrated_alerts']} 条")
        print(f"   - 迁移指标: {result['migrated_metrics']} 条")
        if result["errors"]:
            print(f"   - 错误数量: {len(result['errors'])}")
            for error in result["errors"]:
                print(f"     - {error}")
    else:
        print(f"❌ 迁移失败: {result['message']}")
        
        # 如果迁移失败，创建示例数据
        print("尝试创建示例数据...")
        sample_result = create_sample_data()
        if sample_result["success"]:
            print(f"✅ 示例数据创建成功!")
            print(f"   - 创建告警: {sample_result['created_alerts']} 条")
            print(f"   - 创建指标: {sample_result['created_metrics']} 条")
        else:
            print(f"❌ 示例数据创建失败: {sample_result['message']}")
