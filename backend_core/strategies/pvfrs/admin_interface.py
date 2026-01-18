"""
PVFRS策略管理端接口实现
负责管理端回测功能和策略管理
"""

from typing import List, Dict, Optional, Any, Callable, Tuple
from datetime import datetime, date, timedelta
import logging
import json
import uuid
import threading
import time
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, Future

from .models import PVFRSException, MarketData, BacktestResult, Trade
from .interfaces import IBacktestEngine
from .pvfrs_system import PVFRSSystem
from .data_interface import PVFRSDataInterface
from .backtest_config_validator import BacktestConfigValidator
from .backtest_monitor import BacktestExecutionMonitor, TaskStatus
from .backtest_report_generator import BacktestReportGenerator
from .strategy_comparison import StrategyComparator
from .backtest_storage import BacktestStorage, QueryFilter, StorageConfig

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """回测配置数据结构"""
    start_date: str            # 回测开始日期
    end_date: str             # 回测结束日期
    stock_pool: List[str]     # 股票池
    initial_capital: float    # 初始资金
    strategy_params: Dict     # 策略参数
    risk_params: Dict         # 风险管理参数
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return asdict(self)


@dataclass
class BacktestTask:
    """回测任务数据结构"""
    task_id: str              # 任务ID
    config: BacktestConfig    # 回测配置
    status: str               # 任务状态：pending, running, completed, failed
    progress: int             # 进度百分比 (0-100)
    current_step: str         # 当前步骤描述
    created_at: str           # 创建时间
    started_at: Optional[str] = None   # 开始时间
    completed_at: Optional[str] = None # 完成时间
    error_message: Optional[str] = None # 错误信息
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return asdict(self)


@dataclass
class BacktestReport:
    """回测报告数据结构"""
    report_id: str            # 报告ID
    task_id: str              # 关联的任务ID
    config: BacktestConfig    # 回测配置
    total_return: float       # 总收益率
    annual_return: float      # 年化收益率
    win_rate: float          # 胜率
    max_drawdown: float      # 最大回撤
    sharpe_ratio: float      # 夏普比率
    trades: List[Dict]       # 交易记录
    equity_curve: List[Dict] # 资金曲线
    created_at: str          # 报告生成时间
    summary: Dict            # 回测摘要
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return asdict(self)


class IAdminInterface:
    """管理端接口抽象类"""
    
    def create_backtest(self, config: BacktestConfig) -> str:
        """创建回测任务，返回任务ID"""
        raise NotImplementedError
    
    def get_backtest_progress(self, task_id: str) -> Dict:
        """获取回测进度"""
        raise NotImplementedError
    
    def get_backtest_report(self, task_id: str) -> BacktestReport:
        """获取回测报告"""
        raise NotImplementedError
    
    def compare_strategies(self, report_ids: List[str]) -> Dict:
        """对比多个策略回测结果"""
        raise NotImplementedError
    
    def save_backtest_report(self, report: BacktestReport) -> str:
        """保存回测报告，返回报告ID"""
        raise NotImplementedError
    
    def list_historical_reports(self, limit: int = 50) -> List[BacktestReport]:
        """查询历史回测报告"""
        raise NotImplementedError


