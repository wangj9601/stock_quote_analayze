# -*- coding: utf-8 -*-
"""管理端环境同步包装：配置维护 + pull/push。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.auth import get_current_admin
from backend_api.database import get_db
from backend_api.env_sync import DEFAULT_RESOURCES
from backend_api.env_sync import remote_http
from backend_api.env_sync.config_store import (
    get_client_config_public,
    get_server_config_public,
    resolve_client_credentials,
    rotate_server_key,
    update_client_config,
    update_server_config,
    write_audit,
)
from backend_api.env_sync.services import export_modules, import_modules, normalize_modules
from backend_api.models import User

router = APIRouter(prefix="/api/admin/env-sync", tags=["admin-env-sync"])

# 行情同步可能较大，拉长超时
_SYNC_TIMEOUT = 600.0


class ServerConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    sync_key: Optional[str] = None
    rotate: bool = False


class ClientConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    prod_base_url: Optional[str] = None
    sync_key: Optional[str] = None


class SyncModulesBody(BaseModel):
    modules: Optional[List[str]] = Field(
        default=None,
        description=f"默认：{list(DEFAULT_RESOURCES)[:3]}…（策略+观察，不含行情）",
    )
    start_date: Optional[str] = Field(None, description="行情起始日 YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="行情结束日 YYYY-MM-DD")


def _operator(admin: User) -> str:
    return getattr(admin, "username", None) or str(getattr(admin, "id", ""))


def _prod_headers(key: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {key}",
        "X-Env-Sync-Key": key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _remote_fail_detail(action: str, status_code: int, body: str) -> str:
    text = (body or "")[:400]
    if status_code == 401:
        return (
            f"{action} 失败 HTTP 401：生产 Sync Key 无效或未启用校验。"
            f"请在生产管理端「服务端 Sync Key」生成并启用后，把同一明文 Key 填到本地客户端。"
            f" 响应: {text}"
        )
    if status_code == 404:
        return (
            f"{action} 失败 HTTP 404：生产未注册 /api/env-sync/v1。"
            f"请确认生产已部署 env_sync 并安装 httpx 后重启 API。 响应: {text}"
        )
    return f"{action} 失败 HTTP {status_code}: {text}"


@router.get("/server-config")
def admin_get_server_config(
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return get_server_config_public(db)


@router.put("/server-config")
@router.post("/server-config")
def admin_update_server_config(
    body: ServerConfigUpdate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if body.rotate:
        return rotate_server_key(db, enabled=body.enabled)
    return update_server_config(db, enabled=body.enabled, sync_key=body.sync_key)


@router.get("/client-config")
def admin_get_client_config(
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return get_client_config_public(db)


@router.put("/client-config")
@router.post("/client-config")
def admin_update_client_config(
    body: ClientConfigUpdate,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return update_client_config(
        db,
        enabled=body.enabled,
        prod_base_url=body.prod_base_url,
        sync_key=body.sync_key,
    )


@router.post("/test-connection")
def admin_test_connection(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    try:
        cred = resolve_client_credentials(db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    url = f"{cred['prod_base_url']}/api/env-sync/v1/health"
    try:
        resp = remote_http.get(url, headers=_prod_headers(cred["sync_key"]), timeout=20.0)
        ok = resp.status_code == 200
        write_audit(
            db,
            direction="test",
            modules=None,
            operator=_operator(admin),
            success=ok,
            summary={"status_code": resp.status_code},
            error_message=None if ok else resp.text[:500],
        )
        if not ok:
            raise HTTPException(
                status_code=400,
                detail=_remote_fail_detail("连通测试", resp.status_code, resp.text),
            )
        return {"success": True, "message": "连接生产环境同步网关成功", "data": resp.json()}
    except HTTPException:
        raise
    except Exception as e:
        write_audit(
            db,
            direction="test",
            modules=None,
            operator=_operator(admin),
            success=False,
            error_message=str(e),
        )
        raise HTTPException(status_code=500, detail=f"连通测试异常: {e}")


@router.post("/pull")
def admin_pull(
    body: SyncModulesBody,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """从生产 export，写入本地。"""
    try:
        mods = normalize_modules(body.modules)
        cred = resolve_client_credentials(db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    params: Dict[str, str] = {"modules": ",".join(mods)}
    if body.start_date:
        params["start_date"] = body.start_date
    if body.end_date:
        params["end_date"] = body.end_date
    url = f"{cred['prod_base_url']}/api/env-sync/v1/export?{urlencode(params)}"
    try:
        resp = remote_http.get(
            url, headers=_prod_headers(cred["sync_key"]), timeout=_SYNC_TIMEOUT
        )
        if resp.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail=_remote_fail_detail("生产 export", resp.status_code, resp.text),
            )
        remote = resp.json()
        bundles = remote.get("bundles") or {}
        result = import_modules(db, bundles, modules=mods)
        write_audit(
            db,
            direction="pull",
            modules=mods,
            operator=_operator(admin),
            success=True,
            summary={
                **(result.get("results") or {}),
                "date_range": remote.get("date_range"),
            },
        )
        return {
            "success": True,
            "direction": "pull",
            "modules": mods,
            "date_range": remote.get("date_range"),
            **result,
        }
    except HTTPException:
        raise
    except Exception as e:
        write_audit(
            db,
            direction="pull",
            modules=body.modules,
            operator=_operator(admin),
            success=False,
            error_message=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/push")
def admin_push(
    body: SyncModulesBody,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """导出本地，push 到生产 import。"""
    try:
        mods = normalize_modules(body.modules)
        cred = resolve_client_credentials(db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        local = export_modules(
            db, mods, start_date=body.start_date, end_date=body.end_date
        )
        url = f"{cred['prod_base_url']}/api/env-sync/v1/import"
        resp = remote_http.post(
            url,
            headers=_prod_headers(cred["sync_key"]),
            json_body={"bundles": local.get("bundles") or {}, "modules": mods},
            timeout=_SYNC_TIMEOUT,
        )
        if resp.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail=_remote_fail_detail("生产 import", resp.status_code, resp.text),
            )
        remote = resp.json()
        write_audit(
            db,
            direction="push",
            modules=mods,
            operator=_operator(admin),
            success=True,
            summary=remote.get("results"),
        )
        return {
            "success": True,
            "direction": "push",
            "modules": mods,
            "date_range": local.get("date_range"),
            "results": remote.get("results"),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        write_audit(
            db,
            direction="push",
            modules=body.modules,
            operator=_operator(admin),
            success=False,
            error_message=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/modules")
def admin_list_modules(_: User = Depends(get_current_admin)):
    from backend_api.env_sync import catalog_for_api

    return catalog_for_api()
