from typing import List, Optional
import io
import re
import math
from datetime import datetime
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from pydantic import BaseModel

from .models import (
    Watchlist, WatchlistGroup,
    WatchlistCreate, WatchlistInDB, WatchlistGroupCreate,
    WatchlistGroupInDB, User, StockRealtimeQuote, StockRealtimeQuoteHK,
    StockBasicInfo, StockBasicInfoHK
)
from .database import get_db
from .auth import get_current_user

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

@router.get("", response_model=None)
async def get_watchlist(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取自选股列表（仅从实时行情表读取）"""
    try:
        user_id = current_user.id
        print(f"[watchlist] 请求用户ID: {user_id}")
        watchlist_rows = db.query(Watchlist).filter(
            Watchlist.user_id == user_id
        ).order_by(desc(Watchlist.created_at)).all()
        print(f"[watchlist] 查询到自选股代码: {[row.stock_code for row in watchlist_rows]}")
        if not watchlist_rows:
            print("[watchlist] 用户无自选股，返回空列表")
            return JSONResponse({'success': True, 'data': []})

        codes = [row.stock_code for row in watchlist_rows]
        unique_codes = list(dict.fromkeys(codes))
        names = {row.stock_code: row.stock_name for row in watchlist_rows}
        watchlist = []

        def safe_float(value):
            try:
                if value in [None, '', '-', '--']:
                    return None
                if isinstance(value, str):
                    cleaned = value.replace(',', '').strip()
                    if cleaned in ['', '-', '--']:
                        return None
                    value = cleaned
                result = float(value)
                if isinstance(result, float) and math.isnan(result):
                    return None
                return result
            except (ValueError, TypeError):
                return None

        today = datetime.now().strftime('%Y-%m-%d')
        today_pattern = f"{today}%"
        
        # 1. 先从A股实时行情表查询
        quotes_today_a = db.query(StockRealtimeQuote).filter(
            StockRealtimeQuote.code.in_(unique_codes),
            StockRealtimeQuote.trade_date.like(today_pattern)
        ).all()
        print(f"[watchlist] A股当日行情数量: {len(quotes_today_a)}")

        quotes_a = quotes_today_a
        target_trade_date_a = today

        if not quotes_a:
            latest_trade_date_a = db.query(func.max(StockRealtimeQuote.trade_date)).scalar()
            if latest_trade_date_a:
                quotes_a = db.query(StockRealtimeQuote).filter(
                    StockRealtimeQuote.code.in_(unique_codes),
                    StockRealtimeQuote.trade_date == latest_trade_date_a
                ).all()
                target_trade_date_a = latest_trade_date_a
                print(f"[watchlist] A股当日无数据，回退至最新交易日 {latest_trade_date_a}，行情数量: {len(quotes_a)}")

        # 2. 从港股实时行情表查询
        quotes_today_hk = db.query(StockRealtimeQuoteHK).filter(
            StockRealtimeQuoteHK.code.in_(unique_codes),
            StockRealtimeQuoteHK.trade_date.like(today_pattern)
        ).all()
        print(f"[watchlist] 港股当日行情数量: {len(quotes_today_hk)}")

        quotes_hk = quotes_today_hk
        target_trade_date_hk = today

        if not quotes_hk:
            latest_trade_date_hk = db.query(func.max(StockRealtimeQuoteHK.trade_date)).scalar()
            if latest_trade_date_hk:
                quotes_hk = db.query(StockRealtimeQuoteHK).filter(
                    StockRealtimeQuoteHK.code.in_(unique_codes),
                    StockRealtimeQuoteHK.trade_date == latest_trade_date_hk
                ).all()
                target_trade_date_hk = latest_trade_date_hk
                print(f"[watchlist] 港股当日无数据，回退至最新交易日 {latest_trade_date_hk}，行情数量: {len(quotes_hk)}")

        # 3. 合并行情数据：A股优先，港股作为补充
        quote_map_a = {q.code: q for q in quotes_a}
        quote_map_hk = {q.code: q for q in quotes_hk}
        
        # 找出在A股中不存在的代码，从港股中补充
        codes_not_in_a = set(unique_codes) - set(quote_map_a.keys())
        print(f"[watchlist] A股中不存在的代码数量: {len(codes_not_in_a)}")

        for row in watchlist_rows:
            code = row.stock_code
            q = quote_map_a.get(code)  # 优先使用A股数据
            
            # 如果A股数据不存在，尝试从港股获取
            if not q:
                q_hk = quote_map_hk.get(code)
                if q_hk:
                    print(f"[watchlist] {code} 从港股表获取行情数据")
                    # 使用港股数据，字段映射
                    watchlist.append({
                        'code': code,
                        'name': names.get(code, '') or row.stock_name or code,
                        'group_name': row.group_name or 'default',
                        'watchlist_id': row.id,
                        'current_price': safe_float(getattr(q_hk, 'current_price', None)),
                        'change_percent': safe_float(getattr(q_hk, 'change_percent', None)),
                        'volume': safe_float(getattr(q_hk, 'volume', None)),
                        'amount': safe_float(getattr(q_hk, 'amount', None)),
                        'high': safe_float(getattr(q_hk, 'high', None)),
                        'low': safe_float(getattr(q_hk, 'low', None)),
                        'open': safe_float(getattr(q_hk, 'open', None)),
                        'pre_close': safe_float(getattr(q_hk, 'pre_close', None)),
                        'change_amount': safe_float(getattr(q_hk, 'change_amount', None)),  # 港股有change_amount字段
                        'turnover_rate': None,  # 港股表没有此字段
                        'pe_dynamic': None,  # 港股表没有此字段
                        'total_market_value': None,  # 港股表没有此字段
                        'pb_ratio': None,  # 港股表没有此字段
                        'circulating_market_value': None,  # 港股表没有此字段
                        'update_time': getattr(q_hk, 'update_time', None).isoformat() if q_hk and getattr(q_hk, 'update_time', None) else None
                    })
                    continue
            
            # 使用A股数据或空数据
            if not q:
                print(f"[watchlist] {code} 无行情数据，但仍返回自选股记录")
            watchlist.append({
                'code': code,
                'name': names.get(code, '') or row.stock_name or code,
                'group_name': row.group_name or 'default',
                'watchlist_id': row.id,
                'current_price': safe_float(getattr(q, 'current_price', None)) if q else None,
                'change_percent': safe_float(getattr(q, 'change_percent', None)) if q else None,
                'volume': safe_float(getattr(q, 'volume', None)) if q else None,
                'amount': safe_float(getattr(q, 'amount', None)) if q else None,
                'high': safe_float(getattr(q, 'high', None)) if q else None,
                'low': safe_float(getattr(q, 'low', None)) if q else None,
                'open': safe_float(getattr(q, 'open', None)) if q else None,
                'pre_close': safe_float(getattr(q, 'pre_close', None)) if q else None,
                'change_amount': (
                    safe_float(getattr(q, 'current_price', None)) - safe_float(getattr(q, 'pre_close', None))
                    if q and safe_float(getattr(q, 'current_price', None)) is not None and safe_float(getattr(q, 'pre_close', None)) is not None
                    else (
                        safe_float(getattr(q, 'current_price', None)) * safe_float(getattr(q, 'change_percent', None)) / 100 / (1 + safe_float(getattr(q, 'change_percent', None)) / 100)
                        if q and safe_float(getattr(q, 'current_price', None)) is not None and safe_float(getattr(q, 'change_percent', None)) is not None
                        else None
                    )
                ),
                'turnover_rate': safe_float(getattr(q, 'turnover_rate', None)) if q else None,
                'pe_dynamic': safe_float(getattr(q, 'pe_dynamic', None)) if q else None,
                'total_market_value': safe_float(getattr(q, 'total_market_value', None)) if q else None,
                'pb_ratio': safe_float(getattr(q, 'pb_ratio', None)) if q else None,
                'circulating_market_value': safe_float(getattr(q, 'circulating_market_value', None)) if q else None,
                'update_time': getattr(q, 'update_time', None).isoformat() if q and getattr(q, 'update_time', None) else None
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

@router.post("", response_model=None)
async def add_to_watchlist(
    watchlist: WatchlistCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """添加股票到自选股"""
    try:
        user_id = current_user.id
        print(f"[watchlist] 添加自选股请求 - 用户ID: {user_id}, 股票代码: {watchlist.stock_code}, 股票名称: {watchlist.stock_name}, 分组: {watchlist.group_name}")
        
        # 检查是否已存在
        existing = db.query(Watchlist).filter(
            Watchlist.user_id == user_id,
            Watchlist.stock_code == watchlist.stock_code,
            Watchlist.group_name == watchlist.group_name
        ).first()
        
        if existing:
            print(f"[watchlist] 股票已存在于自选股列表中")
            return JSONResponse(
                {'success': False, 'message': '该股票已在自选股列表中'},
                status_code=400
            )
        
        # 创建新的自选股记录
        db_watchlist = Watchlist(
            user_id=user_id,
            stock_code=watchlist.stock_code,
            stock_name=watchlist.stock_name,
            group_name=watchlist.group_name
        )
        db.add(db_watchlist)
        db.commit()
        db.refresh(db_watchlist)
        print(f"[watchlist] 自选股添加成功 - ID: {db_watchlist.id}")
        return JSONResponse({'success': True, 'data': db_watchlist.id})
    except Exception as e:
        print(f"[watchlist] 添加自选股异常: {str(e)}")
        db.rollback()
        return JSONResponse(
            {'success': False, 'message': f'添加失败: {str(e)}'},
            status_code=500
        )


class CollectIndicatorsRequest(BaseModel):
    """触发单只自选股历史行情采集与指标计算的请求体"""
    stock_code: str


def _collect_and_calculate_impl(stock_code: str) -> JSONResponse:
    """
    实际执行单股历史行情采集与指标计算的内部函数，供多种HTTP方法复用。
    """
    stock_code = (stock_code or "").strip()
    if not stock_code:
        return JSONResponse(
            {'success': False, 'message': '股票代码不能为空'},
            status_code=400
        )
    try:
        from backend_core.database.db import get_db as get_core_db
        from backend_core.data_collectors.akshare.watchlist_history_collector import (
            collect_one_stock_history_and_indicators,
        )
        db = next(get_core_db())
        try:
            result = collect_one_stock_history_and_indicators(db, stock_code)
        finally:
            db.close()
        if result.get("success"):
            return JSONResponse({'success': True, 'message': result.get('message', '已触发采集与指标计算')})
        return JSONResponse(
            {'success': False, 'message': result.get('message', '采集或指标计算失败')},
            status_code=422
        )
    except Exception as e:
        print(f"[watchlist] 采集与指标计算异常: {e}")
        return JSONResponse(
            {'success': False, 'message': f'请求失败: {str(e)}'},
            status_code=500
        )


@router.post("/collect-and-calculate-indicators", response_model=None)
async def collect_and_calculate_indicators(
    body: CollectIndicatorsRequest,
    current_user: User = Depends(get_current_user),
):
    """
    对单只自选股拉取历史行情并计算 MA、MACD、RSI、KDJ、BOLL、MAVOL、PVFRS 指标。
    添加自选股成功后由前端调用，使用 backend_core 独立会话执行。
    （POST JSON 版本）
    """
    return _collect_and_calculate_impl(body.stock_code)


@router.get("/collect-and-calculate-indicators", response_model=None)
async def collect_and_calculate_indicators_get(
    stock_code: str,
    current_user: User = Depends(get_current_user),
):
    """
    同一功能的 GET 版本，便于调试或直接在浏览器调用：
    /api/watchlist/collect-and-calculate-indicators?stock_code=000001
    """
    return _collect_and_calculate_impl(stock_code)


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

@router.get("/export")
async def export_watchlist(
    format: str = "csv",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """导出自选股列表"""
    try:
        user_id = current_user.id
        watchlist_rows = db.query(Watchlist).filter(
            Watchlist.user_id == user_id
        ).order_by(Watchlist.group_name, Watchlist.created_at).all()
        
        data = []
        for row in watchlist_rows:
            data.append({
                "代码": row.stock_code,
                "名称": row.stock_name,
                "分组": row.group_name,
                "添加时间": row.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })
            
        if not data:
            # 即使没数据，也导出一个带表头的空表
            data = [{"代码": "", "名称": "", "分组": "", "添加时间": ""}]
            
        df = pd.DataFrame(data)
        
        if format.lower() == "xlsx":
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='我的自选股')
            output.seek(0)
            return StreamingResponse(
                output,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename=watchlist_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"}
            )
        elif format.lower() == "txt":
            # 导出纯文本格式（代码 名称）
            output = io.StringIO()
            for row in data:
                output.write(f"{row['代码']} {row['名称']}\n")
            output_bytes = output.getvalue().encode('utf-8')
            return StreamingResponse(
                io.BytesIO(output_bytes),
                media_type="text/plain",
                headers={"Content-Disposition": f"attachment; filename=watchlist_{datetime.now().strftime('%Y%m%d%H%M%S')}.txt"}
            )
        else:
            # 默认导出 CSV
            output = io.StringIO()
            df.to_csv(output, index=False, encoding='utf-8-sig')
            output_bytes = output.getvalue().encode('utf-8-sig')
            return StreamingResponse(
                io.BytesIO(output_bytes),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=watchlist_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"}
            )
            
    except Exception as e:
        print(f"[watchlist] 导出异常: {str(e)}")
        return JSONResponse({'success': False, 'message': f'导出失败: {str(e)}'}, status_code=500)

@router.post("/import")
async def import_watchlist(
    file: UploadFile = File(...),
    group_name: str = "default",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """导入自选股列表"""
    try:
        user_id = current_user.id
        filename = file.filename
        content = await file.read()
        
        stocks_to_import = []
        
        if filename.endswith('.txt'):
            text_content = content.decode('utf-8')
            # 按分隔符拆分，仅保留 4-6 位数字代码（港股5位、A股6位均可，不强制6位）
            potential_codes = re.split(r'[,\n\r\t ]+', text_content)
            for c in potential_codes:
                c = c.strip()
                if c and c.isdigit() and 4 <= len(c) <= 6:
                    stocks_to_import.append({"code": c})
                    
        elif filename.endswith('.csv'):
            # dtype=str 保留前导零，避免 09988/002271 被解析为 9988/2271
            try:
                df = pd.read_csv(io.BytesIO(content), encoding='utf-8-sig', dtype=str, keep_default_na=False)
            except Exception:
                try:
                    df = pd.read_csv(io.BytesIO(content), encoding='gbk', dtype=str, keep_default_na=False)
                except Exception:
                    df = pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False)
            stocks_to_import = df.to_dict('records')

        elif filename.endswith(('.xlsx', '.xls')):
            # dtype=str 保留前导零
            df = pd.read_excel(io.BytesIO(content), dtype=str, keep_default_na=False)
            stocks_to_import = df.to_dict('records')
        else:
            return JSONResponse({'success': False, 'message': '仅支持 .txt, .csv, .xlsx, .xls 格式'}, status_code=400)

        added_count = 0
        skipped_count = 0
        failed_count = 0

        def _resolve_code_by_name(name_str: str) -> Optional[str]:
            """按名称在基础表中查找股票代码"""
            n = str(name_str).strip()
            if not n:
                return None
            basic_a = db.query(StockBasicInfo).filter(StockBasicInfo.name == n).first()
            if basic_a and basic_a.code:
                return str(basic_a.code).zfill(6) if str(basic_a.code).isdigit() else str(basic_a.code)
            basic_hk = db.query(StockBasicInfoHK).filter(StockBasicInfoHK.name == n).first()
            if basic_hk and basic_hk.code:
                c = str(basic_hk.code).strip()
                return c.zfill(5) if c.isdigit() else c
            return None

        def _is_valid_stock_code(s: str) -> bool:
            """是否为有效股票代码格式（4-6位数字）"""
            s = str(s).strip()
            return bool(s and 4 <= len(s) <= 6 and s.isdigit())

        def _normalize_to_canonical_code(raw: str) -> Optional[str]:
            """归一化为规范代码：港股5位、A股6位。已为5位或6位则直接使用，不强制统一为6位。"""
            s = str(raw).strip()
            if not s or not s.isdigit():
                return None
            # 已为5位或6位则直接使用，符合要求
            if len(s) == 5 or len(s) == 6:
                return s
            # 4位需补齐：先查港股，再查A股
            if len(s) <= 5:
                for c in [s.zfill(5), s]:
                    basic_hk = db.query(StockBasicInfoHK).filter(StockBasicInfoHK.code == c).first()
                    if basic_hk and basic_hk.code is not None:
                        cstr = str(basic_hk.code).strip()
                        return cstr.zfill(5) if cstr.isdigit() else cstr
                for c in [s.zfill(6), s]:
                    basic_a = db.query(StockBasicInfo).filter(StockBasicInfo.code == c).first()
                    if not basic_a and c.isdigit():
                        try:
                            basic_a = db.query(StockBasicInfo).filter(StockBasicInfo.code == int(c)).first()
                        except Exception:
                            pass
                    if basic_a and basic_a.code is not None:
                        return str(basic_a.code).zfill(6) if str(basic_a.code).isdigit() else str(basic_a.code)
            else:
                # 6位：先查 A 股
                for c in [s.zfill(6), s]:
                    basic_a = db.query(StockBasicInfo).filter(StockBasicInfo.code == c).first()
                    if not basic_a and c.isdigit():
                        try:
                            basic_a = db.query(StockBasicInfo).filter(StockBasicInfo.code == int(c)).first()
                        except Exception:
                            pass
                    if basic_a and basic_a.code is not None:
                        return str(basic_a.code).zfill(6) if str(basic_a.code).isdigit() else str(basic_a.code)
                for c in [s.zfill(5), s]:
                    basic_hk = db.query(StockBasicInfoHK).filter(StockBasicInfoHK.code == c).first()
                    if basic_hk and basic_hk.code is not None:
                        cstr = str(basic_hk.code).strip()
                        return cstr.zfill(5) if cstr.isdigit() else cstr
            # 未找到：5位保持5位，6位保持6位
            return s.zfill(5) if len(s) <= 5 else s.zfill(6)

        for item in stocks_to_import:
            try:
                # 使用 savepoint 隔离每条记录，单条失败不影响后续
                with db.begin_nested():
                    # 尝试各种可能的键名（优先代码列）
                    code_val = (
                        item.get('code') or item.get('代码') or item.get('Stock Code') or
                        item.get('股票代码') or item.get('证券代码') or item.get('股票编号') or
                        item.get('ts_code') or item.get('Symbol')
                    )
                    if code_val is None and len(item) > 0:
                        code_val = list(item.values())[0]
                    if code_val is None:
                        continue

                    code = str(code_val).strip()
                    if not code.isdigit() and any('\u4e00' <= ch <= '\u9fff' for ch in code):
                        resolved = _resolve_code_by_name(code)
                        if resolved:
                            code = resolved
                        else:
                            continue

                    clean_code = code.split('.')[0].strip()
                    if len(clean_code) > 6:
                        clean_code = clean_code[-6:]
                    if not _is_valid_stock_code(clean_code):
                        continue

                    # 归一化为规范代码：港股5位、A股6位
                    clean_code = _normalize_to_canonical_code(clean_code) or clean_code

                    existing = db.query(Watchlist).filter(
                        Watchlist.user_id == user_id,
                        Watchlist.stock_code == clean_code
                    ).first()
                    if existing:
                        skipped_count += 1
                        continue

                    name = (
                        item.get('name') or item.get('名称') or item.get('Stock Name') or
                        item.get('股票名称') or item.get('证券名称') or item.get('Name')
                    )
                    if not name:
                        try:
                            # 5位代码从港股表取，6位从A股表取
                            if len(clean_code) == 5:
                                basic_hk = db.query(StockBasicInfoHK).filter(StockBasicInfoHK.code == clean_code).first()
                                name = basic_hk.name if basic_hk else clean_code
                            else:
                                basic_a = db.query(StockBasicInfo).filter(StockBasicInfo.code == clean_code).first()
                                if not basic_a and clean_code.isdigit():
                                    try:
                                        basic_a = db.query(StockBasicInfo).filter(StockBasicInfo.code == int(clean_code)).first()
                                    except Exception:
                                        pass
                                if basic_a:
                                    name = basic_a.name
                                else:
                                    basic_hk = db.query(StockBasicInfoHK).filter(StockBasicInfoHK.code == clean_code).first()
                                    name = basic_hk.name if basic_hk else clean_code
                        except Exception:
                            name = clean_code

                    db.add(Watchlist(
                        user_id=user_id,
                        stock_code=clean_code,
                        stock_name=name,
                        group_name=group_name
                    ))
                    db.flush()
                added_count += 1
            except Exception as item_err:
                failed_count += 1
                # savepoint 已自动回滚，继续处理下一条

        db.commit()
        msg = f'导入完成。成功导入 {added_count} 只股票，跳过 {skipped_count} 只已存在股票。'
        if failed_count > 0:
            msg += f' {failed_count} 条导入失败已跳过。'
        return JSONResponse({'success': True, 'message': msg})
        
    except Exception as e:
        print(f"[watchlist] 导入异常: {str(e)}")
        db.rollback()
        return JSONResponse({'success': False, 'message': f'导入异常: {str(e)}'}, status_code=500)
