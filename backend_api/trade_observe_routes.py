# -*- coding: utf-8 -*-
"""统一交易观察 API：/api/stock/trade-observe"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.auth import get_current_user
from backend_api.database import get_db
from backend_api.models import TradeObserveHistory, TradeObserveStock, User
from backend_api import trade_observe_service as svc

router = APIRouter(prefix="/api/stock/trade-observe", tags=["trade-observe"])


class TradeObserveAddRequest(BaseModel):
    source: str = Field(..., description="gms|urt|sbbr|rpe|triple_volume|stock_analysis|gann_trend")
    code: str = Field(..., min_length=1, max_length=20)
    market: Optional[str] = Field(None, description="CN 或 HK")
    name: Optional[str] = None
    signal_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    snapshot: Optional[Dict[str, Any]] = None
    extra: Optional[Dict[str, Any]] = None


class TradeObserveItem(BaseModel):
    id: int
    market: str
    code: str
    name: Optional[str]
    source: str
    signal_date: Optional[str]
    snapshot: Optional[Dict[str, Any]]
    extra: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: str


class TradeObserveListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[TradeObserveItem]


class TradeObserveHistoryItem(BaseModel):
    id: int
    market: str
    code: str
    name: Optional[str]
    source: str
    signal_date: Optional[str]
    snapshot: Optional[Dict[str, Any]]
    extra: Optional[Dict[str, Any]] = None
    observe_created_at: Optional[str]
    observe_updated_at: Optional[str]
    removed_at: str
    source_observe_id: Optional[int]


class TradeObserveHistoryListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[TradeObserveHistoryItem]


def _row_to_item(r: TradeObserveStock) -> TradeObserveItem:
    snap = r.signal_snapshot_json if isinstance(r.signal_snapshot_json, dict) else None
    extra = r.extra_json if isinstance(r.extra_json, dict) else None
    return TradeObserveItem(
        id=r.id,
        market=r.market or "CN",
        code=r.code,
        name=r.name,
        source=r.source,
        signal_date=svc.resolve_signal_date_str(r.signal_date, snap),
        snapshot=snap,
        extra=extra,
        created_at=r.created_at.isoformat() if r.created_at else "",
        updated_at=r.updated_at.isoformat() if r.updated_at else "",
    )


def _history_to_item(r: TradeObserveHistory) -> TradeObserveHistoryItem:
    snap = r.signal_snapshot_json if isinstance(r.signal_snapshot_json, dict) else None
    extra = r.extra_json if isinstance(r.extra_json, dict) else None
    return TradeObserveHistoryItem(
        id=r.id,
        market=r.market or "CN",
        code=r.code,
        name=r.name,
        source=r.source,
        signal_date=svc.resolve_signal_date_str(r.signal_date, snap),
        snapshot=snap,
        extra=extra,
        observe_created_at=r.observe_created_at.isoformat() if r.observe_created_at else None,
        observe_updated_at=r.observe_updated_at.isoformat() if r.observe_updated_at else None,
        removed_at=r.removed_at.isoformat() if r.removed_at else "",
        source_observe_id=r.source_observe_id,
    )


@router.get("/list", response_model=TradeObserveListResponse)
def list_trade_observe(
    page: int = 1,
    page_size: int = 200,
    source: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total, rows = svc.list_observe(
        db, user.id, source=source, page=page, page_size=page_size
    )
    return TradeObserveListResponse(
        total=total,
        page=max(1, int(page)),
        page_size=min(500, max(1, int(page_size))),
        items=[_row_to_item(r) for r in rows],
    )


@router.get("/codes", response_model=List[str])
def list_trade_observe_codes(
    source: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return svc.list_observe_codes(db, user.id, source=source)


@router.post("/add", response_model=TradeObserveItem)
def add_trade_observe(
    body: TradeObserveAddRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sig: Optional[date] = None
    if body.signal_date:
        sig = svc.parse_signal_date_optional(body.signal_date)
    row = svc.add_observe(
        db,
        user,
        source=body.source,
        code=body.code,
        market=body.market,
        name=body.name,
        signal_date=sig,
        snapshot=body.snapshot,
        extra=body.extra,
        require_signal_date=False,
    )
    return _row_to_item(row)


@router.get("/history", response_model=TradeObserveHistoryListResponse)
def list_trade_observe_history(
    page: int = 1,
    page_size: int = 200,
    source: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total, rows = svc.list_history(
        db, user.id, source=source, page=page, page_size=page_size
    )
    return TradeObserveHistoryListResponse(
        total=total,
        page=max(1, int(page)),
        page_size=min(500, max(1, int(page_size))),
        items=[_history_to_item(r) for r in rows],
    )


@router.delete("/{item_id}")
def remove_trade_observe(
    item_id: int,
    source: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    hist = svc.remove_observe(db, user, item_id, source=source)
    return {
        "success": True,
        "message": "已移出交易观察列表并归档",
        "history_id": hist.id,
    }
