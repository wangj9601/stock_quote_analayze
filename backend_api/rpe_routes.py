"""RPE 用户端：交易观察 / 正式交易 / 配置 / 信号追溯。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend_api.auth import get_current_user
from backend_api.database import get_db
from backend_api.models import (
    RPEFormalTrade,
    RPESignalTrace,
    RPETradeObserveHistory,
    RPETradeObserveStock,
    StockRealtimeQuote,
    User,
)
from backend_core.strategies.rpe.config import RPEConfigManager
from backend_core.strategies.rpe.strategy_engine import RPEStrategyEngine

stock_router = APIRouter(prefix="/api/stock", tags=["rpe-stock"])
frontend_router = APIRouter(prefix="/api/frontend/rpe", tags=["rpe-frontend"])


def _norm_code(code: str) -> str:
    s = str(code or "").strip()
    if s.isdigit() and len(s) <= 6:
        return s.zfill(6)
    return s


class ObserveAddReq(BaseModel):
    code: str
    name: Optional[str] = None
    market: str = "CN"
    signal_date: Optional[str] = None
    signal_snapshot: Optional[Dict[str, Any]] = None


class FormalFromObserveReq(BaseModel):
    entry_price: float
    notes: Optional[str] = None


class FormalPatchReq(BaseModel):
    exit_price: Optional[float] = None
    status: Optional[str] = None
    exit_reason: Optional[str] = None
    notes: Optional[str] = None
    structure_support: Optional[float] = None
    structure_resistance: Optional[float] = None


@frontend_router.get("/strategy-configs")
def list_frontend_configs():
    return {"items": RPEConfigManager().list_configs(active_only=True)}


@stock_router.get("/rpe-trade-observe/list")
def list_trade_observe(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(RPETradeObserveStock)
        .filter(RPETradeObserveStock.user_id == current_user.id)
        .order_by(RPETradeObserveStock.created_at.desc())
        .all()
    )
    items = []
    for r in rows:
        snap = r.signal_snapshot_json or {}
        support = snap.get("nearest_support")
        # 盘中二次确认：现价是否仍在支撑上方
        above_support = None
        try:
            rq = (
                db.query(StockRealtimeQuote)
                .filter(StockRealtimeQuote.code == r.code)
                .order_by(StockRealtimeQuote.trade_date.desc())
                .first()
            )
            px = getattr(rq, "current_price", None) or getattr(rq, "price", None) or getattr(rq, "close", None)
            if px is not None and support is not None:
                above_support = float(px) >= float(support)
        except Exception:
            above_support = None
        items.append(
            {
                "id": r.id,
                "market": r.market,
                "code": r.code,
                "name": r.name,
                "signal_date": r.signal_date.isoformat() if r.signal_date else None,
                "signal_snapshot": snap,
                "above_support": above_support,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
        )
    return {"items": items}


@stock_router.post("/rpe-trade-observe/add")
def add_trade_observe(
    body: ObserveAddReq,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    code = _norm_code(body.code)
    existing = (
        db.query(RPETradeObserveStock)
        .filter(
            RPETradeObserveStock.user_id == current_user.id,
            RPETradeObserveStock.market == (body.market or "CN"),
            RPETradeObserveStock.code == code,
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
    row = RPETradeObserveStock(
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


@stock_router.delete("/rpe-trade-observe/{item_id}")
def delete_trade_observe(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        db.query(RPETradeObserveStock)
        .filter(RPETradeObserveStock.id == item_id, RPETradeObserveStock.user_id == current_user.id)
        .first()
    )
    if not row:
        raise HTTPException(404, "not found")
    db.add(
        RPETradeObserveHistory(
            user_id=current_user.id,
            market=row.market,
            code=row.code,
            name=row.name,
            signal_snapshot_json=row.signal_snapshot_json,
            signal_date=row.signal_date,
            source_observe_id=row.id,
            removed_at=datetime.now(),
        )
    )
    db.delete(row)
    db.commit()
    return {"ok": True}


@stock_router.get("/rpe-formal-trade/list")
def list_formal_trades(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(RPEFormalTrade).filter(RPEFormalTrade.user_id == current_user.id)
    if status:
        q = q.filter(RPEFormalTrade.status == status)
    rows = q.order_by(RPEFormalTrade.created_at.desc()).all()
    engine = RPEStrategyEngine()
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
            "structure_support": r.structure_support,
            "structure_resistance": r.structure_resistance,
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
                    r.code, structure_support=r.structure_support
                )
            except Exception:
                item["live_eval"] = None
        items.append(item)
    return {"items": items}


@stock_router.post("/rpe-formal-trade/from-observe/{observe_id}")
def formal_from_observe(
    observe_id: int,
    body: FormalFromObserveReq,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    obs = (
        db.query(RPETradeObserveStock)
        .filter(RPETradeObserveStock.id == observe_id, RPETradeObserveStock.user_id == current_user.id)
        .first()
    )
    if not obs:
        raise HTTPException(404, "observe not found")
    snap = obs.signal_snapshot_json or {}
    row = RPEFormalTrade(
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
        structure_support=snap.get("nearest_support"),
        structure_resistance=snap.get("nearest_resistance"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "ok": True}


@stock_router.patch("/rpe-formal-trade/{trade_id}")
def patch_formal_trade(
    trade_id: int,
    body: FormalPatchReq,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        db.query(RPEFormalTrade)
        .filter(RPEFormalTrade.id == trade_id, RPEFormalTrade.user_id == current_user.id)
        .first()
    )
    if not row:
        raise HTTPException(404, "not found")

    # 禁止把固定百分比止损当作唯一离场理由
    if body.exit_reason and str(body.exit_reason).lower() in (
        "fixed_pct",
        "percent_stop",
        "pct_stop",
        "fixed_stop",
    ):
        raise HTTPException(400, "RPE 禁止使用固定百分比止损作为离场理由，请使用 structure_break")

    if body.notes is not None:
        row.notes = body.notes
    if body.structure_support is not None:
        row.structure_support = body.structure_support
    if body.structure_resistance is not None:
        row.structure_resistance = body.structure_resistance
    if body.exit_reason is not None:
        row.exit_reason = body.exit_reason
    if body.exit_price is not None:
        row.exit_price = float(body.exit_price)
        if row.entry_price:
            row.pnl_percent = (float(body.exit_price) / float(row.entry_price) - 1.0) * 100.0
    if body.status is not None:
        row.status = body.status
        if body.status == "closed":
            row.exit_at = datetime.now()
            if not row.exit_reason:
                row.exit_reason = "structure_break"
    row.updated_at = datetime.now()
    db.commit()
    return {"ok": True, "id": row.id}


@stock_router.delete("/rpe-formal-trade/{trade_id}")
def delete_formal_trade(
    trade_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        db.query(RPEFormalTrade)
        .filter(RPEFormalTrade.id == trade_id, RPEFormalTrade.user_id == current_user.id)
        .first()
    )
    if not row:
        raise HTTPException(404, "not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


@stock_router.get("/rpe-signal-trace")
def get_signal_trace(
    code: str = Query(...),
    config_id: Optional[int] = None,
    limit: int = Query(120, ge=1, le=500),
    db: Session = Depends(get_db),
):
    cm = RPEConfigManager()
    cid = int(config_id) if config_id is not None else cm.get_default_config_id()
    code_n = _norm_code(code)
    rows = (
        db.query(RPESignalTrace)
        .filter(RPESignalTrace.code == code_n, RPESignalTrace.config_id == cid)
        .order_by(RPESignalTrace.trade_date.desc())
        .limit(limit)
        .all()
    )
    return {
        "code": code_n,
        "config_id": cid,
        "items": [
            {
                "date": r.trade_date.isoformat() if r.trade_date else None,
                "z_score": r.z_score,
                "signal_type": r.signal_type,
                "entry_signal": r.entry_signal,
                "sector_id": r.sector_id,
                "sector_name": r.sector_name,
                "nearest_support": r.nearest_support,
                "nearest_resistance": r.nearest_resistance,
                "structure_valid": r.structure_valid,
                "close": r.close_price,
                "detail": r.detail,
            }
            for r in rows
        ],
    }