class AdminInterface(IAdminInterface):
    """PVFRS策略管理端接口实现
    
    负责管理端回测功能和策略管理：
    - 创建和管理回测任务
    - 监控回测执行进度
    - 生成和展示回测报告
    - 提供策略对比功能
    - 管理历史回测记录
    """
    
    def __init__(self, pvfrs_system: Optional[PVFRSSystem] = None):
        """初始化管理端接口
        
        Args:
            pvfrs_system: PVFRS策略系统实例，如果不提供则创建新实例
        """
        self.pvfrs_system = pvfrs_system or PVFRSSystem()
        self.data_interface = PVFRSDataInterface()
        self.config_validator = BacktestConfigValidator()
        self.execution_monitor = BacktestExecutionMonitor(max_workers=3)
        self.report_generator = BacktestReportGenerator()
        self.strategy_comparator = StrategyComparator()
        self.storage = BacktestStorage()
        
        # 任务管理
        self.active_tasks: Dict[str, BacktestTask] = {}
        self.completed_tasks: Dict[str, BacktestTask] = {}
        
        # 报告管理
        self.reports: Dict[str, BacktestReport] = {}
        
        # 异步执行管理（保留兼容性，主要使用execution_monitor）
        self.executor = ThreadPoolExecutor(max_workers=3)
        self.running_futures: Dict[str, Future] = {}
        
        # 配置设置
        self.max_concurrent_tasks = 3  # 最大并发任务数
        self.default_initial_capital = 100000.0  # 默认初始资金
        
        # 进度回调管理
        self.progress_callbacks: Dict[str, Callable] = {}
        
        # 启动执行监控
        self.execution_monitor.start_monitoring()
        
        logger.info("PVFRS管理端接口初始化完成")
    
    def create_backtest(self, config: BacktestConfig) -> str:
        """创建回测任务，返回任务ID
        
        Args:
            config: 回测配置
            
        Returns:
            str: 任务ID
            
        Raises:
            PVFRSException: 创建任务失败时抛出
        """
        try:
            # 检查并发任务数限制
            if len(self.active_tasks) >= self.max_concurrent_tasks:
                raise PVFRSException(f"已达到最大并发任务数限制 ({self.max_concurrent_tasks})")
            
            # 生成任务ID
            task_id = f"pvfrs_backtest_{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # 验证配置
            self._validate_backtest_config(config)
            
            # 创建任务
            task = BacktestTask(
                task_id=task_id,
                config=config,
                status="pending",
                progress=0,
                current_step="任务已创建，等待执行",
                created_at=datetime.now().isoformat()
            )
            
            # 添加到活跃任务列表
            self.active_tasks[task_id] = task
            
            logger.info(f"创建回测任务成功: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"创建回测任务失败: {str(e)}")
            raise PVFRSException(f"创建回测任务失败: {str(e)}")
    
    def get_backtest_progress(self, task_id: str) -> Dict:
        """获取回测进度
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict: 回测进度信息
            
        Raises:
            PVFRSException: 任务不存在时抛出
        """
        try:
            # 首先从执行监控器获取进度信息
            monitor_progress = self.execution_monitor.get_task_progress(task_id)
            
            # 查找任务
            task = None
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
            elif task_id in self.completed_tasks:
                task = self.completed_tasks[task_id]
            
            if not task and not monitor_progress:
                raise PVFRSException(f"任务 {task_id} 不存在")
            
            # 构建进度信息
            if monitor_progress:
                # 使用监控器的进度信息
                progress_info = monitor_progress.copy()
                
                # 添加任务配置摘要
                if task:
                    progress_info["config_summary"] = {
                        "start_date": task.config.start_date,
                        "end_date": task.config.end_date,
                        "stock_count": len(task.config.stock_pool),
                        "initial_capital": task.config.initial_capital
                    }
            else:
                # 使用传统的任务信息
                progress_info = {
                    "task_id": task_id,
                    "status": task.status,
                    "progress": task.progress,
                    "current_step": task.current_step,
                    "created_at": task.created_at,
                    "started_at": task.started_at,
                    "completed_at": task.completed_at,
                    "error_message": task.error_message,
                    "estimated_remaining_time": self._estimate_remaining_time(task),
                    "config_summary": {
                        "start_date": task.config.start_date,
                        "end_date": task.config.end_date,
                        "stock_count": len(task.config.stock_pool),
                        "initial_capital": task.config.initial_capital
                    }
                }
            
            return progress_info
            
        except Exception as e:
            logger.error(f"获取回测进度失败: {str(e)}")
            raise PVFRSException(f"获取回测进度失败: {str(e)}")
    
    def get_backtest_report(self, task_id: str) -> BacktestReport:
        """获取回测报告
        
        Args:
            task_id: 任务ID
            
        Returns:
            BacktestReport: 回测报告
            
        Raises:
            PVFRSException: 报告不存在时抛出
        """
        try:
            # 查找报告
            report = None
            for report_id, report_obj in self.reports.items():
                if report_obj.task_id == task_id:
                    report = report_obj
                    break
            
            if not report:
                raise PVFRSException(f"任务 {task_id} 的回测报告不存在")
            
            logger.info(f"获取回测报告成功: {task_id}")
            return report
            
        except Exception as e:
            logger.error(f"获取回测报告失败: {str(e)}")
            raise PVFRSException(f"获取回测报告失败: {str(e)}")
    
    def compare_strategies(self, report_ids: List[str]) -> Dict:
        """对比多个策略回测结果
        
        Args:
            report_ids: 报告ID列表
            
        Returns:
            Dict: 策略对比结果
            
        Raises:
            PVFRSException: 对比失败时抛出
        """
        try:
            if len(report_ids) < 2:
                raise PVFRSException("至少需要2个报告进行对比")
            
            # 获取报告
            reports = []
            for report_id in report_ids:
                if report_id not in self.reports:
                    raise PVFRSException(f"报告 {report_id} 不存在")
                
                report = self.reports[report_id]
                # 转换为字典格式
                report_dict = report.to_dict()
                
                # 添加详细数据（如果有）
                if hasattr(report, 'comprehensive_data') and report.comprehensive_data:
                    report_dict['comprehensive_data'] = report.comprehensive_data
                
                reports.append(report_dict)
            
            # 使用策略对比器进行对比
            comparison_result = self.strategy_comparator.compare_strategies(reports)
            
            logger.info(f"策略对比完成，对比了 {len(reports)} 个报告")
            return comparison_result
            
        except Exception as e:
            logger.error(f"策略对比失败: {str(e)}")
            raise PVFRSException(f"策略对比失败: {str(e)}")
    
    def compare_two_strategies(self, report_id1: str, report_id2: str) -> Dict:
        """对比两个策略（简化版）
        
        Args:
            report_id1: 第一个报告ID
            report_id2: 第二个报告ID
            
        Returns:
            Dict: 两策略对比结果
            
        Raises:
            PVFRSException: 对比失败时抛出
        """
        try:
            if report_id1 not in self.reports:
                raise PVFRSException(f"报告 {report_id1} 不存在")
            if report_id2 not in self.reports:
                raise PVFRSException(f"报告 {report_id2} 不存在")
            
            report1 = self.reports[report_id1].to_dict()
            report2 = self.reports[report_id2].to_dict()
            
            # 添加详细数据（如果有）
            for report_id, report_dict in [(report_id1, report1), (report_id2, report2)]:
                report_obj = self.reports[report_id]
                if hasattr(report_obj, 'comprehensive_data') and report_obj.comprehensive_data:
                    report_dict['comprehensive_data'] = report_obj.comprehensive_data
            
            # 使用策略对比器进行对比
            comparison_result = self.strategy_comparator.compare_two_strategies(report1, report2)
            
            logger.info(f"两策略对比完成: {report_id1} vs {report_id2}")
            return comparison_result
            
        except Exception as e:
            logger.error(f"两策略对比失败: {str(e)}")
            raise PVFRSException(f"两策略对比失败: {str(e)}")
    
    def rank_strategies_by_metric(self, report_ids: List[str], metric_name: str) -> List[Dict]:
        """按指定指标对策略排名
        
        Args:
            report_ids: 报告ID列表
            metric_name: 指标名称
            
        Returns:
            List[Dict]: 按指标排名的策略列表
            
        Raises:
            PVFRSException: 排名失败时抛出
        """
        try:
            # 获取报告
            reports = []
            for report_id in report_ids:
                if report_id not in self.reports:
                    raise PVFRSException(f"报告 {report_id} 不存在")
                
                report_dict = self.reports[report_id].to_dict()
                if hasattr(self.reports[report_id], 'comprehensive_data'):
                    report_dict['comprehensive_data'] = self.reports[report_id].comprehensive_data
                
                reports.append(report_dict)
            
            # 使用策略对比器进行排名
            ranking_result = self.strategy_comparator.rank_strategies_by_metric(reports, metric_name)
            
            logger.info(f"策略排名完成，按 {metric_name} 指标排序")
            return ranking_result
            
        except Exception as e:
            logger.error(f"策略排名失败: {str(e)}")
            raise PVFRSException(f"策略排名失败: {str(e)}")
    
    def generate_comparison_report_text(self, report_ids: List[str]) -> str:
        """生成策略对比报告文本
        
        Args:
            report_ids: 报告ID列表
            
        Returns:
            str: 对比报告文本
            
        Raises:
            PVFRSException: 生成失败时抛出
        """
        try:
            # 先进行对比
            comparison_result = self.compare_strategies(report_ids)
            
            # 生成报告文本
            report_text = self.strategy_comparator.generate_comparison_report(comparison_result)
            
            logger.info(f"策略对比报告文本生成完成")
            return report_text
            
        except Exception as e:
            logger.error(f"生成策略对比报告文本失败: {str(e)}")
            raise PVFRSException(f"生成策略对比报告文本失败: {str(e)}")
    
    def get_comparison_visualization_data(self, report_ids: List[str]) -> Dict:
        """获取策略对比可视化数据
        
        Args:
            report_ids: 报告ID列表
            
        Returns:
            Dict: 可视化数据
            
        Raises:
            PVFRSException: 获取失败时抛出
        """
        try:
            # 进行对比
            comparison_result = self.compare_strategies(report_ids)
            
            # 返回可视化数据
            visualization_data = comparison_result.get('visualization_data', {})
            
            logger.info(f"策略对比可视化数据获取完成")
            return visualization_data
            
        except Exception as e:
            logger.error(f"获取策略对比可视化数据失败: {str(e)}")
            raise PVFRSException(f"获取策略对比可视化数据失败: {str(e)}")
    
    def get_available_comparison_metrics(self) -> List[Dict]:
        """获取可用的对比指标列表
        
        Returns:
            List[Dict]: 可用指标列表
        """
        metrics = [
            {
                'name': 'total_return',
                'display_name': '总收益率',
                'description': '整个回测期间的总收益率',
                'higher_better': True,
                'format': 'percentage'
            },
            {
                'name': 'annual_return',
                'display_name': '年化收益率',
                'description': '年化后的收益率',
                'higher_better': True,
                'format': 'percentage'
            },
            {
                'name': 'sharpe_ratio',
                'display_name': '夏普比率',
                'description': '风险调整后的收益指标',
                'higher_better': True,
                'format': 'decimal'
            },
            {
                'name': 'max_drawdown',
                'display_name': '最大回撤',
                'description': '最大资金回撤比例',
                'higher_better': False,
                'format': 'percentage'
            },
            {
                'name': 'win_rate',
                'display_name': '胜率',
                'description': '盈利交易占总交易的比例',
                'higher_better': True,
                'format': 'percentage'
            },
            {
                'name': 'volatility',
                'display_name': '波动率',
                'description': '收益率的标准差',
                'higher_better': False,
                'format': 'percentage'
            }
        ]
        
        return metrics
    
    def save_backtest_report(self, report: BacktestReport) -> str:
        """保存回测报告，返回报告ID
        
        Args:
            report: 回测报告
            
        Returns:
            str: 报告ID
        """
        try:
            # 生成报告ID（如果没有）
            if not report.report_id:
                report.report_id = f"report_{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # 保存到内存
            self.reports[report.report_id] = report
            
            # 保存到持久化存储
            report_dict = report.to_dict()
            
            # 添加详细数据（如果有）
            if hasattr(report, 'comprehensive_data') and report.comprehensive_data:
                report_dict['comprehensive_data'] = report.comprehensive_data
            
            storage_id = self.storage.save_report(report_dict)
            
            logger.info(f"保存回测报告成功: {report.report_id} (存储ID: {storage_id})")
            return report.report_id
            
        except Exception as e:
            logger.error(f"保存回测报告失败: {str(e)}")
            raise PVFRSException(f"保存回测报告失败: {str(e)}")
    
    def list_historical_reports(self, limit: int = 50, **filter_kwargs) -> List[BacktestReport]:
        """查询历史回测报告
        
        Args:
            limit: 返回数量限制
            **filter_kwargs: 过滤条件
            
        Returns:
            List[BacktestReport]: 历史回测报告列表
        """
        try:
            # 创建查询过滤器
            query_filter = QueryFilter(limit=limit, **filter_kwargs)
            
            # 从持久化存储查询
            report_dicts = self.storage.query_reports(query_filter)
            
            # 转换为BacktestReport对象
            reports = []
            for report_dict in report_dicts:
                try:
                    # 重构BacktestReport对象
                    config_dict = report_dict.get('config', {})
                    config = BacktestConfig(
                        start_date=config_dict.get('start_date', ''),
                        end_date=config_dict.get('end_date', ''),
                        stock_pool=config_dict.get('stock_pool', []),
                        initial_capital=config_dict.get('initial_capital', 0.0),
                        strategy_params=config_dict.get('strategy_params', {}),
                        risk_params=config_dict.get('risk_params', {})
                    )
                    
                    report = BacktestReport(
                        report_id=report_dict.get('report_id', ''),
                        task_id=report_dict.get('task_id', ''),
                        config=config,
                        total_return=report_dict.get('total_return', 0.0),
                        annual_return=report_dict.get('annual_return', 0.0),
                        win_rate=report_dict.get('win_rate', 0.0),
                        max_drawdown=report_dict.get('max_drawdown', 0.0),
                        sharpe_ratio=report_dict.get('sharpe_ratio', 0.0),
                        trades=report_dict.get('trades', []),
                        equity_curve=report_dict.get('equity_curve', []),
                        created_at=report_dict.get('created_at', ''),
                        summary=report_dict.get('summary', {})
                    )
                    
                    # 添加详细数据（如果有）
                    if 'comprehensive_data' in report_dict:
                        report.comprehensive_data = report_dict['comprehensive_data']
                    
                    reports.append(report)
                    
                except Exception as e:
                    logger.warning(f"转换报告对象失败: {str(e)}")
                    continue
            
            logger.info(f"查询历史回测报告完成，返回 {len(reports)} 个报告")
            return reports
            
        except Exception as e:
            logger.error(f"查询历史回测报告失败: {str(e)}")
            raise PVFRSException(f"查询历史回测报告失败: {str(e)}")
    
    def get_historical_report(self, report_id: str) -> Optional[BacktestReport]:
        """获取历史回测报告
        
        Args:
            report_id: 报告ID
            
        Returns:
            Optional[BacktestReport]: 回测报告，如果不存在则返回None
        """
        try:
            # 先从内存查找
            if report_id in self.reports:
                return self.reports[report_id]
            
            # 从持久化存储查找
            report_dict = self.storage.get_report(report_id)
            
            if report_dict:
                # 重构BacktestReport对象
                config_dict = report_dict.get('config', {})
                config = BacktestConfig(
                    start_date=config_dict.get('start_date', ''),
                    end_date=config_dict.get('end_date', ''),
                    stock_pool=config_dict.get('stock_pool', []),
                    initial_capital=config_dict.get('initial_capital', 0.0),
                    strategy_params=config_dict.get('strategy_params', {}),
                    risk_params=config_dict.get('risk_params', {})
                )
                
                report = BacktestReport(
                    report_id=report_dict.get('report_id', ''),
                    task_id=report_dict.get('task_id', ''),
                    config=config,
                    total_return=report_dict.get('total_return', 0.0),
                    annual_return=report_dict.get('annual_return', 0.0),
                    win_rate=report_dict.get('win_rate', 0.0),
                    max_drawdown=report_dict.get('max_drawdown', 0.0),
                    sharpe_ratio=report_dict.get('sharpe_ratio', 0.0),
                    trades=report_dict.get('trades', []),
                    equity_curve=report_dict.get('equity_curve', []),
                    created_at=report_dict.get('created_at', ''),
                    summary=report_dict.get('summary', {})
                )
                
                # 添加详细数据（如果有）
                if 'comprehensive_data' in report_dict:
                    report.comprehensive_data = report_dict['comprehensive_data']
                
                # 缓存到内存
                self.reports[report_id] = report
                
                return report
            
            return None
            
        except Exception as e:
            logger.error(f"获取历史回测报告失败: {str(e)}")
            raise PVFRSException(f"获取历史回测报告失败: {str(e)}")
    
    def delete_historical_report(self, report_id: str) -> bool:
        """删除历史回测报告
        
        Args:
            report_id: 报告ID
            
        Returns:
            bool: 是否成功删除
        """
        try:
            # 从内存删除
            if report_id in self.reports:
                del self.reports[report_id]
            
            # 从持久化存储删除
            success = self.storage.delete_report(report_id)
            
            if success:
                logger.info(f"删除历史回测报告成功: {report_id}")
            else:
                logger.warning(f"历史回测报告不存在: {report_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"删除历史回测报告失败: {str(e)}")
            raise PVFRSException(f"删除历史回测报告失败: {str(e)}")
    
    def get_storage_statistics(self) -> Dict:
        """获取存储统计信息
        
        Returns:
            Dict: 存储统计信息
        """
        try:
            return self.storage.get_statistics()
            
        except Exception as e:
            logger.error(f"获取存储统计信息失败: {str(e)}")
            raise PVFRSException(f"获取存储统计信息失败: {str(e)}")
    
    def cleanup_old_historical_reports(self, days: int = 365) -> int:
        """清理旧的历史回测报告
        
        Args:
            days: 保留天数
            
        Returns:
            int: 清理的报告数量
        """
        try:
            cleaned_count = self.storage.cleanup_old_reports(days)
            
            # 同时清理内存中的旧报告
            cutoff_time = datetime.now() - timedelta(days=days)
            memory_cleaned = 0
            
            reports_to_remove = []
            for report_id, report in self.reports.items():
                try:
                    created_time = datetime.fromisoformat(report.created_at)
                    if created_time < cutoff_time:
                        reports_to_remove.append(report_id)
                except ValueError:
                    continue
            
            for report_id in reports_to_remove:
                del self.reports[report_id]
                memory_cleaned += 1
            
            total_cleaned = cleaned_count + memory_cleaned
            logger.info(f"清理旧历史报告完成，总共清理 {total_cleaned} 个报告")
            
            return total_cleaned
            
        except Exception as e:
            logger.error(f"清理旧历史报告失败: {str(e)}")
            raise PVFRSException(f"清理旧历史报告失败: {str(e)}")
    
    def backup_storage(self, backup_path: Optional[str] = None) -> str:
        """备份存储数据
        
        Args:
            backup_path: 备份文件路径
            
        Returns:
            str: 备份文件路径
        """
        try:
            return self.storage.backup_database(backup_path)
            
        except Exception as e:
            logger.error(f"备份存储数据失败: {str(e)}")
            raise PVFRSException(f"备份存储数据失败: {str(e)}")
    
    def restore_storage(self, backup_path: str) -> bool:
        """恢复存储数据
        
        Args:
            backup_path: 备份文件路径
            
        Returns:
            bool: 是否成功恢复
        """
        try:
            success = self.storage.restore_database(backup_path)
            
            if success:
                # 清理内存缓存，强制重新加载
                self.reports.clear()
                logger.info("存储数据恢复成功，内存缓存已清理")
            
            return success
            
        except Exception as e:
            logger.error(f"恢复存储数据失败: {str(e)}")
            raise PVFRSException(f"恢复存储数据失败: {str(e)}")
    
    def start_backtest_execution(self, task_id: str) -> bool:
        """开始执行回测任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功开始执行
        """
        try:
            if task_id not in self.active_tasks:
                raise PVFRSException(f"任务 {task_id} 不存在")
            
            task = self.active_tasks[task_id]
            
            if task.status != "pending":
                raise PVFRSException(f"任务 {task_id} 状态不正确，当前状态: {task.status}")
            
            # 更新任务状态
            task.status = "running"
            task.started_at = datetime.now().isoformat()
            task.current_step = "开始执行回测"
            task.progress = 5
            
            # 添加进度回调
            def progress_callback(progress_update):
                if task_id in self.active_tasks:
                    task = self.active_tasks[task_id]
                    task.progress = progress_update.progress
                    task.current_step = progress_update.current_step
                    
                    # 调用用户设置的回调
                    if task_id in self.progress_callbacks:
                        try:
                            self.progress_callbacks[task_id](
                                task_id, progress_update.progress, progress_update.current_step
                            )
                        except Exception as e:
                            logger.warning(f"用户进度回调执行失败: {str(e)}")
            
            self.execution_monitor.add_progress_callback(task_id, progress_callback)
            
            # 提交任务到执行监控器
            success = self.execution_monitor.submit_task(
                task_id, 
                self._execute_backtest_with_monitor, 
                task_id
            )
            
            if not success:
                raise PVFRSException(f"提交回测任务到执行监控器失败: {task_id}")
            
            logger.info(f"开始执行回测任务: {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"开始执行回测任务失败: {str(e)}")
            # 更新任务状态为失败
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                task.status = "failed"
                task.error_message = str(e)
                task.completed_at = datetime.now().isoformat()
            return False
    
    def _execute_backtest_with_monitor(self, task_id: str) -> None:
        """使用监控器执行回测任务的内部方法
        
        Args:
            task_id: 任务ID
        """
        try:
            task = self.active_tasks[task_id]
            config = task.config
            
            # 更新进度：准备数据
            self.execution_monitor.update_progress(task_id, 10, "准备历史数据")
            
            # 获取历史数据
            stock_data_dict = {}
            total_stocks = len(config.stock_pool)
            
            for i, symbol in enumerate(config.stock_pool):
                try:
                    # 获取股票历史数据
                    data = self.data_interface.get_historical_data(
                        symbol, config.start_date, config.end_date
                    )
                    if data and len(data) >= 20:  # 确保有足够的数据
                        stock_data_dict[symbol] = data
                    
                    # 更新数据准备进度
                    data_progress = 10 + (i + 1) / total_stocks * 20  # 10-30%
                    self.execution_monitor.update_progress(
                        task_id, int(data_progress), 
                        f"准备数据 ({i+1}/{total_stocks}): {symbol}"
                    )
                    
                except Exception as e:
                    logger.warning(f"获取股票 {symbol} 数据失败: {str(e)}")
                    continue
            
            if not stock_data_dict:
                raise PVFRSException("没有获取到有效的股票数据")
            
            # 更新进度：开始回测
            self.execution_monitor.update_progress(task_id, 35, "开始执行PVFRS策略回测")
            
            # 执行回测
            backtest_result = self.pvfrs_system.backtest_engine.run_backtest_with_data(
                stock_data_dict=stock_data_dict,
                start_date=config.start_date,
                end_date=config.end_date,
                initial_capital=config.initial_capital
            )
            
            # 更新进度：生成报告
            self.execution_monitor.update_progress(task_id, 80, "生成回测报告")
            
            # 创建回测报告
            report = self._create_backtest_report(task_id, config, backtest_result)
            
            # 保存报告
            report_id = self.save_backtest_report(report)
            
            # 更新进度：完成
            self.execution_monitor.update_progress(task_id, 100, "回测完成")
            
            # 标记任务完成
            task.status = "completed"
            task.completed_at = datetime.now().isoformat()
            
            # 移动到已完成任务列表
            self.completed_tasks[task_id] = task
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]
            
            logger.info(f"回测任务 {task_id} 执行完成，报告ID: {report_id}")
            
        except Exception as e:
            logger.error(f"回测任务 {task_id} 执行失败: {str(e)}")
            
            # 更新任务状态为失败
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                task.status = "failed"
                task.error_message = str(e)
                task.completed_at = datetime.now().isoformat()
                
                # 移动到已完成任务列表
                self.completed_tasks[task_id] = task
                del self.active_tasks[task_id]
            
            # 重新抛出异常，让监控器处理
            raise
    
    def _update_task_progress(self, task_id: str, progress: int, current_step: str) -> None:
        """更新任务进度
        
        Args:
            task_id: 任务ID
            progress: 进度百分比 (0-100)
            current_step: 当前步骤描述
        """
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            task.progress = progress
            task.current_step = current_step
            
            # 调用进度回调（如果有）
            if task_id in self.progress_callbacks:
                try:
                    self.progress_callbacks[task_id](task_id, progress, current_step)
                except Exception as e:
                    logger.warning(f"进度回调执行失败: {str(e)}")
    
    def _create_backtest_report(self, task_id: str, config: BacktestConfig, 
                               backtest_result: BacktestResult) -> BacktestReport:
        """创建回测报告
        
        Args:
            task_id: 任务ID
            config: 回测配置
            backtest_result: 回测结果
            
        Returns:
            BacktestReport: 回测报告
        """
        # 生成报告ID
        report_id = f"report_{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 使用报告生成器生成详细报告
        comprehensive_report = self.report_generator.generate_comprehensive_report(
            backtest_result=backtest_result,
            initial_capital=config.initial_capital,
            start_date=config.start_date,
            end_date=config.end_date
        )
        
        # 转换交易记录为字典格式
        trades_dict = []
        for trade in backtest_result.trades:
            trade_dict = {
                'symbol': trade.symbol,
                'entry_date': trade.entry_date,
                'entry_price': trade.entry_price,
                'exit_date': trade.exit_date,
                'exit_price': trade.exit_price,
                'quantity': trade.quantity,
                'pnl': trade.pnl,
                'return_rate': trade.return_rate,
                'holding_days': trade.holding_days,
                'exit_reason': trade.exit_reason
            }
            trades_dict.append(trade_dict)
        
        # 创建报告对象
        report = BacktestReport(
            report_id=report_id,
            task_id=task_id,
            config=config,
            total_return=backtest_result.total_return,
            annual_return=backtest_result.annual_return,
            win_rate=backtest_result.win_rate,
            max_drawdown=backtest_result.max_drawdown,
            sharpe_ratio=backtest_result.sharpe_ratio,
            trades=trades_dict,
            equity_curve=comprehensive_report['equity_curve'],
            created_at=datetime.now().isoformat(),
            summary=comprehensive_report['summary']
        )
        
        # 添加详细报告数据
        report.comprehensive_data = comprehensive_report
        
        return report
    
    def get_default_backtest_config(self) -> Dict:
        """获取默认回测配置
        
        Returns:
            Dict: 默认回测配置
        """
        return self.config_validator.get_default_config()
    
    def get_config_schema(self) -> Dict:
        """获取配置参数模式
        
        Returns:
            Dict: 配置参数模式，用于前端界面生成
        """
        return self.config_validator.get_parameter_schema()
    
    def validate_config(self, config_dict: Dict) -> Tuple[bool, List[str]]:
        """验证回测配置
        
        Args:
            config_dict: 配置字典
            
        Returns:
            Tuple[bool, List[str]]: (是否有效, 错误信息列表)
        """
        return self.config_validator.validate_backtest_config(config_dict)
    
    def create_config_from_dict(self, config_dict: Dict) -> BacktestConfig:
        """从字典创建回测配置对象
        
        Args:
            config_dict: 配置字典
            
        Returns:
            BacktestConfig: 回测配置对象
            
        Raises:
            PVFRSException: 配置无效时抛出
        """
        try:
            # 验证并标准化配置
            normalized_config = self.config_validator.validate_and_normalize_config(config_dict)
            
            # 创建BacktestConfig对象
            config = BacktestConfig(
                start_date=normalized_config['start_date'],
                end_date=normalized_config['end_date'],
                stock_pool=normalized_config['stock_pool'],
                initial_capital=normalized_config['initial_capital'],
                strategy_params=normalized_config.get('strategy_params', {}),
                risk_params=normalized_config.get('risk_params', {})
            )
            
            return config
            
        except Exception as e:
            logger.error(f"创建配置对象失败: {str(e)}")
            raise PVFRSException(f"创建配置对象失败: {str(e)}")
    
    def create_backtest_from_dict(self, config_dict: Dict) -> str:
        """从配置字典创建回测任务
        
        Args:
            config_dict: 配置字典
            
        Returns:
            str: 任务ID
            
        Raises:
            PVFRSException: 创建任务失败时抛出
        """
        try:
            # 创建配置对象
            config = self.create_config_from_dict(config_dict)
            
            # 创建回测任务
            task_id = self.create_backtest(config)
            
            logger.info(f"从配置字典创建回测任务成功: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"从配置字典创建回测任务失败: {str(e)}")
            raise PVFRSException(f"从配置字典创建回测任务失败: {str(e)}")
    
    def create_and_start_backtest_from_dict(self, config_dict: Dict) -> str:
        """从配置字典创建并立即开始回测任务
        
        Args:
            config_dict: 配置字典
            
        Returns:
            str: 任务ID
            
        Raises:
            PVFRSException: 创建或启动任务失败时抛出
        """
        try:
            # 创建任务
            task_id = self.create_backtest_from_dict(config_dict)
            
            # 立即开始执行
            success = self.start_backtest_execution(task_id)
            
            if not success:
                raise PVFRSException(f"启动回测任务失败: {task_id}")
            
            logger.info(f"从配置字典创建并启动回测任务成功: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"从配置字典创建并启动回测任务失败: {str(e)}")
            raise PVFRSException(f"从配置字典创建并启动回测任务失败: {str(e)}")
    
    def get_config_validation_errors(self, config_dict: Dict) -> List[str]:
        """获取配置验证错误信息
        
        Args:
            config_dict: 配置字典
            
        Returns:
            List[str]: 错误信息列表
        """
        _, errors = self.config_validator.validate_backtest_config(config_dict)
        return errors
    
    def suggest_config_improvements(self, config_dict: Dict) -> List[str]:
        """建议配置改进
        
        Args:
            config_dict: 配置字典
            
        Returns:
            List[str]: 改进建议列表
        """
        suggestions = []
        
        try:
            # 检查回测期间长度
            if 'start_date' in config_dict and 'end_date' in config_dict:
                try:
                    start_date = datetime.strptime(config_dict['start_date'], "%Y-%m-%d")
                    end_date = datetime.strptime(config_dict['end_date'], "%Y-%m-%d")
                    period_days = (end_date - start_date).days
                    
                    if period_days < 90:
                        suggestions.append("建议回测期间至少3个月，以获得更可靠的结果")
                    elif period_days > 1095:  # 3年
                        suggestions.append("回测期间超过3年，可能需要较长时间执行")
                except:
                    pass
            
            # 检查股票池大小
            stock_pool = config_dict.get('stock_pool', [])
            if isinstance(stock_pool, list):
                if len(stock_pool) < 10:
                    suggestions.append("建议股票池包含至少10只股票，以提高策略的稳定性")
                elif len(stock_pool) > 50:
                    suggestions.append("股票池较大，回测可能需要较长时间")
            
            # 检查资金配置
            initial_capital = config_dict.get('initial_capital', 0)
            if initial_capital < 50000:
                suggestions.append("建议初始资金至少5万元，以支持更好的分散投资")
            
            # 检查风险参数
            risk_params = config_dict.get('risk_params', {})
            stop_loss_rate = risk_params.get('stop_loss_rate', 0)
            take_profit_rate = risk_params.get('take_profit_rate', 0)
            
            if stop_loss_rate > 0.15:
                suggestions.append("止损比例较高，可能导致频繁止损")
            elif stop_loss_rate < 0.05:
                suggestions.append("止损比例较低，可能增加风险")
            
            if take_profit_rate < 0.1:
                suggestions.append("止盈比例较低，可能限制收益潜力")
            elif take_profit_rate > 0.5:
                suggestions.append("止盈比例较高，可能难以达到")
            
        except Exception as e:
            logger.warning(f"生成配置建议时发生异常: {str(e)}")
        
        return suggestions
    
    def get_report_visualization_data(self, report_id: str) -> Dict:
        """获取报告可视化数据
        
        Args:
            report_id: 报告ID
            
        Returns:
            Dict: 可视化数据
            
        Raises:
            PVFRSException: 报告不存在时抛出
        """
        try:
            if report_id not in self.reports:
                raise PVFRSException(f"报告 {report_id} 不存在")
            
            report = self.reports[report_id]
            
            # 如果报告有详细数据，返回可视化数据
            if hasattr(report, 'comprehensive_data') and report.comprehensive_data:
                return report.comprehensive_data.get('visualization_data', {})
            
            # 否则生成基本的可视化数据
            basic_viz_data = {
                'equity_curve_chart': {
                    'dates': [point['date'] for point in report.equity_curve],
                    'equity_values': [point['equity'] for point in report.equity_curve],
                    'return_rates': [point['return_rate'] for point in report.equity_curve]
                },
                'win_loss_pie': {
                    'wins': report.summary.get('winning_trades', 0),
                    'losses': report.summary.get('losing_trades', 0),
                    'breakevens': 0
                },
                'trade_distribution': {
                    'pnl_values': [trade['pnl'] for trade in report.trades],
                    'holding_days': [trade['holding_days'] for trade in report.trades],
                    'return_rates': [trade['return_rate'] for trade in report.trades]
                }
            }
            
            return basic_viz_data
            
        except Exception as e:
            logger.error(f"获取报告可视化数据失败: {str(e)}")
            raise PVFRSException(f"获取报告可视化数据失败: {str(e)}")
    
    def get_report_summary(self, report_id: str) -> Dict:
        """获取报告摘要
        
        Args:
            report_id: 报告ID
            
        Returns:
            Dict: 报告摘要
            
        Raises:
            PVFRSException: 报告不存在时抛出
        """
        try:
            if report_id not in self.reports:
                raise PVFRSException(f"报告 {report_id} 不存在")
            
            report = self.reports[report_id]
            
            # 基本摘要信息
            basic_summary = {
                'report_id': report.report_id,
                'task_id': report.task_id,
                'created_at': report.created_at,
                'period': {
                    'start_date': report.config.start_date,
                    'end_date': report.config.end_date,
                    'duration_days': (datetime.strptime(report.config.end_date, '%Y-%m-%d') - 
                                    datetime.strptime(report.config.start_date, '%Y-%m-%d')).days
                },
                'performance': {
                    'total_return': report.total_return,
                    'annual_return': report.annual_return,
                    'win_rate': report.win_rate,
                    'max_drawdown': report.max_drawdown,
                    'sharpe_ratio': report.sharpe_ratio
                },
                'trading': {
                    'total_trades': len(report.trades),
                    'winning_trades': len([t for t in report.trades if t['pnl'] > 0]),
                    'losing_trades': len([t for t in report.trades if t['pnl'] < 0]),
                    'total_pnl': sum(t['pnl'] for t in report.trades),
                    'avg_holding_days': sum(t['holding_days'] for t in report.trades) / len(report.trades) if report.trades else 0
                }
            }
            
            # 如果有详细数据，添加更多信息
            if hasattr(report, 'comprehensive_data') and report.comprehensive_data:
                comprehensive_summary = report.comprehensive_data.get('summary', {})
                basic_summary.update(comprehensive_summary)
            
            return basic_summary
            
        except Exception as e:
            logger.error(f"获取报告摘要失败: {str(e)}")
            raise PVFRSException(f"获取报告摘要失败: {str(e)}")
    
    def export_report_to_json(self, report_id: str) -> str:
        """导出报告为JSON格式
        
        Args:
            report_id: 报告ID
            
        Returns:
            str: JSON格式的报告数据
            
        Raises:
            PVFRSException: 报告不存在时抛出
        """
        try:
            if report_id not in self.reports:
                raise PVFRSException(f"报告 {report_id} 不存在")
            
            report = self.reports[report_id]
            
            # 构建导出数据
            export_data = {
                'report_metadata': {
                    'report_id': report.report_id,
                    'task_id': report.task_id,
                    'created_at': report.created_at,
                    'export_time': datetime.now().isoformat()
                },
                'config': report.config.to_dict(),
                'performance_summary': {
                    'total_return': report.total_return,
                    'annual_return': report.annual_return,
                    'win_rate': report.win_rate,
                    'max_drawdown': report.max_drawdown,
                    'sharpe_ratio': report.sharpe_ratio
                },
                'trades': report.trades,
                'equity_curve': report.equity_curve,
                'summary': report.summary
            }
            
            # 如果有详细数据，也包含进去
            if hasattr(report, 'comprehensive_data') and report.comprehensive_data:
                export_data['comprehensive_analysis'] = report.comprehensive_data
            
            # 转换为JSON
            json_data = json.dumps(export_data, indent=2, ensure_ascii=False)
            
            logger.info(f"报告 {report_id} 导出为JSON完成")
            return json_data
            
        except Exception as e:
            logger.error(f"导出报告为JSON失败: {str(e)}")
            raise PVFRSException(f"导出报告为JSON失败: {str(e)}")
    
    def generate_report_html(self, report_id: str) -> str:
        """生成报告HTML展示页面
        
        Args:
            report_id: 报告ID
            
        Returns:
            str: HTML格式的报告页面
            
        Raises:
            PVFRSException: 报告不存在时抛出
        """
        try:
            if report_id not in self.reports:
                raise PVFRSException(f"报告 {report_id} 不存在")
            
            report = self.reports[report_id]
            summary = self.get_report_summary(report_id)
            
            # 生成简单的HTML报告
            html_content = f"""
            <!DOCTYPE html>
            <html lang="zh-CN">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>PVFRS策略回测报告 - {report.report_id}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    .header {{ background-color: #f5f5f5; padding: 20px; border-radius: 5px; }}
                    .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
                    .metric {{ display: inline-block; margin: 10px; padding: 10px; background-color: #f9f9f9; border-radius: 3px; }}
                    .positive {{ color: #28a745; }}
                    .negative {{ color: #dc3545; }}
                    table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                    th {{ background-color: #f2f2f2; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>PVFRS策略回测报告</h1>
                    <p>报告ID: {report.report_id}</p>
                    <p>生成时间: {report.created_at}</p>
                    <p>回测期间: {report.config.start_date} 至 {report.config.end_date}</p>
                </div>
                
                <div class="section">
                    <h2>核心指标</h2>
                    <div class="metric">
                        <strong>总收益率:</strong> 
                        <span class="{'positive' if report.total_return > 0 else 'negative'}">
                            {report.total_return:.2%}
                        </span>
                    </div>
                    <div class="metric">
                        <strong>年化收益率:</strong> 
                        <span class="{'positive' if report.annual_return > 0 else 'negative'}">
                            {report.annual_return:.2%}
                        </span>
                    </div>
                    <div class="metric">
                        <strong>胜率:</strong> {report.win_rate:.2%}
                    </div>
                    <div class="metric">
                        <strong>最大回撤:</strong> 
                        <span class="negative">{report.max_drawdown:.2%}</span>
                    </div>
                    <div class="metric">
                        <strong>夏普比率:</strong> {report.sharpe_ratio:.2f}
                    </div>
                </div>
                
                <div class="section">
                    <h2>交易统计</h2>
                    <p>总交易次数: {len(report.trades)}</p>
                    <p>盈利交易: {len([t for t in report.trades if t['pnl'] > 0])}</p>
                    <p>亏损交易: {len([t for t in report.trades if t['pnl'] < 0])}</p>
                    <p>总盈亏: {sum(t['pnl'] for t in report.trades):.2f} 元</p>
                </div>
                
                <div class="section">
                    <h2>配置信息</h2>
                    <p>初始资金: {report.config.initial_capital:,.2f} 元</p>
                    <p>股票池数量: {len(report.config.stock_pool)} 只</p>
                    <p>策略参数: {json.dumps(report.config.strategy_params, ensure_ascii=False, indent=2)}</p>
                    <p>风险参数: {json.dumps(report.config.risk_params, ensure_ascii=False, indent=2)}</p>
                </div>
            </body>
            </html>
            """
            
            logger.info(f"报告 {report_id} HTML生成完成")
            return html_content
            
        except Exception as e:
            logger.error(f"生成报告HTML失败: {str(e)}")
            raise PVFRSException(f"生成报告HTML失败: {str(e)}")
    
    def set_progress_callback(self, task_id: str, callback: Callable) -> None:
        """设置进度回调函数
        
        Args:
            task_id: 任务ID
            callback: 回调函数，签名为 callback(task_id: str, progress: int, current_step: str)
        """
        self.progress_callbacks[task_id] = callback
    
    def cancel_backtest(self, task_id: str) -> bool:
        """取消回测任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功取消
        """
        try:
            # 首先尝试从执行监控器取消
            monitor_success = self.execution_monitor.cancel_task(task_id)
            
            # 更新本地任务状态
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                
                if task.status in ["completed", "failed"]:
                    raise PVFRSException(f"任务 {task_id} 已完成，无法取消")
                
                # 更新任务状态
                task.status = "cancelled"
                task.completed_at = datetime.now().isoformat()
                task.current_step = "任务已取消"
                
                # 移动到已完成任务列表
                self.completed_tasks[task_id] = task
                del self.active_tasks[task_id]
                
                logger.info(f"取消回测任务成功: {task_id}")
                return True
            
            return monitor_success
            
        except Exception as e:
            logger.error(f"取消回测任务失败: {str(e)}")
            return False
    
    def get_all_tasks_progress(self) -> Dict[str, Dict]:
        """获取所有任务的进度信息
        
        Returns:
            Dict[str, Dict]: 所有任务的进度信息
        """
        try:
            all_progress = {}
            
            # 从执行监控器获取所有任务状态
            monitor_status = self.execution_monitor.get_all_tasks_status()
            
            # 合并本地任务信息
            all_task_ids = set()
            all_task_ids.update(self.active_tasks.keys())
            all_task_ids.update(self.completed_tasks.keys())
            all_task_ids.update(monitor_status.keys())
            
            for task_id in all_task_ids:
                try:
                    progress_info = self.get_backtest_progress(task_id)
                    all_progress[task_id] = progress_info
                except Exception as e:
                    logger.warning(f"获取任务 {task_id} 进度失败: {str(e)}")
                    continue
            
            return all_progress
            
        except Exception as e:
            logger.error(f"获取所有任务进度失败: {str(e)}")
            return {}
    
    def get_execution_statistics(self) -> Dict:
        """获取执行统计信息
        
        Returns:
            Dict: 执行统计信息
        """
        try:
            # 获取监控器统计信息
            monitor_stats = self.execution_monitor.get_monitor_statistics()
            
            # 添加本地统计信息
            local_stats = {
                'local_active_tasks': len(self.active_tasks),
                'local_completed_tasks': len(self.completed_tasks),
                'total_reports': len(self.reports),
                'max_concurrent_tasks': self.max_concurrent_tasks,
                'default_initial_capital': self.default_initial_capital
            }
            
            # 合并统计信息
            combined_stats = {
                'monitor_statistics': monitor_stats,
                'local_statistics': local_stats,
                'system_status': self.get_system_status()
            }
            
            return combined_stats
            
        except Exception as e:
            logger.error(f"获取执行统计信息失败: {str(e)}")
            return {}
    
    def cleanup_old_tasks(self, keep_recent_hours: int = 24) -> Dict:
        """清理旧任务记录
        
        Args:
            keep_recent_hours: 保留最近几小时的记录
            
        Returns:
            Dict: 清理结果统计
        """
        try:
            # 清理监控器中的任务
            monitor_cleaned = self.execution_monitor.cleanup_completed_tasks(keep_recent_hours)
            
            # 清理本地任务记录
            cutoff_time = datetime.now() - timedelta(hours=keep_recent_hours)
            local_cleaned = 0
            
            tasks_to_remove = []
            for task_id, task in self.completed_tasks.items():
                if task.completed_at:
                    try:
                        completed_time = datetime.fromisoformat(task.completed_at)
                        if completed_time < cutoff_time:
                            tasks_to_remove.append(task_id)
                    except ValueError:
                        # 如果时间格式有问题，保留任务
                        continue
            
            for task_id in tasks_to_remove:
                del self.completed_tasks[task_id]
                local_cleaned += 1
            
            cleanup_result = {
                'monitor_cleaned_count': monitor_cleaned,
                'local_cleaned_count': local_cleaned,
                'total_cleaned_count': monitor_cleaned + local_cleaned,
                'cleanup_time': datetime.now().isoformat()
            }
            
            logger.info(f"清理旧任务完成: {cleanup_result}")
            return cleanup_result
            
        except Exception as e:
            logger.error(f"清理旧任务失败: {str(e)}")
            return {'error': str(e)}
    
    def get_task_list(self, status_filter: Optional[str] = None) -> List[Dict]:
        """获取任务列表
        
        Args:
            status_filter: 状态过滤器，可选值：pending, running, completed, failed, cancelled
            
        Returns:
            List[Dict]: 任务列表
        """
        try:
            all_tasks = list(self.active_tasks.values()) + list(self.completed_tasks.values())
            
            # 状态过滤
            if status_filter:
                all_tasks = [task for task in all_tasks if task.status == status_filter]
            
            # 按创建时间降序排序
            all_tasks.sort(key=lambda t: t.created_at, reverse=True)
            
            # 转换为字典格式
            task_list = [task.to_dict() for task in all_tasks]
            
            logger.info(f"获取任务列表完成，返回 {len(task_list)} 个任务")
            return task_list
            
        except Exception as e:
            logger.error(f"获取任务列表失败: {str(e)}")
            raise PVFRSException(f"获取任务列表失败: {str(e)}")
    
    def create_and_start_backtest(self, config: BacktestConfig) -> str:
        """创建并立即开始执行回测任务
        
        Args:
            config: 回测配置
            
        Returns:
            str: 任务ID
            
        Raises:
            PVFRSException: 创建或启动任务失败时抛出
        """
        try:
            # 创建任务
            task_id = self.create_backtest(config)
            
            # 立即开始执行
            success = self.start_backtest_execution(task_id)
            
            if not success:
                raise PVFRSException(f"启动回测任务失败: {task_id}")
            
            logger.info(f"创建并启动回测任务成功: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"创建并启动回测任务失败: {str(e)}")
            raise PVFRSException(f"创建并启动回测任务失败: {str(e)}")
    
    def get_system_status(self) -> Dict:
        """获取系统状态信息
        
        Returns:
            Dict: 系统状态信息
        """
        return {
            'admin_interface_status': 'active',
            'pvfrs_system_status': self.pvfrs_system.get_system_status(),
            'active_tasks_count': len(self.active_tasks),
            'completed_tasks_count': len(self.completed_tasks),
            'total_reports_count': len(self.reports),
            'running_futures_count': len(self.running_futures),
            'max_concurrent_tasks': self.max_concurrent_tasks,
            'executor_status': {
                'max_workers': self.executor._max_workers,
                'threads_count': len(self.executor._threads) if hasattr(self.executor, '_threads') else 0
            }
        }
    
    def _validate_backtest_config(self, config: BacktestConfig) -> None:
        """验证回测配置
        
        Args:
            config: 回测配置
            
        Raises:
            PVFRSException: 配置无效时抛出
        """
        # 转换为字典格式进行验证
        config_dict = config.to_dict()
        
        # 使用配置验证器进行验证
        is_valid, errors = self.config_validator.validate_backtest_config(config_dict)
        
        if not is_valid:
            error_msg = "回测配置验证失败:\n" + "\n".join(errors)
            raise PVFRSException(error_msg)
    
    def _estimate_remaining_time(self, task: BacktestTask) -> Optional[str]:
        """估算剩余时间
        
        Args:
            task: 回测任务
            
        Returns:
            Optional[str]: 估算的剩余时间，格式为 "HH:MM:SS"
        """
        if task.status != "running" or not task.started_at:
            return None
        
        try:
            # 简单的线性估算
            started_time = datetime.fromisoformat(task.started_at)
            elapsed_seconds = (datetime.now() - started_time).total_seconds()
            
            if task.progress > 0:
                total_estimated_seconds = elapsed_seconds * 100 / task.progress
                remaining_seconds = total_estimated_seconds - elapsed_seconds
                
                if remaining_seconds > 0:
                    hours = int(remaining_seconds // 3600)
                    minutes = int((remaining_seconds % 3600) // 60)
                    seconds = int(remaining_seconds % 60)
                    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
            return None
            
        except Exception:
            return None
    
    def _calculate_volatility(self, equity_curve: List[Dict]) -> float:
        """计算收益率波动率
        
        Args:
            equity_curve: 资金曲线
            
        Returns:
            float: 波动率
        """
        try:
            if len(equity_curve) < 2:
                return 0.0
            
            # 计算日收益率
            returns = []
            for i in range(1, len(equity_curve)):
                prev_equity = equity_curve[i-1]['equity']
                curr_equity = equity_curve[i]['equity']
                if prev_equity > 0:
                    daily_return = (curr_equity - prev_equity) / prev_equity
                    returns.append(daily_return)
            
            if not returns:
                return 0.0
            
            # 计算标准差
            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
            volatility = variance ** 0.5
            
            return volatility
            
        except Exception:
            return 0.0


# 便捷函数
def create_admin_interface(pvfrs_system: Optional[PVFRSSystem] = None) -> AdminInterface:
    """创建管理端接口实例
    
    Args:
        pvfrs_system: PVFRS策略系统实例
        
    Returns:
        AdminInterface: 管理端接口实例
    """
    return AdminInterface(pvfrs_system)