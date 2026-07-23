"""
用户 URT 交易观察股：网站选股页「观察」加入 / 列表 / 移除 / 历史。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.auth import get_current_user
from backend_api.database import get_db
from backend_api.models import (
    UrtFormalTrade,
    UrtTradeObserveHistory,
    UrtTradeObserveStock,
    User,
)
from backend_api.permissions import require_permission

router = APIRouter(prefix="/api/stock/urt-trade-observe", tags=["urt-trade-observe"])


def _normalize_market(market: Optional[str], code: str) -> str:
    m = (market or "").strip().upper()
    if m in ("CN", "HK"):
        return m
    c = str(code or "").strip()
    if len(c) == 5 and c.isdigit():
        return "HK"
    return "CN"


def _normalize_code(code: str) -> str:
    c = str(code or "").strip()
    if len(c) == 5 and c.isdigit():
        return c.zfill(5)
    if c.isdigit() and len(c) <= 6:
        return c.zfill(6)
    return c


def _parse_signal_date_optional(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw).strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="signal_date 格式应为 YYYY-MM-DD")


def _resolve_signal_date_str(
    stored: Optional[date],
    snapshot: Optional[Dict[str, Any]],
) -> Optional[str]:
    if stored and hasattr(stored, "strftime"):
        return stored.strftime("%Y-%m-%d")
    if stored:
        s = str(stored).strip()[:10]
        return s if s else None
    if isinstance(snapshot, dict):
        for key in ("signal_date", "search_date", "date"):
            raw = snapshot.get(key)
            if raw:
                return str(raw).strip()[:10]
    return None


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


def _observe_row_key(row: UrtTradeObserveStock) -> tuple[str, str]:
    market = (row.market or "CN").upper()
    return market, _normalize_code(row.code)


def _formal_trade_keys_for_user(db: Session, user_id: int) -> set[tuple[str, str]]:
    rows = (
        db.query(UrtFormalTrade.market, UrtFormalTrade.code)
        .filter(UrtFormalTrade.user_id == user_id)
        .all()
    )
    return {
        ((m or "CN").upper(), _normalize_code(c))
        for m, c in rows
        if c
    }


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


def _row_to_item(r: UrtTradeObserveStock) -> UrtTradeObserveItem:
    snap = r.signal_snapshot_json if isinstance(r.signal_snapshot_json, dict) else None
    return UrtTradeObserveItem(
        id=r.id,
        market=r.market or "CN",
        code=r.code,
        name=r.name,
        signal_date=_resolve_signal_date_str(r.signal_date, snap),
        snapshot=snap,
        config_id=r.config_id,
        created_at=r.created_at.isoformat() if r.created_at else "",
        updated_at=r.updated_at.isoformat() if r.updated_at else "",
    )


def _archive_trade_observe_row(
    db: Session,
    row: UrtTradeObserveStock,
    *,
    removed_at: Optional[datetime] = None,
) -> UrtTradeObserveHistory:
    now = removed_at or datetime.now()
    hist = UrtTradeObserveHistory(
        user_id=row.user_id,
        market=row.market,
        code=row.code,
        name=row.name,
        signal_snapshot_json=row.signal_snapshot_json,
        signal_date=row.signal_date,
        config_id=row.config_id,
        observe_created_at=row.created_at,
        observe_updated_at=row.updated_at,
        source_observe_id=row.id,
        removed_at=now,
    )
    db.add(hist)
    return hist


def _history_row_to_item(r: UrtTradeObserveHistory) -> UrtTradeObserveHistoryItem:
    snap = r.signal_snapshot_json if isinstance(r.signal_snapshot_json, dict) else None
    return UrtTradeObserveHistoryItem(
        id=r.id,
        market=r.market or "CN",
        code=r.code,
        name=r.name,
        signal_date=_resolve_signal_date_str(r.signal_date, snap),
        snapshot=snap,
        config_id=r.config_id,
        observe_created_at=r.observe_created_at.isoformat() if r.observe_created_at else None,
        observe_updated_at=r.observe_updated_at.isoformat() if r.observe_updated_at else None,
        removed_at=r.removed_at.isoformat() if r.removed_at else "",
        source_observe_id=r.source_observe_id,
    )


def _purge_observe_rows_already_formal_traded(db: Session, user_id: int) -> int:
    formal_keys = _formal_trade_keys_for_user(db, user_id)
    if not formal_keys:
        return 0
    rows = (
        db.query(UrtTradeObserveStock)
        .filter(UrtTradeObserveStock.user_id == user_id)
        .all()
    )
    removed = 0
    now = datetime.now()
    for row in rows:
        if _observe_row_key(row) in formal_keys:
            _archive_trade_observe_row(db, row, removed_at=now)
            db.delete(row)
            removed += 1
    if removed:
        db.commit()
    return removed


def list_user_trade_observe_code_keys(db: Session, user_id: int) -> List[str]:
    _purge_observe_rows_already_formal_traded(db, user_id)
    rows = (
        db.query(UrtTradeObserveStock.market, UrtTradeObserveStock.code)
        .filter(UrtTradeObserveStock.user_id == user_id)
        .all()
    )
    return [
        f"{(m or 'CN').upper()}:{_normalize_code(c)}"
        for m, c in rows
        if c
    ]


@router.get("/list", response_model=UrtTradeObserveListResponse)
def list_urt_trade_observe(
    page: int = 1,
    page_size: int = 200,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page = max(1, int(page))
    page_size = min(500, max(1, int(page_size)))
    _purge_observe_rows_already_formal_traded(db, user.id)
    q = db.query(UrtTradeObserveStock).filter(UrtTradeObserveStock.user_id == user.id)
    total = q.count()
    rows = (
        q.order_by(
            UrtTradeObserveStock.updated_at.desc(),
            UrtTradeObserveStock.code,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return UrtTradeObserveListResponse(
        total=total,
        page=page,
        page_size=page_size,
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
    code = _normalize_code(body.code)
    if not code:
        raise HTTPException(status_code=400, detail="股票代码无效")
    market = _normalize_market(body.market, code)
    sig_date = _signal_date_from_body(body)
    if sig_date is None:
        raise HTTPException(
            status_code=400,
            detail="缺少 signal_date：请传入信号对应交易日",
        )

    existing = (
        db.query(UrtTradeObserveStock)
        .filter(
            UrtTradeObserveStock.user_id == user.id,
            UrtTradeObserveStock.market == market,
            UrtTradeObserveStock.code == code,
        )
        .first()
    )
    now = datetime.now()
    snapshot = body.snapshot if isinstance(body.snapshot, dict) else None

    if existing:
        existing.name = body.name or existing.name
        existing.signal_snapshot_json = snapshot
        existing.signal_date = sig_date
        existing.config_id = body.config_id if body.config_id is not None else existing.config_id
        existing.updated_at = now
        db.commit()
        db.refresh(existing)
        return _row_to_item(existing)

    row = UrtTradeObserveStock(
        user_id=user.id,
        market=market,
        code=code,
        name=body.name,
        signal_snapshot_json=snapshot,
        signal_date=sig_date,
        config_id=body.config_id,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _row_to_item(row)


@router.get("/history", response_model=UrtTradeObserveHistoryListResponse)
def list_urt_trade_observe_history(
    page: int = 1,
    page_size: int = 200,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page = max(1, int(page))
    page_size = min(500, max(1, int(page_size)))
    q = db.query(UrtTradeObserveHistory).filter(UrtTradeObserveHistory.user_id == user.id)
    total = q.count()
    rows = (
        q.order_by(UrtTradeObserveHistory.removed_at.desc(), UrtTradeObserveHistory.code)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return UrtTradeObserveHistoryListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[_history_row_to_item(r) for r in rows],
    )


@router.delete("/{item_id}")
def remove_urt_trade_observe(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _perm: None = Depends(require_permission("channel.screening.tab.urt.btn.observe")),
):
    row = (
        db.query(UrtTradeObserveStock)
        .filter(UrtTradeObserveStock.id == item_id, UrtTradeObserveStock.user_id == user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    hist = _archive_trade_observe_row(db, row)
    db.delete(row)
    db.commit()
    db.refresh(hist)
    return {
        "success": True,
        "message": "已移出交易观察列表并归档",
        "history_id": hist.id,
    }
