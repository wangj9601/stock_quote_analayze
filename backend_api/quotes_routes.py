from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, func, or_
from typing import List, Optional
from datetime import datetime
import sys
import os
# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, current_dir)
from database import get_db
from models import (
    StockRealtimeQuote, IndexRealtimeQuotes, IndustryBoardRealtimeQuotes,
    HistoricalQuotes, StockRealtimeQuoteHK, HKIndexRealtimeQuotes,
    HistoricalQuotesHK
)
from backend_core.data_collectors.akshare.hk_historical_import_from_file import complete_hk_change_fields

router = APIRouter(prefix="/api/quotes", tags=["quotes"])


def _historical_quotes_hk_to_api(row: HistoricalQuotesHK) -> dict:
    """序列化港股历史行情 ORM，避免 __dict__ 混入 _sa_instance_state；缺失时补算涨跌额/涨跌幅。"""
    keys = (
        'code', 'ts_code', 'name', 'english_name', 'date', 'open', 'high', 'low', 'close',
        'pre_close', 'volume', 'amount', 'change_amount', 'amplitude', 'turnover_rate',
        'change_percent', 'five_day_change_percent', 'ten_day_change_percent',
        'thirty_day_change_percent', 'sixty_day_change_percent',
        'collected_source', 'collected_date',
    )
    out = {}
    for k in keys:
        v = getattr(row, k, None)
        if v is not None and hasattr(v, 'isoformat'):
            v = v.isoformat()
        out[k] = v
    pc, cl, ca, cp = complete_hk_change_fields(
        out.get('pre_close'), out.get('close'), out.get('change_amount'), out.get('change_percent')
    )
    out['pre_close'] = pc
    out['close'] = cl
    out['change_amount'] = ca
    out['change_percent'] = cp
    # 与 A 股 historical_quotes.change（涨跌额）字段对齐，便于导出/联表
    out['change'] = ca
    return out


# 通用分页响应模型
def paginate_query(query, page, page_size):
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size
    }

# 1. A股股票实时行情
@router.get("/stocks")
def get_stock_quotes(
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    market: Optional[str] = None,
    sort_by: Optional[str] = "change_percent",
    db: Session = Depends(get_db)
):
    # 获取最新交易日期
    latest_date_row = db.query(StockRealtimeQuote.trade_date).order_by(desc(StockRealtimeQuote.trade_date)).first()
    if not latest_date_row:
        return {"success": True, "data": [], "total": 0, "page": page, "page_size": page_size}
    
    latest_date = latest_date_row[0]
    
    # 只查询最新交易日期的数据
    query = db.query(StockRealtimeQuote).filter(StockRealtimeQuote.trade_date == latest_date)
    
    # 筛选
    if keyword:
        query = query.filter(or_(
            StockRealtimeQuote.code.like(f"%{keyword}%"),
            StockRealtimeQuote.name.like(f"%{keyword}%")
        ))
    
    # 排序
    if sort_by:
        if sort_by.startswith("-"):
            query = query.order_by(asc(getattr(StockRealtimeQuote, sort_by[1:])))
        else:
            query = query.order_by(desc(getattr(StockRealtimeQuote, sort_by)))
            
    # 分页
    result = paginate_query(query, page, page_size)
    
    return {
        "success": True,
        "data": [item.__dict__ for item in result["items"]],
        "total": result["total"],
        "page": page,
        "page_size": page_size
    }

# 2. A股指数实时行情
@router.get("/indices")
def get_index_quotes(
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    sort_by: Optional[str] = "pct_chg",
    db: Session = Depends(get_db)
):
    query = db.query(IndexRealtimeQuotes)
    
    if keyword:
        query = query.filter(or_(
            IndexRealtimeQuotes.code.like(f"%{keyword}%"),
            IndexRealtimeQuotes.name.like(f"%{keyword}%")
        ))
        
    if sort_by:
        if sort_by.startswith("-"):
            query = query.order_by(asc(getattr(IndexRealtimeQuotes, sort_by[1:])))
        else:
            query = query.order_by(desc(getattr(IndexRealtimeQuotes, sort_by)))
            
    result = paginate_query(query, page, page_size)
    
    return {
        "success": True,
        "data": [item.__dict__ for item in result["items"]],
        "total": result["total"],
        "page": page,
        "page_size": page_size
    }

