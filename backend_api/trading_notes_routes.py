#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易备注管理API路由
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime
from pydantic import BaseModel

from database import get_db, engine
from auth import get_current_user
from models import TradingNotes, HistoricalQuotes, TradingJournalLog, User, TradeExecutionLog
from sqlalchemy import text

router = APIRouter(prefix="/api/trading_notes", tags=["trading_notes"])


def ensure_trading_journal_table(db: Session) -> None:
    """在缺少迁移工具的情况下，尽力保证交易日志表存在。"""
    try:
        TradingJournalLog.__table__.create(bind=engine, checkfirst=True)
        TradeExecutionLog.__table__.create(bind=engine, checkfirst=True)
    except Exception:
        db.rollback()


# Pydantic模型
class TradingNoteCreate(BaseModel):
    stock_code: str
    trade_date: date
    notes: Optional[str] = None
    strategy_type: Optional[str] = None
    risk_level: Optional[str] = None
    created_by: Optional[str] = None

class TradingNoteUpdate(BaseModel):
    notes: Optional[str] = None
    strategy_type: Optional[str] = None
    risk_level: Optional[str] = None

class TradingNoteResponse(BaseModel):
    id: int
    stock_code: str
    trade_date: date
    notes: Optional[str]
    strategy_type: Optional[str]
    risk_level: Optional[str]
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]

    class Config:
        from_attributes = True


class TradingJournalDailyCreate(BaseModel):
    log_date: date
    mood: Optional[str] = None
    content: str


class TradingJournalWeeklyCreate(BaseModel):
    week_start: date
    score: Optional[str] = None
    content: str


class TradingJournalUpdate(BaseModel):
    mood: Optional[str] = None
    score: Optional[str] = None
    content: Optional[str] = None


class TradingJournalResponse(BaseModel):
    id: int
    user_id: int
    log_type: str
    log_date: Optional[date]
    week_start: Optional[date]
    mood: Optional[str]
    score: Optional[str]
    content: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TradeExecutionLogCreate(BaseModel):
    stock_code: str
    stock_name: Optional[str] = None
    trade_date: date
    entry_thinking: Optional[str] = None
    market_context: Optional[str] = None
    buy_price: Optional[float] = None
    position_size: Optional[str] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    strictly_execute: Optional[str] = None
    emotional_trading: Optional[str] = None
    content: Optional[str] = None
    image_url: Optional[str] = None


