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
1. 查询个股资金流向历史数据
"""
@router.get("/today")
async def get_stock_fund_flow_today(code: str = Query(None, description="股票代码")):
    """
    获取个股资金流向历史数据
    """
    print(f"[get_stock_fund_flow_today] 输入参数: code={code}")
    if not code:
        print("[get_stock_fund_flow_today] 缺少参数code")
        return JSONResponse({"success": False, "message": "缺少股票代码参数code"}, status_code=400)
    try:
        # 尝试方法1：使用 stock_individual_fund_flow
        try:
            print(f"[get_stock_fund_flow_today] 尝试方法-上交所: 调用ak.stock_individual_fund_flow, stock={code}")
            df = ak.stock_individual_fund_flow(stock=code,market='sh')
            if df is not None and not df.empty:
                print(f"[get_stock_fund_flow_today] 方法1成功获取数据，DataFrame形状: {df.shape}")
            else:
                print("[get_stock_fund_flow_today] 方法1返回空数据，尝试方法2")
                df = None
        except Exception as e1:
            print(f"[get_stock_fund_flow_today] 方法1异常: {str(e1)}")
            df = None

        if df is None or df.empty:
            try:
                print(f"[get_stock_fund_flow_today] 尝试方法-深交所: 调用ak.stock_individual_fund_flow, stock={code}")
                df = ak.stock_individual_fund_flow(stock=code,market='sz')
                if df is not None and not df.empty:
                    print(f"[get_stock_fund_flow_today] 方法2成功获取数据，DataFrame形状: {df.shape}")
                else:
                    print("[get_stock_fund_flow_today] 方法2返回空数据")
                    df = None
            except Exception as e2:
                print(f"[get_stock_fund_flow_today] 方法2异常: {str(e2)}")
                df = None

        if df is None or df.empty:
            try:
                print(f"[get_stock_fund_flow_today] 尝试方法-北交所: 调用ak.stock_individual_fund_flow, stock={code}")
                df = ak.stock_individual_fund_flow(stock=code,market='bj')
                if df is not None and not df.empty:
                    print(f"[get_stock_fund_flow_today] 方法3成功获取数据，DataFrame形状: {df.shape}")
                else:
                    print("[get_stock_fund_flow_today] 方法3返回空数据")
                    df = None
            except Exception as e3:
                print(f"[get_stock_fund_flow_today] 方法3异常: {str(e3)}")
                df = None

        if df is None or df.empty:
            print(f"[get_stock_fund_flow_today] 未找到股票代码: {code} 的资金流向里历史数据")
            return JSONResponse({"success": False, "message": f"未找到股票代码: {code} 的资金流向历史数据"}, status_code=404)
       
        # 假设有一个变量 rows 是多天的查询结果（如DataFrame或列表），遍历每一天
        rows = df.to_dict(orient='records')
        result = []
        for row in rows:  # rows 应为多天的记录
            result.append({
                "date": row.get("date") or row.get("日期"),
                "code": code,  # 直接使用入口参数code
                "main_net_inflow": float(row.get("主力净流入-净额")) if row.get("主力净流入-净额") is not None else None,
                #"main_net_inflow_pct": float(row.get("主力净流入-净占比")) if row.get("主力净流入-净占比") is not None else None,
                #"retail_net_inflow": float(row.get("散户净流入-净额")) if row.get("散户净流入-净额") is not None else None,
                #"retail_net_inflow_pct": float(row.get("散户净流入-净占比")) if row.get("散户净流入-净占比") is not None else None,
                #"super_large_net_inflow": float(row.get("超大单净流入-净额")) if row.get("超大单净流入-净额") is not None else None,
                #"super_large_net_inflow_pct": float(row.get("超大单净流入-净占比")) if row.get("今日超大单净流入-净占比") is not None else None,
                "large_net_inflow": float(row.get("大单净流入-净额")) if row.get("大单净流入-净额") is not None else None
                #"large_net_inflow_pct": float(row.get("大单净流入-净占比")) if row.get("大单净流入-净占比") is not None else None,
                #"medium_net_inflow": float(row.get("中单净流入-净额")) if row.get("中单净流入-净额") is not None else None,
                #"medium_net_inflow_pct": float(row.get("中单净流入-净占比")) if row.get("中单净流入-净占比") is not None else None,
                #"small_net_inflow": float(row.get("小单净流入-净额")) if row.get("小单净流入-净额") is not None else None,
                #"small_net_inflow_pct": float(row.get("小单净流入-净占比")) if row.get("小单净流入-净占比") is not None else None
            })
        return {"success": True, "data": result}
    except Exception as e:
        print(f"[get_stock_fund_flow_today] 查询个股资金流向历史数据异常: {e}")
        import traceback
        print(traceback.format_exc())
        return JSONResponse({"success": False, "message": f"查询个股资金流向历史数据异常: {e}"}, status_code=500)

@router.get("/fund_flow")
async def get_stock_fund_flow(code: str = Query(None, description="股票代码")):
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