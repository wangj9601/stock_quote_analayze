# -*- coding: utf-8 -*-
"""URT 上升趋势策略 — 管理端 API（参数版本 CRUD）。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.database import get_db
from backend_core.strategies.urt.config import URTConfigManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/urt", tags=["URT Admin"])


class StrategyConfigCreateBody(BaseModel):
    name: str = Field(..., description="版本名称")
    config_params: Optional[Dict[str, Any]] = None
    version_label: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    is_default: bool = False
    created_by: Optional[str] = None


class StrategyConfigUpdateBody(BaseModel):
    name: Optional[str] = None
    config_params: Optional[Dict[str, Any]] = None
    version_label: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


@router.get("/strategy-configs")
async def list_strategy_configs(
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
):
    try:
        mgr = URTConfigManager()
        mgr.ensure_default_row(db)
        return {"success": True, "data": mgr.list_configs(db, active_only=active_only)}
    except Exception as e:
        logger.exception("URT strategy-configs list 失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategy-configs/{config_id}")
async def get_strategy_config(config_id: int, db: Session = Depends(get_db)):
    try:
        mgr = URTConfigManager()
        row = mgr.get_config_row(db, config_id)
        if not row:
            raise HTTPException(status_code=404, detail="策略参数版本不存在")
        data = mgr._serialize_row(row)
        data["config_params"] = mgr.get_config(config_id, db=db)
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("URT strategy-config get 失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/strategy-configs")
async def create_strategy_config(body: StrategyConfigCreateBody, db: Session = Depends(get_db)):
    try:
        mgr = URTConfigManager()
        mgr.ensure_default_row(db)
        new_id = mgr.create_config(
            db,
            name=body.name,
            config_params=body.config_params,
            version_label=body.version_label,
            description=body.description,
            is_active=body.is_active,
            is_default=body.is_default,
            created_by=body.created_by,
        )
        row = mgr.get_config_row(db, new_id)
        data = mgr._serialize_row(row)
        data["config_params"] = mgr.get_config(new_id, db=db)
        return {"success": True, "data": data}
    except Exception as e:
        logger.exception("URT strategy-config create 失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/strategy-configs/{config_id}")
@router.post("/strategy-configs/{config_id}/update")
async def update_strategy_config(
    config_id: int,
    body: StrategyConfigUpdateBody,
    db: Session = Depends(get_db),
):
    try:
        mgr = URTConfigManager()
        if not mgr.get_config_row(db, config_id):
            raise HTTPException(status_code=404, detail="策略参数版本不存在")
        ok = mgr.update_config(
            db,
            config_id,
            name=body.name,
            version_label=body.version_label,
            description=body.description,
            config_params=body.config_params,
            is_active=body.is_active,
            is_default=body.is_default,
        )
        if not ok:
            raise HTTPException(status_code=400, detail="更新失败")
        row = mgr.get_config_row(db, config_id)
        data = mgr._serialize_row(row)
        data["config_params"] = mgr.get_config(config_id, db=db)
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("URT strategy-config update 失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/default-params")
async def get_default_params():
    """返回内置默认参数（不含 DB）。"""
    mgr = URTConfigManager()
    return {"success": True, "data": mgr.load_file_config()}


@router.post("/screen-preview")
async def screen_preview(
    limit: int = Query(50, ge=1, le=500),
    date: Optional[str] = Query(None),
    config_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """管理端试跑选股摘要。"""
    try:
        from backend_core.strategies.urt import URTFrontendInterface

        payload = URTFrontendInterface.screen(
            db,
            scope="all",
            limit=limit,
            screening_date=date,
            config_id=config_id,
        )
        return payload
    except Exception as e:
        logger.exception("URT screen-preview 失败")
        raise HTTPException(status_code=500, detail=str(e))
