"""
用户 URT 交易观察股：薄封装，读写走统一 trade_observe_service（source=urt）。
响应形状保持旧前端兼容（config_id 来自 extra_json）。
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.auth import get_current_user
from backend_api.database import get_db
from backend_api.models import TradeObserveHistory, TradeObserveStock, User
from backend_api.permissions import require_permission
from backend_api import trade_observe_service as svc

router = APIRouter(prefix="/api/stock/urt-trade-observe", tags=["urt-trade-observe"])

SOURCE = svc.SOURCE_URT


def _normalize_market(market: Optional[str], code: str) -> str:
    return svc.normalize_market(market, code)


def _normalize_code(code: str) -> str:
    return svc.normalize_code(code)


def _parse_signal_date_optional(raw: Optional[str]) -> Optional[date]:
    return svc.parse_signal_date_optional(raw)


def _resolve_signal_date_str(
    stored: Optional[date],
    snapshot: Optional[Dict[str, Any]],
) -> Optional[str]:
    return svc.resolve_signal_date_str(stored, snapshot)


def _signal_date_from_body(body: "UrtTradeObserveAddRequest") -> Optional[date]:
    if body.signal_date:
        return _parse_signal_date_optional(body.signal_date)
    snap = body.snapshot if isinstance(body.snapshot, dict) else None
    if snap:
        for key in ("signal_date", "search_date", "date"):
            raw = snap.get(key)
            if raw:
                return _parse_signal_date_optional(str(raw))
    return None


def _extra_config_id(extra: Any) -> Optional[int]:
    if not isinstance(extra, dict):
        return None
    raw = extra.get("config_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


class UrtTradeObserveAddRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    market: Optional[str] = Field(None, description="CN 或 HK，可省略由代码推断")
    name: Optional[str] = None
    signal_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    snapshot: Optional[Dict[str, Any]] = None
    config_id: Optional[int] = Field(None, description="URT 策略参数版本 ID")


class UrtTradeObserveItem(BaseModel):
    id: int
    market: str
    code: str
    name: Optional[str]
    signal_date: Optional[str]
    snapshot: Optional[Dict[str, Any]]
    config_id: Optional[int]
    created_at: str
    updated_at: str


class UrtTradeObserveListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[UrtTradeObserveItem]


class UrtTradeObserveHistoryItem(BaseModel):
    id: int
    market: str
    code: str
    name: Optional[str]
    signal_date: Optional[str]
    snapshot: Optional[Dict[str, Any]]
    config_id: Optional[int]
    observe_created_at: Optional[str]
    observe_updated_at: Optional[str]
    removed_at: str
    source_observe_id: Optional[int]


class UrtTradeObserveHistoryListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[UrtTradeObserveHistoryItem]


def _row_to_item(r: TradeObserveStock) -> UrtTradeObserveItem:
    snap = r.signal_snapshot_json if isinstance(r.signal_snapshot_json, dict) else None
    return UrtTradeObserveItem(
        id=r.id,
        market=r.market or "CN",
        code=r.code,
        name=r.name,
        signal_date=_resolve_signal_date_str(r.signal_date, snap),
        snapshot=snap,
        config_id=_extra_config_id(r.extra_json),
        created_at=r.created_at.isoformat() if r.created_at else "",
        updated_at=r.updated_at.isoformat() if r.updated_at else "",
    )


def _history_row_to_item(r: TradeObserveHistory) -> UrtTradeObserveHistoryItem:
    snap = r.signal_snapshot_json if isinstance(r.signal_snapshot_json, dict) else None
    return UrtTradeObserveHistoryItem(
        id=r.id,
        market=r.market or "CN",
        code=r.code,
        name=r.name,
        signal_date=_resolve_signal_date_str(r.signal_date, snap),
        snapshot=snap,
        config_id=_extra_config_id(r.extra_json),
        observe_created_at=r.observe_created_at.isoformat() if r.observe_created_at else None,
        observe_updated_at=r.observe_updated_at.isoformat() if r.observe_updated_at else None,
        removed_at=r.removed_at.isoformat() if r.removed_at else "",
        source_observe_id=r.source_observe_id,
    )


def list_user_trade_observe_code_keys(db: Session, user_id: int) -> List[str]:
    svc.purge_observe_already_formal(db, user_id, source=SOURCE)
    return svc.list_observe_codes(db, user_id, source=SOURCE)


@router.get("/list", response_model=UrtTradeObserveListResponse)
def list_urt_trade_observe(
    page: int = 1,
    page_size: int = 200,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc.purge_observe_already_formal(db, user.id, source=SOURCE)
    total, rows = svc.list_observe(
        db, user.id, source=SOURCE, page=page, page_size=page_size
    )
    return UrtTradeObserveListResponse(
        total=total,
        page=max(1, int(page)),
        page_size=min(500, max(1, int(page_size))),
        items=[_row_to_item(r) for r in rows],
    )


@router.get("/codes", response_model=List[str])
def list_urt_trade_observe_codes(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_user_trade_observe_code_keys(db, user.id)


@router.post("/add", response_model=UrtTradeObserveItem)
def add_urt_trade_observe(
    body: UrtTradeObserveAddRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _perm: None = Depends(require_permission("channel.screening.tab.urt.btn.observe")),
):
    sig_date = _signal_date_from_body(body)
    if sig_date is None:
        raise HTTPException(
            status_code=400,
            detail="缺少 signal_date：请传入信号对应交易日",
        )
    extra: Optional[Dict[str, Any]] = None
    if body.config_id is not None:
        extra = {"config_id": int(body.config_id)}
    row = svc.add_observe(
        db,
        user,
        source=SOURCE,
        code=body.code,
        market=body.market,
        name=body.name,
        signal_date=sig_date,
        snapshot=body.snapshot if isinstance(body.snapshot, dict) else None,
        extra=extra,
        require_signal_date=True,
    )
    return _row_to_item(row)


@router.get("/history", response_model=UrtTradeObserveHistoryListResponse)
def list_urt_trade_observe_history(
    page: int = 1,
    page_size: int = 200,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total, rows = svc.list_history(
        db, user.id, source=SOURCE, page=page, page_size=page_size
    )
    return UrtTradeObserveHistoryListResponse(
        total=total,
        page=max(1, int(page)),
        page_size=min(500, max(1, int(page_size))),
        items=[_history_row_to_item(r) for r in rows],
    )


@router.delete("/{item_id}")
def remove_urt_trade_observe(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _perm: None = Depends(require_permission("channel.screening.tab.urt.btn.observe")),
):
    hist = svc.remove_observe(db, user, item_id, source=SOURCE)
    return {
        "success": True,
        "message": "已移出交易观察列表并归档",
        "history_id": hist.id,
    }
