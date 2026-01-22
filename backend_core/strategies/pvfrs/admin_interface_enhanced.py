"""
PVFRS策略管理增强接口
重构后的AdminInterface，使用数据库存储替代内存存储
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
import logging
import json
import uuid
from dataclasses import dataclass, asdict

from backend_api.database import SessionLocal
from backend_api.services.pvfrs_admin_service import PVFRSAdminService
from backend_core.strategies.pvfrs.models import PVFRSException

logger = logging.getLogger(__name__)

@dataclass
class BacktestConfig:
    """回测配置"""
    strategy_name: str
    stock_pool: List[str]
    start_date: str
    end_date: str
    initial_capital: float
    strategy_params: Dict
    risk_params: Dict
    name: Optional[str] = None
    mode: str = "single"
    force_update: bool = False

@dataclass
class BacktestTask:
    """回测任务"""
    task_id: str
    config: BacktestConfig
    status: str
    progress: int
    current_step: str
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

@dataclass
class BacktestReport:
    """回测报告"""
    report_id: str
    task_id: str
    config: BacktestConfig
    performance: Dict
    trades: List[Dict]
    equity_curve: List[Dict]
    created_at: datetime

class AdminInterfaceEnhanced:
    """PVFRS策略管理增强接口
    
    使用数据库存储替代内存存储，提供更稳定和可扩展的策略管理功能
    """
    
    def __init__(self, pvfrs_system=None):
        """初始化管理接口"""
        self.pvfrs_system = pvfrs_system
        self.db = SessionLocal()
        self.service = PVFRSAdminService(self.db)
        logger.info("PVFRS策略管理增强接口初始化完成")
    
    def create_backtest(self, config: BacktestConfig) -> str:
        """创建回测任务"""
        try:
            # 获取或创建策略配置
            strategy_config = self.service.get_strategy_config_by_name(config.strategy_name)
            if not strategy_config:
                # 创建新的策略配置
                config_id = self.service.create_strategy_config(
                    name=config.strategy_name,
                    description=f"PVFRS策略: {config.strategy_name}",
                    config_params={
                        'strategy_params': config.strategy_params,
                        'risk_params': config.risk_params
                    }
                )
            else:
                config_id = strategy_config.id
            
            # 创建回测任务
            task_id = self.service.create_backtest_task(
                strategy_config_id=config_id,
                mode=config.mode,
                stock_codes=config.stock_pool,
                market="CN",
                start_date=datetime.strptime(config.start_date, "%Y-%m-%d").date(),
                end_date=datetime.strptime(config.end_date, "%Y-%m-%d").date(),
                initial_capital=config.initial_capital,
                task_name=config.name
            )
            
            logger.info(f"创建回测任务成功: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"创建回测任务失败: {str(e)}")
            raise PVFRSException(f"创建回测任务失败: {str(e)}")
    
    def get_task_progress(self, task_id: str) -> Dict:
        """获取任务进度"""
        try:
            task = self.service.get_backtest_task(task_id)
            if not task:
                return {'error': '任务不存在'}
            
            return {
                'task_id': task.task_id,
                'name': task.task_name,
                'status': task.status,
                'progress': task.progress,
                'current_step': task.current_step,
                'error_message': task.error_message,
                'created_at': task.created_at.isoformat() if task.created_at else None,
                'started_at': task.started_at.isoformat() if task.started_at else None,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None
            }
            
        except Exception as e:
            logger.error(f"获取任务进度失败: {str(e)}")
            return {'error': str(e)}
    
    def update_task_progress(self, task_id: str, progress: int, 
                           current_step: str, status: str = "running") -> bool:
        """更新任务进度"""
        try:
            return self.service.update_task_status(
                task_id=task_id,
                status=status,
                progress=progress,
                current_step=current_step
            )
        except Exception as e:
            logger.error(f"更新任务进度失败: {str(e)}")
            return False
    
    def complete_task(self, task_id: str, performance: Dict, 
                     trades: List[Dict], equity_curve: List[Dict]) -> str:
        """完成任务并保存结果"""
        try:
            # 更新任务状态
            self.service.update_task_status(task_id, "completed", 100, "任务完成")
            
            # 获取任务信息
            task = self.service.get_backtest_task(task_id)
            if not task:
                raise PVFRSException("任务不存在")
            
            # 创建回测结果
            result_id = self.service.create_backtest_result(
                task_id=task_id,
                stock_code=task.stock_codes[0] if task.stock_codes else "UNKNOWN",
                market=task.market,
                backtest_date=datetime.now().date(),
                performance_data=performance
            )
            
            # 保存交易记录
            for trade in trades:
                self.service.create_trade_record(result_id, trade.get('stock_code', 'UNKNOWN'), trade)
            
            # 保存收益曲线
            for point in equity_curve:
                self.service.create_equity_curve_point(result_id, point.get('stock_code', 'UNKNOWN'), point)
            
            # 生成报告ID
            report_id = f"report_{task_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            logger.info(f"任务完成: {task_id}, 报告ID: {report_id}")
            return report_id
            
        except Exception as e:
            logger.error(f"完成任务失败: {str(e)}")
            self.service.update_task_status(task_id, "failed", 0, f"任务失败: {str(e)}")
            raise PVFRSException(f"完成任务失败: {str(e)}")
    
    def get_report(self, report_id: str) -> Optional[Dict]:
        """获取回测报告"""
        try:
            # 从report_id提取task_id
            if report_id.startswith("report_"):
                task_id = report_id.split("_", 2)[1]
            else:
                task_id = report_id
            
            # 获取任务信息
            task = self.service.get_backtest_task(task_id)
            if not task:
                return None
            
            # 获取结果信息
            results = self.service.get_backtest_results(task_id)
            if not results:
                return None
            
            result = results[0]
            
            # 获取交易记录
            trades = self.service.get_trade_records(result.id)
            
            # 获取收益曲线
            equity_curve = self.service.get_equity_curve(result.id)
            
            # 转换对象为字典的辅助函数
            def sa_to_dict(obj):
                if not obj: return {}
                return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
            
            # 构建报告数据
            report_data = {
                'report_id': report_id,
                'task_id': task_id,
                'config': {
                    'strategy_name': task.strategy_config.name if task.strategy_config else 'Unknown',
                    'stock_pool': task.stock_codes,
                    'start_date': task.start_date.isoformat(),
                    'end_date': task.end_date.isoformat(),
                    'initial_capital': float(task.initial_capital),
                    'strategy_params': task.strategy_config.config_params.get('strategy_params', {}) if task.strategy_config else {},
                    'risk_params': task.strategy_config.config_params.get('risk_params', {}) if task.strategy_config else {}
                },
                'performance': {
                    'total_return': float(result.total_return),
                    'annual_return': float(result.annual_return),
                    'max_drawdown': float(result.max_drawdown),
                    'sharpe_ratio': float(result.sharpe_ratio),
                    'win_rate': float(result.win_rate),
                    'profit_factor': float(result.profit_factor),
                    'total_trades': result.total_trades,
                    'winning_trades': result.winning_trades,
                    'avg_holding_period': float(result.avg_holding_period),
                    'volatility': float(result.volatility)
                },
                'trades': [sa_to_dict(trade) for trade in trades],
                'equity_curve': [sa_to_dict(point) for point in equity_curve],
                'created_at': result.created_at.isoformat()
            }
            
            return report_data
            
        except Exception as e:
            logger.error(f"获取报告失败: {str(e)}")
            return None

    def get_trades(self, task_id: str) -> List[Dict]:
        """获取指定任务的交易明细"""
        try:
            results = self.service.get_backtest_results(task_id)
            if not results:
                return []
            
            result = results[0]
            trades = self.service.get_trade_records(result.id)
            
            def sa_to_dict(obj):
                if not obj: return {}
                from datetime import datetime, date
                
                trade_dict = {}
                for c in obj.__table__.columns:
                    value = getattr(obj, c.name)
                    # 处理日期时间字段
                    if isinstance(value, datetime):
                        trade_dict[c.name] = value.isoformat() if value else None
                    elif isinstance(value, date):
                        trade_dict[c.name] = value.strftime('%Y-%m-%d') if value else None
                    elif isinstance(value, Decimal):
                        trade_dict[c.name] = float(value)
                    else:
                        trade_dict[c.name] = value
                
                # 确保 entry_date 字段存在（从 entry_time 或 entry_date 提取）
                if 'entry_date' not in trade_dict or not trade_dict.get('entry_date'):
                    if trade_dict.get('entry_time'):
                        try:
                            if isinstance(trade_dict['entry_time'], str):
                                # 如果是字符串，尝试解析
                                entry_dt = datetime.fromisoformat(trade_dict['entry_time'].replace('Z', '+00:00'))
                            else:
                                entry_dt = trade_dict['entry_time']
                            trade_dict['entry_date'] = entry_dt.strftime('%Y-%m-%d') if isinstance(entry_dt, datetime) else None
                        except (ValueError, AttributeError, TypeError):
                            # 如果已经是字符串格式，尝试直接提取日期部分
                            if isinstance(trade_dict.get('entry_time'), str):
                                trade_dict['entry_date'] = trade_dict['entry_time'][:10] if len(trade_dict['entry_time']) >= 10 else None
                            else:
                                trade_dict['entry_date'] = None
                
                # 确保 exit_time 字段正确格式化
                # 数据库字段是 exit_time (DateTime)，需要确保正确返回
                exit_time_value = trade_dict.get('exit_time')
                exit_reason = trade_dict.get('exit_reason')
                exit_price = trade_dict.get('exit_price', 0)
                
                # 判断交易是否已完成
                is_completed = bool(exit_reason) or (exit_price and float(exit_price) > 0)
                
                # 如果 exit_time 是空字符串，转换为 None
                if exit_time_value == '':
                    exit_time_value = None
                    trade_dict['exit_time'] = None
                
                # 如果 exit_time 已经有值（从数据库读取的 DateTime），确保格式正确
                if exit_time_value and isinstance(exit_time_value, str):
                    # 如果已经是 ISO 格式字符串，直接使用
                    # 确保格式是前端可以识别的（ISO 8601 格式）
                    try:
                        # 验证格式是否正确
                        datetime.fromisoformat(exit_time_value.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        # 如果格式不对，尝试修复
                        try:
                            # 尝试解析为日期时间
                            if len(exit_time_value) == 10:  # 只有日期部分 'YYYY-MM-DD'
                                exit_dt = datetime.strptime(exit_time_value, '%Y-%m-%d')
                                trade_dict['exit_time'] = exit_dt.isoformat()
                            else:
                                # 尝试其他格式
                                exit_dt = datetime.strptime(exit_time_value, '%Y-%m-%d %H:%M:%S')
                                trade_dict['exit_time'] = exit_dt.isoformat()
                        except (ValueError, TypeError):
                            logger.warning(f"无法解析 exit_time 格式: {exit_time_value}")
                            pass
                
                # 如果 exit_time 为空但交易已完成，尝试从 exit_date 获取
                if is_completed and not trade_dict.get('exit_time'):
                    exit_date_value = trade_dict.get('exit_date')
                    if exit_date_value:
                        try:
                            if isinstance(exit_date_value, str):
                                exit_dt = datetime.strptime(exit_date_value, '%Y-%m-%d')
                            elif isinstance(exit_date_value, date):
                                exit_dt = datetime.combine(exit_date_value, datetime.min.time())
                            else:
                                exit_dt = None
                            if exit_dt:
                                trade_dict['exit_time'] = exit_dt.isoformat()
                                logger.info(f"从 exit_date 推断 exit_time: {trade_dict.get('stock_code')} -> {exit_dt.isoformat()}")
                        except (ValueError, TypeError, AttributeError):
                            logger.warning(f"无法从 exit_date 转换 exit_time: {exit_date_value}")
                            pass
                
                # 确保 exit_time 不为空字符串（前端判断需要）
                if trade_dict.get('exit_time') == '':
                    trade_dict['exit_time'] = None
                
                # 调试日志：记录 exit_time 的值（仅对已完成的交易）
                if is_completed:
                    logger.info(f"交易记录 - stock_code: {trade_dict.get('stock_code')}, "
                               f"exit_time: {trade_dict.get('exit_time')}, "
                               f"exit_reason: {exit_reason}, exit_price: {exit_price}, "
                               f"exit_time类型: {type(trade_dict.get('exit_time'))}, "
                               f"exit_date: {trade_dict.get('exit_date')}")
                
                return trade_dict
            
            return [sa_to_dict(trade) for trade in trades]
        except Exception as e:
            logger.error(f"获取交易记录失败: {str(e)}")
            return []
    
    def list_backtest_tasks(self, status: Optional[str] = None, 
                          limit: int = 50, offset: int = 0) -> List[Dict]:
        """列出回测任务"""
        try:
            tasks = self.service.list_backtest_tasks(status, limit, offset)
            
            task_list = []
            for task in tasks:
                # 获取结果数量
                results = self.service.get_backtest_results(task.task_id)
                
                task_data = {
                    'id': task.id,
                    'task_id': task.task_id,
                    'name': task.task_name or task.task_id,
                    'strategy_name': task.strategy_config.name if task.strategy_config else 'Unknown',
                    'status': task.status,
                    'progress': task.progress,
                    'current_step': task.current_step,
                    'created_at': task.created_at.isoformat() if task.created_at else None,
                    'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                    'stock_count': len(task.stock_codes),
                    'results_count': len(results),
                    'initial_capital': float(task.initial_capital)
                }
                
                task_list.append(task_data)
            
            return task_list
            
        except Exception as e:
            logger.error(f"列出回测任务失败: {str(e)}")
            return []
    
    def compare_reports(self, report_ids: List[str]) -> Dict:
        """比较多个报告"""
        try:
            reports = []
            for report_id in report_ids:
                report = self.get_report(report_id)
                if report:
                    reports.append(report)
            
            if len(reports) < 2:
                return {'error': '需要至少2个报告进行比较'}
            
            # 构建比较结果
            comparison = {
                'report_count': len(reports),
                'reports': [],
                'comparison_metrics': {}
            }
            
            # 收集所有报告的性能指标
            metrics = ['total_return', 'annual_return', 'max_drawdown', 'sharpe_ratio', 'win_rate']
            
            for report in reports:
                report_summary = {
                    'report_id': report['report_id'],
                    'strategy_name': report['config']['strategy_name'],
                    'stock_count': len(report['config']['stock_pool']),
                    'total_trades': report['performance']['total_trades'],
                    'performance': report['performance']
                }
                comparison['reports'].append(report_summary)
                
                # 收集指标数据
                for metric in metrics:
                    if metric not in comparison['comparison_metrics']:
                        comparison['comparison_metrics'][metric] = []
                    comparison['comparison_metrics'][metric].append(report['performance'][metric])
            
            # 计算统计信息
            for metric in metrics:
                values = comparison['comparison_metrics'][metric]
                if values:
                    comparison['comparison_metrics'][f'{metric}_stats'] = {
                        'best': max(values),
                        'worst': min(values),
                        'average': sum(values) / len(values)
                    }
            
            return comparison
            
        except Exception as e:
            logger.error(f"比较报告失败: {str(e)}")
            return {'error': str(e)}
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        try:
            return self.service.get_database_statistics()
        except Exception as e:
            logger.error(f"获取统计信息失败: {str(e)}")
            return {'error': str(e)}
    
    def cleanup_old_data(self, days: int = 365) -> Dict:
        """清理旧数据"""
        try:
            return self.service.cleanup_old_data(days)
        except Exception as e:
            logger.error(f"清理旧数据失败: {str(e)}")
            return {'error': str(e)}
    
    def __del__(self):
        """析构函数，关闭数据库连接"""
        if hasattr(self, 'db'):
            self.db.close()

# 便捷函数
def create_admin_interface_enhanced(pvfrs_system=None) -> AdminInterfaceEnhanced:
    """创建增强的管理接口实例"""
    return AdminInterfaceEnhanced(pvfrs_system)
