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
from backend_api.env_sync import DEFAULT_RESOURCES, filter_modules_for_bundle
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
from backend_api.env_sync.bundle import merge_results
from backend_api.env_sync.services import export_modules, import_modules, normalize_modules
from backend_api.env_sync.services.market_data import (
    iter_adj_factor_push_chunks,
    iter_board_data_push_chunks,
    iter_fina_indicator_push_chunks,
)
from backend_api.models import User

router = APIRouter(prefix="/api/admin/env-sync", tags=["admin-env-sync"])

# 行情/复权因子同步可能较大，拉长超时
_SYNC_TIMEOUT = 600.0
# 生产若仍为逐行 ORM 导入，单块过大易 502；默认偏小，失败再自动对半拆
_DEFAULT_PUSH_ROW_CHUNK = 400
_MIN_PUSH_SPLIT_ROWS = 50
_RETRYABLE_PUSH_STATUS = frozenset({502, 503, 504, 413})


def _push_row_chunk_size() -> int:
    import os

    try:
        return max(50, int(os.getenv("ENV_SYNC_PUSH_ROW_CHUNK") or _DEFAULT_PUSH_ROW_CHUNK))
    except ValueError:
        return _DEFAULT_PUSH_ROW_CHUNK


def _merge_remote_results(
    merged_results: Dict[str, Any], part: Dict[str, Any]
) -> None:
    for mod_key, mod_res in part.items():
        if (
            mod_key in merged_results
            and isinstance(merged_results[mod_key], dict)
            and isinstance(mod_res, dict)
        ):
            merged_results[mod_key] = merge_results(merged_results[mod_key], mod_res)
        else:
            merged_results[mod_key] = mod_res


