# -*- coding: utf-8 -*-
"""生产端环境同步网关：Key 认证后 export / import。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.database import get_db
from backend_api.env_sync.auth import require_env_sync_key
from backend_api.env_sync.config_store import write_audit
from backend_api.env_sync.services import export_modules, import_modules, normalize_modules

router = APIRouter(prefix="/api/env-sync/v1", tags=["env-sync-gateway"])


class ImportBody(BaseModel):
    bundles: Dict[str, Any] = Field(..., description="module -> SyncBundle")
    modules: Optional[List[str]] = Field(
        None, description="可选：限制导入细项；空则导入包内全部"
    )


@router.get("/health")
def health(
    _: str = Depends(require_env_sync_key),
    db: Session = Depends(get_db),
):
    return {"success": True, "message": "env sync gateway ok"}


@router.get("/export")
def export_data(
    modules: Optional[str] = Query(
        None,
        description="逗号分隔模块/细项；空=默认策略+观察（不含行情）",
    ),
    start_date: Optional[str] = Query(None, description="行情起始日 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="行情结束日 YYYY-MM-DD"),
    _: str = Depends(require_env_sync_key),
    db: Session = Depends(get_db),
):
    try:
        mod_list: Optional[List[str]] = None
        if modules:
            mod_list = [x.strip() for x in modules.split(",") if x.strip()]
            mod_list = normalize_modules(mod_list)
        payload = export_modules(
            db, mod_list, start_date=start_date, end_date=end_date
        )
        write_audit(
            db,
            direction="export",
            modules=payload.get("modules"),
            operator="env-sync-key",
            success=True,
            summary={
                "module_count": len(payload.get("modules") or []),
                "date_range": payload.get("date_range"),
            },
        )
        return payload
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        write_audit(
            db,
            direction="export",
            modules=None,
            operator="env-sync-key",
            success=False,
            error_message=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import")
def import_data(
    body: ImportBody,
    _: str = Depends(require_env_sync_key),
    db: Session = Depends(get_db),
):
    try:
        if not body.bundles:
            raise HTTPException(status_code=400, detail="bundles 不能为空")
        payload = import_modules(db, body.bundles, modules=body.modules)
        write_audit(
            db,
            direction="import",
            modules=list(body.bundles.keys()),
            operator="env-sync-key",
            success=True,
            summary=payload.get("results"),
        )
        return payload
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        write_audit(
            db,
            direction="import",
            modules=list((body.bundles or {}).keys()),
            operator="env-sync-key",
            success=False,
            error_message=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))
