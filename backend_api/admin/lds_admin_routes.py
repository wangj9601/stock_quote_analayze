# -*- coding: utf-8 -*-
"""LDS 管理端：配置 / 试算 / 强制计算 / 信号列表。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.auth import get_current_admin
from backend_api.database import get_db
from backend_api.models import Admin
from backend_core.strategies.lds.config import LdsConfigManager
from backend_core.strategies.lds.scheduled_precompute import run_lds_precompute
from backend_core.strategies.lds.signal_storage import (
    delete_traces_for_date,
    load_traces,
    upsert_signal_traces,
)
from backend_core.strategies.lds.strategy_engine import LdsStrategyEngine

router = APIRouter(prefix="/api/admin/lds", tags=["admin-lds"])


def _require_admin(admin: Admin = Depends(get_current_admin)) -> Admin:
    return admin


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
    stock_pool_mode: str = Field(
        "stocks", description="industry_board | concept_board | stocks | market"
    )
    industry_board_codes: Optional[List[str]] = None
    concept_board_codes: Optional[List[str]] = None
    stock_codes: Optional[List[str]] = None
    universe_limit: Optional[int] = None
    max_results: Optional[int] = None
    persist: bool = True
    force: bool = False


def _validate_scope(body: ScopeBody) -> str:
    mode = (body.stock_pool_mode or "stocks").strip().lower()
    if mode not in ("industry_board", "concept_board", "stocks", "market"):
        raise HTTPException(400, f"不支持的 stock_pool_mode: {mode}")
    if mode == "industry_board" and not (body.industry_board_codes or []):
        raise HTTPException(400, "请选择行业板块")
    if mode == "concept_board" and not (body.concept_board_codes or []):
        raise HTTPException(400, "请选择概念板块")
    if mode == "stocks" and not (body.stock_codes or []):
        raise HTTPException(400, "请输入个股代码")
    return mode


def _run_screen(db: Session, body: ScopeBody, *, force: bool) -> Dict[str, Any]:
    mode = _validate_scope(body)
    cm = LdsConfigManager()
    cid = int(body.config_id) if body.config_id is not None else cm.get_default_config_id()
    cfg = cm.get_config(cid)
    engine = LdsStrategyEngine(config=cfg)
    try:
        result = engine.screen(
            db,
            trade_date=body.trade_date,
            config_id=cid,
            stock_pool_mode=mode,
            industry_board_codes=body.industry_board_codes,
            concept_board_codes=body.concept_board_codes,
            stock_codes=body.stock_codes,
            universe_limit=body.universe_limit,
            max_results=body.max_results,
            force_recompute=force,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    if int(result.get("screened") or 0) == 0 and int(result.get("hit_count") or 0) == 0:
        # 允许 screened>0 无 hit；仅当完全无候选时提示
        if not (result.get("scope_codes") or []):
            raise HTTPException(400, "股票池为空，请检查分析条件")
    return result


def _persist_result(db: Session, result: Dict[str, Any], *, force: bool) -> Dict[str, int]:
    """合并后按日整表替换，避免旧多板重复行残留。"""
    items = list(result.get("items") or [])
    cid = int(result["config_id"])
    date_s = str(result.get("trade_date") or "")
    deleted = delete_traces_for_date(db, trade_date=date_s, config_id=cid)
    saved = 0
    if items:
        saved = upsert_signal_traces(db, items, config_id=cid, trade_date=date_s)
    return {"saved": saved, "deleted_stale": deleted, "force": bool(force)}


@router.get("/strategy-configs")
def admin_list_configs(_user: Admin = Depends(_require_admin)):
    return {"items": LdsConfigManager().list_configs(active_only=False)}


@router.post("/strategy-configs")
def admin_create_config(body: ConfigCreateReq, _user: Admin = Depends(_require_admin)):
    return LdsConfigManager().create_config(
        name=body.name,
        config_params=body.config_params,
        description=body.description,
        set_default=body.set_default,
    )


@router.put("/strategy-configs/{config_id}/update")
def admin_update_config(
    config_id: int, body: ConfigUpdateReq, _user: Admin = Depends(_require_admin)
):
    try:
        return LdsConfigManager().update_config(
            config_id, body.dict(exclude_unset=True)
        )
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.patch("/strategy-configs/{config_id}/default")
def admin_set_default(config_id: int, _user: Admin = Depends(_require_admin)):
    try:
        return LdsConfigManager().set_default(config_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/trial")
def admin_trial(
    body: ScopeBody,
    db: Session = Depends(get_db),
    _user: Admin = Depends(_require_admin),
):
    force = bool(body.force)
    result = _run_screen(db, body, force=force)
    persist_meta = {"saved": 0, "deleted_stale": 0}
    if body.persist:
        persist_meta = _persist_result(db, result, force=force)
    result.pop("scope_codes", None)
    return {
        **result,
        "persist": bool(body.persist),
        "force": force,
        **persist_meta,
    }


@router.post("/precompute/trigger")
def admin_trigger_precompute(
    body: ScopeBody,
    _user: Admin = Depends(_require_admin),
):
    mode = _validate_scope(body)
    try:
        return run_lds_precompute(
            config_id=body.config_id,
            trade_date=body.trade_date,
            stock_pool_mode=mode,
            industry_board_codes=body.industry_board_codes,
            concept_board_codes=body.concept_board_codes,
            stock_codes=body.stock_codes,
            universe_limit=body.universe_limit,
            max_results=body.max_results,
            force_recompute=True,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"预计算失败: {e}")


@router.get("/signals")
def admin_list_signals(
    trade_date: str = Query(..., description="YYYY-MM-DD"),
    config_id: Optional[int] = None,
    code: Optional[str] = None,
    role: Optional[str] = None,
    watch_ready: Optional[bool] = None,
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _user: Admin = Depends(_require_admin),
):
    try:
        return load_traces(
            db,
            trade_date=trade_date,
            config_id=config_id,
            code=code,
            role=role,
            watch_ready=watch_ready,
            limit=limit,
            offset=offset,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
