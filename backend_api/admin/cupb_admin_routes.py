# -*- coding: utf-8 -*-
"""CUPB 管理端：配置 / 试算（利旧入库）/ 强制计算 / 信号列表。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.auth import get_current_admin
from backend_api.database import get_db
from backend_api.models import Admin
from backend_core.strategies.cup_bottom.config import CupbConfigManager
from backend_core.strategies.cup_bottom.scheduled_precompute import run_cupb_precompute
from backend_core.strategies.cup_bottom.signal_storage import (
    delete_traces_not_in_codes,
    load_traces,
    upsert_signal_traces,
)
from backend_core.strategies.cup_bottom.strategy_engine import CupbStrategyEngine

router = APIRouter(prefix="/api/admin/cupb", tags=["admin-cupb"])


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
    market_scopes: Optional[List[str]] = Field(
        None, description="全市场时：CN / HK，可多选"
    )
    cn_board_segments: Optional[List[str]] = Field(
        None, description="A股板块多选：MAIN/CYB/SZ_SME/KCB/BJ"
    )
    persist: bool = True
    force: bool = False
    price_adjust: Optional[str] = Field(
        None, description="价格口径：none（不复权，默认）| qfq（前复权）"
    )


def _normalize_price_adjust(adjust: Optional[str]) -> str:
    from backend_core.analysis.chart_patterns.scanner import normalize_price_adjust

    try:
        return normalize_price_adjust(adjust)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


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
    if mode == "market":
        scopes = [str(s or "").strip().upper() for s in (body.market_scopes or []) if str(s or "").strip()]
        if not scopes:
            raise HTTPException(400, "全市场请至少选择 A股 或 港股")
    return mode


def _run_screen(db: Session, body: ScopeBody, *, force: bool) -> Dict[str, Any]:
    mode = _validate_scope(body)
    cm = CupbConfigManager()
    cid = int(body.config_id) if body.config_id is not None else cm.get_default_config_id()
    cfg = cm.get_config(cid)
    engine = CupbStrategyEngine(config=cfg)
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
            market_scopes=body.market_scopes,
            cn_board_segments=body.cn_board_segments,
            force_recompute=force,
            price_adjust=_normalize_price_adjust(body.price_adjust),
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    if int(result.get("screened") or 0) == 0:
        raise HTTPException(400, "股票池为空，请检查分析条件")
    return result


def _persist_result(db: Session, result: Dict[str, Any], *, force: bool) -> Dict[str, int]:
    items = list(result.get("items") or [])
    to_save = items if force else [r for r in items if not r.get("_from_cache")]
    saved = 0
    if to_save:
        saved = upsert_signal_traces(
            db,
            to_save,
            config_id=int(result["config_id"]),
            trade_date=str(result.get("trade_date") or ""),
        )
    deleted = 0
    if force:
        scope_codes = list(result.get("scope_codes") or [])
        keep = [str(r.get("code") or "") for r in items]
        deleted = delete_traces_not_in_codes(
            db,
            trade_date=str(result.get("trade_date") or ""),
            config_id=int(result["config_id"]),
            scope_codes=scope_codes,
            keep_codes=keep,
        )
    return {"saved": saved, "deleted_stale": deleted}


@router.get("/strategy-configs")
def admin_list_configs(_user: Admin = Depends(_require_admin)):
    return {"items": CupbConfigManager().list_configs(active_only=False)}


@router.post("/strategy-configs")
def admin_create_config(body: ConfigCreateReq, _user: Admin = Depends(_require_admin)):
    return CupbConfigManager().create_config(
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
        return CupbConfigManager().update_config(
            config_id, body.dict(exclude_unset=True)
        )
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.patch("/strategy-configs/{config_id}/default")
def admin_set_default(config_id: int, _user: Admin = Depends(_require_admin)):
    try:
        return CupbConfigManager().set_default(config_id)
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
    for r in result.get("items") or []:
        r.pop("_from_cache", None)
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
        return run_cupb_precompute(
            config_id=body.config_id,
            trade_date=body.trade_date,
            status_filter=body.status_filter,
            stock_pool_mode=mode,
            industry_board_codes=body.industry_board_codes,
            concept_board_codes=body.concept_board_codes,
            stock_codes=body.stock_codes,
            universe_limit=body.universe_limit,
            max_results=body.max_results,
            market_scopes=body.market_scopes,
            cn_board_segments=body.cn_board_segments,
            force_recompute=True,
            price_adjust=_normalize_price_adjust(body.price_adjust),
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
    _user: Admin = Depends(_require_admin),
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
