# -*- coding: utf-8 -*-
"""统一正式交易 API：/api/stock/formal-trade"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.auth import get_current_user
from backend_api.database import get_db
from backend_api.models import FormalTrade, User
from backend_api import trade_observe_service as svc

router = APIRouter(prefix="/api/stock/formal-trade", tags=["formal-trade"])

TradeStatus = Literal["open", "closed"]


class FormalTradeFromObserveRequest(BaseModel):
    entry_price: float = Field(..., gt=0, description="入场价格")
    position_lots: int = Field(0, ge=0, description="仓位（手），GMS/URT 常用；其它来源可为 0")
    notes: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None
    source: Optional[str] = Field(None, description="可选，用于校验观察来源")


class FormalTradeUpdateRequest(BaseModel):
    entry_price: Optional[float] = Field(None, gt=0)
    position_lots: Optional[int] = Field(None, ge=0)
    exit_price: Optional[float] = Field(None, gt=0)
    status: Optional[TradeStatus] = None
    notes: Optional[str] = None
    reopen: Optional[bool] = Field(None, description="为 true 时清空出场价并恢复为持仓中")
    extra: Optional[Dict[str, Any]] = None
    source: Optional[str] = None


class FormalTradeItem(BaseModel):
    id: int
    market: str
    code: str
    name: Optional[str]
    source: str
    source_observe_id: Optional[int]
    entry_price: float
    position_lots: int
    exit_price: Optional[float]
    status: str
    signal_date: Optional[str]
    snapshot: Optional[Dict[str, Any]]
    notes: Optional[str]
    extra: Optional[Dict[str, Any]] = None
    entry_at: str
    exit_at: Optional[str]
    created_at: str
    updated_at: str
    pnl_amount: Optional[float] = None
    pnl_percent: Optional[float] = None


class FormalTradeListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[FormalTradeItem]


def _row_to_item(r: FormalTrade) -> FormalTradeItem:
    snap = r.signal_snapshot_json if isinstance(r.signal_snapshot_json, dict) else None
    extra = r.extra_json if isinstance(r.extra_json, dict) else None
    pnl_amount = r.pnl_amount
    pnl_percent = r.pnl_percent
    if pnl_amount is None and pnl_percent is None and r.exit_price is not None and r.entry_price:
        pnl_amount, pnl_percent = svc.compute_formal_trade_pnl(
            r.entry_price,
            r.exit_price,
            r.position_lots,
            r.market,
        )
    return FormalTradeItem(
        id=r.id,
        market=r.market or "CN",
        code=r.code,
        name=r.name,
        source=r.source,
        source_observe_id=r.source_observe_id,
        entry_price=float(r.entry_price),
        position_lots=int(r.position_lots or 0),
        exit_price=float(r.exit_price) if r.exit_price is not None else None,
        status=r.status or "open",
        signal_date=svc.resolve_signal_date_str(r.signal_date, snap),
        snapshot=snap,
        notes=r.notes,
        extra=extra,
        entry_at=r.entry_at.isoformat() if r.entry_at else "",
        exit_at=r.exit_at.isoformat() if r.exit_at else None,
        created_at=r.created_at.isoformat() if r.created_at else "",
        updated_at=r.updated_at.isoformat() if r.updated_at else "",
        pnl_amount=float(pnl_amount) if pnl_amount is not None else None,
        pnl_percent=float(pnl_percent) if pnl_percent is not None else None,
    )


@router.get("/list", response_model=FormalTradeListResponse)
def list_formal_trades(
    page: int = 1,
    page_size: int = 200,
    status: Optional[str] = None,
    source: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total, rows = svc.list_formal(
        db,
        user.id,
        source=source,
        status=status,
        page=page,
        page_size=page_size,
    )
    return FormalTradeListResponse(
        total=total,
        page=max(1, int(page)),
        page_size=min(500, max(1, int(page_size))),
        items=[_row_to_item(r) for r in rows],
    )


@router.get("/codes", response_model=List[str])
def list_formal_trade_codes(
    source: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return svc.list_formal_codes(db, user.id, source=source)


@router.post("/from-observe/{observe_id}", response_model=FormalTradeItem)
def create_from_observe(
    observe_id: int,
    body: FormalTradeFromObserveRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = svc.add_formal_from_observe(
        db,
        user,
        observe_id,
        entry_price=body.entry_price,
        position_lots=body.position_lots,
        notes=body.notes,
        source=body.source,
        extra=body.extra,
    )
    return _row_to_item(row)


@router.patch("/{trade_id}", response_model=FormalTradeItem)
def update_formal_trade(
    trade_id: int,
    body: FormalTradeUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = svc.patch_formal(
        db,
        user,
        trade_id,
        source=body.source,
        entry_price=body.entry_price,
        position_lots=body.position_lots,
        exit_price=body.exit_price,
        status=body.status,
        notes=body.notes,
        reopen=body.reopen,
        extra=body.extra,
    )
    return _row_to_item(row)


@router.delete("/{trade_id}")
def delete_formal_trade(
    trade_id: int,
    source: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc.delete_formal(db, user, trade_id, source=source)
    return {"success": True, "message": "已删除正式交易记录"}
