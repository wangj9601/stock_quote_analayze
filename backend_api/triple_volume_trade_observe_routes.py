"""
用户 3倍量策略交易观察股：日终爆量列表「交易观察」加入 / 列表 / 移除。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.auth import get_current_user
from backend_api.database import get_db
from backend_api.models import TripleVolumeTradeObserveStock, User

router = APIRouter(
    prefix="/api/stock/triple-volume-trade-observe",
    tags=["triple-volume-trade-observe"],
)


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


def _row_to_item(r: TripleVolumeTradeObserveStock) -> TvoTradeObserveItem:
    snap = r.observe_snapshot_json if isinstance(r.observe_snapshot_json, dict) else None
    ob = (
        r.observe_trade_date.strftime("%Y-%m-%d")
        if r.observe_trade_date and hasattr(r.observe_trade_date, "strftime")
        else (str(r.observe_trade_date)[:10] if r.observe_trade_date else None)
    )
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
    q = db.query(TripleVolumeTradeObserveStock).filter(
        TripleVolumeTradeObserveStock.user_id == user.id
    )
    total = q.count()
    rows = (
        q.order_by(
            TripleVolumeTradeObserveStock.updated_at.desc(),
            TripleVolumeTradeObserveStock.code,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
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
    """当前用户已加入观察的 code 列表（用于日终爆量列表按钮态）。"""
    rows = (
        db.query(TripleVolumeTradeObserveStock.code, TripleVolumeTradeObserveStock.market)
        .filter(TripleVolumeTradeObserveStock.user_id == user.id)
        .all()
    )
    return [f"{(m or 'CN').upper()}:{c}" for c, m in rows]


@router.post("/add", response_model=TvoTradeObserveItem)
def add_tvo_trade_observe(
    body: TvoTradeObserveAddRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    code = _normalize_code(body.code)
    if not code:
        raise HTTPException(status_code=400, detail="股票代码无效")
    market = _normalize_market(body.market, code)
    ob_date = _observe_date_from_body(body)
    if ob_date is None:
        raise HTTPException(status_code=400, detail="缺少 observe_trade_date（观察日）")

    existing = (
        db.query(TripleVolumeTradeObserveStock)
        .filter(
            TripleVolumeTradeObserveStock.user_id == user.id,
            TripleVolumeTradeObserveStock.market == market,
            TripleVolumeTradeObserveStock.code == code,
        )
        .first()
    )
    now = datetime.now()
    if existing:
        existing.name = body.name or existing.name
        existing.observe_snapshot_json = (
            body.snapshot if body.snapshot is not None else existing.observe_snapshot_json
        )
        existing.observe_trade_date = ob_date
        existing.updated_at = now
        db.commit()
        db.refresh(existing)
        return _row_to_item(existing)

    row = TripleVolumeTradeObserveStock(
        user_id=user.id,
        market=market,
        code=code,
        name=body.name,
        observe_snapshot_json=body.snapshot,
        observe_trade_date=ob_date,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _row_to_item(row)


@router.delete("/{item_id}")
def remove_tvo_trade_observe(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(TripleVolumeTradeObserveStock)
        .filter(
            TripleVolumeTradeObserveStock.id == item_id,
            TripleVolumeTradeObserveStock.user_id == user.id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(row)
    db.commit()
    return {"success": True, "message": "已移出3倍量交易观察列表"}
