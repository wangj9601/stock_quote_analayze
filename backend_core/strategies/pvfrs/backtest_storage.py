"""
PVFRS策略回测结果持久化存储模块
负责回测报告的数据库存储和历史查询功能，使用SQLAlchemy ORM
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import logging
import json
from dataclasses import dataclass, asdict
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from .models import PVFRSException
from backend_api.database import SessionLocal
from backend_api.models import (
    PVFRSStrategyConfig,
    PVFRSBacktestTask,
    PVFRSBacktestResult,
    PVFRSTradeRecord,
    PVFRSEquityCurve
)

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class StorageConfig:
    """存储配置"""
    max_reports_per_strategy: int = 100
    auto_cleanup_days: int = 365


@dataclass
class QueryFilter:
    """查询过滤器"""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    strategy_name: Optional[str] = None
    min_return: Optional[float] = None
    max_drawdown: Optional[float] = None
    min_sharpe_ratio: Optional[float] = None
    task_ids: Optional[List[str]] = None
    report_ids: Optional[List[str]] = None
    limit: int = 50
    offset: int = 0
    order_by: str = "created_at"
    order_desc: bool = True


class BacktestStorage:
    """回测结果存储管理器
    
    负责回测报告的持久化存储和查询：
    - 使用 SQLAlchemy ORM 进行数据库操作
    - 支持任务、结果、交易记录和收益曲线的结构化存储
    - 历史查询和过滤
    """
    
    def __init__(self, config: Optional[StorageConfig] = None):
        """初始化存储管理器"""
        self.config = config or StorageConfig()
        logger.info("PVFRS回测存储管理器初始化完成（SQLAlchemy版本）")
    
    def _get_db(self) -> Session:
        """获取数据库会话"""
        return SessionLocal()

    def save_task(self, task_data: Dict, db: Optional[Session] = None) -> str:
        """保存或更新回测任务"""
        _db = db or self._get_db()
        try:
            task_id = task_data.get('task_id')
            task = _db.query(PVFRSBacktestTask).filter_by(task_id=task_id).first()
            
            if not task:
                # 获取或创建策略配置
                strategy_name = task_data.get('config', {}).get('strategy_name', 'PVFRS')
                strategy_config = _db.query(PVFRSStrategyConfig).filter_by(name=strategy_name).first()
                if not strategy_config:
                    strategy_config = PVFRSStrategyConfig(
                        name=strategy_name,
                        config_params=task_data.get('config', {}).get('strategy_params', {})
                    )
                    _db.add(strategy_config)
                    _db.flush()

                task = PVFRSBacktestTask(
                    task_id=task_id,
                    task_name=task_data.get('name') or task_data.get('task_name'),
                    strategy_config_id=strategy_config.id,
                    mode=task_data.get('mode', 'single'),
                    stock_codes=task_data.get('config', {}).get('stock_pool', []),
                    market=task_data.get('config', {}).get('market', 'CN'),
                    start_date=datetime.strptime(task_data.get('config', {}).get('start_date'), '%Y-%m-%d').date() if task_data.get('config', {}).get('start_date') else None,
                    end_date=datetime.strptime(task_data.get('config', {}).get('end_date'), '%Y-%m-%d').date() if task_data.get('config', {}).get('end_date') else None,
                    initial_capital=task_data.get('config', {}).get('initial_capital', 100000.0),
                    status=task_data.get('status', 'pending'),
                    progress=task_data.get('progress', 0),
                    created_at=datetime.fromisoformat(task_data.get('created_at')) if task_data.get('created_at') else datetime.now()
                )
                _db.add(task)
            else:
                # 更新任务状态
                task.status = task_data.get('status', task.status)
                task.progress = task_data.get('progress', task.progress)
                task.current_step = task_data.get('current_step', task.current_step)
                task.error_message = task_data.get('error_message', task.error_message)
                if task_data.get('started_at'):
                    task.started_at = datetime.fromisoformat(task_data.get('started_at'))
                if task_data.get('completed_at'):
                    task.completed_at = datetime.fromisoformat(task_data.get('completed_at'))
                
                # 更新进度相关字段
                if 'total_stocks' in task_data:
                    task.total_stocks = task_data['total_stocks']
                if 'processed_stocks' in task_data:
                    task.processed_stocks = task_data['processed_stocks']
                if 'name' in task_data:
                    task.task_name = task_data['name']

            _db.commit()
            return task_id
        except Exception as e:
            _db.rollback()
            logger.error(f"保存回测任务失败: {str(e)}")
            raise PVFRSException(f"保存回测任务失败: {str(e)}")
        finally:
            if not db:
                _db.close()

    def save_report(self, report_data: Dict, db: Optional[Session] = None) -> str:
        """保存完整回测报告到结构化数据库"""
        _db = db or self._get_db()
        try:
            report_id = report_data.get('report_id')
            task_id = report_data.get('task_id')
            config_data = report_data.get('config', {})
            
            # 1. 确保任务和策略配置存在
            task = _db.query(PVFRSBacktestTask).filter_by(task_id=task_id).first()
            if not task:
                # 如果任务不存在，手动创建一个简单的任务记录
                self.save_task({'task_id': task_id, 'config': config_data, 'status': 'completed'}, db=_db)
                task = _db.query(PVFRSBacktestTask).filter_by(task_id=task_id).first()

            # 2. 创建或更新结果记录
            result = _db.query(PVFRSBacktestResult).filter_by(report_id=report_id).first()
            if not result:
                result = PVFRSBacktestResult(
                    report_id=report_id,
                    task_id=task_id,
                    strategy_config_id=task.strategy_config_id,
                    stock_code=config_data.get('stock_pool', ['MULTI'])[0], # 简化处理
                    market=config_data.get('market', 'CN'),
                    backtest_date=datetime.now().date(),
                    start_date=datetime.strptime(config_data.get('start_date'), '%Y-%m-%d').date() if config_data.get('start_date') else None,
                    end_date=datetime.strptime(config_data.get('end_date'), '%Y-%m-%d').date() if config_data.get('end_date') else None,
                    initial_capital=config_data.get('initial_capital', 0.0),
                    final_capital=report_data.get('final_capital') or 0.0,
                    total_return=report_data.get('total_return') or 0.0,
                    annual_return=report_data.get('annual_return') or 0.0,
                    max_drawdown=report_data.get('max_drawdown') or 0.0,
                    sharpe_ratio=report_data.get('sharpe_ratio') or 0.0,
                    win_rate=report_data.get('win_rate') or 0.0,
                    profit_factor=report_data.get('profit_factor') or 0.0,
                    total_trades=len(report_data.get('trades', [])),
                    winning_trades=len([t for t in report_data.get('trades', []) if (t.get('pnl') or 0) > 0]),
                    avg_holding_period=report_data.get('avg_holding_period') or 0.0,
                    volatility=report_data.get('volatility') or 0.0,
                    config_snapshot=config_data,
                    summary_data=report_data.get('summary', {})
                )
                _db.add(result)
                _db.flush() # 获取 result.id
            
            # 3. 保存交易记录
            # 先清理原有交易记录（如果是在更新）
            _db.query(PVFRSTradeRecord).filter_by(result_id=result.id).delete()
            for t_data in report_data.get('trades', []):
                trade = PVFRSTradeRecord(
                    result_id=result.id,
                    stock_code=t_data.get('stock_code', result.stock_code),
                    market=result.market,
                    trade_date=datetime.strptime(t_data.get('exit_date'), '%Y-%m-%d').date() if t_data.get('exit_date') else None,
                    entry_date=datetime.strptime(t_data.get('entry_date'), '%Y-%m-%d').date() if t_data.get('entry_date') else None,
                    entry_time=datetime.strptime(t_data.get('entry_date'), '%Y-%m-%d') if t_data.get('entry_date') else None,
                    exit_time=datetime.strptime(t_data.get('exit_date'), '%Y-%m-%d') if t_data.get('exit_date') else None,
                    entry_price=t_data.get('entry_price') or 0.0,
                    exit_price=t_data.get('exit_price') or 0.0,
                    quantity=t_data.get('quantity') or 0,
                    pnl=t_data.get('pnl') or 0.0,
                    pnl_percent=t_data.get('pnl_percent') or 0.0,
                    exit_reason=t_data.get('exit_reason', ''),
                    holding_period=t_data.get('holding_days') or 0
                )
                _db.add(trade)

            # 4. 保存收益曲线
            _db.query(PVFRSEquityCurve).filter_by(result_id=result.id).delete()
            for e_data in report_data.get('equity_curve', []):
                point = PVFRSEquityCurve(
                    result_id=result.id,
                    stock_code=result.stock_code,
                    market=result.market,
                    curve_date=datetime.strptime(e_data.get('date'), '%Y-%m-%d').date() if e_data.get('date') else None,
                    equity=e_data.get('equity') or 0.0,
                    cash=e_data.get('cash') or 0.0,
                    portfolio_value=e_data.get('total_value') or e_data.get('equity') or 0.0,
                    daily_return=e_data.get('daily_return') or 0.0,
                    cumulative_return=e_data.get('cumulative_return') or 0.0,
                    drawdown=e_data.get('drawdown') or 0.0
                )
                _db.add(point)

            _db.commit()
            logger.info(f"回测报告及明细已保存至数据库: {report_id}")
            return str(result.id)
        except Exception as e:
            _db.rollback()
            logger.error(f"保存回测分析数据失败: {str(e)}")
            raise PVFRSException(f"保存回测分析数据失败: {str(e)}")
        finally:
            if not db:
                _db.close()

    def get_report(self, report_id: str, db: Optional[Session] = None) -> Optional[Dict]:
        """从数据库重建报告字典"""
        _db = db or self._get_db()
        try:
            result = _db.query(PVFRSBacktestResult).filter_by(report_id=report_id).first()
            if not result:
                # 尝试通过任务ID查找
                result = _db.query(PVFRSBacktestResult).filter_by(task_id=report_id).first()
            
            if not result:
                return None
            
            # 重建基础数据
            report_data = {
                'report_id': result.report_id,
                'task_id': result.task_id,
                'config': result.config_snapshot,
                'total_return': float(result.total_return),
                'annual_return': float(result.annual_return),
                'win_rate': float(result.win_rate),
                'max_drawdown': float(result.max_drawdown),
                'sharpe_ratio': float(result.sharpe_ratio or 0),
                'final_capital': float(result.final_capital),
                'avg_holding_period': float(result.avg_holding_period),
                'volatility': float(result.volatility or 0),
                'profit_factor': float(result.profit_factor or 0),
                'summary': result.summary_data or {},
                'created_at': result.created_at.isoformat()
            }
            
            # 获取交易记录
            trades = []
            for t in result.trades:
                trades.append({
                    'stock_code': t.stock_code,
                    'entry_date': t.entry_time.strftime('%Y-%m-%d') if t.entry_time else None,
                    'exit_date': t.exit_time.strftime('%Y-%m-%d') if t.exit_time else None,
                    'entry_price': float(t.entry_price),
                    'exit_price': float(t.exit_price),
                    'quantity': t.quantity,
                    'pnl': float(t.pnl),
                    'pnl_percent': float(t.pnl_percent),
                    'exit_reason': t.exit_reason,
                    'holding_days': t.holding_period
                })
            report_data['trades'] = trades
            
            # 获取资金曲线
            equity_curve = []
            for e in result.equity_curve:
                equity_curve.append({
                    'date': e.curve_date.strftime('%Y-%m-%d'),
                    'equity': float(e.equity),
                    'cash': float(e.cash),
                    'daily_return': float(e.daily_return or 0),
                    'drawdown': float(e.drawdown or 0)
                })
            report_data['equity_curve'] = equity_curve
            
            return report_data
        except Exception as e:
            logger.error(f"获取回测报告失败: {str(e)}")
            return None
        finally:
            if not db:
                _db.close()

    def query_reports(self, filter_obj: Optional[QueryFilter] = None, db: Optional[Session] = None) -> List[Dict]:
        """查询符合条件的报告摘要"""
        _db = db or self._get_db()
        try:
            filter_obj = filter_obj or QueryFilter()
            query = _db.query(PVFRSBacktestResult)
            
            if filter_obj.strategy_name:
                query = query.join(PVFRSStrategyConfig).filter(PVFRSStrategyConfig.name.like(f"%{filter_obj.strategy_name}%"))
            
            if filter_obj.min_return is not None:
                query = query.filter(PVFRSBacktestResult.total_return >= filter_obj.min_return)
            
            if filter_obj.max_drawdown is not None:
                query = query.filter(PVFRSBacktestResult.max_drawdown <= filter_obj.max_drawdown)
            
            if filter_obj.start_date:
                query = query.filter(PVFRSBacktestResult.created_at >= filter_obj.start_date)
            
            if filter_obj.end_date:
                query = query.filter(PVFRSBacktestResult.created_at <= filter_obj.end_date)

            if filter_obj.order_desc:
                query = query.order_by(desc(getattr(PVFRSBacktestResult, filter_obj.order_by)))
            else:
                query = query.order_by(getattr(PVFRSBacktestResult, filter_obj.order_by))
            
            results = query.offset(filter_obj.offset).limit(filter_obj.limit).all()
            
            output = []
            for r in results:
                summary = {
                    'report_id': r.report_id,
                    'task_id': r.task_id,
                    'stock_code': r.stock_code,
                    'total_return': float(r.total_return),
                    'annual_return': float(r.annual_return),
                    'max_drawdown': float(r.max_drawdown),
                    'sharpe_ratio': float(r.sharpe_ratio or 0),
                    'win_rate': float(r.win_rate),
                    'total_trades': r.total_trades,
                    'created_at': r.created_at.isoformat()
                }
                output.append(summary)
            return output
        finally:
            if not db:
                _db.close()

    def delete_report(self, report_id: str, db: Optional[Session] = None) -> bool:
        """从数据库删除报告及其关联数据"""
        _db = db or self._get_db()
        try:
            result = _db.query(PVFRSBacktestResult).filter_by(report_id=report_id).first()
            if result:
                # 级联删除由于关系设置可能由ORM处理，但手动清理明细表更安全
                _db.query(PVFRSTradeRecord).filter_by(result_id=result.id).delete()
                _db.query(PVFRSEquityCurve).filter_by(result_id=result.id).delete()
                _db.delete(result)
                _db.commit()
                return True
            return False
        except Exception as e:
            _db.rollback()
            logger.error(f"删除回测记录失败: {str(e)}")
            return False
        finally:
            if not db:
                _db.close()

    def get_statistics(self, db: Optional[Session] = None) -> Dict:
        """获取全库回测统计信息"""
        _db = db or self._get_db()
        try:
            total_count = _db.query(PVFRSBacktestResult).count()
            avg_return = _db.query(func.avg(PVFRSBacktestResult.total_return)).scalar() or 0
            max_return = _db.query(func.max(PVFRSBacktestResult.total_return)).scalar() or 0
            
            return {
                'total_reports': total_count,
                'performance_statistics': {
                    'average_return': float(avg_return),
                    'max_return': float(max_return)
                }
            }
        finally:
            if not db:
                _db.close()


def create_backtest_storage(config: Optional[StorageConfig] = None) -> BacktestStorage:
    return BacktestStorage(config)


def create_query_filter(**kwargs) -> QueryFilter:
    return QueryFilter(**kwargs)