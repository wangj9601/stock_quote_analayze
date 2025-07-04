"""
自选股管理API模块
提供自选股管理相关的接口
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime
from fastapi.responses import JSONResponse
import akshare as ak
from pydantic import BaseModel
import sqlite3

from .models import (
    Watchlist, WatchlistGroup,
    WatchlistCreate, WatchlistInDB, WatchlistGroupCreate,
    WatchlistGroupInDB, User, StockRealtimeQuote
)
from .database import get_db
from .auth import get_current_user

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

@router.get("", response_model=None)
async def get_watchlist(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取自选股列表（SQLAlchemy查询实时行情）"""
    try:
        user_id = current_user.id
        print(f"[watchlist] 请求用户ID: {user_id}")
        rows = db.query(Watchlist.stock_code, Watchlist.stock_name).filter(
            Watchlist.user_id == user_id
        ).order_by(desc(Watchlist.created_at)).all()
        print(f"[watchlist] 查询到自选股代码: {[row[0] for row in rows]}")
        if not rows:
            print("[watchlist] 用户无自选股，返回空列表")
            return JSONResponse({'success': True, 'data': []})

        codes = [row[0] for row in rows]
        names = {row[0]: row[1] for row in rows}
        watchlist = []

        # 批量查行情
        quotes = db.query(StockRealtimeQuote).filter(StockRealtimeQuote.code.in_(codes)).all()
        print(f"[watchlist] 批量查到行情数量: {len(quotes)}")
        quote_map = {q.code: q for q in quotes}

        def safe_float(value):
            try:
                if value in [None, '', '-']:
                    return None
                return float(value)
            except (ValueError, TypeError):
                return None

        for code in codes:
            q = quote_map.get(code)
            if not q:
                print(f"[watchlist] {code} 无行情数据，跳过")
                continue
            watchlist.append({
                'code': code,
                'name': names.get(code, ''),
                'current_price': safe_float(getattr(q, 'current_price', None)),
                'change_percent': safe_float(getattr(q, 'change_percent', None)),
                'volume': safe_float(getattr(q, 'volume', None)),
                'amount': safe_float(getattr(q, 'amount', None)),
                'high': safe_float(getattr(q, 'high', None)),
                'low': safe_float(getattr(q, 'low', None)),
                'open': safe_float(getattr(q, 'open', None)),
                'pre_close': safe_float(getattr(q, 'pre_close', None)),
                'change_amount': (
                    safe_float(getattr(q, 'current_price', None)) - safe_float(getattr(q, 'pre_close', None))
                    if safe_float(getattr(q, 'current_price', None)) is not None and safe_float(getattr(q, 'pre_close', None)) is not None
                    else None
                ),                
                'turnover_rate': safe_float(getattr(q, 'turnover_rate', None)),
                'pe_dynamic': safe_float(getattr(q, 'pe_dynamic', None)),
                'total_market_value': safe_float(getattr(q, 'total_market_value', None)),
                'pb_ratio': safe_float(getattr(q, 'pb_ratio', None)),
                'circulating_market_value': safe_float(getattr(q, 'circulating_market_value', None)),
                'update_time': getattr(q, 'update_time', None).isoformat() if getattr(q, 'update_time', None) else None
            })
        print(f"[watchlist] 最终返回watchlist条数: {len(watchlist)}")
        if watchlist:
            print(f"[watchlist] 返回示例: {watchlist[0]}")
        return JSONResponse({'success': True, 'data': watchlist})
    except Exception as e:
        print(f"[watchlist] 异常: {str(e)}")
        return JSONResponse({'success': False, 'message': str(e)}, status_code=500)

