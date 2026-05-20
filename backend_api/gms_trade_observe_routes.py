"""
用户 GMS 交易观察股：网站选股页「交易观察」加入 / 列表 / 移除。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.auth import get_current_user
from backend_api.database import get_db
from backend_api.models import GmsTradeObserveStock, User

router = APIRouter(prefix="/api/stock/gms-trade-observe", tags=["gms-trade-observe"])


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


class GmsTradeObserveAddRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    market: Optional[str] = Field(None, description="CN 或 HK，可省略由代码推断")
    name: Optional[str] = None
    signal_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    snapshot: Optional[Dict[str, Any]] = None


class GmsTradeObserveItem(BaseModel):
    id: int
    market: str
    code: str
    name: Optional[str]
    signal_date: Optional[str]
    snapshot: Optional[Dict[str, Any]]
    created_at: str
    updated_at: str


class GmsTradeObserveListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[GmsTradeObserveItem]


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
        for key in ("signal_date", "indicator_date", "search_date", "d20_date", "date"):
            raw = snapshot.get(key)
            if raw:
                return str(raw).strip()[:10]
    return None


def _parse_signal_date_optional(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw).strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="signal_date 格式应为 YYYY-MM-DD")


def _signal_date_from_body(body: GmsTradeObserveAddRequest) -> Optional[date]:
    if body.signal_date:
        return _parse_signal_date_optional(body.signal_date)
    snap = body.snapshot if isinstance(body.snapshot, dict) else None
    if snap:
        for key in ("signal_date", "indicator_date", "search_date", "d20_date", "date"):
            raw = snap.get(key)
            if raw:
                return _parse_signal_date_optional(str(raw))
    return None


def _row_to_item(r: GmsTradeObserveStock) -> GmsTradeObserveItem:
    snap = r.signal_snapshot_json if isinstance(r.signal_snapshot_json, dict) else None
    sd = _resolve_signal_date_str(r.signal_date, snap)
    return GmsTradeObserveItem(
        id=r.id,
        market=r.market or "CN",
        code=r.code,
        name=r.name,
        signal_date=sd,
        snapshot=snap,
        created_at=r.created_at.isoformat() if r.created_at else "",
        updated_at=r.updated_at.isoformat() if r.updated_at else "",
    )


@router.get("/list", response_model=GmsTradeObserveListResponse)
def list_gms_trade_observe(
    page: int = 1,
    page_size: int = 200,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page = max(1, int(page))
    page_size = min(500, max(1, int(page_size)))
    q = db.query(GmsTradeObserveStock).filter(GmsTradeObserveStock.user_id == user.id)
    total = q.count()
    rows = (
        q.order_by(GmsTradeObserveStock.updated_at.desc(), GmsTradeObserveStock.code)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return GmsTradeObserveListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[_row_to_item(r) for r in rows],
    )


@router.get("/codes", response_model=List[str])
def list_gms_trade_observe_codes(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """当前用户已加入观察的 code 列表（用于信号列表按钮态）。"""
    rows = (
        db.query(GmsTradeObserveStock.code, GmsTradeObserveStock.market)
        .filter(GmsTradeObserveStock.user_id == user.id)
        .all()
    )
    return [f"{(m or 'CN').upper()}:{c}" for c, m in rows]


@router.post("/add", response_model=GmsTradeObserveItem)
def add_gms_trade_observe(
    body: GmsTradeObserveAddRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    code = _normalize_code(body.code)
    if not code:
        raise HTTPException(status_code=400, detail="股票代码无效")
    market = _normalize_market(body.market, code)
    sig_date = _signal_date_from_body(body)
    if sig_date is None:
        raise HTTPException(
            status_code=400,
            detail="缺少 signal_date：请传入信号对应交易日（与 GMS 筛选基准日一致）",
        )

    existing = (
        db.query(GmsTradeObserveStock)
        .filter(
            GmsTradeObserveStock.user_id == user.id,
            GmsTradeObserveStock.market == market,
            GmsTradeObserveStock.code == code,
        )
        .first()
    )
    now = datetime.now()
    if existing:
        existing.name = body.name or existing.name
        existing.signal_snapshot_json = body.snapshot if body.snapshot is not None else existing.signal_snapshot_json
        existing.signal_date = sig_date
        existing.updated_at = now
        db.commit()
        db.refresh(existing)
        return _row_to_item(existing)

    row = GmsTradeObserveStock(
        user_id=user.id,
        market=market,
        code=code,
        name=body.name,
        signal_snapshot_json=body.snapshot,
        signal_date=sig_date,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _row_to_item(row)


@router.delete("/{item_id}")
def remove_gms_trade_observe(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(GmsTradeObserveStock)
        .filter(GmsTradeObserveStock.id == item_id, GmsTradeObserveStock.user_id == user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(row)
    db.commit()
    return {"success": True, "message": "已移出交易观察列表"}
