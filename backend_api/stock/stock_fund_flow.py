from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
import akshare as ak
from ..database import get_db
from sqlalchemy.orm import Session
from fastapi import Depends
import traceback
import numpy as np
import time
from threading import Lock
import sqlite3
from datetime import datetime  # 直接导入 datetime 类
from backend_api.config import DB_PATH



router = APIRouter(prefix="/api/stock_fund_flow", tags=["stock_fund_flow"])

def safe_float(value):
    try:
        if value in [None, '', '-']:
            return None
        return float(value)
    except (ValueError, TypeError):
        return None
   

"""
个股资金流向相关API
提供查询个股资金流向数据的功能，包括:
1. 查询个股资金流向
2. 查询个股资金流向历史数据
3. 查询个股资金流向实时数据
"""
@router.get("/today")
async def get_stock_fund_flow_today(code: str = Query(None, description="股票代码")):
    """
    获取个股当日资金流向数据
    """
    print(f"[get_stock_fund_flow_today] 输入参数: code={code}")
    if not code:
        print("[get_stock_fund_flow_today] 缺少参数code")
        return JSONResponse({"success": False, "message": "缺少股票代码参数code"}, status_code=400)
    try:
        # 尝试方法1：使用 stock_individual_fund_flow
        try:
            print(f"[get_stock_fund_flow_today] 尝试方法1: 调用ak.stock_individual_fund_flow, stock={code}")
            df = ak.stock_individual_fund_flow(stock=code)
            if df is not None and not df.empty:
                print(f"[get_stock_fund_flow_today] 方法1成功获取数据，DataFrame形状: {df.shape}")
            else:
                print("[get_stock_fund_flow_today] 方法1返回空数据，尝试方法2")
                df = None
        except Exception as e1:
            print(f"[get_stock_fund_flow_today] 方法1异常: {str(e1)}")
            df = None

        # 如果方法1失败，尝试方法2：使用 stock_individual_fund_flow_rank
        if df is None or df.empty:
            try:
                print(f"[get_stock_fund_flow_today] 尝试方法2: 调用ak.stock_individual_fund_flow_rank")
                df = ak.stock_individual_fund_flow_rank(indicator='今日')
                if df is not None and not df.empty:
                    print(f"[get_stock_fund_flow_today] 方法2成功获取数据，DataFrame形状: {df.shape}")
                    # 过滤出指定股票代码的数据
                    df = df[df['代码'] == code]
                else:
                    print("[get_stock_fund_flow_today] 方法2返回空数据")
            except Exception as e2:
                print(f"[get_stock_fund_flow_today] 方法2异常: {str(e2)}")
                df = None

        if df is None or df.empty:
            print(f"[get_stock_fund_flow_today] 未找到股票代码: {code} 的资金流向数据")
            return JSONResponse({"success": False, "message": f"未找到股票代码: {code} 的资金流向数据"}, status_code=404)
            
        # 获取当前日期的资金流向数据
        today = datetime.now().strftime('%Y-%m-%d')
        today_row = None
        print(f"[get_stock_fund_flow_today] 开始查找日期为 {today} 的数据")
        print(f"[get_stock_fund_flow_today] DataFrame列名: {df.columns.tolist()}")
        for _, row in df.iterrows():
            date_val = row.get("日期")
            if date_val is None:
                print(f"[get_stock_fund_flow_today] 行数据缺少日期字段: {row.to_dict()}")
                continue
            if hasattr(date_val, 'strftime'):
                date_val = date_val.strftime('%Y-%m-%d')
            print(f"[get_stock_fund_flow_today] 检查日期: {date_val}")
            if date_val == today:
                today_row = row
                print(f"[get_stock_fund_flow_today] 找到今日数据: {row.to_dict()}")
                break
        
        # 如果没找到今天的数据，使用最新一天的数据
        if today_row is None:
            print(f"[get_stock_fund_flow_today] 未找到今日数据，使用最新一天数据")
            today_row = df.iloc[0]
            date_val = today_row.get("日期")
            if hasattr(date_val, 'strftime'):
                date_val = date_val.strftime('%Y-%m-%d')
            print(f"[get_stock_fund_flow_today] 使用最新数据，日期: {date_val}")
        else:
            date_val = today
            
        print(f"[get_stock_fund_flow_today] 开始构建返回数据，使用行数据: {today_row.to_dict()}")
        result = {
            "date": date_val,
            "code": code,
            "main_net_inflow": float(today_row.get("今日主力净流入-净额")) if today_row.get("今日主力净流入-净额") is not None else None,
            "main_net_inflow_pct": float(today_row.get("今日主力净流入-净占比")) if today_row.get("今日主力净流入-净占比") is not None else None,
            "retail_net_inflow": float(today_row.get("今日散户净流入-净额")) if today_row.get("今日散户净流入-净额") is not None else None,
            "retail_net_inflow_pct": float(today_row.get("今日散户净流入-净占比")) if today_row.get("今日散户净流入-净占比") is not None else None,
            "super_large_net_inflow": float(today_row.get("今日超大单净流入-净额")) if today_row.get("今日超大单净流入-净额") is not None else None,
            "super_large_net_inflow_pct": float(today_row.get("今日超大单净流入-净占比")) if today_row.get("今日超大单净流入-净占比") is not None else None,
            "large_net_inflow": float(today_row.get("今日大单净流入-净额")) if today_row.get("今日大单净流入-净额") is not None else None,
            "large_net_inflow_pct": float(today_row.get("今日大单净流入-净占比")) if today_row.get("今日大单净流入-净占比") is not None else None,
            "medium_net_inflow": float(today_row.get("今日中单净流入-净额")) if today_row.get("今日中单净流入-净额") is not None else None,
            "medium_net_inflow_pct": float(today_row.get("今日中单净流入-净占比")) if today_row.get("今日中单净流入-净占比") is not None else None,
            "small_net_inflow": float(today_row.get("今日小单净流入-净额")) if today_row.get("今日小单净流入-净额") is not None else None,
            "small_net_inflow_pct": float(today_row.get("今日小单净流入-净占比")) if today_row.get("今日小单净流入-净占比") is not None else None
        }
            
        print(f"[get_stock_fund_flow_today] 返回当日资金流向数据: {result}")
        return JSONResponse({"success": True, "data": result})
    except Exception as e:
        print(f"[get_stock_fund_flow_today] 查询个股当日资金流向数据异常: {e}")
        import traceback
        print(traceback.format_exc())
        return JSONResponse({"success": False, "message": f"查询个股当日资金流向数据异常: {e}"}, status_code=500)

