# -*- coding: utf-8 -*-
"""生产端环境同步网关：Key 认证后 export / import。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.database import get_db
from backend_api.env_sync.auth import require_env_sync_key
from backend_api.env_sync.config_store import write_audit
from backend_api.env_sync.job_runner import run_server_export_job, start_thread
from backend_api.env_sync.job_store import (
    create_job,
    get_job,
    is_direction_busy,
    job_public,
    update_job,
)
from backend_api.env_sync.services import export_modules, import_modules, normalize_modules

router = APIRouter(prefix="/api/env-sync/v1", tags=["env-sync-gateway"])


class ImportBody(BaseModel):
    bundles: Dict[str, Any] = Field(..., description="module -> SyncBundle")
    modules: Optional[List[str]] = Field(
        None, description="可选：限制导入细项；空则导入包内全部"
    )


class ExportJobBody(BaseModel):
    modules: Optional[List[str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class ImportJobPartBody(BaseModel):
    """异步分片导入：每片立即 import。"""

    bundles: Dict[str, Any] = Field(..., description="module -> SyncBundle")
    modules: Optional[List[str]] = None
    client_job_id: Optional[str] = None
    part_name: Optional[str] = None
    part_index: Optional[int] = None
    part_total: Optional[int] = None
    job_id: Optional[str] = Field(None, description="已有 import job；空则新建")


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
        err = f"{type(e).__name__}: {e}"
        write_audit(
            db,
            direction="export",
            modules=None,
            operator="env-sync-key",
            success=False,
            error_message=err,
        )
        raise HTTPException(status_code=500, detail=err)


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
        err = f"{type(e).__name__}: {e}"
        write_audit(
            db,
            direction="import",
            modules=list((body.bundles or {}).keys()),
            operator="env-sync-key",
            success=False,
            error_message=err,
        )
        raise HTTPException(status_code=500, detail=err)


@router.post("/jobs/export")
def create_export_job(
    body: ExportJobBody,
    _: str = Depends(require_env_sync_key),
    db: Session = Depends(get_db),
):
    try:
        mods = normalize_modules(body.modules) if body.modules is not None else None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if is_direction_busy("async_export"):
        raise HTTPException(status_code=409, detail="已有异步 export 在运行")
    row = create_job(
        db,
        direction="async_export",
        modules=mods,
        start_date=body.start_date,
        end_date=body.end_date,
        created_by="env-sync-key",
    )
    start_thread(
        lambda jid=row.id: run_server_export_job(jid),
        name=f"env-sync-export-{row.id[:8]}",
    )
    write_audit(
        db,
        direction="async_export",
        modules=mods,
        operator="env-sync-key",
        success=True,
        summary={"job_id": row.id, "accepted": True},
    )
    return {"job_id": row.id, "status": "pending"}


@router.get("/jobs/{job_id}")
def get_gateway_job(
    job_id: str,
    _: str = Depends(require_env_sync_key),
    db: Session = Depends(get_db),
):
    row = get_job(db, job_id)
    if not row:
        raise HTTPException(status_code=404, detail="job 不存在")
    return job_public(row)


@router.get("/jobs/{job_id}/parts/{name}")
def download_job_part(
    job_id: str,
    name: str,
    _: str = Depends(require_env_sync_key),
    db: Session = Depends(get_db),
):
    row = get_job(db, job_id)
    if not row:
        raise HTTPException(status_code=404, detail="job 不存在")
    safe = Path(name).name
    if safe != name or ".." in name or "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail="非法分片名")
    base = Path(row.artifact_dir or "")
    path = base / "parts" / safe
    if not path.is_file():
        raise HTTPException(status_code=404, detail="分片不存在")
    return FileResponse(path, media_type="application/gzip", filename=safe)


@router.post("/jobs/import")
def import_job_part(
    body: ImportJobPartBody,
    _: str = Depends(require_env_sync_key),
    db: Session = Depends(get_db),
):
    """接收一片并立即导入（异步 Push 对端）。"""
    try:
        if not body.bundles:
            raise HTTPException(status_code=400, detail="bundles 不能为空")
        job_id = body.job_id
        if not job_id:
            row = create_job(
                db,
                direction="async_import",
                modules=body.modules,
                created_by="env-sync-key",
            )
            job_id = row.id
            update_job(db, job_id, status="running", stage="importing", progress=0)
        else:
            row = get_job(db, job_id)
            if not row:
                raise HTTPException(status_code=404, detail="job 不存在")
            update_job(db, job_id, status="running", stage="importing")

        payload = import_modules(db, body.bundles, modules=body.modules)
        idx = body.part_index or 0
        total = body.part_total or 0
        prog = int(100 * idx / total) if total else None
        msg = f"已导入 {body.part_name or ''}".strip()
        if total and idx:
            msg = f"已导入 {idx}/{total}: {body.part_name or ''}"
            if idx >= total:
                update_job(
                    db,
                    job_id,
                    status="succeeded",
                    stage="succeeded",
                    progress=100,
                    message=msg,
                    summary={
                        "results": payload.get("results"),
                        "client_job_id": body.client_job_id,
                    },
                )
            else:
                update_job(
                    db,
                    job_id,
                    progress=prog,
                    message=msg,
                    summary={
                        "results": payload.get("results"),
                        "client_job_id": body.client_job_id,
                    },
                )
        else:
            update_job(
                db,
                job_id,
                status="succeeded",
                stage="succeeded",
                progress=100,
                message=msg,
                summary={
                    "results": payload.get("results"),
                    "client_job_id": body.client_job_id,
                },
            )
        write_audit(
            db,
            direction="async_import",
            modules=list(body.bundles.keys()),
            operator="env-sync-key",
            success=True,
            summary={
                "job_id": job_id,
                "part_name": body.part_name,
                "results": payload.get("results"),
            },
        )
        return {"success": True, "job_id": job_id, "results": payload.get("results")}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        if body.job_id:
            try:
                update_job(
                    db,
                    body.job_id,
                    status="failed",
                    stage="failed",
                    error_message=err,
                )
            except Exception:
                pass
        write_audit(
            db,
            direction="async_import",
            modules=list((body.bundles or {}).keys()),
            operator="env-sync-key",
            success=False,
            error_message=err,
        )
        raise HTTPException(status_code=500, detail=err)
