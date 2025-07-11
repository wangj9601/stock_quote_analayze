# backend_api/market_routes.py

from fastapi import APIRouter, Depends
import akshare as ak
from datetime import datetime
from fastapi.responses import JSONResponse
import random
import traceback
import pandas as pd
import numpy as np
import sqlite3
from sqlalchemy.orm import Session
from backend_api.database import get_db
from backend_api.models import IndexRealtimeQuotes, IndustryBoardRealtimeQuotes



router = APIRouter(prefix="/api/market", tags=["market"])

def safe_float(value):
    """安全地将值转换为浮点数，处理 NaN 和无效值"""
    try:
        if pd.isna(value) or value in [None, '', '-']:
            return None
        return float(value)
    except (ValueError, TypeError):
        return None

def row_to_dict(row):
    d = {}
    for c in row.__table__.columns:
        v = getattr(row, c.name)
        if isinstance(v, datetime):
            d[c.name] = v.strftime('%Y-%m-%d %H:%M:%S')
        else:
            d[c.name] = v
    return d

# 获取市场指数数据(修改为从数据库 index_realtime_quotes 表中获取)
@router.get("/indices")
def get_market_indices(db: Session = Depends(get_db)):
    """获取市场指数数据(从数据库 index_realtime_quotes 表中获取)"""
    def map_index_fields(row):
        return {
            "code": row.code,
            "name": row.name,
            "current": row.price,
            "change": row.change,
            "change_percent": row.pct_chg,
            "volume": row.volume,
            "timestamp": row.update_time,
        }
    try:
        index_codes = {
            '上证指数': '000001',
            '深圳成指': '399001',
            '创业板指': '399006',
            '沪深300': '000300',
        }
        indices_data = []
        for name, code in index_codes.items():
            row = db.query(IndexRealtimeQuotes).filter(IndexRealtimeQuotes.code == code).order_by(IndexRealtimeQuotes.update_time.desc()).first()
            if row is None:
                continue
            indices_data.append(map_index_fields(row))
        return JSONResponse({'success': True, 'data': indices_data})
    except Exception as e:
        return JSONResponse({'success': False, 'message': str(e)})

# 获取当日最新板块行情，按涨幅降序排序
@router.get("/industry_board")
def get_industry_board(db: Session = Depends(get_db)):
    """获取当日最新板块行情，按涨幅降序排序（从industry_board_realtime_quotes表读取）"""
    def map_board_fields(row):
        return {
            "board_code": row.board_code,
            "board_name": row.board_name,
            "latest_price": row.latest_price,
            "change_amount": row.change_amount,
            "change_percent": row.change_percent,
            "total_market_value": row.total_market_value,
            "volume": row.volume,
            "amount": row.amount,
            "turnover_rate": row.turnover_rate,
            "leading_stock_name": row.leading_stock_name,
            "leading_stock_code": row.leading_stock_code,
            "leading_stock_change_percent": row.leading_stock_change_percent,
            "update_time": row.update_time,
        }
    try:
        rows = db.query(IndustryBoardRealtimeQuotes).order_by(IndustryBoardRealtimeQuotes.change_percent.desc(), IndustryBoardRealtimeQuotes.update_time.desc()).all()
        data = [row_to_dict(row) for row in rows]
        return JSONResponse({'success': True, 'data': data})
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        return JSONResponse({
            'success': False,
            'message': '获取板块行情数据失败',
            'error': str(e),
            'traceback': tb
        }, status_code=500) 