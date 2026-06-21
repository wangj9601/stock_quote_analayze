# backend_api/market_routes.py

from fastapi import APIRouter, Depends, Query
import akshare as ak
from datetime import datetime
from fastapi.responses import JSONResponse
import random
import traceback
import pandas as pd
import numpy as np
import sqlite3
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, text
from backend_api.database import get_db
from backend_api.models import (
    IndexRealtimeQuotes,
    IndustryBoardRealtimeQuotes,
    IndustryBoardConstituent,
    HKIndexRealtimeQuotes,
)
from backend_api.utils.industry_board_query import get_boards_by_stock_code



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


def _normalize_stock_code(code: str) -> str:
    s = str(code).strip()
    if s.isdigit() and len(s) < 6:
        return s.zfill(6)
    return s


def _latest_ashare_trade_date(db: Session) -> Optional[str]:
    row = db.execute(
        text(
            """
            SELECT MAX(trade_date) AS latest_date
            FROM stock_realtime_quote
            WHERE change_percent IS NOT NULL
            """
        )
    ).fetchone()
    return str(row[0]) if row and row[0] else None


def _fetch_board_constituents_with_quotes(
    db: Session, board_code: str, limit: int, sort_desc: bool = True
) -> List[dict]:
    """成分股 + 最新实时涨跌幅。"""
    cons = (
        db.query(IndustryBoardConstituent)
        .filter(IndustryBoardConstituent.board_code == board_code)
        .all()
    )
    if not cons:
        return []
    trade_date = _latest_ashare_trade_date(db)
    codes = [_normalize_stock_code(c.stock_code) for c in cons]
    quote_map = {}
    if trade_date and codes:
        placeholders = ",".join([f":c{i}" for i in range(len(codes))])
        params = {f"c{i}": codes[i] for i in range(len(codes))}
        params["trade_date"] = trade_date
        sql = text(
            f"""
            SELECT code, name, current_price, change_percent
            FROM stock_realtime_quote
            WHERE trade_date = :trade_date AND code IN ({placeholders})
            """
        )
        for row in db.execute(sql, params).fetchall():
            quote_map[str(row[0])] = {
                "name_rt": row[1],
                "current_price": row[2],
                "change_percent": float(row[3]) if row[3] is not None else None,
            }
    items = []
    for c in cons:
        code = _normalize_stock_code(c.stock_code)
        q = quote_map.get(code, {})
        items.append({
            "code": code,
            "name": c.stock_name or q.get("name_rt") or code,
            "change_percent": q.get("change_percent"),
            "current_price": q.get("current_price"),
        })
    items.sort(
        key=lambda x: x["change_percent"] if x["change_percent"] is not None else -1e9,
        reverse=sort_desc,
    )
    return items[:limit]

