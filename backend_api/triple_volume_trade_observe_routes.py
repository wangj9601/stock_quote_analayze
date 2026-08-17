"""
用户 3倍量策略交易观察股：薄封装，读写走统一 trade_observe_service（source=triple_volume）。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api import trade_observe_service as svc
from backend_api.auth import get_current_user
from backend_api.database import get_db
from backend_api.models import TradeObserveStock, User

router = APIRouter(
    prefix="/api/stock/triple-volume-trade-observe",
    tags=["triple-volume-trade-observe"],
)

_SOURCE = svc.SOURCE_TRIPLE_VOLUME


class TvoTradeObserveAddRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    market: Optional[str] = Field(None, description="CN 或 HK，可省略由代码推断")
    name: Optional[str] = None
    observe_trade_date: Optional[str] = Field(None, description="观察日 YYYY-MM-DD")
    snapshot: Optional[Dict[str, Any]] = None


class TvoTradeObserveItem(BaseModel):
    id: int
    market: str
    code: str
    name: Optional[str]
    observe_trade_date: Optional[str]
    snapshot: Optional[Dict[str, Any]]
    created_at: str
    updated_at: str


class TvoTradeObserveListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[TvoTradeObserveItem]


def _parse_observe_date_optional(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw).strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="observe_trade_date 格式应为 YYYY-MM-DD")


def _observe_date_from_body(body: TvoTradeObserveAddRequest) -> Optional[date]:
    if body.observe_trade_date:
        return _parse_observe_date_optional(body.observe_trade_date)
    snap = body.snapshot if isinstance(body.snapshot, dict) else None
    if snap:
        for key in ("observe_trade_date", "signal_date", "date"):
            raw = snap.get(key)
            if raw:
                return _parse_observe_date_optional(str(raw))
    return None


def _row_to_item(r: TradeObserveStock) -> TvoTradeObserveItem:
    snap = r.signal_snapshot_json if isinstance(r.signal_snapshot_json, dict) else None
    ob = svc.resolve_signal_date_str(r.signal_date, snap)
    return TvoTradeObserveItem(
        id=r.id,
        market=r.market or "CN",
        code=r.code,
        name=r.name,
        observe_trade_date=ob,
        snapshot=snap,
        created_at=r.created_at.isoformat() if r.created_at else "",
        updated_at=r.updated_at.isoformat() if r.updated_at else "",
    )


@router.get("/list", response_model=TvoTradeObserveListResponse)
def list_tvo_trade_observe(
    page: int = 1,
    page_size: int = 200,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page = max(1, int(page))
    page_size = min(500, max(1, int(page_size)))
    total, rows = svc.list_observe(
        db, user.id, source=_SOURCE, page=page, page_size=page_size
    )
    return TvoTradeObserveListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[_row_to_item(r) for r in rows],
    )


@router.get("/codes", response_model=List[str])
def list_tvo_trade_observe_codes(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return svc.list_observe_codes(db, user.id, source=_SOURCE)


@router.post("/add", response_model=TvoTradeObserveItem)
def add_tvo_trade_observe(
    body: TvoTradeObserveAddRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    signal_date = _observe_date_from_body(body)
    row = svc.add_observe(
        db,
        user,
        source=_SOURCE,
        code=body.code,
        market=body.market,
        name=body.name,
        signal_date=signal_date,
        snapshot=body.snapshot if isinstance(body.snapshot, dict) else None,
        extra=None,
        require_signal_date=False,
    )
    return _row_to_item(row)


@router.delete("/{item_id}")
def remove_tvo_trade_observe(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc.remove_observe(db, user, item_id, source=_SOURCE)
    return {"ok": True, "id": item_id}
