"""
PVFRS策略管理服务层
提供统一的业务逻辑接口，分离业务逻辑与数据访问
"""

from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc, func
import logging
import json

from backend_api.models.pvfrs_enhanced import (
    PVFRSStrategyConfig, PVFRSBacktestTaskEnhanced, 
    PVFRSBacktestResultEnhanced, PVFRSTradeRecordEnhanced, 
    PVFRSEquityCurveEnhanced
)
from backend_core.strategies.pvfrs.models import PVFRSException

logger = logging.getLogger(__name__)

class PVFRSAdminService:
    """PVFRS策略管理服务
    
    负责：
    - 策略配置管理
    - 回测任务管理
    - 回测结果分析
    - 交易记录管理
    - 收益曲线分析
    """
    
    def __init__(self, db: Session):
        """初始化服务
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    # ==================== 策略配置管理 ====================
    
    def create_strategy_config(self, name: str, description: str, 
                          config_params: Dict, is_active: bool = True) -> int:
        """创建策略配置
        
        Args:
            name: 策略名称
            description: 策略描述
            config_params: 策略参数
            is_active: 是否激活
            
        Returns:
            int: 配置ID
        """
        try:
            config = PVFRSStrategyConfig(
                name=name,
                description=description,
                config_params=config_params,
                is_active=is_active
            )
            
            self.db.add(config)
            self.db.commit()
            self.db.refresh(config)
            
            logger.info(f"创建策略配置成功: {name} (ID: {config.id})")
            return config.id
            
        except Exception as e:
            logger.error(f"创建策略配置失败: {str(e)}")
            self.db.rollback()
            raise PVFRSException(f"创建策略配置失败: {str(e)}")
    
    def get_strategy_config(self, config_id: int) -> Optional[PVFRSStrategyConfig]:
        """获取策略配置"""
        try:
            return self.db.query(PVFRSStrategyConfig).filter(
                PVFRSStrategyConfig.id == config_id
            ).first()
        except Exception as e:
            logger.error(f"获取策略配置失败: {str(e)}")
            return None
    
    def get_strategy_config_by_name(self, name: str) -> Optional[PVFRSStrategyConfig]:
        """根据名称获取策略配置"""
        try:
            return self.db.query(PVFRSStrategyConfig).filter(
                PVFRSStrategyConfig.name == name
            ).first()
        except Exception as e:
            logger.error(f"根据名称获取策略配置失败: {str(e)}")
            return None
    
    def list_strategy_configs(self, active_only: bool = False) -> List[PVFRSStrategyConfig]:
        """列出策略配置"""
        try:
            query = self.db.query(PVFRSStrategyConfig)
            if active_only:
                query = query.filter(PVFRSStrategyConfig.is_active == True)
            
            return query.order_by(desc(PVFRSStrategyConfig.created_at)).all()
        except Exception as e:
            logger.error(f"列出策略配置失败: {str(e)}")
            return []
    
    def update_strategy_config(self, config_id: int, **kwargs) -> bool:
        """更新策略配置"""
        try:
            config = self.get_strategy_config(config_id)
            if not config:
                return False
            
            for key, value in kwargs.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            
            config.updated_at = datetime.now()
            self.db.commit()
            
            logger.info(f"更新策略配置成功: {config_id}")
            return True
            
        except Exception as e:
            logger.error(f"更新策略配置失败: {str(e)}")
            self.db.rollback()
            return False
    
    def delete_strategy_config(self, config_id: int) -> bool:
        """删除策略配置"""
        try:
            config = self.get_strategy_config(config_id)
            if not config:
                return False
            
            self.db.delete(config)
            self.db.commit()
            
            logger.info(f"删除策略配置成功: {config_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除策略配置失败: {str(e)}")
            self.db.rollback()
            return False
    
    # ==================== 回测任务管理 ====================
    
    def create_backtest_task(self, strategy_config_id: int, mode: str, 
                          stock_codes: List[str], market: str,
                          start_date: date, end_date: date,
                          initial_capital: float, priority: int = 5) -> str:
        """创建回测任务
        
        Args:
            strategy_config_id: 策略配置ID
            mode: 模式（single, batch, optimize）
            stock_codes: 股票代码列表
            market: 市场类型
            start_date: 开始日期
            end_date: 结束日期
            initial_capital: 初始资金
            priority: 优先级
            
        Returns:
            str: 任务ID
        """
        try:
            task_id = f"pvfrs_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(stock_codes)}"
            
            task = PVFRSBacktestTaskEnhanced(
                task_id=task_id,
                strategy_config_id=strategy_config_id,
                mode=mode,
                stock_codes=stock_codes,
                market=market,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                status="pending",
                priority=priority
            )
            
            self.db.add(task)
            self.db.commit()
            self.db.refresh(task)
            
            logger.info(f"创建回测任务成功: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"创建回测任务失败: {str(e)}")
            self.db.rollback()
            raise PVFRSException(f"创建回测任务失败: {str(e)}")
    
    def get_backtest_task(self, task_id: str) -> Optional[PVFRSBacktestTaskEnhanced]:
        """获取回测任务"""
        try:
            return self.db.query(PVFRSBacktestTaskEnhanced).filter(
                PVFRSBacktestTaskEnhanced.task_id == task_id
            ).first()
        except Exception as e:
            logger.error(f"获取回测任务失败: {str(e)}")
            return None
    
    def list_backtest_tasks(self, status: Optional[str] = None, 
                        limit: int = 50, offset: int = 0) -> List[PVFRSBacktestTaskEnhanced]:
        """列出回测任务"""
        try:
            query = self.db.query(PVFRSBacktestTaskEnhanced)
            
            if status:
                query = query.filter(PVFRSBacktestTaskEnhanced.status == status)
            
            return query.order_by(desc(PVFRSBacktestTaskEnhanced.created_at)).offset(offset).limit(limit).all()
        except Exception as e:
            logger.error(f"列出回测任务失败: {str(e)}")
            return []
    
    def update_task_status(self, task_id: str, status: str, 
                       progress: Optional[int] = None, 
                       current_step: Optional[str] = None,
                       error_message: Optional[str] = None) -> bool:
        """更新任务状态"""
        try:
            task = self.get_backtest_task(task_id)
            if not task:
                return False
            
            task.status = status
            if progress is not None:
                task.progress = progress
            if current_step is not None:
                task.current_step = current_step
            if error_message is not None:
                task.error_message = error_message
            
            if status == "running" and not task.started_at:
                task.started_at = datetime.now()
            elif status in ["completed", "failed", "cancelled"] and not task.completed_at:
                task.completed_at = datetime.now()
            
            self.db.commit()
            
            logger.info(f"更新任务状态成功: {task_id} -> {status}")
            return True
            
        except Exception as e:
            logger.error(f"更新任务状态失败: {str(e)}")
            self.db.rollback()
            return False
    
    # ==================== 回测结果管理 ====================
    
    def create_backtest_result(self, task_id: str, stock_code: str,
                           market: str, backtest_date: date,
                           performance_data: Dict) -> int:
        """创建回测结果
        
        Args:
            task_id: 任务ID
            stock_code: 股票代码
            market: 市场类型
            backtest_date: 回测日期
            performance_data: 性能数据
            
        Returns:
            int: 结果ID
        """
        try:
            result = PVFRSBacktestResultEnhanced(
                task_id=task_id,
                strategy_config_id=1,  # 默认策略配置
                stock_code=stock_code,
                market=market,
                backtest_date=backtest_date,
                start_date=performance_data.get('start_date', backtest_date),
                end_date=performance_data.get('end_date', backtest_date),
                initial_capital=performance_data.get('initial_capital', 100000),
                final_capital=performance_data.get('final_capital', 100000),
                total_return=performance_data.get('total_return', 0),
                annual_return=performance_data.get('annual_return', 0),
                max_drawdown=performance_data.get('max_drawdown', 0),
                sharpe_ratio=performance_data.get('sharpe_ratio', 0),
                win_rate=performance_data.get('win_rate', 0),
                profit_factor=performance_data.get('profit_factor', 0),
                total_trades=performance_data.get('total_trades', 0),
                winning_trades=performance_data.get('winning_trades', 0),
                avg_holding_period=performance_data.get('avg_holding_period', 0),
                volatility=performance_data.get('volatility', 0)
            )
            
            self.db.add(result)
            self.db.commit()
            self.db.refresh(result)
            
            logger.info(f"创建回测结果成功: {task_id} - {stock_code}")
            return result.id
            
        except Exception as e:
            logger.error(f"创建回测结果失败: {str(e)}")
            self.db.rollback()
            raise PVFRSException(f"创建回测结果失败: {str(e)}")
    
    def get_backtest_results(self, task_id: Optional[str] = None,
                         stock_code: Optional[str] = None,
                         limit: int = 50, offset: int = 0) -> List[PVFRSBacktestResultEnhanced]:
        """获取回测结果"""
        try:
            query = self.db.query(PVFRSBacktestResultEnhanced)
            
            if task_id:
                query = query.filter(PVFRSBacktestResultEnhanced.task_id == task_id)
            if stock_code:
                query = query.filter(PVFRSBacktestResultEnhanced.stock_code == stock_code)
            
            return query.order_by(desc(PVFRSBacktestResultEnhanced.created_at)).offset(offset).limit(limit).all()
        except Exception as e:
            logger.error(f"获取回测结果失败: {str(e)}")
            return []
    
    def get_performance_statistics(self, strategy_config_id: Optional[int] = None) -> Dict:
        """获取性能统计"""
        try:
            query = self.db.query(PVFRSBacktestResultEnhanced)
            
            if strategy_config_id:
                query = query.filter(PVFRSBacktestResultEnhanced.strategy_config_id == strategy_config_id)
            
            # 计算统计数据
            results = query.all()
            if not results:
                return {}
            
            total_results = len(results)
            avg_return = sum(r.total_return for r in results) / total_results
            avg_sharpe = sum(r.sharpe_ratio for r in results) / total_results
            avg_drawdown = sum(r.max_drawdown for r in results) / total_results
            avg_win_rate = sum(r.win_rate for r in results) / total_results
            
            return {
                'total_results': total_results,
                'avg_total_return': avg_return,
                'avg_sharpe_ratio': avg_sharpe,
                'avg_max_drawdown': avg_drawdown,
                'avg_win_rate': avg_win_rate,
                'best_return': max(r.total_return for r in results),
                'worst_return': min(r.total_return for r in results),
                'best_sharpe': max(r.sharpe_ratio for r in results),
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取性能统计失败: {str(e)}")
            return {}
    
    # ==================== 交易记录管理 ====================
    
    def create_trade_record(self, result_id: int, stock_code: str,
                        trade_data: Dict) -> int:
        """创建交易记录"""
        try:
            trade = PVFRSTradeRecordEnhanced(
                result_id=result_id,
                stock_code=stock_code,
                market=trade_data.get('market', 'CN'),
                trade_date=trade_data.get('trade_date', datetime.now().date()),
                entry_time=trade_data.get('entry_time', datetime.now()),
                exit_time=trade_data.get('exit_time', datetime.now()),
                entry_price=trade_data.get('entry_price', 0),
                exit_price=trade_data.get('exit_price', 0),
                quantity=trade_data.get('quantity', 0),
                pnl=trade_data.get('pnl', 0),
                pnl_percent=trade_data.get('pnl_percent', 0),
                commission=trade_data.get('commission', 0),
                slippage=trade_data.get('slippage', 0),
                exit_reason=trade_data.get('exit_reason', ''),
                trade_type=trade_data.get('trade_type', 'long'),
                holding_period=trade_data.get('holding_period', 0)
            )
            
            self.db.add(trade)
            self.db.commit()
            self.db.refresh(trade)
            
            logger.info(f"创建交易记录成功: {stock_code}")
            return trade.id
            
        except Exception as e:
            logger.error(f"创建交易记录失败: {str(e)}")
            self.db.rollback()
            raise PVFRSException(f"创建交易记录失败: {str(e)}")
    
    def get_trade_records(self, result_id: Optional[int] = None,
                         stock_code: Optional[str] = None,
                         limit: int = 100, offset: int = 0) -> List[PVFRSTradeRecordEnhanced]:
        """获取交易记录"""
        try:
            query = self.db.query(PVFRSTradeRecordEnhanced)
            
            if result_id:
                query = query.filter(PVFRSTradeRecordEnhanced.result_id == result_id)
            if stock_code:
                query = query.filter(PVFRSTradeRecordEnhanced.stock_code == stock_code)
            
            return query.order_by(desc(PVFRSTradeRecordEnhanced.trade_date)).offset(offset).limit(limit).all()
        except Exception as e:
            logger.error(f"获取交易记录失败: {str(e)}")
            return []
    
    # ==================== 收益曲线管理 ====================
    
    def create_equity_curve_point(self, result_id: int, stock_code: str,
                                curve_data: Dict) -> int:
        """创建收益曲线点"""
        try:
            point = PVFRSEquityCurveEnhanced(
                result_id=result_id,
                stock_code=stock_code,
                market=curve_data.get('market', 'CN'),
                curve_date=curve_data.get('curve_date', datetime.now().date()),
                equity=curve_data.get('equity', 0),
                cash=curve_data.get('cash', 0),
                portfolio_value=curve_data.get('portfolio_value', 0),
                benchmark_value=curve_data.get('benchmark_value', 0),
                daily_return=curve_data.get('daily_return', 0),
                cumulative_return=curve_data.get('cumulative_return', 0),
                drawdown=curve_data.get('drawdown', 0),
                max_drawdown=curve_data.get('max_drawdown', 0)
            )
            
            self.db.add(point)
            self.db.commit()
            self.db.refresh(point)
            
            logger.debug(f"创建收益曲线点成功: {stock_code}")
            return point.id
            
        except Exception as e:
            logger.error(f"创建收益曲线点失败: {str(e)}")
            self.db.rollback()
            raise PVFRSException(f"创建收益曲线点失败: {str(e)}")
    
    def get_equity_curve(self, result_id: Optional[int] = None,
                       stock_code: Optional[str] = None,
                       start_date: Optional[date] = None,
                       end_date: Optional[date] = None) -> List[PVFRSEquityCurveEnhanced]:
        """获取收益曲线"""
        try:
            query = self.db.query(PVFRSEquityCurveEnhanced)
            
            if result_id:
                query = query.filter(PVFRSEquityCurveEnhanced.result_id == result_id)
            if stock_code:
                query = query.filter(PVFRSEquityCurveEnhanced.stock_code == stock_code)
            if start_date:
                query = query.filter(PVFRSEquityCurveEnhanced.curve_date >= start_date)
            if end_date:
                query = query.filter(PVFRSEquityCurveEnhanced.curve_date <= end_date)
            
            return query.order_by(asc(PVFRSEquityCurveEnhanced.curve_date)).all()
        except Exception as e:
            logger.error(f"获取收益曲线失败: {str(e)}")
            return []
    
    # ==================== 数据清理和维护 ====================
    
    def cleanup_old_data(self, days: int = 365) -> Dict[str, int]:
        """清理旧数据"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # 清理旧任务
            old_tasks = self.db.query(PVFRSBacktestTaskEnhanced).filter(
                PVFRSBacktestTaskEnhanced.created_at < cutoff_date
            ).all()
            
            tasks_deleted = 0
            for task in old_tasks:
                if task.status in ['completed', 'failed', 'cancelled']:
                    self.db.delete(task)
                    tasks_deleted += 1
            
            # 清理旧结果
            old_results = self.db.query(PVFRSBacktestResultEnhanced).filter(
                PVFRSBacktestResultEnhanced.created_at < cutoff_date
            ).all()
            
            results_deleted = len(old_results)
            for result in old_results:
                self.db.delete(result)
            
            self.db.commit()
            
            logger.info(f"数据清理完成: 任务 {tasks_deleted}, 结果 {results_deleted}")
            
            return {
                'tasks_deleted': tasks_deleted,
                'results_deleted': results_deleted,
                'total_deleted': tasks_deleted + results_deleted
            }
            
        except Exception as e:
            logger.error(f"数据清理失败: {str(e)}")
            return {'error': str(e)}
    
    def get_database_statistics(self) -> Dict:
        """获取数据库统计信息"""
        try:
            stats = {}
            
            # 策略配置统计
            stats['strategy_configs'] = {
                'total': self.db.query(PVFRSStrategyConfig).count(),
                'active': self.db.query(PVFRSStrategyConfig).filter(PVFRSStrategyConfig.is_active == True).count()
            }
            
            # 任务统计
            stats['tasks'] = {
                'total': self.db.query(PVFRSBacktestTaskEnhanced).count(),
                'pending': self.db.query(PVFRSBacktestTaskEnhanced).filter(PVFRSBacktestTaskEnhanced.status == 'pending').count(),
                'running': self.db.query(PVFRSBacktestTaskEnhanced).filter(PVFRSBacktestTaskEnhanced.status == 'running').count(),
                'completed': self.db.query(PVFRSBacktestTaskEnhanced).filter(PVFRSBacktestTaskEnhanced.status == 'completed').count(),
                'failed': self.db.query(PVFRSBacktestTaskEnhanced).filter(PVFRSBacktestTaskEnhanced.status == 'failed').count()
            }
            
            # 结果统计
            stats['results'] = {
                'total': self.db.query(PVFRSBacktestResultEnhanced).count(),
                'avg_return': self.db.query(func.avg(PVFRSBacktestResultEnhanced.total_return)).scalar() or 0,
                'avg_sharpe': self.db.query(func.avg(PVFRSBacktestResultEnhanced.sharpe_ratio)).scalar() or 0,
                'avg_win_rate': self.db.query(func.avg(PVFRSBacktestResultEnhanced.win_rate)).scalar() or 0
            }
            
            # 交易记录统计
            stats['trades'] = {
                'total': self.db.query(PVFRSTradeRecordEnhanced).count(),
                'total_pnl': self.db.query(func.sum(PVFRSTradeRecordEnhanced.pnl)).scalar() or 0
            }
            
            # 收益曲线统计
            stats['equity_curves'] = {
                'total': self.db.query(PVFRSEquityCurveEnhanced).count()
            }
            
            stats['generated_at'] = datetime.now().isoformat()
            
            return stats
            
        except Exception as e:
            logger.error(f"获取数据库统计失败: {str(e)}")
            return {'error': str(e)}