@router.get("/groups", response_model=List[WatchlistGroupInDB])
async def get_watchlist_groups(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户的自选股分组列表"""
    groups = db.query(WatchlistGroup).filter(
        WatchlistGroup.user_id == current_user.id
    ).order_by(desc(WatchlistGroup.created_at)).all()
    return groups

@router.post("", response_model=WatchlistInDB)
async def add_to_watchlist(
    watchlist: WatchlistCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """添加股票到自选股"""
    # 检查是否已存在
    existing = db.query(Watchlist).filter(
        Watchlist.user_id == current_user.id,
        Watchlist.stock_code == watchlist.stock_code,
        Watchlist.group_name == watchlist.group_name
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该股票已在自选股列表中"
        )
    
    # 创建新的自选股记录
    db_watchlist = Watchlist(
        user_id=current_user.id,
        stock_code=watchlist.stock_code,
        stock_name=watchlist.stock_name,
        group_name=watchlist.group_name
    )
    db.add(db_watchlist)
    db.commit()
    db.refresh(db_watchlist)
    #return db_watchlist
    return JSONResponse({'success': True, 'data': db_watchlist.id})

@router.post("/groups", response_model=WatchlistGroupInDB)
async def create_watchlist_group(
    group: WatchlistGroupCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建自选股分组"""
    # 检查分组名是否已存在
    existing = db.query(WatchlistGroup).filter(
        WatchlistGroup.user_id == current_user.id,
        WatchlistGroup.group_name == group.group_name
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该分组名已存在"
        )
    
    # 创建新的分组
    db_group = WatchlistGroup(
        user_id=current_user.id,
        group_name=group.group_name
    )
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group

@router.put("/{watchlist_id}/group")
async def update_watchlist_group(
    watchlist_id: int,
    group_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新自选股的分组"""
    # 检查自选股是否存在
    watchlist = db.query(Watchlist).filter(
        Watchlist.id == watchlist_id,
        Watchlist.user_id == current_user.id
    ).first()
    
    if not watchlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="自选股不存在"
        )
    
    # 检查新分组是否存在
    group = db.query(WatchlistGroup).filter(
        WatchlistGroup.user_id == current_user.id,
        WatchlistGroup.group_name == group_name
    ).first()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分组不存在"
        )
    
    # 更新分组
    watchlist.group_name = group_name
    db.commit()
    return {"message": "分组更新成功"}

@router.delete("/{watchlist_id}")
async def remove_from_watchlist(
    watchlist_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """从自选股中删除股票"""
    # 检查自选股是否存在
    watchlist = db.query(Watchlist).filter(
        Watchlist.id == watchlist_id,
        Watchlist.user_id == current_user.id
    ).first()
    
    if not watchlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="自选股不存在"
        )
    
    # 删除自选股
    db.delete(watchlist)
    db.commit()
    return {"message": "删除成功"}


class DeleteByCodeRequest(BaseModel):
    stock_code: str
    user_id: int

@router.post("/delete_by_code")
async def delete_watchlist_by_code(
    req: DeleteByCodeRequest,
    db: Session = Depends(get_db)
):
    stock_code = req.stock_code
    user_id = req.user_id
    print(f"[watchlist] 请求用户ID: {user_id}, 股票代码: {stock_code}")
    """根据股票代码+用户ID删除自选股"""
    # 检查自选股是否存在
    watchlist = db.query(Watchlist).filter(
        Watchlist.user_id == user_id,
        Watchlist.stock_code == stock_code
    ).first()

    if not watchlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="自选股不存在"
        )

    # 删除自选股
    db.delete(watchlist)
    db.commit()
    return JSONResponse({'success': True, 'message': "删除成功"})


@router.delete("/groups/{group_id}")
async def delete_watchlist_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除自选股分组"""
    # 检查分组是否存在
    group = db.query(WatchlistGroup).filter(
        WatchlistGroup.id == group_id,
        WatchlistGroup.user_id == current_user.id
    ).first()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分组不存在"
        )
    
    # 检查是否为默认分组
    if group.group_name == "default":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除默认分组"
        )
    
    # 将该分组下的自选股移动到默认分组
    db.query(Watchlist).filter(
        Watchlist.user_id == current_user.id,
        Watchlist.group_name == group.group_name
    ).update({"group_name": "default"})
    
    # 删除分组
    db.delete(group)
    db.commit()
    return {"message": "分组删除成功"}