@router.post("/fund_flow/{code}", summary="查询个股资金流向", description="根据股票代码查询个股资金流向数据，调用akshare.stock_individual_fund_flow_rank(indicator='今日')")
async def get_stock_fund_flow(code: str):
    print(f"[get_stock_fund_flow] 输入参数: code={code}")
    if not code:
        print("[get_stock_fund_flow] 缺少参数code")
        return JSONResponse({"success": False, "message": "缺少股票代码参数code"}, status_code=400)
    try:
        print(f"[get_stock_fund_flow] 调用ak.stock_individual_fund_flow_rank")
        df = ak.stock_individual_fund_flow_rank(indicator='今日')
        if df is None or df.empty:
            print(f"[get_stock_fund_flow] 未找到股票代码: {code} 的资金流向数据")
            return JSONResponse({"success": False, "message": f"未找到股票代码: {code} 的资金流向数据"}, status_code=404)
        df_filtered = df[df['代码'] == code]
        if df_filtered.empty:
            print(f"[get_stock_fund_flow] 未找到股票代码: {code} 的资金流向数据")
            return JSONResponse({"success": False, "message": f"未找到股票代码: {code} 的资金流向数据"}, status_code=404)
        fund_flow = df_filtered.to_dict(orient='records')[0]
        print(f"[get_stock_fund_flow] 输出数据: {fund_flow}")
        return JSONResponse({"success": True, "data": fund_flow})
    except Exception as e:
        print(f"[get_stock_fund_flow] 查询个股资金流向异常: {e}")
        import traceback
        print(traceback.format_exc())
        return JSONResponse({"success": False, "message": f"查询个股资金流向异常: {e}"}, status_code=500)