# 3. A股历史行情
@router.get("/history")
def get_historical_quotes(
    page: int = 1,
    size: int = 20,
    code: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(HistoricalQuotes)
    
    if code:
        query = query.filter(HistoricalQuotes.code == code)
        
    if keyword:
        # 如果提供了关键字但没有提供代码，尝试搜索代码或名称
        # 注意：HistoricalQuotes表可能没有name字段，需要关联查询或假设有
        # 这里假设HistoricalQuotes有name字段，如果没有需要调整
        query = query.filter(or_(
            HistoricalQuotes.code.like(f"%{keyword}%"),
            HistoricalQuotes.name.like(f"%{keyword}%")
        ))
        
    if start_date:
        query = query.filter(HistoricalQuotes.date >= start_date)
    if end_date:
        query = query.filter(HistoricalQuotes.date <= end_date)
        
    # 默认按日期降序
    query = query.order_by(desc(HistoricalQuotes.date))
    
    result = paginate_query(query, page, size)
    
    return {
        "items": [item.__dict__ for item in result["items"]],
        "total": result["total"],
        "page": page,
        "size": size
    }

# 4. A股行业板块实时行情
@router.get("/industries")
def get_industry_quotes(
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    sort_by: Optional[str] = "change_percent",
    db: Session = Depends(get_db)
):
    query = db.query(IndustryBoardRealtimeQuotes)
    
    if keyword:
        query = query.filter(IndustryBoardRealtimeQuotes.board_name.like(f"%{keyword}%"))
        
    if sort_by:
        if sort_by.startswith("-"):
            query = query.order_by(asc(getattr(IndustryBoardRealtimeQuotes, sort_by[1:])))
        else:
            query = query.order_by(desc(getattr(IndustryBoardRealtimeQuotes, sort_by)))
            
    result = paginate_query(query, page, page_size)
    
    return {
        "success": True,
        "data": [item.__dict__ for item in result["items"]],
        "total": result["total"],
        "page": page,
        "page_size": page_size
    }

# 5. 港股实时行情
@router.get("/hk-stocks")
def get_hk_stock_quotes(
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db)
):
    # 获取最新日期
    latest_date_row = db.query(StockRealtimeQuoteHK.trade_date).order_by(desc(StockRealtimeQuoteHK.trade_date)).first()
    if not latest_date_row:
        return {"success": True, "data": [], "total": 0, "page": page, "page_size": page_size}
    
    latest_date = latest_date_row[0]
    
    query = db.query(StockRealtimeQuoteHK).filter(StockRealtimeQuoteHK.trade_date == latest_date)
    
    if keyword:
        query = query.filter(or_(
            StockRealtimeQuoteHK.code.like(f"%{keyword}%"),
            StockRealtimeQuoteHK.name.like(f"%{keyword}%")
        ))
        
    # 默认按涨跌幅排序
    query = query.order_by(desc(StockRealtimeQuoteHK.change_percent))
    
    result = paginate_query(query, page, page_size)
    
    return {
        "success": True,
        "data": [item.__dict__ for item in result["items"]],
        "total": result["total"],
        "page": page,
        "page_size": page_size
    }

# 6. 港股历史行情
@router.get("/hk-history")
def get_hk_historical_quotes(
    page: int = 1,
    size: int = 20,
    code: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(HistoricalQuotesHK)
    
    if code:
        query = query.filter(HistoricalQuotesHK.code == code)
        
    if keyword:
        query = query.filter(or_(
            HistoricalQuotesHK.code.like(f"%{keyword}%"),
            HistoricalQuotesHK.name.like(f"%{keyword}%")
        ))
        
    if start_date:
        query = query.filter(HistoricalQuotesHK.date >= start_date)
    if end_date:
        query = query.filter(HistoricalQuotesHK.date <= end_date)
        
    query = query.order_by(desc(HistoricalQuotesHK.date))
    
    result = paginate_query(query, page, size)
    
    return {
        "items": [_historical_quotes_hk_to_api(item) for item in result["items"]],
        "total": result["total"],
        "page": page,
        "size": size
    }

# 7. 港股指数实时行情
@router.get("/hk-indices")
def get_hk_index_quotes(
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db)
):
    # 获取最新日期
    latest_date_row = db.query(HKIndexRealtimeQuotes.trade_date).order_by(desc(HKIndexRealtimeQuotes.trade_date)).first()
    if not latest_date_row:
        return {"success": True, "data": [], "total": 0, "page": page, "page_size": page_size}
    
    latest_date = latest_date_row[0]
    
    query = db.query(HKIndexRealtimeQuotes).filter(HKIndexRealtimeQuotes.trade_date == latest_date)
    
    if keyword:
        query = query.filter(or_(
            HKIndexRealtimeQuotes.code.like(f"%{keyword}%"),
            HKIndexRealtimeQuotes.name.like(f"%{keyword}%")
        ))
        
    # 默认按涨跌幅排序
    query = query.order_by(desc(HKIndexRealtimeQuotes.pct_chg))
    
    result = paginate_query(query, page, page_size)
    
    return {
        "success": True,
        "data": [item.__dict__ for item in result["items"]],
        "total": result["total"],
        "page": page,
        "page_size": page_size
    }

# 8. 港股指数历史行情
@router.get("/hk-index-history")
def get_hk_index_historical_quotes(
    page: int = 1,
    size: int = 20,
    code: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(HKIndexHistoricalQuotes)
    
    if code:
        query = query.filter(HKIndexHistoricalQuotes.code == code)
        
    if keyword:
        query = query.filter(or_(
            HKIndexHistoricalQuotes.code.like(f"%{keyword}%"),
            HKIndexHistoricalQuotes.name.like(f"%{keyword}%")
        ))
        
    if start_date:
        query = query.filter(HKIndexHistoricalQuotes.date >= start_date)
    if end_date:
        query = query.filter(HKIndexHistoricalQuotes.date <= end_date)
        
    query = query.order_by(desc(HKIndexHistoricalQuotes.date))
    
    result = paginate_query(query, page, size)
    
    return {
        "items": [item.__dict__ for item in result["items"]],
        "total": result["total"],
        "page": page,
        "size": size
    }
