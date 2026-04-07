"""
采集日历管理路由
"""

import logging
from datetime import datetime, date
from typing import List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import text, UniqueConstraint

from backend_api.database import get_db
from backend_api.models import TradingCalendar, TradingCalendarCreate, TradingCalendarInDB
from backend_api.auth import get_current_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/trading-calendar", tags=["admin-trading-calendar"])

@router.get("/list", response_model=List[TradingCalendarInDB])
async def list_calendar(
    market: Optional[str] = Query(None, description="市场筛选: CN 或 HK"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    db: Session = Depends(get_db),
    admin: Any = Depends(get_current_admin)
):
    """获取采集日历列表"""
    query = db.query(TradingCalendar)
    if market:
        query = query.filter(TradingCalendar.market == market)
    if start_date:
        query = query.filter(TradingCalendar.holiday_date >= start_date)
    if end_date:
        query = query.filter(TradingCalendar.holiday_date <= end_date)
    
    return query.order_by(TradingCalendar.holiday_date.desc()).all()

@router.post("/add", response_model=TradingCalendarInDB)
async def add_holiday(
    holiday: TradingCalendarCreate,
    db: Session = Depends(get_db),
    admin: Any = Depends(get_current_admin)
):
    """添加节假日"""
    # 检查是否已存在
    existing = db.query(TradingCalendar).filter(
        TradingCalendar.market == holiday.market,
        TradingCalendar.holiday_date == holiday.holiday_date
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{holiday.market} 市场在 {holiday.holiday_date} 已存在节假日设置"
        )
    
    db_holiday = TradingCalendar(**holiday.dict())
    db.add(db_holiday)
    db.commit()
    db.refresh(db_holiday)
    return db_holiday
@router.post("/batch_add")
async def batch_add_holidays(
    holidays: List[TradingCalendarCreate],
    db: Session = Depends(get_db),
    admin: Any = Depends(get_current_admin)
):
    """批量添加节假日"""
    success_count = 0
    skip_count = 0
    
    for holiday in holidays:
        # 检查是否已存在
        existing = db.query(TradingCalendar).filter(
            TradingCalendar.market == holiday.market,
            TradingCalendar.holiday_date == holiday.holiday_date
        ).first()
        
        if existing:
            skip_count += 1
            continue
            
        db_holiday = TradingCalendar(
            market=holiday.market,
            holiday_date=holiday.holiday_date,
            description=holiday.description
        )
        db.add(db_holiday)
        success_count += 1
        
    db.commit()
    return {"success_count": success_count, "skip_count": skip_count}

@router.delete("/delete/{holiday_id}")
async def delete_holiday(
    holiday_id: int,
    db: Session = Depends(get_db),
    admin: Any = Depends(get_current_admin)
):
    """删除节假日"""
    db_holiday = db.query(TradingCalendar).filter(TradingCalendar.id == holiday_id).first()
    if not db_holiday:
        raise HTTPException(status_code=404, detail="未找到该节假日设置")
    
    db.delete(db_holiday)
    db.commit()
    return {"success": True, "message": "删除成功"}

@router.put("/update/{holiday_id}", response_model=TradingCalendarInDB)
async def update_holiday(
    holiday_id: int,
    holiday_update: TradingCalendarCreate,
    db: Session = Depends(get_db),
    admin: Any = Depends(get_current_admin)
):
    """更新节假日"""
    db_holiday = db.query(TradingCalendar).filter(TradingCalendar.id == holiday_id).first()
    if not db_holiday:
        raise HTTPException(status_code=404, detail="未找到该节假日设置")
    
    # 检查更新后的日期冲突
    existing = db.query(TradingCalendar).filter(
        TradingCalendar.market == holiday_update.market,
        TradingCalendar.holiday_date == holiday_update.holiday_date,
        TradingCalendar.id != holiday_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{holiday_update.market} 市场在 {holiday_update.holiday_date} 已存在节假日设置"
        )
    
    db_holiday.market = holiday_update.market
    db_holiday.holiday_date = holiday_update.holiday_date
    db_holiday.description = holiday_update.description
    db_holiday.updated_at = datetime.now()
    
    db.commit()
    db.refresh(db_holiday)
    return db_holiday
