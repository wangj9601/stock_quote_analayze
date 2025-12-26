"""
指标数据管理API模块
提供MA、MACD、RSI、KDJ等指标数据的查询接口
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, or_
from datetime import datetime

from backend_api.models import (
    MAIndicators, MACDIndicators, RSIIndicators, KDJIndicators, BOLLIndicators, MAVOLIndicators, User
)
from backend_api.database import get_db
from backend_api.auth import get_current_admin_user

router = APIRouter(prefix="/api/admin/indicators", tags=["admin_indicators"])

def paginate_query(query, page, page_size):
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size
    }

@router.get("/ma")
async def get_ma_indicators(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    code: Optional[str] = None,
    market_type: Optional[str] = Query(None, description="CN 或 HK"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """查询 MA 移动平均线指标"""
    query = db.query(MAIndicators)
    
    if code:
        query = query.filter(MAIndicators.code == code)
    if market_type:
        query = query.filter(MAIndicators.market_type == market_type)
    if start_date:
        query = query.filter(MAIndicators.date >= start_date)
    if end_date:
        query = query.filter(MAIndicators.date <= end_date)
        
    query = query.order_by(desc(MAIndicators.date), MAIndicators.code)
    result = paginate_query(query, page, page_size)
    
    return {
        "success": True,
        "data": result["items"],
        "total": result["total"],
        "page": page,
        "page_size": page_size
    }

@router.get("/macd")
async def get_macd_indicators(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    code: Optional[str] = None,
    market_type: Optional[str] = Query(None, description="CN 或 HK"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """查询 MACD 指标"""
    query = db.query(MACDIndicators)
    
    if code:
        query = query.filter(MACDIndicators.code == code)
    if market_type:
        # MACD 模型的 market_type 字段在 models.py 中似乎叫 market_type，
        # 但在有些地方可能叫别的。检查 models.py 发现是 market_type。
        query = query.filter(MACDIndicators.market_type == market_type)
    if start_date:
        query = query.filter(MACDIndicators.date >= start_date)
    if end_date:
        query = query.filter(MACDIndicators.date <= end_date)
        
    query = query.order_by(desc(MACDIndicators.date), MACDIndicators.code)
    result = paginate_query(query, page, page_size)
    
    return {
        "success": True,
        "data": result["items"],
        "total": result["total"],
        "page": page,
        "page_size": page_size
    }

@router.get("/rsi")
async def get_rsi_indicators(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    code: Optional[str] = None,
    market_type: Optional[str] = Query(None, description="CN 或 HK"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """查询 RSI 指标"""
    query = db.query(RSIIndicators)
    
    if code:
        query = query.filter(RSIIndicators.code == code)
    if market_type:
        query = query.filter(RSIIndicators.market_type == market_type)
    if start_date:
        query = query.filter(RSIIndicators.date >= start_date)
    if end_date:
        query = query.filter(RSIIndicators.date <= end_date)
        
    query = query.order_by(desc(RSIIndicators.date), RSIIndicators.code)
    result = paginate_query(query, page, page_size)
    
    return {
        "success": True,
        "data": result["items"],
        "total": result["total"],
        "page": page,
        "page_size": page_size
    }

@router.get("/kdj")
async def get_kdj_indicators(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    code: Optional[str] = None,
    market_type: Optional[str] = Query(None, description="CN 或 HK"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """查询 KDJ 指标"""
    query = db.query(KDJIndicators)
    
    if code:
        query = query.filter(KDJIndicators.code == code)
    if market_type:
        query = query.filter(KDJIndicators.market_type == market_type)
    if start_date:
        query = query.filter(KDJIndicators.date >= start_date)
    if end_date:
        query = query.filter(KDJIndicators.date <= end_date)
        
    query = query.order_by(desc(KDJIndicators.date), KDJIndicators.code)
    result = paginate_query(query, page, page_size)
    
    return {
        "success": True,
        "data": result["items"],
        "total": result["total"],
        "page": page,
        "page_size": page_size
    }

@router.get("/boll")
async def get_boll_indicators(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    code: Optional[str] = None,
    market_type: Optional[str] = Query(None, description="CN 或 HK"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """查询 BOLL 布林带指标"""
    query = db.query(BOLLIndicators)
    
    if code:
        query = query.filter(BOLLIndicators.code == code)
    if market_type:
        query = query.filter(BOLLIndicators.market_type == market_type)
    if start_date:
        query = query.filter(BOLLIndicators.date >= start_date)
    if end_date:
        query = query.filter(BOLLIndicators.date <= end_date)
        
    query = query.order_by(desc(BOLLIndicators.date), BOLLIndicators.code)
    result = paginate_query(query, page, page_size)
    
    return {
        "success": True,
        "data": result["items"],
        "total": result["total"],
        "page": page,
        "page_size": page_size
    }

@router.get("/mavol")
async def get_mavol_indicators(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    code: Optional[str] = None,
    market_type: Optional[str] = Query(None, description="CN 或 HK"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """查询 MAVOL 成交量移动平均线指标"""
    query = db.query(MAVOLIndicators)
    
    if code:
        query = query.filter(MAVOLIndicators.code == code)
    if market_type:
        query = query.filter(MAVOLIndicators.market_type == market_type)
    if start_date:
        query = query.filter(MAVOLIndicators.date >= start_date)
    if end_date:
        query = query.filter(MAVOLIndicators.date <= end_date)
        
    query = query.order_by(desc(MAVOLIndicators.date), MAVOLIndicators.code)
    result = paginate_query(query, page, page_size)
    
    return {
        "success": True,
        "data": result["items"],
        "total": result["total"],
        "page": page,
        "page_size": page_size
    }