# 获取市场指数数据(修改为从数据库 index_realtime_quotes 表中获取)
@router.get("/indices")
def get_market_indices(db: Session = Depends(get_db)):
    """获取市场指数数据(从数据库 index_realtime_quotes 表中获取)"""
    def map_index_fields(row, target_code):
        """映射字段，并标准化code为前端期望的格式"""
        return {
            "code": target_code,  # 使用标准化的代码（不带sh/sz前缀）
            "name": row.name,
            "current": row.price,
            "change": row.change,
            "change_percent": row.pct_chg,
            "volume": row.volume,
            "timestamp": row.update_time,
        }
    try:
        # 定义目标指数：名称和对应的标准代码
        target_indices = {
            '000001': ['上证指数'],  # 可能有sh000001格式
            '399001': ['深证成指', '深圳成指'],  # 支持两种名称
            '399006': ['创业板指'],
            '000300': ['沪深300'],
        }
        indices_data = []
        for target_code, possible_names in target_indices.items():
            # 尝试按名称匹配（支持多种可能的名称）
            row = None
            for name in possible_names:
                row = db.query(IndexRealtimeQuotes).filter(
                    IndexRealtimeQuotes.name == name
                ).order_by(IndexRealtimeQuotes.update_time.desc()).first()
                if row:
                    break
            
            # 如果按名称没找到，尝试按代码匹配（支持sh/sz前缀格式）
            if row is None:
                # 尝试直接匹配代码
                row = db.query(IndexRealtimeQuotes).filter(
                    IndexRealtimeQuotes.code == target_code
                ).order_by(IndexRealtimeQuotes.update_time.desc()).first()
            
            # 如果还是没找到，尝试匹配带前缀的代码
            if row is None:
                # 根据代码判断市场前缀：000开头是sh，399开头是sz
                if target_code.startswith('000'):
                    prefix_code = f'sh{target_code}'
                elif target_code.startswith('399') or target_code.startswith('159'):
                    prefix_code = f'sz{target_code}'
                else:
                    prefix_code = target_code
                
                row = db.query(IndexRealtimeQuotes).filter(
                    IndexRealtimeQuotes.code == prefix_code
                ).order_by(IndexRealtimeQuotes.update_time.desc()).first()
            
            if row:
                indices_data.append(map_index_fields(row, target_code))
        
        return JSONResponse({'success': True, 'data': indices_data})
    except Exception as e:
        import traceback
        return JSONResponse({
            'success': False, 
            'message': str(e),
            'traceback': traceback.format_exc()
        })

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
            "up_count": row.up_count,
            "down_count": row.down_count,
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
            'success': False, 'message': '获取板块行情数据失败',
            'error': str(e),
            'traceback': tb
        }, status_code=500)

# 获取概念板块列表（基本信息表）
@router.get("/concept_board")
def get_concept_board(db: Session = Depends(get_db)):
    """获取概念板块列表（从 concept_board_basic_info 读取，按创建时间倒序）。"""
    try:
        rows = db.execute(
            text(
                """
                SELECT board_code, board_name, create_date
                FROM concept_board_basic_info
                WHERE board_code IS NOT NULL AND TRIM(board_code) <> ''
                ORDER BY create_date DESC NULLS LAST, board_code
                """
            )
        ).fetchall()
        data = [
            {
                "board_code": row[0],
                "board_name": row[1],
                "create_date": row[2].isoformat() if row[2] else None,
            }
            for row in rows
        ]
        return JSONResponse({"success": True, "data": data})
    except Exception as e:
        tb = traceback.format_exc()
        return JSONResponse(
            {
                "success": False,
                "message": "获取概念板块列表失败",
                "error": str(e),
                "traceback": tb,
            },
            status_code=500,
        )

# 获取港股指数数据
@router.get("/hk-indices")
def get_hk_market_indices(db: Session = Depends(get_db)):
    """获取港股指数数据（从数据库 hk_index_realtime_quotes 表中获取当前日期的数据）"""
    try:
        # 获取当前日期
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # 查询当前日期的所有港股指数数据，如果没有则查询最新日期的数据
        rows = db.query(HKIndexRealtimeQuotes).filter(
            HKIndexRealtimeQuotes.trade_date == current_date
        ).all()
        
        # 如果当前日期没有数据，查询最新日期的数据
        if not rows:
            # 获取最新的交易日期
            latest_date_row = db.query(HKIndexRealtimeQuotes).order_by(
                desc(HKIndexRealtimeQuotes.trade_date)
            ).first()
            
            if latest_date_row:
                latest_date = latest_date_row.trade_date
                rows = db.query(HKIndexRealtimeQuotes).filter(
                    HKIndexRealtimeQuotes.trade_date == latest_date
                ).all()
        
        indices_data = []
        if rows:
            for row in rows:
                indices_data.append({
                    'code': row.code,
                    'name': row.name,
                    'current': row.price,
                    'change': row.change,
                    'change_percent': row.pct_chg,
                    'volume': row.volume or 0,
                    'timestamp': row.update_time or datetime.now().isoformat()
                })
        
        if indices_data:
            return JSONResponse({'success': True, 'data': indices_data})
        else:
            # 如果数据库没有数据，返回空数据提示
            return JSONResponse({
                'success': False,
                'message': '数据库中暂无港股指数数据，请先运行数据采集任务',
                'data': []
            })
        
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f'[get_hk_market_indices] 获取港股指数数据异常: {str(e)}')
        print(tb)
        return JSONResponse({
            'success': False,
            'message': f'获取港股指数数据失败: {str(e)}',
            'error': str(e),
            'traceback': tb
        }, status_code=500)

