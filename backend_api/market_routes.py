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
    """获取当日最新板块行情，按涨幅降序排序"""
    try:
        print("📈 开始获取板块行情数据...")
        df = ak.stock_board_industry_name_em()
        df = df.sort_values(by='涨跌幅', ascending=False)
        print("实际字段：", df.columns.tolist())
        expected_fields = ['板块名称', '最新价', '涨跌额', '涨跌幅', '总市值', '换手率', '成交额', '领涨股', '领涨股涨跌幅']
        actual_fields = [f for f in expected_fields if f in df.columns]
        # 统一将 NaN 转为 None
        df = df.replace({np.nan: None})
        # 字段名映射为英文
        field_map = {
            '板块名称': 'name',
            '最新价': 'price',
            '涨跌额': 'change_amount',
            '涨跌幅': 'change_percent',
            '总市值': 'market_cap',
            '换手率': 'turnover_rate',
            '成交额': 'turnover',
            '领涨股': 'leading_stock',
            '领涨股涨跌幅': 'leading_stock_change'
        }
        data = []
        for _, row in df[actual_fields].iterrows():
            item = {}
            for k in actual_fields:
                item[field_map.get(k, k)] = row[k]
            data.append(item)
        print(f"✅ 成功获取 {len(data)} 条板块数据")
        return JSONResponse({'success': True, 'data': data})
    except Exception as e:
        print(f"❌ 获取板块行情数据失败: {str(e)}")
        print("详细错误信息:")
        tb = traceback.format_exc()
        print(tb)
        return JSONResponse({
            'success': False,
            'message': '获取板块行情数据失败',
            'error': str(e),
            'traceback': tb
        }, status_code=500) 