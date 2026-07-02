"""
用户 GMS 正式交易：从交易观察转入、列表、更新出场等。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.auth import get_current_user
from backend_api.database import get_db
from backend_api.gms_trade_observe_routes import (
    _archive_trade_observe_row,
    _normalize_code,
    _resolve_signal_date_str,
)
from backend_api.models import GmsFormalTrade, GmsTradeObserveStock, User

router = APIRouter(prefix="/api/stock/gms-formal-trade", tags=["gms-formal-trade"])

TradeStatus = Literal["open", "closed"]

# 与行情库「手」约定一致：A 股 / 港股默认 1 手 = 100 股
_DEFAULT_LOT_SIZE = 100


def _lot_size_for_market(market: Optional[str]) -> int:
    _ = (market or "").strip().upper()
    return _DEFAULT_LOT_SIZE


def _compute_formal_trade_pnl(
    entry_price: Optional[float],
    exit_price: Optional[float],
    position_lots: Optional[int],
    market: Optional[str],
) -> tuple[Optional[float], Optional[float]]:
    """计算盈亏金额（元）与盈亏比例（%）。"""
    if entry_price is None or exit_price is None:
        return None, None
    ep = float(entry_price)
    xp = float(exit_price)
    if ep <= 0:
        return None, None
    lots = max(0, int(position_lots or 0))
    shares = lots * _lot_size_for_market(market)
    pnl_amount = round((xp - ep) * shares, 2)
    pnl_percent = round((xp - ep) / ep * 100, 2)
    return pnl_amount, pnl_percent


def _sync_formal_trade_pnl(row: GmsFormalTrade) -> None:
    """平仓时写入盈亏；持仓中或重新开仓时清空。"""
    if (row.status or "open") == "closed" and row.exit_price is not None:
        amt, pct = _compute_formal_trade_pnl(
            row.entry_price,
            row.exit_price,
            row.position_lots,
            row.market,
        )
        row.pnl_amount = amt
        row.pnl_percent = pct
    else:
        row.pnl_amount = None
        row.pnl_percent = None


class GmsFormalTradeFromObserveRequest(BaseModel):
    entry_price: float = Field(..., gt=0, description="入场价格")
    position_lots: int = Field(..., ge=1, description="仓位（手）")
    notes: Optional[str] = None


class GmsFormalTradeUpdateRequest(BaseModel):
    entry_price: Optional[float] = Field(None, gt=0)
    position_lots: Optional[int] = Field(None, ge=1)
    exit_price: Optional[float] = Field(None, gt=0)
    status: Optional[TradeStatus] = None
    notes: Optional[str] = None
    reopen: Optional[bool] = Field(None, description="为 true 时清空出场价并恢复为持仓中")


class GmsFormalTradeItem(BaseModel):
    id: int
    market: str
    code: str
    name: Optional[str]
    source_observe_id: Optional[int]
    entry_price: float
    position_lots: int
    exit_price: Optional[float]
    status: str
    signal_date: Optional[str]
    snapshot: Optional[Dict[str, Any]]
    notes: Optional[str]
    entry_at: str
    exit_at: Optional[str]
    created_at: str
    updated_at: str
    pnl_amount: Optional[float] = None
    pnl_percent: Optional[float] = None


class GmsFormalTradeListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[GmsFormalTradeItem]


def _row_to_item(r: GmsFormalTrade) -> GmsFormalTradeItem:
    snap = r.signal_snapshot_json if isinstance(r.signal_snapshot_json, dict) else None
    sd = _resolve_signal_date_str(r.signal_date, snap)
    pnl_amount = r.pnl_amount
    pnl_percent = r.pnl_percent
    if pnl_amount is None and pnl_percent is None and r.exit_price is not None and r.entry_price:
        pnl_amount, pnl_percent = _compute_formal_trade_pnl(
            r.entry_price,
            r.exit_price,
            r.position_lots,
            r.market,
        )
    elif pnl_percent is None and r.exit_price is not None and r.entry_price:
        _, pnl_percent = _compute_formal_trade_pnl(
            r.entry_price,
            r.exit_price,
            r.position_lots,
            r.market,
        )
    return GmsFormalTradeItem(
        id=r.id,
        market=r.market or "CN",
        code=r.code,
        name=r.name,
        source_observe_id=r.source_observe_id,
        entry_price=float(r.entry_price),
        position_lots=int(r.position_lots or 0),
        exit_price=float(r.exit_price) if r.exit_price is not None else None,
        status=r.status or "open",
        signal_date=sd,
        snapshot=snap,
        notes=r.notes,
        entry_at=r.entry_at.isoformat() if r.entry_at else "",
        exit_at=r.exit_at.isoformat() if r.exit_at else None,
        created_at=r.created_at.isoformat() if r.created_at else "",
        updated_at=r.updated_at.isoformat() if r.updated_at else "",
        pnl_amount=float(pnl_amount) if pnl_amount is not None else None,
        pnl_percent=float(pnl_percent) if pnl_percent is not None else None,
    )


@router.get("/list", response_model=GmsFormalTradeListResponse)
def list_gms_formal_trades(
    page: int = 1,
    page_size: int = 200,
    status: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page = max(1, int(page))
    page_size = min(500, max(1, int(page_size)))
    q = db.query(GmsFormalTrade).filter(GmsFormalTrade.user_id == user.id)
    st = (status or "").strip().lower()
    if st in ("open", "closed"):
        q = q.filter(GmsFormalTrade.status == st)
    total = q.count()
    rows = (
        q.order_by(GmsFormalTrade.entry_at.desc(), GmsFormalTrade.code)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return GmsFormalTradeListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[_row_to_item(r) for r in rows],
    )


def list_user_formal_trade_code_keys(db: Session, user_id: int) -> List[str]:
    """当前用户正式交易 code 键（CN:000001，code 已归一化），供信号列表按钮态。"""
    rows = (
        db.query(GmsFormalTrade.market, GmsFormalTrade.code)
        .filter(GmsFormalTrade.user_id == user_id)
        .all()
    )
    return [
        f"{(m or 'CN').upper()}:{_normalize_code(c)}"
        for m, c in rows
        if c
    ]


@router.get("/codes", response_model=List[str])
def list_gms_formal_trade_codes(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """当前用户正式交易 code 列表（用于信号列表「已观察」按钮态）。"""
    return list_user_formal_trade_code_keys(db, user.id)


@router.post("/from-observe/{observe_id}", response_model=GmsFormalTradeItem)
def create_from_observe(
    observe_id: int,
    body: GmsFormalTradeFromObserveRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """从交易观察记录转入正式交易。"""
    observe = (
        db.query(GmsTradeObserveStock)
        .filter(GmsTradeObserveStock.id == observe_id, GmsTradeObserveStock.user_id == user.id)
        .first()
    )
    if not observe:
        raise HTTPException(status_code=404, detail="交易观察记录不存在")
    now = datetime.now()
    existing_trade = (
        db.query(GmsFormalTrade)
        .filter(
            GmsFormalTrade.user_id == user.id,
            GmsFormalTrade.market == observe.market,
            GmsFormalTrade.code == observe.code,
        )
        .first()
    )
    if existing_trade:
        _archive_trade_observe_row(db, observe, removed_at=now)
        db.delete(observe)
        db.commit()
        return _row_to_item(existing_trade)
    source_observe_id = observe.id
    row = GmsFormalTrade(
        user_id=user.id,
        market=observe.market,
        code=observe.code,
        name=observe.name,
        source_observe_id=source_observe_id,
        entry_price=float(body.entry_price),
        position_lots=int(body.position_lots),
        exit_price=None,
        status="open",
        signal_date=observe.signal_date,
        signal_snapshot_json=observe.signal_snapshot_json,
        notes=(body.notes or "").strip() or None,
        entry_at=now,
        exit_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    _archive_trade_observe_row(db, observe, removed_at=now)
    db.delete(observe)
    db.commit()
    db.refresh(row)
    return _row_to_item(row)


@router.patch("/{trade_id}", response_model=GmsFormalTradeItem)
def update_gms_formal_trade(
    trade_id: int,
    body: GmsFormalTradeUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(GmsFormalTrade)
        .filter(GmsFormalTrade.id == trade_id, GmsFormalTrade.user_id == user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="正式交易记录不存在")
    now = datetime.now()
    was_closed = (row.status or "open") == "closed"
    if body.entry_price is not None:
        row.entry_price = float(body.entry_price)
    if body.position_lots is not None:
        row.position_lots = int(body.position_lots)
    if body.notes is not None:
        row.notes = body.notes.strip() or None
    if body.reopen:
        row.exit_price = None
        row.status = "open"
        row.exit_at = None
    elif body.exit_price is not None:
        row.exit_price = float(body.exit_price)
        if not was_closed:
            row.status = "closed"
            row.exit_at = now
    if body.status is not None and not body.reopen:
        row.status = body.status
        if body.status == "closed" and row.exit_at is None:
            row.exit_at = now
        if body.status == "open":
            row.exit_at = None
            if body.exit_price is None:
                row.exit_price = None
    _sync_formal_trade_pnl(row)
    row.updated_at = now
    db.commit()
    db.refresh(row)
    return _row_to_item(row)


@router.delete("/{trade_id}")
def delete_gms_formal_trade(
    trade_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(GmsFormalTrade)
        .filter(GmsFormalTrade.id == trade_id, GmsFormalTrade.user_id == user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="正式交易记录不存在")
    db.delete(row)
    db.commit()
    return {"success": True, "message": "已删除正式交易记录"}
