"""
行情数据管理API模块
提供行情数据管理相关的接口
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime, timedelta
import logging
import json
import os
import akshare as ak
import pandas as pd
from pathlib import Path
from pydantic import BaseModel

from ..models import (
    QuoteData, QuoteDataCreate, QuoteDataInDB,
    User, QuoteSyncTask, QuoteSyncTaskCreate
)
from ..database import get_db
from ..auth import get_current_user, get_current_admin_user

# 定义分页响应模型
class PaginatedResponse(BaseModel):
    success: bool
    data: List[QuoteDataInDB]
    total: int
    page: int
    page_size: int

router = APIRouter(prefix="/api/admin/quotes", tags=["admin_quotes"])

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('quotes.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 行情数据相关路由
@router.get("/realtime", response_model=PaginatedResponse)
async def get_realtime_quotes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """获取实时行情数据"""
    query = db.query(QuoteData)
    
    if keyword:
        query = query.filter(
            (QuoteData.stock_code.contains(keyword)) |
            (QuoteData.stock_name.contains(keyword))
        )
    
    total = query.count()
    quotes = query.order_by(desc(QuoteData.updated_at)) \
        .offset((page - 1) * page_size) \
        .limit(page_size) \
        .all()
    
    return {
        "success": True,
        "data": quotes,
        "total": total,
        "page": page,
        "page_size": page_size
    }

@router.get("/historical", response_model=PaginatedResponse)
async def get_historical_quotes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    date_range: str = Query("today", regex="^(today|week|month|custom)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """获取历史行情数据"""
    query = db.query(QuoteData)
    
    if keyword:
        query = query.filter(
            (QuoteData.stock_code.contains(keyword)) |
            (QuoteData.stock_name.contains(keyword))
        )
    
    # 处理日期范围
    now = datetime.now()
    if date_range == "today":
        query = query.filter(QuoteData.trade_date == now.date())
    elif date_range == "week":
        week_start = now - timedelta(days=now.weekday())
        query = query.filter(QuoteData.trade_date >= week_start.date())
    elif date_range == "month":
        month_start = now.replace(day=1)
        query = query.filter(QuoteData.trade_date >= month_start.date())
    elif date_range == "custom":
        if not start_date or not end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="自定义日期范围需要提供开始和结束日期"
            )
        query = query.filter(
            QuoteData.trade_date >= start_date.date(),
            QuoteData.trade_date <= end_date.date()
        )
    
    total = query.count()
    quotes = query.order_by(desc(QuoteData.trade_date)) \
        .offset((page - 1) * page_size) \
        .limit(page_size) \
        .all()
    
    return {
        "success": True,
        "data": quotes,
        "total": total,
        "page": page,
        "page_size": page_size
    }

@router.get("/{quote_type}/export")
async def export_quote_data(
    quote_type: str,
    keyword: Optional[str] = None,
    date_range: str = Query("today", regex="^(today|week|month|custom)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """导出行情数据"""
    if quote_type not in ["realtime", "historical"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的数据类型"
        )
    
    query = db.query(QuoteData)
    
    if keyword:
        query = query.filter(
            (QuoteData.stock_code.contains(keyword)) |
            (QuoteData.stock_name.contains(keyword))
        )
    
    # 处理日期范围
    now = datetime.now()
    if date_range == "today":
        query = query.filter(QuoteData.trade_date == now.date())
    elif date_range == "week":
        week_start = now - timedelta(days=now.weekday())
        query = query.filter(QuoteData.trade_date >= week_start.date())
    elif date_range == "month":
        month_start = now.replace(day=1)
        query = query.filter(QuoteData.trade_date >= month_start.date())
    elif date_range == "custom":
        if not start_date or not end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="自定义日期范围需要提供开始和结束日期"
            )
        query = query.filter(
            QuoteData.trade_date >= start_date.date(),
            QuoteData.trade_date <= end_date.date()
        )
    
    quotes = query.order_by(desc(QuoteData.trade_date)).all()
    
    # 转换为DataFrame
    df = pd.DataFrame([{
        "股票代码": q.stock_code,
        "股票名称": q.stock_name,
        "最新价": q.last_price,
        "涨跌幅": q.change_percent,
        "成交量": q.volume,
        "成交额": q.amount,
        "最高价": q.high,
        "最低价": q.low,
        "开盘价": q.open,
        "昨收价": q.pre_close,
        "更新时间": q.updated_at.strftime("%Y-%m-%d %H:%M:%S")
    } for q in quotes])
    
    # 创建Excel文件
    output_dir = Path("exports")
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"quotes_{quote_type}_{timestamp}.xlsx"
    filepath = output_dir / filename
    
    # 保存为Excel
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="行情数据")
        
        # 调整列宽
        worksheet = writer.sheets["行情数据"]
        for idx, col in enumerate(df.columns):
            max_length = max(
                df[col].astype(str).apply(len).max(),
                len(col)
            )
            worksheet.column_dimensions[chr(65 + idx)].width = max_length + 2
    
    return {
        "success": True,
        "message": "数据导出成功",
        "data": {
            "filename": filename,
            "download_url": f"/exports/{filename}"
        }
    } 