"""
用户 GMS 正式交易：薄封装，读写走统一 trade_observe_service（source=gms）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.auth import get_current_user
from backend_api.database import get_db
from backend_api.gms_trade_observe_routes import _resolve_signal_date_str
from backend_api.models import FormalTrade, User
from backend_api import trade_observe_service as svc

router = APIRouter(prefix="/api/stock/gms-formal-trade", tags=["gms-formal-trade"])

SOURCE = svc.SOURCE_GMS
TradeStatus = Literal["open", "closed"]


def ensure_gms_formal_trade_pnl_columns(db: Session) -> None:
    """兼容旧调用：统一表已含 pnl 列。"""
    _ = db


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


def _row_to_item(r: FormalTrade) -> GmsFormalTradeItem:
    snap = r.signal_snapshot_json if isinstance(r.signal_snapshot_json, dict) else None
    sd = _resolve_signal_date_str(r.signal_date, snap)
    pnl_amount = r.pnl_amount
    pnl_percent = r.pnl_percent
    if pnl_amount is None and pnl_percent is None and r.exit_price is not None and r.entry_price:
        pnl_amount, pnl_percent = svc.compute_formal_trade_pnl(
            r.entry_price,
            r.exit_price,
            r.position_lots,
            r.market,
        )
    elif pnl_percent is None and r.exit_price is not None and r.entry_price:
        _, pnl_percent = svc.compute_formal_trade_pnl(
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
    total, rows = svc.list_formal(
        db, user.id, source=SOURCE, status=status, page=page, page_size=page_size
    )
    return GmsFormalTradeListResponse(
        total=total,
        page=max(1, int(page)),
        page_size=min(500, max(1, int(page_size))),
        items=[_row_to_item(r) for r in rows],
    )


def list_user_formal_trade_code_keys(db: Session, user_id: int) -> List[str]:
    """当前用户正式交易 code 键（CN:000001，code 已归一化），供信号列表按钮态。"""
    return svc.list_formal_codes(db, user_id, source=SOURCE)


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
    row = svc.add_formal_from_observe(
        db,
        user,
        observe_id,
        entry_price=body.entry_price,
        position_lots=body.position_lots,
        notes=body.notes,
        source=SOURCE,
    )
    return _row_to_item(row)


@router.patch("/{trade_id}", response_model=GmsFormalTradeItem)
def update_gms_formal_trade(
    trade_id: int,
    body: GmsFormalTradeUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = svc.patch_formal(
        db,
        user,
        trade_id,
        source=SOURCE,
        entry_price=body.entry_price,
        position_lots=body.position_lots,
        exit_price=body.exit_price,
        status=body.status,
        notes=body.notes,
        reopen=body.reopen,
    )
    return _row_to_item(row)


@router.delete("/{trade_id}")
def delete_gms_formal_trade(
    trade_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc.delete_formal(db, user, trade_id, source=SOURCE)
    return {"success": True, "message": "已删除正式交易记录"}
