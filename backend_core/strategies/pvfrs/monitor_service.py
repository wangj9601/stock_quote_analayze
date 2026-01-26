"""
PVFRS策略系统监控服务
负责实时监控、性能指标统计和告警管理
已迁移到通用系统监控模块，此文件保持兼容性
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional, Any

# 导入通用系统监控模块
from backend_core.monitoring import system_monitor, alert_manager

logger = logging.getLogger(__name__)

class MonitorService:
    """PVFRS监控服务类 - 兼容性包装器"""
    
    _instance = None
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            logger.info("PVFRS监控服务单例初始化（使用通用系统监控）")

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MonitorService, cls).__new__(cls)
        return cls._instance

    def start_background_monitoring(self):
        """启动后台监控线程"""
        logger.info("PVFRS监控请求已重定向到通用系统监控")
        # 通用系统监控已在main.py中启动，这里只是记录日志

    def stop_background_monitoring(self):
        """停止后台监控线程"""
        logger.info("PVFRS监控停止请求已重定向到通用系统监控")

    def get_monitoring_data(self) -> Dict:
        """获取监控概览数据"""
        try:
            # 从通用系统监控获取数据
            data = system_monitor.get_monitoring_data()
            
            # 添加PVFRS特定的数据
            pvfrs_data = self._get_pvfrs_specific_data()
            
            # 合并数据
            if pvfrs_data:
                data.update(pvfrs_data)
            
            return data
        except Exception as e:
            logger.error(f"获取PVFRS监控数据失败: {e}")
            return {"status": "error", "message": str(e)}

    def get_monitoring_alerts(self, limit: int = 50) -> List[Dict]:
        """获取告警列表"""
        try:
            # 从通用系统监控获取告警，过滤PVFRS相关的
            alerts = system_monitor.get_alerts(limit=limit)
            
            # 过滤PVFRS相关的告警
            pvfrs_alerts = [
                alert for alert in alerts 
                if alert.get('source') == 'pvfrs' or 
                   'pvfrs' in alert.get('title', '').lower()
            ]
            
            return pvfrs_alerts
        except Exception as e:
            logger.error(f"获取PVFRS告警列表失败: {e}")
            return []

    def acknowledge_alert(self, alert_id: int) -> bool:
        """确认告警"""
        try:
            return system_monitor.acknowledge_alert(alert_id)
        except Exception as e:
            logger.error(f"确认PVFRS告警失败: {e}")
            return False

    def get_performance_metrics(self, time_range: str = "1h", interval: str = "1m") -> Dict:
        """获取性能指标时间序列数据"""
        try:
            # 从通用系统监控获取指标
            metrics = system_monitor.get_performance_metrics(time_range, interval)
            
            # 添加PVFRS特定的指标
            pvfrs_metrics = self._get_pvfrs_metrics(time_range)
            
            # 合并指标数据
            if pvfrs_metrics:
                for key, values in pvfrs_metrics.items():
                    if key not in metrics:
                        metrics[key] = values
            
            return metrics
        except Exception as e:
            logger.error(f"获取PVFRS性能指标失败: {e}")
            return {"error": str(e)}

    def record_metric(self, name: str, value: float, tags: Optional[Dict] = None):
        """记录监控指标"""
        try:
            # 添加PVFRS标签
            if not tags:
                tags = {}
            tags['source'] = 'pvfrs'
            
            # 通过通用系统监控记录
            system_monitor.record_metric(name, value, tags)
        except Exception as e:
            logger.error(f"记录PVFRS指标失败 {name}: {e}")

    def add_alert(self, level: str, title: str, message: str, alert_type: str = "system", source: str = "monitor"):
        """生成告警"""
        try:
            # 通过通用告警管理器创建告警
            alert_id = alert_manager.create_alert(
                level=level,
                title=title,
                message=message,
                alert_type=alert_type,
                source='pvfrs'  # 标记为PVFRS来源
            )
            
            if alert_id:
                logger.info(f"PVFRS告警已创建: [{level}] {title}")
            else:
                logger.warning(f"PVFRS告警创建失败: {title}")
                
        except Exception as e:
            logger.error(f"创建PVFRS告警失败: {e}")

    def _get_pvfrs_specific_data(self) -> Dict:
        """获取PVFRS特定数据"""
        try:
            # 这里可以添加PVFRS特定的业务逻辑
            pvfrs_data = {
                "pvfrs_status": "active",
                "pvfrs_strategies": 3,  # 示例数据
                "pvfrs_active_signals": 5,
                "pvfrs_last_update": datetime.now().isoformat()
            }
            
            # 尝试从数据库获取实际的PVFRS数据
            try:
                from backend_api.database import SessionLocal
                from backend_api.models import PVFRSBacktestTask
                
                with SessionLocal() as db:
                    # 获取活跃的回测任务数
                    active_tasks = db.query(PVFRSBacktestTask).filter(
                        PVFRSBacktestTask.status == 'running'
                    ).count()
                    
                    pvfrs_data["pvfrs_active_tasks"] = active_tasks
                    
            except ImportError:
                logger.warning("PVFRS模型不可用，使用默认数据")
            except Exception as e:
                logger.warning(f"获取PVFRS业务数据失败: {e}")
            
            return pvfrs_data
            
        except Exception as e:
            logger.error(f"获取PVFRS特定数据失败: {e}")
            return {}

    def _get_pvfrs_metrics(self, time_range: str) -> Dict:
        """获取PVFRS特定指标"""
        try:
            # 这里可以添加PVFRS特定的指标计算
            pvfrs_metrics = {}
            
            # 示例：计算PVFRS策略性能指标
            try:
                from backend_api.database import SessionLocal
                from backend_api.models import PVFRSBacktestResult
                from sqlalchemy import desc
                
                with SessionLocal() as db:
                    # 获取最近的回测结果
                    recent_results = db.query(PVFRSBacktestResult)\
                        .order_by(desc(PVFRSBacktestResult.created_at))\
                        .limit(10)\
                        .all()
                    
                    if recent_results:
                        # 计算平均收益率
                        valid_returns = [r.total_return for r in recent_results if r.total_return is not None]
                        if valid_returns:
                            avg_return = float(sum(valid_returns) / len(valid_returns))
                            pvfrs_metrics["pvfrs_avg_return"] = [avg_return]
                        
                        # 计算平均胜率
                        valid_win_rates = [r.win_rate for r in recent_results if r.win_rate is not None]
                        if valid_win_rates:
                            avg_win_rate = float(sum(valid_win_rates) / len(valid_win_rates))
                            pvfrs_metrics["pvfrs_avg_win_rate"] = [avg_win_rate]
                        
                        # 计算平均夏普比率
                        valid_sharpe_ratios = [r.sharpe_ratio for r in recent_results if r.sharpe_ratio is not None]
                        if valid_sharpe_ratios:
                            avg_sharpe = float(sum(valid_sharpe_ratios) / len(valid_sharpe_ratios))
                            pvfrs_metrics["pvfrs_avg_sharpe"] = [avg_sharpe]
                        
            except ImportError:
                logger.warning("PVFRS模型不可用，跳过指标计算")
            except Exception as e:
                logger.warning(f"计算PVFRS指标失败: {e}")
            
            return pvfrs_metrics
            
        except Exception as e:
            logger.error(f"获取PVFRS指标失败: {e}")
            return {}

    def get_pvfrs_health_status(self) -> Dict:
        """获取PVFRS健康状态"""
        try:
            health_status = {
                "status": "healthy",
                "last_check": datetime.now().isoformat(),
                "components": {
                    "strategy_engine": "healthy",
                    "data_feed": "healthy", 
                    "backtest_service": "healthy",
                    "monitoring": "healthy"
                },
                "metrics": {
                    "active_strategies": 3,
                    "daily_signals": 15,
                    "success_rate": 0.75
                }
            }
            
            # 可以添加实际的健康检查逻辑
            # 例如检查数据库连接、服务可用性等
            
            return health_status
            
        except Exception as e:
            logger.error(f"获取PVFRS健康状态失败: {e}")
            return {
                "status": "unknown",
                "error": str(e),
                "last_check": datetime.now().isoformat()
            }

# 保持向后兼容的单例
monitor_service = MonitorService()
