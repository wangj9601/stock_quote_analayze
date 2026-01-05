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
    MAIndicators, MACDIndicators, RSIIndicators, KDJIndicators, BOLLIndicators, MAVOLIndicators, 
    MeanFrequencyResonanceIndicators, User
)
from backend_api.database import get_db
from backend_api.auth import get_current_admin_user, get_current_user

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

@router.get("/pvfrs")
async def get_pvfrs_indicators(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    code: Optional[str] = None,
    market_type: Optional[str] = Query(None, description="CN 或 HK"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """查询 PVFRS 均值频率共振指标"""
    query = db.query(MeanFrequencyResonanceIndicators)
    
    if code:
        query = query.filter(MeanFrequencyResonanceIndicators.code == code)
    if market_type:
        query = query.filter(MeanFrequencyResonanceIndicators.market_type == market_type)
    if start_date:
        query = query.filter(MeanFrequencyResonanceIndicators.date >= start_date)
    if end_date:
        query = query.filter(MeanFrequencyResonanceIndicators.date <= end_date)
        
    query = query.order_by(desc(MeanFrequencyResonanceIndicators.date), MeanFrequencyResonanceIndicators.code)
    result = paginate_query(query, page, page_size)
    
    return {
        "success": True,
        "data": result["items"],
        "total": result["total"],
        "page": page,
        "page_size": page_size
    }

@router.get("/details")
async def get_indicator_details(
    code: str = Query(..., description="股票代码"),
    date: str = Query(..., description="日期 YYYY-MM-DD"),
    market_type: str = Query("CN", description="CN 或 HK"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """查询指定股票和日期的所有指标数据"""
    
    # helper to process query result to dict or None
    def row_to_dict(row):
        if not row:
            return None
        d = row.__dict__.copy()
        if '_sa_instance_state' in d:
            del d['_sa_instance_state']
        return d

    # Run queries
    ma_data = db.query(MAIndicators).filter_by(code=code, date=date, market_type=market_type).first()
    macd_data = db.query(MACDIndicators).filter_by(code=code, date=date, market_type=market_type).first()
    kdj_data = db.query(KDJIndicators).filter_by(code=code, date=date, market_type=market_type).first()
    rsi_data = db.query(RSIIndicators).filter_by(code=code, date=date, market_type=market_type).first()
    boll_data = db.query(BOLLIndicators).filter_by(code=code, date=date, market_type=market_type).first()
    mavol_data = db.query(MAVOLIndicators).filter_by(code=code, date=date, market_type=market_type).first()
    pvfrs_data = db.query(MeanFrequencyResonanceIndicators).filter_by(code=code, date=date, market_type=market_type).first()

    return {
        "success": True,
        "data": {
            "code": code,
            "date": date,
            "market_type": market_type,
            "ma": row_to_dict(ma_data),
            "macd": row_to_dict(macd_data),
            "kdj": row_to_dict(kdj_data),
            "rsi": row_to_dict(rsi_data),
            "boll": row_to_dict(boll_data),
            "mavol": row_to_dict(mavol_data),
            "pvfrs": row_to_dict(pvfrs_data)
        }
    }

@router.get("/history")
async def get_indicator_history(
    code: str = Query(..., description="股票代码"),
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    market_type: str = Query("CN", description="CN 或 HK"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """查询指定股票和日期范围的所有指标数据"""
    
    # 辅助函数：将查询结果转换为以日期为键的字典
    def list_to_date_dict(items):
        result = {}
        for item in items:
            d = item.__dict__.copy()
            if '_sa_instance_state' in d:
                del d['_sa_instance_state']
            
            # 确保日期格式一致
            date_key = str(d.get('date'))
            result[date_key] = d
        return result

    # 并行查询所有指标表
    # 注意：这里假设数据量不大（单只股票一段时间），直接全部查询后在内存合并
    
    # 1. MA
    ma_items = db.query(MAIndicators).filter(
        MAIndicators.code == code,
        MAIndicators.date >= start_date,
        MAIndicators.date <= end_date,
        MAIndicators.market_type == market_type
    ).all()
    ma_dict = list_to_date_dict(ma_items)
    
    # 2. MACD
    macd_items = db.query(MACDIndicators).filter(
        MACDIndicators.code == code,
        MACDIndicators.date >= start_date,
        MACDIndicators.date <= end_date,
        MACDIndicators.market_type == market_type
    ).all()
    macd_dict = list_to_date_dict(macd_items)
    
    # 3. KDJ
    kdj_items = db.query(KDJIndicators).filter(
        KDJIndicators.code == code,
        KDJIndicators.date >= start_date,
        KDJIndicators.date <= end_date,
        KDJIndicators.market_type == market_type
    ).all()
    kdj_dict = list_to_date_dict(kdj_items)
    
    # 4. RSI
    rsi_items = db.query(RSIIndicators).filter(
        RSIIndicators.code == code,
        RSIIndicators.date >= start_date,
        RSIIndicators.date <= end_date,
        RSIIndicators.market_type == market_type
    ).all()
    rsi_dict = list_to_date_dict(rsi_items)
    
    # 5. BOLL
    boll_items = db.query(BOLLIndicators).filter(
        BOLLIndicators.code == code,
        BOLLIndicators.date >= start_date,
        BOLLIndicators.date <= end_date,
        BOLLIndicators.market_type == market_type
    ).all()
    boll_dict = list_to_date_dict(boll_items)
    
    # 6. MAVOL
    mavol_items = db.query(MAVOLIndicators).filter(
        MAVOLIndicators.code == code,
        MAVOLIndicators.date >= start_date,
        MAVOLIndicators.date <= end_date,
        MAVOLIndicators.market_type == market_type
    ).all()
    mavol_dict = list_to_date_dict(mavol_items)
    
    # 7. PVFRS
    pvfrs_items = db.query(MeanFrequencyResonanceIndicators).filter(
        MeanFrequencyResonanceIndicators.code == code,
        MeanFrequencyResonanceIndicators.date >= start_date,
        MeanFrequencyResonanceIndicators.date <= end_date,
        MeanFrequencyResonanceIndicators.market_type == market_type
    ).all()
    pvfrs_dict = list_to_date_dict(pvfrs_items)
    
    # 收集所有涉及的日期
    all_dates = set()
    all_dates.update(ma_dict.keys())
    all_dates.update(macd_dict.keys())
    all_dates.update(kdj_dict.keys())
    all_dates.update(rsi_dict.keys())
    all_dates.update(boll_dict.keys())
    all_dates.update(mavol_dict.keys())
    all_dates.update(pvfrs_dict.keys())
    
    # 排序日期（降序，最近的在前）
    sorted_dates = sorted(list(all_dates), reverse=True)
    
    # 构建最终列表
    result_list = []
    for date in sorted_dates:
        result_list.append({
            "code": code,
            "date": date,
            "market_type": market_type,
            "ma": ma_dict.get(date),
            "macd": macd_dict.get(date),
            "kdj": kdj_dict.get(date),
            "rsi": rsi_dict.get(date),
            "boll": boll_dict.get(date),
            "mavol": mavol_dict.get(date),
            "pvfrs": pvfrs_dict.get(date)
        })
        
    return {
        "success": True,
        "data": result_list,
        "total": len(result_list)
    }