@router.get("/industry_board/{board_code}/stocks")
def get_industry_board_stocks(
    board_code: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """板块成分股列表（分页，按涨跌幅降序）。"""
    try:
        board_data = (
            db.query(IndustryBoardRealtimeQuotes)
            .filter(IndustryBoardRealtimeQuotes.board_code == board_code)
            .first()
        )
        board_name = board_data.board_name if board_data else board_code
        all_items = _fetch_board_constituents_with_quotes(db, board_code, limit=10000)
        total = len(all_items)
        start = (page - 1) * page_size
        items = all_items[start : start + page_size]
        return JSONResponse({
            "success": True,
            "data": {
                "board_code": board_code,
                "board_name": board_name,
                "stocks": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "data_source": "industry_board_constituents",
            },
        })
    except Exception as e:
        tb = traceback.format_exc()
        return JSONResponse(
            {
                "success": False,
                "message": "获取板块成分股失败",
                "error": str(e),
                "traceback": tb,
            },
            status_code=500,
        )


@router.get("/industry_board/{board_code}/top_stocks")
def get_industry_board_top_stocks(
    board_code: str,
    board_name: str = None,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """板块内涨幅领先股票（优先成分股表 + 实时行情）。"""
    try:
        board_data = (
            db.query(IndustryBoardRealtimeQuotes)
            .filter(IndustryBoardRealtimeQuotes.board_code == board_code)
            .first()
        )
        display_name = (board_data.board_name if board_data else None) or board_name or board_code

        top_stocks = _fetch_board_constituents_with_quotes(db, board_code, limit=limit)
        data_source = "industry_board_constituents"

        if not top_stocks and board_data and board_data.leading_stock_name:
            top_stocks = [{
                "code": board_data.leading_stock_code or "",
                "name": board_data.leading_stock_name,
                "change_percent": board_data.leading_stock_change_percent or 0.0,
            }]
            data_source = "industry_board_realtime_quotes"

        if not top_stocks:
            return JSONResponse({
                "success": False,
                "message": f"板块 {display_name} 暂无成分股数据，请先运行成分股同步",
            })

        return JSONResponse({
            "success": True,
            "data": {
                "board_code": board_code,
                "board_name": display_name,
                "top_stocks": top_stocks,
                "total_stocks": len(top_stocks),
                "data_source": data_source,
            },
        })
    except Exception as e:
        tb = traceback.format_exc()
        return JSONResponse(
            {
                "success": False,
                "message": "获取板块龙头股数据失败",
                "error": str(e),
                "traceback": tb,
            },
            status_code=500,
        )


@router.get("/stock/{code}/industry_boards")
def get_stock_industry_boards(code: str, db: Session = Depends(get_db)):
    """个股所属东财行业板块列表。"""
    try:
        stock_code = _normalize_stock_code(code)
        boards = get_boards_by_stock_code(db, stock_code)
        return JSONResponse({
            "success": True,
            "data": {"stock_code": stock_code, "boards": boards},
        })
    except Exception as e:
        tb = traceback.format_exc()
        return JSONResponse(
            {
                "success": False,
                "message": "获取个股行业板块失败",
                "error": str(e),
                "traceback": tb,
            },
            status_code=500,
        )