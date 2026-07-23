# -*- coding: utf-8 -*-
"""URT 前台公开只读 API（选股页参数版本等）。前缀: /api/frontend/urt"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend_api.database import get_db
from backend_core.strategies.urt.config import URTConfigManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/frontend/urt", tags=["URT前端接口"])


@router.get("/strategy-configs")
async def list_urt_strategy_configs_public(db: Session = Depends(get_db)):
    """公开：列出启用的 URT 策略参数版本（供网站选股页选择）。"""
    try:
        mgr = URTConfigManager()
        mgr.ensure_default_row(db)
        rows = mgr.list_configs(db, active_only=True)
        data = []
        default_id = None
        for r in rows:
            item = {
                "id": r["id"],
                "name": r["name"],
                "version_label": r.get("version_label"),
                "description": r.get("description"),
                "is_default": bool(r.get("is_default")),
                "precompute_enabled": bool(r.get("precompute_enabled")),
            }
            data.append(item)
            if item["is_default"] and default_id is None:
                default_id = item["id"]
        if default_id is None and data:
            default_id = data[0]["id"]
        return JSONResponse(
            {"success": True, "data": data, "default_config_id": default_id}
        )
    except Exception as e:
        logger.exception("URT strategy-configs list 失败")
        raise HTTPException(status_code=500, detail=str(e))