def _push_adj_rows_adaptive(
    *,
    url: str,
    headers: Dict[str, str],
    batch_mods: List[str],
    base_bundle: Dict[str, Any],
    rows: List[Any],
    label: str,
    merged_results: Dict[str, Any],
    push_batches: List[str],
) -> None:
    """推送复权因子行；遇 502/413 等自动对半拆分重试，适配生产慢导入/短超时。"""
    chunk_data = {k: v for k, v in base_bundle.items() if k != "items"}
    chunk_data["items"] = {"stock_adj_factor": rows}
    chunk_data["chunk"] = {"size": len(rows)}

    resp = remote_http.post(
        url,
        headers=headers,
        json_body={
            "bundles": {"adj_factors": chunk_data},
            "modules": batch_mods or None,
        },
        timeout=_SYNC_TIMEOUT,
    )
    if resp.status_code == 200:
        push_batches.append(f"{label}({len(rows)}行)")
        remote = resp.json() or {}
        part = remote.get("results") or {}
        if isinstance(part, dict):
            _merge_remote_results(merged_results, part)
        return

    if resp.status_code in _RETRYABLE_PUSH_STATUS and len(rows) > _MIN_PUSH_SPLIT_ROWS:
        mid = max(1, len(rows) // 2)
        _push_adj_rows_adaptive(
            url=url,
            headers=headers,
            batch_mods=batch_mods,
            base_bundle=base_bundle,
            rows=rows[:mid],
            label=f"{label}a",
            merged_results=merged_results,
            push_batches=push_batches,
        )
        _push_adj_rows_adaptive(
            url=url,
            headers=headers,
            batch_mods=batch_mods,
            base_bundle=base_bundle,
            rows=rows[mid:],
            label=f"{label}b",
            merged_results=merged_results,
            push_batches=push_batches,
        )
        return

    raise HTTPException(
        status_code=400,
        detail=_remote_fail_detail(
            f"生产 import[{label}|{len(rows)}行]",
            resp.status_code,
            resp.text,
        ),
    )


def _largest_list_item_key(items: Dict[str, Any]) -> tuple:
    best_key = None
    best_n = 0
    for k, v in (items or {}).items():
        if isinstance(v, list) and len(v) > best_n:
            best_key = k
            best_n = len(v)
    return best_key, best_n


def _push_bundle_adaptive(
    *,
    url: str,
    headers: Dict[str, str],
    batch_mods: List[str],
    bundle_key: str,
    bundle_data: Dict[str, Any],
    label: str,
    merged_results: Dict[str, Any],
    push_batches: List[str],
) -> None:
    """通用 bundle 推送；遇 502/413 等对最大列表项对半拆分重试。"""
    resp = remote_http.post(
        url,
        headers=headers,
        json_body={
            "bundles": {bundle_key: bundle_data},
            "modules": batch_mods or None,
        },
        timeout=_SYNC_TIMEOUT,
    )
    if resp.status_code == 200:
        items = (bundle_data.get("items") or {}) if isinstance(bundle_data, dict) else {}
        _, n = _largest_list_item_key(items)
        push_batches.append(f"{label}({n}行)" if n else label)
        remote = resp.json() or {}
        part = remote.get("results") or {}
        if isinstance(part, dict):
            _merge_remote_results(merged_results, part)
        return

    items = dict((bundle_data or {}).get("items") or {})
    split_key, split_n = _largest_list_item_key(items)
    if (
        resp.status_code in _RETRYABLE_PUSH_STATUS
        and split_key
        and split_n > _MIN_PUSH_SPLIT_ROWS
    ):
        rows = list(items[split_key])
        mid = max(1, split_n // 2)
        base = {k: v for k, v in bundle_data.items() if k != "items"}
        left = dict(base)
        left_items = dict(items)
        left_items[split_key] = rows[:mid]
        left["items"] = left_items
        right = dict(base)
        # 右半只推剩余大表行，避免基础信息重复写入拖慢
        right["items"] = {split_key: rows[mid:]}
        _push_bundle_adaptive(
            url=url,
            headers=headers,
            batch_mods=batch_mods,
            bundle_key=bundle_key,
            bundle_data=left,
            label=f"{label}a",
            merged_results=merged_results,
            push_batches=push_batches,
        )
        _push_bundle_adaptive(
            url=url,
            headers=headers,
            batch_mods=batch_mods,
            bundle_key=bundle_key,
            bundle_data=right,
            label=f"{label}b",
            merged_results=merged_results,
            push_batches=push_batches,
        )
        return

    raise HTTPException(
        status_code=400,
        detail=_remote_fail_detail(
            f"生产 import[{label}]",
            resp.status_code,
            resp.text,
        ),
    )


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
    if status_code == 413:
        return (
            f"{action} 失败 HTTP 413：请求体过大，被生产 nginx 拒绝（Request Entity Too Large）。"
            f"请在生产 nginx 的 location /api/ 将 client_max_body_size 调整为 200m 后 reload；"
            f"或缩小同步范围（尤其缩短行情日期）。 响应: {text}"
        )
    if status_code == 502:
        return (
            f"{action} 失败 HTTP 502：生产 nginx 上游无响应（常见：导入超时/进程被杀/"
            f"单包过大）。board_data/quotes/adj_factors/fina_indicator 本地 Push 已分块，并会在 502 时自动对半拆"
            f"（ENV_SYNC_PUSH_ROW_CHUNK，默认 400）。请重启本地 API 后再试；"
            f"生产请部署批量 UPSERT 版本，并检查 gunicorn --timeout 与 nginx proxy_read_timeout（建议≥600s）/ API 日志。"
            f" 响应: {text}"
        )
    if status_code == 400 and "未知同步模块" in text:
        return (
            f"{action} 失败 HTTP 400：生产端不识别该同步模块（{text}）。"
            f"若涉及 frontend_permissions / frontend_roles / role_permissions / permissions_resources，"
            f"请将含权限资源同步的 env_sync 版本部署到生产并重启 API 后再试。"
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
    """导出本地，push 到生产 import。

    按 bundle 分批 POST，避免整包 JSON 超过生产 nginx ``client_max_body_size``（413）。
    """
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
        headers = _prod_headers(cred["sync_key"])
        bundles = local.get("bundles") or {}
        if not bundles:
            raise HTTPException(status_code=400, detail="本地导出结果为空，无可推送数据")

        merged_results: Dict[str, Any] = {}
        push_batches: List[str] = []
        row_chunk = _push_row_chunk_size()
        # 大包分批：strategy / observe / basic / board / quotes / adj_factors / fina / permissions；
        # adj_factors / board_data / fina_indicator 再按行切开，遇 502 自动对半拆。
        # modules 仅带本 bundle 细项，避免把其它类 code 交给生产 expand_modules 白名单。
        for bundle_key, bundle_data in bundles.items():
            batch_mods = filter_modules_for_bundle(bundle_key, mods)
            if bundle_key == "adj_factors":
                chunk_bundles = iter_adj_factor_push_chunks(
                    bundle_data, chunk_rows=row_chunk
                )
                for ci, chunk_data in enumerate(chunk_bundles):
                    rows = list(
                        ((chunk_data.get("items") or {}).get("stock_adj_factor")) or []
                    )
                    label = (
                        f"adj_factors[{ci + 1}/{len(chunk_bundles)}]"
                        if len(chunk_bundles) > 1
                        else "adj_factors"
                    )
                    _push_adj_rows_adaptive(
                        url=url,
                        headers=headers,
                        batch_mods=batch_mods,
                        base_bundle=chunk_data,
                        rows=rows,
                        label=label,
                        merged_results=merged_results,
                        push_batches=push_batches,
                    )
                continue

            if bundle_key == "board_data":
                chunk_bundles = iter_board_data_push_chunks(
                    bundle_data, chunk_rows=row_chunk
                )
                for ci, chunk_data in enumerate(chunk_bundles):
                    label = (
                        f"board_data[{ci + 1}/{len(chunk_bundles)}]"
                        if len(chunk_bundles) > 1
                        else "board_data"
                    )
                    _push_bundle_adaptive(
                        url=url,
                        headers=headers,
                        batch_mods=batch_mods,
                        bundle_key=bundle_key,
                        bundle_data=chunk_data,
                        label=label,
                        merged_results=merged_results,
                        push_batches=push_batches,
                    )
                continue

            if bundle_key == "fina_indicator":
                chunk_bundles = iter_fina_indicator_push_chunks(
                    bundle_data, chunk_rows=row_chunk
                )
                for ci, chunk_data in enumerate(chunk_bundles):
                    label = (
                        f"fina_indicator[{ci + 1}/{len(chunk_bundles)}]"
                        if len(chunk_bundles) > 1
                        else "fina_indicator"
                    )
                    _push_bundle_adaptive(
                        url=url,
                        headers=headers,
                        batch_mods=batch_mods,
                        bundle_key=bundle_key,
                        bundle_data=chunk_data,
                        label=label,
                        merged_results=merged_results,
                        push_batches=push_batches,
                    )
                continue

            _push_bundle_adaptive(
                url=url,
                headers=headers,
                batch_mods=batch_mods,
                bundle_key=bundle_key,
                bundle_data=bundle_data,
                label=bundle_key,
                merged_results=merged_results,
                push_batches=push_batches,
            )

        write_audit(
            db,
            direction="push",
            modules=mods,
            operator=_operator(admin),
            success=True,
            summary=merged_results,
        )
        return {
            "success": True,
            "direction": "push",
            "modules": mods,
            "date_range": local.get("date_range"),
            "results": merged_results,
            "push_batches": push_batches,
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
