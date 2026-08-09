# -*- coding: utf-8 -*-
"""分析频道：板块多策略信号聚合与一键加入观察。"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.auth import get_current_user, get_current_user_optional
from backend_api.database import get_db
from backend_api.models import User
from backend_api.permissions import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["板块分析"])


class BoardObserveRequest(BaseModel):
    strategy: str = Field(..., description="gms|urt|sbbr|rpe")
    code: str = Field(..., min_length=1, max_length=20)
    name: Optional[str] = None
    market: Optional[str] = "CN"
    signal_date: Optional[str] = None
    note: Optional[str] = None
    snapshot: Optional[Dict[str, Any]] = None


def _parse_strategies(raw: Optional[str]) -> List[str]:
    if not raw or not str(raw).strip():
        return ["gms", "urt", "sbbr", "rpe"]
    parts = [p.strip().lower() for p in str(raw).split(",") if p.strip()]
    allowed = {"gms", "urt", "sbbr", "rpe"}
    out = [p for p in parts if p in allowed]
    return out or ["gms", "urt", "sbbr", "rpe"]


def _parse_date(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw).strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _norm_code(code: str) -> str:
    c = str(code or "").strip()
    if c.isdigit() and len(c) <= 6:
        return c.zfill(6)
    return c


@router.get("/board-signals")
def get_board_signals(
    board_kind: str = Query(..., description="industry | concept"),
    board_code: str = Query(..., min_length=1),
    board_code_source: str = Query("tonghuashun"),
    board_name: Optional[str] = Query(None),
    strategies: Optional[str] = Query(
        None, description="逗号分隔：gms,urt,sbbr,rpe；默认全部"
    ),
    db: Session = Depends(get_db),
    _user: Optional[User] = Depends(get_current_user_optional),
):
    """按行业/概念板聚合四策略命中，并附买卖建议与 Fib/Pivot 参考价。"""
    kind = (board_kind or "").strip().lower()
    if kind not in ("industry", "concept"):
        return JSONResponse(
            {"success": False, "message": "board_kind 须为 industry 或 concept"},
            status_code=400,
        )
    try:
        from backend_core.analysis.board_signals import collect_board_signals

        data = collect_board_signals(
            db,
            board_kind=kind,
            board_code=board_code.strip(),
            board_code_source=board_code_source,
            board_name=board_name,
            strategies=_parse_strategies(strategies),
        )
        return {"success": True, "data": data}
    except Exception as e:
        logger.exception("board-signals failed")
        try:
            db.rollback()
        except Exception:
            pass
        return JSONResponse(
            {"success": False, "message": f"板块分析失败: {e}"},
            status_code=500,
        )


@router.get("/leader-mid-signals")
def get_leader_mid_signals(
    board_kind: str = Query(..., description="industry | concept"),
    board_code: Optional[str] = Query(
        None, description="单板代码；all/全部=该类型下全部板块"
    ),
    board_codes: Optional[str] = Query(
        None, description="多板代码，逗号分隔；优先于 board_code"
    ),
    board_code_source: str = Query("tonghuashun"),
    board_name: Optional[str] = Query(None),
    strategies: Optional[str] = Query(
        None, description="逗号分隔：gms,urt,sbbr,rpe；默认全部"
    ),
    db: Session = Depends(get_db),
    _user: Optional[User] = Depends(get_current_user_optional),
):
    """板块龙头+中军在 GMS/URT/SBBR/RPE 上的命中矩阵。

    支持 board_codes 多选，或 board_code=all 汇总全部板块。
    """
    kind = (board_kind or "").strip().lower()
    if kind not in ("industry", "concept"):
        return JSONResponse(
            {"success": False, "message": "board_kind 须为 industry 或 concept"},
            status_code=400,
        )
    codes_list = [
        p.strip()
        for p in str(board_codes or "").split(",")
        if p and str(p).strip()
    ]
    single = (board_code or "").strip()
    if not codes_list and not single:
        return JSONResponse(
            {"success": False, "message": "请提供 board_code 或 board_codes"},
            status_code=400,
        )
    try:
        from backend_core.analysis.board_signals import collect_leader_mid_strategy_hits

        data = collect_leader_mid_strategy_hits(
            db,
            board_kind=kind,
            board_code="" if codes_list else single,
            board_codes=codes_list or None,
            board_code_source=board_code_source,
            board_name=board_name,
            strategies=_parse_strategies(strategies),
        )
        return {"success": True, "data": data}
    except Exception as e:
        logger.exception("leader-mid-signals failed")
        try:
            db.rollback()
        except Exception:
            pass
        return JSONResponse(
            {"success": False, "message": f"龙头中军分析失败: {e}"},
            status_code=500,
        )


@router.post("/board-signals/observe")
def add_board_signal_observe(
    body: BoardObserveRequest = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _perm: None = Depends(require_permission("channel.analyze.tab.board.btn.observe")),
):
    """一键加入对应策略交易观察池。"""
    strategy = (body.strategy or "").strip().lower()
    code = _norm_code(body.code)
    if not code:
        raise HTTPException(status_code=400, detail="股票代码无效")
    if strategy not in ("gms", "urt", "sbbr", "rpe"):
        raise HTTPException(status_code=400, detail="strategy 须为 gms/urt/sbbr/rpe")

    market = (body.market or "CN").strip().upper() or "CN"
    snap = dict(body.snapshot or {})
    if body.note:
        snap["analysis_note"] = body.note
    advice = snap.get("trade_advice") if isinstance(snap.get("trade_advice"), dict) else {}
    if advice.get("summary") and "analysis_note" not in snap:
        snap["analysis_note"] = advice.get("summary")

    sig_date = _parse_date(body.signal_date) or _parse_date(
        snap.get("search_date") or snap.get("signal_date") or snap.get("date")
    )
    if sig_date is None:
        sig_date = date.today()

    try:
        if strategy == "gms":
            return _add_gms(db, user, code, body.name, market, sig_date, snap)
        if strategy == "urt":
            return _add_urt(db, user, code, body.name, market, sig_date, snap)
        if strategy == "sbbr":
            return _add_sbbr(db, user, code, body.name, market, sig_date, snap)
        return _add_rpe(db, user, code, body.name, market, sig_date, snap)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("board observe failed")
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"加入观察失败: {e}")


def _add_gms(db, user, code, name, market, sig_date, snap):
    from backend_api.gms_trade_observe_routes import (
        attach_price_plan_to_snapshot,
        ensure_gms_trade_observe_schema,
    )
    from backend_api.models import GmsTradeObserveStock
    from backend_api.services.gms_strategy_watchlist import ensure_gms_strategy_watchlist_stock

    ensure_gms_trade_observe_schema(db)
    ensure_gms_strategy_watchlist_stock(db, market=market, code=code, name=name)
    snapshot_with_plan = attach_price_plan_to_snapshot(
        db, snap, market=market, code=code, signal_date=sig_date
    )
    now = datetime.now()
    existing = (
        db.query(GmsTradeObserveStock)
        .filter(
            GmsTradeObserveStock.user_id == user.id,
            GmsTradeObserveStock.market == market,
            GmsTradeObserveStock.code == code,
        )
        .first()
    )
    if existing:
        existing.name = name or existing.name
        existing.signal_snapshot_json = snapshot_with_plan
        existing.signal_date = sig_date
        existing.updated_at = now
        db.commit()
        return {"success": True, "id": existing.id, "duplicated": True, "strategy": "gms"}
    row = GmsTradeObserveStock(
        user_id=user.id,
        market=market,
        code=code,
        name=name,
        signal_snapshot_json=snapshot_with_plan,
        signal_date=sig_date,
        key_focus_flag=False,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"success": True, "id": row.id, "strategy": "gms"}


def _add_urt(db, user, code, name, market, sig_date, snap):
    from backend_api.models import UrtTradeObserveStock

    now = datetime.now()
    existing = (
        db.query(UrtTradeObserveStock)
        .filter(
            UrtTradeObserveStock.user_id == user.id,
            UrtTradeObserveStock.market == market,
            UrtTradeObserveStock.code == code,
        )
        .first()
    )
    if existing:
        existing.name = name or existing.name
        existing.signal_snapshot_json = snap
        existing.signal_date = sig_date
        existing.updated_at = now
        db.commit()
        return {"success": True, "id": existing.id, "duplicated": True, "strategy": "urt"}
    row = UrtTradeObserveStock(
        user_id=user.id,
        market=market,
        code=code,
        name=name,
        signal_snapshot_json=snap,
        signal_date=sig_date,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"success": True, "id": row.id, "strategy": "urt"}


def _add_sbbr(db, user, code, name, market, sig_date, snap):
    from backend_api.models import SBBRTradeObserveStock

    existing = (
        db.query(SBBRTradeObserveStock)
        .filter(
            SBBRTradeObserveStock.user_id == user.id,
            SBBRTradeObserveStock.market == market,
            SBBRTradeObserveStock.code == code,
        )
        .first()
    )
    if existing:
        return {"success": True, "id": existing.id, "duplicated": True, "strategy": "sbbr"}
    row = SBBRTradeObserveStock(
        user_id=user.id,
        market=market,
        code=code,
        name=name,
        signal_snapshot_json=snap,
        signal_date=sig_date,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"success": True, "id": row.id, "strategy": "sbbr"}


def _add_rpe(db, user, code, name, market, sig_date, snap):
    from backend_api.models import RPETradeObserveStock
    from backend_api.rpe_routes import _ensure_rpe_trade_observe_schema

    _ensure_rpe_trade_observe_schema()
    existing = (
        db.query(RPETradeObserveStock)
        .filter(
            RPETradeObserveStock.user_id == user.id,
            RPETradeObserveStock.market == market,
            RPETradeObserveStock.code == code,
        )
        .first()
    )
    if existing:
        return {"success": True, "id": existing.id, "duplicated": True, "strategy": "rpe"}
    row = RPETradeObserveStock(
        user_id=user.id,
        market=market,
        code=code,
        name=name,
        signal_snapshot_json=snap,
        signal_date=sig_date,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"success": True, "id": row.id, "strategy": "rpe"}
