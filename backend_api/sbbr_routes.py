"""SBBR 用户端：储备箱 / 交易观察 / 正式交易。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.auth import get_current_user
from backend_api.database import get_db
from backend_api.models import (
    SBBRFormalTrade,
    SBBRReserveBox,
    SBBRTradeObserveStock,
    User,
)
from backend_core.strategies.sbbr.config import SBBRConfigManager
from backend_core.strategies.sbbr.strategy_engine import SBBRStrategyEngine

router = APIRouter(prefix="/api/sbbr", tags=["sbbr"])


def _norm_code(code: str) -> str:
    s = str(code or "").strip()
    if s.isdigit() and len(s) <= 6:
        return s.zfill(6)
    return s


# ---------- reserve box ----------


class ReserveAddReq(BaseModel):
    stock_code: str
    stock_name: Optional[str] = None
    industry_note: Optional[str] = None


@router.get("/reserve-box")
def list_reserve_box(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(SBBRReserveBox)
        .filter(SBBRReserveBox.user_id == current_user.id)
        .order_by(SBBRReserveBox.created_at.desc())
        .all()
    )
    return {
        "items": [
            {
                "id": r.id,
                "stock_code": r.stock_code,
                "stock_name": r.stock_name,
                "industry_note": r.industry_note,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }


@router.post("/reserve-box")
def add_reserve_box(
    body: ReserveAddReq,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    code = _norm_code(body.stock_code)
    existing = (
        db.query(SBBRReserveBox)
        .filter(SBBRReserveBox.user_id == current_user.id, SBBRReserveBox.stock_code == code)
        .first()
    )
    if existing:
        return {"id": existing.id, "ok": True, "duplicated": True}
    row = SBBRReserveBox(
        user_id=current_user.id,
        stock_code=code,
        stock_name=body.stock_name,
        industry_note=body.industry_note,
        status="watching",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "ok": True}


@router.delete("/reserve-box/{item_id}")
def delete_reserve_box(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        db.query(SBBRReserveBox)
        .filter(SBBRReserveBox.id == item_id, SBBRReserveBox.user_id == current_user.id)
        .first()
    )
    if not row:
        raise HTTPException(404, "not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


# ---------- trade observe ----------


class ObserveAddReq(BaseModel):
    code: str
    name: Optional[str] = None
    market: str = "CN"
    signal_date: Optional[str] = None
    signal_snapshot: Optional[Dict[str, Any]] = None


@router.get("/trade-observe/list")
def list_trade_observe(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(SBBRTradeObserveStock)
        .filter(SBBRTradeObserveStock.user_id == current_user.id)
        .order_by(SBBRTradeObserveStock.created_at.desc())
        .all()
    )
    return {
        "items": [
            {
                "id": r.id,
                "market": r.market,
                "code": r.code,
                "name": r.name,
                "signal_date": r.signal_date.isoformat() if r.signal_date else None,
                "signal_snapshot": r.signal_snapshot_json,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }


@router.post("/trade-observe/add")
def add_trade_observe(
    body: ObserveAddReq,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    code = _norm_code(body.code)
    existing = (
        db.query(SBBRTradeObserveStock)
        .filter(
            SBBRTradeObserveStock.user_id == current_user.id,
            SBBRTradeObserveStock.market == (body.market or "CN"),
            SBBRTradeObserveStock.code == code,
        )
        .first()
    )
    if existing:
        return {"id": existing.id, "ok": True, "duplicated": True}
    sd = None
    if body.signal_date:
        try:
            sd = datetime.strptime(body.signal_date[:10], "%Y-%m-%d").date()
        except ValueError:
            sd = None
    row = SBBRTradeObserveStock(
        user_id=current_user.id,
        market=body.market or "CN",
        code=code,
        name=body.name,
        signal_snapshot_json=body.signal_snapshot,
        signal_date=sd,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "ok": True}


@router.delete("/trade-observe/{item_id}")
def delete_trade_observe(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        db.query(SBBRTradeObserveStock)
        .filter(SBBRTradeObserveStock.id == item_id, SBBRTradeObserveStock.user_id == current_user.id)
        .first()
    )
    if not row:
        raise HTTPException(404, "not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


# ---------- formal trades ----------


class FormalFromObserveReq(BaseModel):
    entry_price: float
    budget_total: Optional[float] = None
    allocated_pct: float = 50.0
    notes: Optional[str] = None


class FormalPatchReq(BaseModel):
    stage: Optional[str] = None
    allocated_pct: Optional[float] = None
    exit_price: Optional[float] = None
    status: Optional[str] = None
    exit_reason: Optional[str] = None
    notes: Optional[str] = None
    budget_total: Optional[float] = None


@router.get("/formal-trades/list")
def list_formal_trades(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(SBBRFormalTrade).filter(SBBRFormalTrade.user_id == current_user.id)
    if status:
        q = q.filter(SBBRFormalTrade.status == status)
    rows = q.order_by(SBBRFormalTrade.created_at.desc()).all()
    engine = SBBRStrategyEngine()
    open_count = sum(1 for r in rows if r.status == "open")
    items = []
    for r in rows:
        item = {
            "id": r.id,
            "market": r.market,
            "code": r.code,
            "name": r.name,
            "entry_price": r.entry_price,
            "exit_price": r.exit_price,
            "status": r.status,
            "stage": r.stage,
            "budget_total": r.budget_total,
            "allocated_pct": r.allocated_pct,
            "defense_anchor_low": r.defense_anchor_low,
            "defense_buffer_pct": r.defense_buffer_pct,
            "exit_reason": r.exit_reason,
            "pnl_amount": r.pnl_amount,
            "pnl_percent": r.pnl_percent,
            "signal_date": r.signal_date.isoformat() if r.signal_date else None,
            "last_eval": r.last_eval_json,
            "notes": r.notes,
            "entry_at": r.entry_at.isoformat() if r.entry_at else None,
            "exit_at": r.exit_at.isoformat() if r.exit_at else None,
        }
        if r.status == "open":
            try:
                item["live_eval"] = engine.evaluate_position(
                    r.code,
                    entry_price=float(r.entry_price),
                    entry_date=item["signal_date"],
                    defense_anchor_low=r.defense_anchor_low,
                    defense_buffer_pct=r.defense_buffer_pct,
                    stage=r.stage,
                    allocated_pct=float(r.allocated_pct or 0),
                    open_positions=open_count,
                )
            except Exception:
                item["live_eval"] = None
        items.append(item)
    return {"items": items}


@router.post("/formal-trades/from-observe/{observe_id}")
def formal_from_observe(
    observe_id: int,
    body: FormalFromObserveReq,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    obs = (
        db.query(SBBRTradeObserveStock)
        .filter(SBBRTradeObserveStock.id == observe_id, SBBRTradeObserveStock.user_id == current_user.id)
        .first()
    )
    if not obs:
        raise HTTPException(404, "observe not found")

    cm = SBBRConfigManager()
    cfg = cm.get_config()
    pcfg = cfg.get("position") or {}
    max_pos = int(pcfg.get("max_open_positions", 3))
    open_n = (
        db.query(SBBRFormalTrade)
        .filter(SBBRFormalTrade.user_id == current_user.id, SBBRFormalTrade.status == "open")
        .count()
    )
    if open_n >= max_pos:
        raise HTTPException(400, f"同时开仓不得超过 {max_pos} 个标的")

    reserve = float(pcfg.get("reserve_cash_pct", 20))
    alloc = float(body.allocated_pct or pcfg.get("probe_pct", 50))
    if alloc > 100.0 - reserve + 1e-6:
        raise HTTPException(400, f"allocated_pct 不得超过 {100 - reserve}%")

    snap = obs.signal_snapshot_json or {}
    row = SBBRFormalTrade(
        user_id=current_user.id,
        market=obs.market,
        code=obs.code,
        name=obs.name,
        source_observe_id=obs.id,
        entry_price=float(body.entry_price),
        status="open",
        signal_date=obs.signal_date,
        signal_snapshot_json=snap,
        notes=body.notes,
        stage="probe",
        budget_total=body.budget_total,
        allocated_pct=alloc,
        defense_anchor_low=snap.get("defense_high") or snap.get("entry_low") or snap.get("defense_anchor_low"),
        defense_buffer_pct=snap.get("defense_buffer_pct"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "ok": True}


@router.patch("/formal-trades/{trade_id}")
def patch_formal_trade(
    trade_id: int,
    body: FormalPatchReq,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        db.query(SBBRFormalTrade)
        .filter(SBBRFormalTrade.id == trade_id, SBBRFormalTrade.user_id == current_user.id)
        .first()
    )
    if not row:
        raise HTTPException(404, "not found")

    cm = SBBRConfigManager()
    cfg = cm.get_config()
    reserve = float((cfg.get("position") or {}).get("reserve_cash_pct", 20))

    if body.stage is not None:
        row.stage = body.stage
    if body.allocated_pct is not None:
        if float(body.allocated_pct) > 100.0 - reserve + 1e-6:
            raise HTTPException(400, f"allocated_pct 不得超过 {100 - reserve}%")
        row.allocated_pct = float(body.allocated_pct)
        if float(body.allocated_pct) >= float((cfg.get("position") or {}).get("probe_pct", 50)) + float(
            (cfg.get("position") or {}).get("add_pct", 30)
        ) - 1:
            row.stage = "add"
    if body.budget_total is not None:
        row.budget_total = body.budget_total
    if body.notes is not None:
        row.notes = body.notes
    if body.exit_reason is not None:
        row.exit_reason = body.exit_reason
    if body.exit_price is not None:
        row.exit_price = float(body.exit_price)
        if row.entry_price:
            row.pnl_percent = (float(body.exit_price) / float(row.entry_price) - 1.0) * 100.0
            if row.budget_total and row.allocated_pct:
                row.pnl_amount = float(row.budget_total) * float(row.allocated_pct) / 100.0 * (row.pnl_percent / 100.0)
    if body.status is not None:
        row.status = body.status
        if body.status == "closed":
            row.exit_at = datetime.now()

    row.updated_at = datetime.now()
    db.commit()
    return {"ok": True, "id": row.id}


@router.delete("/formal-trades/{trade_id}")
def delete_formal_trade(
    trade_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        db.query(SBBRFormalTrade)
        .filter(SBBRFormalTrade.id == trade_id, SBBRFormalTrade.user_id == current_user.id)
        .first()
    )
    if not row:
        raise HTTPException(404, "not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.get("/strategy-configs")
def list_user_strategy_configs():
    cm = SBBRConfigManager()
    return {"items": cm.list_configs(active_only=True)}
