"""
修复后的 query_reports 方法
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
from backend_api.models.pvfrs_enhanced import (
    PVFRSBacktestResultEnhanced,
    PVFRSStrategyConfigEnhanced,
    PVFRSBacktestTaskEnhanced,
    PVFRSTradeRecordEnhanced,
    PVFRSEquityCurveEnhanced
)

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

def query_reports_fixed(filter_obj: Optional[QueryFilter] = None, db: Optional[Session] = None) -> List[Dict]:
    """查询符合条件的报告摘要（使用增强版表）"""
    _db = db or SessionLocal()
    try:
        filter_obj = filter_obj or QueryFilter()
        query = _db.query(PVFRSBacktestResultEnhanced)
        
        if filter_obj.strategy_name:
            query = query.join(PVFRSStrategyConfigEnhanced).filter(PVFRSStrategyConfigEnhanced.name.like(f"%{filter_obj.strategy_name}%"))
        
        if filter_obj.min_return is not None:
            query = query.filter(PVFRSBacktestResultEnhanced.total_return >= filter_obj.min_return)
        
        if filter_obj.max_drawdown is not None:
            query = query.filter(PVFRSBacktestResultEnhanced.max_drawdown <= filter_obj.max_drawdown)
        
        if filter_obj.start_date:
            query = query.filter(PVFRSBacktestResultEnhanced.created_at >= filter_obj.start_date)
        
        if filter_obj.end_date:
            query = query.filter(PVFRSBacktestResultEnhanced.created_at <= filter_obj.end_date)

        if filter_obj.order_desc:
            query = query.order_by(desc(getattr(PVFRSBacktestResultEnhanced, filter_obj.order_by)))
        else:
            query = query.order_by(getattr(PVFRSBacktestResultEnhanced, filter_obj.order_by))
        
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
