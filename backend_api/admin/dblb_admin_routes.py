# -*- coding: utf-8 -*-
"""DBLB 管理端：配置 / 试算 / 手动预计算 / 信号列表。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.auth import get_current_user
from backend_api.database import get_db
from backend_api.models import User
from backend_core.strategies.double_bottom.config import DblbConfigManager
from backend_core.strategies.double_bottom.scheduled_precompute import run_dblb_precompute
from backend_core.strategies.double_bottom.signal_storage import load_traces
from backend_core.strategies.double_bottom.strategy_engine import DblbStrategyEngine

router = APIRouter(prefix="/api/admin/dblb", tags=["admin-dblb"])


def _require_admin(user: User = Depends(get_current_user)) -> User:
    return user


class ConfigCreateReq(BaseModel):
    name: str
    description: str = ""
    config_params: Optional[Dict[str, Any]] = None
    set_default: bool = False


class ConfigUpdateReq(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config_params: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ScopeBody(BaseModel):
    trade_date: Optional[str] = None
    config_id: Optional[int] = None
    status_filter: Optional[str] = Field(
        None, description="forming | confirmed | both"
    )
    stock_pool_mode: str = Field(
        "stocks", description="industry_board | concept_board | stocks | market"
    )
    industry_board_codes: Optional[List[str]] = None
    concept_board_codes: Optional[List[str]] = None
    stock_codes: Optional[List[str]] = None
    universe_limit: Optional[int] = None
    max_results: Optional[int] = None
    persist: bool = False


@router.get("/strategy-configs")
def admin_list_configs(_user: User = Depends(_require_admin)):
    return {"items": DblbConfigManager().list_configs(active_only=False)}


@router.post("/strategy-configs")
def admin_create_config(body: ConfigCreateReq, _user: User = Depends(_require_admin)):
    return DblbConfigManager().create_config(
        name=body.name,
        config_params=body.config_params,
        description=body.description,
        set_default=body.set_default,
    )


@router.put("/strategy-configs/{config_id}/update")
def admin_update_config(
    config_id: int, body: ConfigUpdateReq, _user: User = Depends(_require_admin)
):
    try:
        return DblbConfigManager().update_config(
            config_id, body.dict(exclude_unset=True)
        )
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.patch("/strategy-configs/{config_id}/default")
def admin_set_default(config_id: int, _user: User = Depends(_require_admin)):
    try:
        return DblbConfigManager().set_default(config_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


def _run_screen(db: Session, body: ScopeBody) -> Dict[str, Any]:
    mode = (body.stock_pool_mode or "stocks").strip().lower()
    if mode not in ("industry_board", "concept_board", "stocks", "market"):
        raise HTTPException(400, f"不支持的 stock_pool_mode: {mode}")
    if mode == "industry_board" and not (body.industry_board_codes or []):
        raise HTTPException(400, "请选择行业板块")
    if mode == "concept_board" and not (body.concept_board_codes or []):
        raise HTTPException(400, "请选择概念板块")
    if mode == "stocks" and not (body.stock_codes or []):
        raise HTTPException(400, "请输入个股代码")

    cm = DblbConfigManager()
    cid = int(body.config_id) if body.config_id is not None else cm.get_default_config_id()
    cfg = cm.get_config(cid)
    engine = DblbStrategyEngine(config=cfg)
    try:
        result = engine.screen(
            db,
            trade_date=body.trade_date,
            config_id=cid,
            status_filter=body.status_filter,
            stock_pool_mode=mode,
            industry_board_codes=body.industry_board_codes,
            concept_board_codes=body.concept_board_codes,
            stock_codes=body.stock_codes,
            universe_limit=body.universe_limit,
            max_results=body.max_results,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    if int(result.get("screened") or 0) == 0:
        raise HTTPException(400, "股票池为空，请检查分析条件")
    return result


@router.post("/trial")
def admin_trial(
    body: ScopeBody,
    db: Session = Depends(get_db),
    _user: User = Depends(_require_admin),
):
    """即时试算；默认不落库，persist=true 时写入 trace。"""
    result = _run_screen(db, body)
    saved = 0
    if body.persist:
        from backend_core.strategies.double_bottom.signal_storage import (
            upsert_signal_traces,
        )

        saved = upsert_signal_traces(
            db,
            list(result.get("items") or []),
            config_id=int(result["config_id"]),
            trade_date=str(result.get("trade_date") or ""),
        )
    return {**result, "persist": bool(body.persist), "saved": saved}


@router.post("/precompute/trigger")
def admin_trigger_precompute(
    body: ScopeBody,
    _user: User = Depends(_require_admin),
):
    mode = (body.stock_pool_mode or "stocks").strip().lower()
    if mode not in ("industry_board", "concept_board", "stocks", "market"):
        raise HTTPException(400, f"不支持的 stock_pool_mode: {mode}")
    if mode == "industry_board" and not (body.industry_board_codes or []):
        raise HTTPException(400, "请选择行业板块")
    if mode == "concept_board" and not (body.concept_board_codes or []):
        raise HTTPException(400, "请选择概念板块")
    if mode == "stocks" and not (body.stock_codes or []):
        raise HTTPException(400, "请输入个股代码")
    try:
        return run_dblb_precompute(
            config_id=body.config_id,
            trade_date=body.trade_date,
            status_filter=body.status_filter,
            stock_pool_mode=mode,
            industry_board_codes=body.industry_board_codes,
            concept_board_codes=body.concept_board_codes,
            stock_codes=body.stock_codes,
            universe_limit=body.universe_limit,
            max_results=body.max_results,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"预计算失败: {e}")


@router.get("/signals")
def admin_list_signals(
    trade_date: str = Query(..., description="YYYY-MM-DD"),
    config_id: Optional[int] = None,
    status: Optional[str] = None,
    code: Optional[str] = None,
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _user: User = Depends(_require_admin),
):
    try:
        return load_traces(
            db,
            trade_date=trade_date,
            config_id=config_id,
            status=status,
            code=code,
            limit=limit,
            offset=offset,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
