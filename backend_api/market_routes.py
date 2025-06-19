# backend_api/market_routes.py

from fastapi import APIRouter
import akshare as ak
from datetime import datetime
from fastapi.responses import JSONResponse
import random
import traceback
import pandas as pd
import numpy as np
import sqlite3
from backend_core.config.config import DATA_COLLECTORS
from backend_api.config import DB_PATH



router = APIRouter(prefix="/api/market", tags=["market"])

def safe_float(value):
    """安全地将值转换为浮点数，处理 NaN 和无效值"""
    try:
        if pd.isna(value) or value in [None, '', '-']:
            return None
        return float(value)
    except (ValueError, TypeError):
        return None

# 获取市场指数数据(修改为从数据库 index_realtime_quotes 表中获取)
@router.get("/indices")
def get_market_indices():
    """获取市场指数数据(修改为从数据库 index_realtime_quotes 表中获取)"""
    db_file = DB_PATH
    
    def map_index_fields(row):
        return {
            "code": row.get("code"),
            "name": row.get("name"),
            "current": row.get("price"),
            "change": row.get("change"),
            "change_percent": row.get("pct_chg"),
            "volume": row.get("volume"),
            "timestamp": row.get("update_time"),
            # 其他字段可按需补充
        }
    try:
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 指数代码映射
        index_codes = {
            '上证指数': '000001',
            '深圳成指': '399001',
            '创业板指': '399006',
            '沪深300': '000300',
        }
        indices_data = []
        for name, code in index_codes.items():
            cursor.execute(
                """
                SELECT * FROM index_realtime_quotes
                WHERE code = ?
                ORDER BY update_time DESC
                LIMIT 1
                """, (code,)
            )
            row = cursor.fetchone()
            if row is None:
                continue
            # 格式化数据，确保数值类型正确
            formatted_row = {}
            for key in row.keys():
                value = row[key]
                if key in ['price', 'change', 'pct_chg', 'high', 'low', 'open', 'pre_close', 'volume', 'amount', 'amplitude', 'turnover', 'pe', 'volume_ratio']:
                    formatted_row[key] = safe_float(value)
                elif key == 'update_time':
                    formatted_row[key] = value
                else:
                    formatted_row[key] = value
            indices_data.append(map_index_fields(formatted_row))
        conn.close()
        return JSONResponse({'success': True, 'data': indices_data})    
    except Exception as e:
        return JSONResponse({'success': False, 'message': str(e)})

# 获取当日最新板块行情，按涨幅降序排序
@router.get("/industry_board")
def get_industry_board():
    """获取当日最新板块行情，按涨幅降序排序（从industry_board_realtime_quotes表读取）"""
    db_file = DB_PATH
    def map_board_fields(row):
        return {
            "board_code": row.get("board_code"),
            "board_name": row.get("board_name"),
            "latest_price": row.get("latest_price"),
            "change_amount": row.get("change_amount"),
            "change_percent": row.get("change_percent"),
            "total_market_value": row.get("total_market_value"),
            "volume": row.get("volume"),
            "amount": row.get("amount"),
            "turnover_rate": row.get("turnover_rate"),
            "leading_stock_name": row.get("leading_stock_name"),
            "leading_stock_code": row.get("leading_stock_code"),
            "leading_stock_change_percent": row.get("leading_stock_change_percent"),
            "update_time": row.get("update_time"),
        }
    try:
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM industry_board_realtime_quotes
            ORDER BY change_percent DESC, update_time DESC
            """
        )
        rows = cursor.fetchall()
        data = []
        for row in rows:
            formatted_row = {}
            for key in row.keys():
                value = row[key]
                # 需要转为float的字段
                if key in [
                    'latest_price', 'change_amount', 'change_percent', 'total_market_value',
                    'volume', 'amount', 'turnover_rate', 'leading_stock_change_percent']:
                    formatted_row[key] = safe_float(value)
                else:
                    formatted_row[key] = value
            data.append(map_board_fields(formatted_row))
        conn.close()
        return JSONResponse({'success': True, 'data': data})
    except Exception as e:
        tb = traceback.format_exc()
        return JSONResponse({
            'success': False,
            'message': '获取板块行情数据失败',
            'error': str(e),
            'traceback': tb
        }, status_code=500) 