class TradeExecutionLogResponse(TradeExecutionLogCreate):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.get("/journals", response_model=List[TradingJournalResponse])
def list_trading_journals(
    log_type: str = Query(..., description="daily / weekly"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_trading_journal_table(db)
    if log_type not in ("daily", "weekly"):
        raise HTTPException(status_code=400, detail="log_type 必须是 daily 或 weekly")

    q = db.query(TradingJournalLog).filter(
        TradingJournalLog.user_id == current_user.id,
        TradingJournalLog.log_type == log_type,
    )

    if log_type == "daily":
        if start_date:
            q = q.filter(TradingJournalLog.log_date >= start_date)
        if end_date:
            q = q.filter(TradingJournalLog.log_date <= end_date)
        q = q.order_by(TradingJournalLog.log_date.desc().nullslast())
    else:
        if start_date:
            q = q.filter(TradingJournalLog.week_start >= start_date)
        if end_date:
            q = q.filter(TradingJournalLog.week_start <= end_date)
        q = q.order_by(TradingJournalLog.week_start.desc().nullslast())

    return q.all()


@router.post("/journals/daily", response_model=TradingJournalResponse)
def upsert_daily_journal(
    payload: TradingJournalDailyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_trading_journal_table(db)
    existing = db.query(TradingJournalLog).filter(
        TradingJournalLog.user_id == current_user.id,
        TradingJournalLog.log_type == "daily",
        TradingJournalLog.log_date == payload.log_date,
    ).first()

    now = datetime.now()
    if existing:
        existing.mood = payload.mood
        existing.content = payload.content
        existing.updated_at = now
        db.commit()
        db.refresh(existing)
        return existing

    record = TradingJournalLog(
        user_id=current_user.id,
        log_type="daily",
        log_date=payload.log_date,
        week_start=None,
        mood=payload.mood,
        score=None,
        content=payload.content,
        created_at=now,
        updated_at=now,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.post("/journals/weekly", response_model=TradingJournalResponse)
def upsert_weekly_journal(
    payload: TradingJournalWeeklyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_trading_journal_table(db)
    existing = db.query(TradingJournalLog).filter(
        TradingJournalLog.user_id == current_user.id,
        TradingJournalLog.log_type == "weekly",
        TradingJournalLog.week_start == payload.week_start,
    ).first()

    now = datetime.now()
    if existing:
        existing.score = payload.score
        existing.content = payload.content
        existing.updated_at = now
        db.commit()
        db.refresh(existing)
        return existing

    record = TradingJournalLog(
        user_id=current_user.id,
        log_type="weekly",
        log_date=None,
        week_start=payload.week_start,
        mood=None,
        score=payload.score,
        content=payload.content,
        created_at=now,
        updated_at=now,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.put("/journals/{journal_id}", response_model=TradingJournalResponse)
def update_trading_journal(
    journal_id: int,
    payload: TradingJournalUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_trading_journal_table(db)
    record = db.query(TradingJournalLog).filter(
        TradingJournalLog.id == journal_id,
        TradingJournalLog.user_id == current_user.id,
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="交易日志不存在")

    if payload.mood is not None:
        record.mood = payload.mood
    if payload.score is not None:
        record.score = payload.score
    if payload.content is not None:
        record.content = payload.content
    record.updated_at = datetime.now()

    db.commit()
    db.refresh(record)
    return record


@router.delete("/journals/{journal_id}")
def delete_trading_journal(
    journal_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_trading_journal_table(db)
    record = db.query(TradingJournalLog).filter(
        TradingJournalLog.id == journal_id,
        TradingJournalLog.user_id == current_user.id,
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="交易日志不存在")

    db.delete(record)
    db.commit()
    return {"message": "交易日志删除成功"}


# --- Trade Execution Log Routes ---

@router.get("/trade_logs", response_model=List[TradeExecutionLogResponse])
def list_trade_execution_logs(
    stock_code: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_trading_journal_table(db)
    q = db.query(TradeExecutionLog).filter(TradeExecutionLog.user_id == current_user.id)
    
    if stock_code:
        q = q.filter(TradeExecutionLog.stock_code == stock_code)
    if start_date:
        q = q.filter(TradeExecutionLog.trade_date >= start_date)
    if end_date:
        q = q.filter(TradeExecutionLog.trade_date <= end_date)
        
    return q.order_by(TradeExecutionLog.trade_date.desc()).all()


@router.post("/trade_logs", response_model=TradeExecutionLogResponse)
def create_trade_execution_log(
    payload: TradeExecutionLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_trading_journal_table(db)
    now = datetime.now()
    record = TradeExecutionLog(
        user_id=current_user.id,
        stock_code=payload.stock_code,
        stock_name=payload.stock_name,
        trade_date=payload.trade_date,
        entry_thinking=payload.entry_thinking,
        market_context=payload.market_context,
        buy_price=payload.buy_price,
        position_size=payload.position_size,
        stop_loss=payload.stop_loss,
        take_profit=payload.take_profit,
        strictly_execute=payload.strictly_execute,
        emotional_trading=payload.emotional_trading,
        content=payload.content,
        image_url=payload.image_url,
        created_at=now,
        updated_at=now,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.put("/trade_logs/{log_id}", response_model=TradeExecutionLogResponse)
def update_trade_execution_log(
    log_id: int,
    payload: TradeExecutionLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_trading_journal_table(db)
    record = db.query(TradeExecutionLog).filter(
        TradeExecutionLog.id == log_id,
        TradeExecutionLog.user_id == current_user.id,
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    for key, value in payload.model_dump().items():
        setattr(record, key, value)
    
    record.updated_at = datetime.now()
    db.commit()
    db.refresh(record)
    return record


@router.delete("/trade_logs/{log_id}")
def delete_trade_execution_log(
    log_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_trading_journal_table(db)
    record = db.query(TradeExecutionLog).filter(
        TradeExecutionLog.id == log_id,
        TradeExecutionLog.user_id == current_user.id,
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    db.delete(record)
    db.commit()
    return {"message": "记录删除成功"}

class HistoricalQuoteWithNotes(BaseModel):
    code: str
    name: Optional[str]
    date: date
    open: Optional[float]
    close: Optional[float]
    high: Optional[float]
    low: Optional[float]
    volume: Optional[int]
    amount: Optional[float]
    change_percent: Optional[float]
    change: Optional[float]
    turnover_rate: Optional[float]
    cumulative_change_percent: Optional[float]
    five_day_change_percent: Optional[float]
    remarks: Optional[str]
    # 交易备注信息
    user_notes: Optional[str]
    strategy_type: Optional[str]
    risk_level: Optional[str]
    notes_creator: Optional[str]
    notes_created_at: Optional[datetime]
    notes_updated_at: Optional[datetime]

    class Config:
        from_attributes = True

@router.post("/", response_model=TradingNoteResponse)
def create_or_update_trading_note(note: TradingNoteCreate, db: Session = Depends(get_db)):
    """创建或更新交易备注（upsert操作）"""
    try:
        # 检查是否已存在
        existing_note = db.query(TradingNotes).filter(
            TradingNotes.stock_code == note.stock_code,
            TradingNotes.trade_date == note.trade_date
        ).first()
        
        if existing_note:
            # 如果存在，更新现有记录
            if note.notes is not None:
                existing_note.notes = note.notes
            if note.strategy_type is not None:
                existing_note.strategy_type = note.strategy_type
            if note.risk_level is not None:
                existing_note.risk_level = note.risk_level
            
            existing_note.updated_at = datetime.now()
            db.commit()
            db.refresh(existing_note)
            
            return existing_note
        else:
            # 如果不存在，创建新记录
            db_note = TradingNotes(
                stock_code=note.stock_code,
                trade_date=note.trade_date,
                notes=note.notes,
                strategy_type=note.strategy_type,
                risk_level=note.risk_level,
                created_by=note.created_by or "system"
            )
            
            db.add(db_note)
            db.commit()
            db.refresh(db_note)
            
            return db_note
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建或更新交易备注失败: {str(e)}")

@router.get("/{stock_code}", response_model=List[TradingNoteResponse])
def get_trading_notes(
    stock_code: str,
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    db: Session = Depends(get_db)
):
    """获取指定股票的交易备注"""
    try:
        query = db.query(TradingNotes).filter(TradingNotes.stock_code == stock_code)
        
        if start_date:
            query = query.filter(TradingNotes.trade_date >= start_date)
        if end_date:
            query = query.filter(TradingNotes.trade_date <= end_date)
        
        notes = query.order_by(TradingNotes.trade_date.desc()).all()
        return notes
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取交易备注失败: {str(e)}")

@router.put("/{note_id}", response_model=TradingNoteResponse)
def update_trading_note(
    note_id: int,
    note_update: TradingNoteUpdate,
    db: Session = Depends(get_db)
):
    """更新交易备注"""
    try:
        db_note = db.query(TradingNotes).filter(TradingNotes.id == note_id).first()
        if not db_note:
            raise HTTPException(status_code=404, detail="交易备注不存在")
        
        # 更新字段
        if note_update.notes is not None:
            db_note.notes = note_update.notes
        if note_update.strategy_type is not None:
            db_note.strategy_type = note_update.strategy_type
        if note_update.risk_level is not None:
            db_note.risk_level = note_update.risk_level
        
        db_note.updated_at = datetime.now()
        db.commit()
        db.refresh(db_note)
        
        return db_note
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新交易备注失败: {str(e)}")

@router.delete("/{note_id}")
def delete_trading_note(note_id: int, db: Session = Depends(get_db)):
    """删除交易备注"""
    try:
        db_note = db.query(TradingNotes).filter(TradingNotes.id == note_id).first()
        if not db_note:
            raise HTTPException(status_code=404, detail="交易备注不存在")
        
        db.delete(db_note)
        db.commit()
        
        return {"message": "交易备注删除成功"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除交易备注失败: {str(e)}")

@router.get("/{stock_code}/with_quotes", response_model=List[HistoricalQuoteWithNotes])
def get_historical_quotes_with_notes(
    stock_code: str,
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    include_notes: bool = Query(True, description="是否包含备注"),
    db: Session = Depends(get_db)
):
    """获取指定股票的历史行情数据（包含交易备注）"""
    try:
        if include_notes:
            # 使用视图查询
            query = f"""
                SELECT 
                    h.*,
                    COALESCE(tn.notes, '') as user_notes,
                    COALESCE(tn.strategy_type, '') as strategy_type,
                    COALESCE(tn.risk_level, '') as risk_level,
                    COALESCE(tn.created_by, '') as notes_creator,
                    tn.created_at as notes_created_at,
                    tn.updated_at as notes_updated_at
                FROM historical_quotes h
                LEFT JOIN trading_notes tn ON h.code = tn.stock_code AND h.date::date = tn.trade_date
                WHERE h.code = :stock_code
            """
            
            params = {"stock_code": stock_code}
            if start_date:
                query += " AND h.date::date >= :start_date"
                params["start_date"] = start_date
            if end_date:
                query += " AND h.date::date <= :end_date"
                params["end_date"] = end_date
            
            query += " ORDER BY h.date DESC"
            
            result = db.execute(text(query), params)
            rows = result.fetchall()
            
            # 转换为响应模型
            quotes_with_notes = []
            for row in rows:
                quote_data = dict(row._mapping)
                quotes_with_notes.append(HistoricalQuoteWithNotes(**quote_data))
            
            return quotes_with_notes
        else:
            # 只查询历史行情数据
            query = db.query(HistoricalQuotes).filter(HistoricalQuotes.code == stock_code)
            
            if start_date:
                query = query.filter(HistoricalQuotes.date >= start_date)
            if end_date:
                query = query.filter(HistoricalQuotes.date <= end_date)
            
            quotes = query.order_by(HistoricalQuotes.date.desc()).all()
            
            # 转换为响应模型
            quotes_with_notes = []
            for quote in quotes:
                quote_data = {
                    "code": quote.code,
                    "name": quote.name,
                    "date": quote.date,
                    "open": quote.open,
                    "close": quote.close,
                    "high": quote.high,
                    "low": quote.low,
                    "volume": quote.volume,
                    "amount": quote.amount,
                    "change_percent": quote.change_percent,
                    "change": quote.change,
                    "turnover_rate": quote.turnover_rate,
                    "cumulative_change_percent": quote.cumulative_change_percent,
                    "five_day_change_percent": quote.five_day_change_percent,
                    "remarks": quote.remarks,
                    "user_notes": None,
                    "strategy_type": None,
                    "risk_level": None,
                    "notes_creator": None,
                    "notes_created_at": None,
                    "notes_updated_at": None
                }
                quotes_with_notes.append(HistoricalQuoteWithNotes(**quote_data))
            
            return quotes_with_notes
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取历史行情数据失败: {str(e)}")

@router.post("/{stock_code}/calculate_fields")
def calculate_derived_fields(
    stock_code: str,
    base_date: Optional[date] = Query(None, description="基准日期（累计升跌%计算用）"),
    db: Session = Depends(get_db)
):
    """计算派生字段：累计升跌%和5天升跌%"""
    try:
        # 计算累计升跌%
        if base_date:
            base_quote = db.query(HistoricalQuotes).filter(
                HistoricalQuotes.code == stock_code,
                HistoricalQuotes.date == base_date
            ).first()
            
            if base_quote and base_quote.close:
                base_price = base_quote.close
                
                # 更新所有日期的累计升跌%
                quotes = db.query(HistoricalQuotes).filter(
                    HistoricalQuotes.code == stock_code
                ).all()
                
                for quote in quotes:
                    if quote.close and base_price > 0:
                        quote.cumulative_change_percent = ((quote.close - base_price) / base_price) * 100
                
                db.commit()
        
        # 计算5天升跌%
        quotes = db.query(HistoricalQuotes).filter(
            HistoricalQuotes.code == stock_code
        ).order_by(HistoricalQuotes.date).all()
        
        for i, quote in enumerate(quotes):
            if i >= 5:  # 从第6天开始计算
                prev_quote = quotes[i-5]
                if quote.close and prev_quote.close and prev_quote.close > 0:
                    quote.five_day_change_percent = ((quote.close - prev_quote.close) / prev_quote.close) * 100
        
        db.commit()
        
        return {
            "message": "派生字段计算完成",
            "stock_code": stock_code,
            "base_date": base_date.isoformat() if base_date else None,
            "updated_records": len(quotes)
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"计算派生字段失败: {str(e)}")

@router.post("/upsert")
def upsert_trading_note(note: TradingNoteCreate, db: Session = Depends(get_db)):
    """创建或更新交易备注（upsert操作）"""
    try:
        # 检查是否已存在
        existing_note = db.query(TradingNotes).filter(
            TradingNotes.stock_code == note.stock_code,
            TradingNotes.trade_date == note.trade_date
        ).first()
        
        if existing_note:
            # 如果存在，更新现有记录
            if note.notes is not None:
                existing_note.notes = note.notes
            if note.strategy_type is not None:
                existing_note.strategy_type = note.strategy_type
            if note.risk_level is not None:
                existing_note.risk_level = note.risk_level
            
            existing_note.updated_at = datetime.now()
            db.commit()
            db.refresh(existing_note)
            
            return {
                "message": "交易备注更新成功",
                "operation": "update",
                "note": existing_note
            }
        else:
            # 如果不存在，创建新记录
            db_note = TradingNotes(
                stock_code=note.stock_code,
                trade_date=note.trade_date,
                notes=note.notes,
                strategy_type=note.strategy_type,
                risk_level=note.risk_level,
                created_by=note.created_by or "system"
            )
            
            db.add(db_note)
            db.commit()
            db.refresh(db_note)
            
            return {
                "message": "交易备注创建成功",
                "operation": "create",
                "note": db_note
            }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建或更新交易备注失败: {str(e)}")

@router.post("/{stock_code}/calculate_five_day_change")
def calculate_stock_five_day_change(
    stock_code: str,
    db: Session = Depends(get_db)
):
    """计算指定股票的5天升跌%"""
    try:
        success = calculate_five_day_change_percent(stock_code, db)
        if success:
            return {"message": f"股票 {stock_code} 的5天升跌%计算完成"}
        else:
            raise HTTPException(status_code=400, detail="数据不足，无法计算")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"计算失败: {str(e)}")

@router.post("/calculate_all_five_day_change")
def calculate_all_five_day_change(db: Session = Depends(get_db)):
    """计算所有股票的5天升跌%"""
    try:
        # 获取所有股票代码
        stock_codes = db.query(HistoricalQuotes.code).distinct().all()
        stock_codes = [code[0] for code in stock_codes]
        
        success_count = 0
        for stock_code in stock_codes:
            if calculate_five_day_change_percent(stock_code, db):
                success_count += 1
        
        return {
            "message": f"批量计算完成，成功: {success_count}/{len(stock_codes)}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"计算失败: {str(e)}")

def calculate_five_day_change_percent(stock_code: str, db: Session) -> bool:
    """计算指定股票的5天升跌%"""
    try:
        # 获取股票的历史数据，按日期排序
        quotes = db.query(HistoricalQuotes).filter(
            HistoricalQuotes.code == stock_code
        ).order_by(HistoricalQuotes.date).all()
        
        if len(quotes) < 6:
            # 数据不足5天，无法计算
            return False
        
        # 从第6天开始计算5天升跌%
        for i in range(5, len(quotes)):
            current_quote = quotes[i]
            prev_quote = quotes[i-5]  # 5天前的数据
            
            if current_quote.close and prev_quote.close and prev_quote.close > 0:
                five_day_change = ((current_quote.close - prev_quote.close) / prev_quote.close) * 100
                current_quote.five_day_change_percent = round(five_day_change, 2)
        
        db.commit()
        return True
        
    except Exception as e:
        db.rollback()
        print(f"计算股票 {stock_code} 的5天升跌%失败: {e}")
        return False

@router.get("/strategy_types")
def get_strategy_types():
    """获取可用的策略类型"""
    return {
        "strategy_types": [
            "买入信号",
            "卖出信号", 
            "观察",
            "持有",
            "加仓",
            "减仓",
            "止损",
            "止盈"
        ],
        "risk_levels": [
            "低",
            "中",
            "高"
        ]
    }
