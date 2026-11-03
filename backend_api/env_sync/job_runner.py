# -*- coding: utf-8 -*-
"""环境同步异步 Job 后台执行。"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from backend_api.database import SessionLocal
from backend_api.env_sync import remote_http
from backend_api.env_sync.artifacts import ensure_job_dirs, read_manifest
from backend_api.env_sync.job_store import (
    claim_running_slot,
    get_job,
    release_running_slot,
    update_job,
)
from backend_api.env_sync.part_io import build_export_parts, read_part_json, sha256_file
from backend_api.env_sync.services import import_modules

logger = logging.getLogger(__name__)


def _prod_headers(key: str) -> Dict[str, str]:
    return {
        "X-Env-Sync-Key": key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _merge_results(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
    for k, v in (src or {}).items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            for kk, vv in v.items():
                if isinstance(vv, (int, float)) and isinstance(dst[k].get(kk), (int, float)):
                    dst[k][kk] = dst[k].get(kk, 0) + vv
                elif kk == "errors" and isinstance(vv, list):
                    dst[k].setdefault("errors", []).extend(vv)
                else:
                    dst[k][kk] = vv
        else:
            dst[k] = v


def start_thread(target: Callable, *, name: str) -> None:
    t = threading.Thread(target=target, name=name, daemon=True)
    t.start()


def run_server_export_job(job_id: str) -> None:
    """生产侧：异步 export 落盘。"""
    db = SessionLocal()
    direction = "async_export"
    try:
        row = get_job(db, job_id)
        if not row:
            return
        if not claim_running_slot(direction, job_id):
            update_job(
                db,
                job_id,
                status="failed",
                stage="failed",
                error_message="已有同方向异步任务在运行",
            )
            return
        if not update_job(db, job_id, status="running", stage="exporting", progress=5, message="开始导出"):
            return
        dest = ensure_job_dirs(job_id)
        update_job(db, job_id, artifact_dir=str(dest))
        row = get_job(db, job_id)
        if row and row.cancel_requested:
            update_job(db, job_id, status="failed", stage="cancelled", error_message="已取消")
            return
        manifest = build_export_parts(
            db,
            row.modules if row else None,
            start_date=row.start_date if row else None,
            end_date=row.end_date if row else None,
            dest=dest,
            env_label="prod",
        )
        update_job(
            db,
            job_id,
            status="succeeded",
            stage="ready",
            progress=100,
            message=f"导出完成，共 {manifest.get('part_count', 0)} 片",
            summary={"manifest": {"part_count": manifest.get("part_count"), "parts": manifest.get("parts")}},
        )
    except Exception as e:
        logger.exception("async_export failed job=%s", job_id)
        try:
            update_job(
                db,
                job_id,
                status="failed",
                stage="failed",
                error_message=f"{type(e).__name__}: {e}",
            )
        except Exception:
            pass
    finally:
        release_running_slot(direction, job_id)
        db.close()


def run_admin_push_job(job_id: str, *, prod_base_url: str, sync_key: str) -> None:
    """客户端：本地分片导出并上传到生产 import。"""
    db = SessionLocal()
    direction = "async_push"
    try:
        row = get_job(db, job_id)
        if not row:
            return
        if not claim_running_slot(direction, job_id):
            update_job(
                db,
                job_id,
                status="failed",
                stage="failed",
                error_message="已有异步 Push 在运行",
            )
            return
        update_job(db, job_id, status="running", stage="exporting", progress=5, message="本地导出分片")
        dest = ensure_job_dirs(job_id)
        update_job(db, job_id, artifact_dir=str(dest))
        row = get_job(db, job_id)
        manifest = build_export_parts(
            db,
            row.modules if row else None,
            start_date=row.start_date if row else None,
            end_date=row.end_date if row else None,
            dest=dest,
        )
        parts = list(manifest.get("parts") or [])
        if not parts:
            update_job(
                db,
                job_id,
                status="failed",
                stage="failed",
                error_message="导出结果为空",
            )
            return

        base = prod_base_url.rstrip("/")
        headers = _prod_headers(sync_key)
        merged: Dict[str, Any] = {}
        total = len(parts)
        remote_import_job_id: Optional[str] = None
        for i, meta in enumerate(parts):
            row = get_job(db, job_id)
            if row and row.cancel_requested:
                update_job(db, job_id, status="failed", stage="cancelled", error_message="已取消")
                return
            name = meta["name"]
            path = dest / "parts" / name
            payload = read_part_json(path)
            progress = 10 + int(80 * (i / max(total, 1)))
            update_job(
                db,
                job_id,
                stage="uploading",
                progress=progress,
                message=f"上传 {i + 1}/{total}: {name}",
            )
            url = f"{base}/api/env-sync/v1/jobs/import"
            body: Dict[str, Any] = {
                "client_job_id": job_id,
                "part_name": name,
                "part_index": i + 1,
                "part_total": total,
                "bundles": payload.get("bundles") or {},
                "modules": payload.get("modules"),
            }
            if remote_import_job_id:
                body["job_id"] = remote_import_job_id
            resp = remote_http.post(url, headers=headers, json_body=body, timeout=600.0)
            if resp.status_code != 200:
                raise RuntimeError(
                    f"生产 import 分片失败 HTTP {resp.status_code}: {(resp.text or '')[:400]}"
                )
            try:
                data = resp.json() or {}
                if data.get("job_id"):
                    remote_import_job_id = str(data["job_id"])
                    update_job(db, job_id, remote_job_id=remote_import_job_id)
                _merge_results(merged, data.get("results") or {})
            except Exception:
                pass

        update_job(
            db,
            job_id,
            status="succeeded",
            stage="succeeded",
            progress=100,
            message=f"Push 完成，共 {total} 片",
            summary={"results": merged, "part_count": total},
        )
    except Exception as e:
        logger.exception("async_push failed job=%s", job_id)
        try:
            update_job(
                db,
                job_id,
                status="failed",
                stage="failed",
                error_message=f"{type(e).__name__}: {e}",
            )
        except Exception:
            pass
    finally:
        release_running_slot(direction, job_id)
        db.close()


def run_admin_pull_job(job_id: str, *, prod_base_url: str, sync_key: str) -> None:
    """客户端：请求生产异步 export，下载分片并本地 import。"""
    db = SessionLocal()
    direction = "async_pull"
    try:
        row = get_job(db, job_id)
        if not row:
            return
        if not claim_running_slot(direction, job_id):
            update_job(
                db,
                job_id,
                status="failed",
                stage="failed",
                error_message="已有异步 Pull 在运行",
            )
            return
        update_job(db, job_id, status="running", stage="request_export", progress=5, message="请求生产导出")
        base = prod_base_url.rstrip("/")
        headers = _prod_headers(sync_key)
        create_url = f"{base}/api/env-sync/v1/jobs/export"
        create_body = {
            "modules": row.modules,
            "start_date": row.start_date,
            "end_date": row.end_date,
        }
        resp = remote_http.post(create_url, headers=headers, json_body=create_body, timeout=60.0)
        if resp.status_code != 200:
            raise RuntimeError(
                f"生产创建 export job 失败 HTTP {resp.status_code}: {(resp.text or '')[:400]}"
            )
        remote_id = (resp.json() or {}).get("job_id")
        if not remote_id:
            raise RuntimeError("生产未返回 job_id")
        update_job(db, job_id, remote_job_id=str(remote_id), stage="wait_export", message="等待生产导出")

        # 轮询生产 job
        status_url = f"{base}/api/env-sync/v1/jobs/{remote_id}"
        remote_status = None
        remote_summary = None
        for _ in range(3600):  # 最多约 2h（2s 间隔）
            row = get_job(db, job_id)
            if row and row.cancel_requested:
                update_job(db, job_id, status="failed", stage="cancelled", error_message="已取消")
                return
            st = remote_http.get(status_url, headers=headers, timeout=30.0)
            if st.status_code != 200:
                raise RuntimeError(
                    f"查询生产 job 失败 HTTP {st.status_code}: {(st.text or '')[:300]}"
                )
            info = st.json() or {}
            remote_status = info.get("status")
            remote_summary = info.get("summary")
            prog = info.get("progress")
            update_job(
                db,
                job_id,
                progress=min(40, int(prog or 0) // 2 + 5),
                message=f"生产导出中: {info.get('stage') or remote_status}",
            )
            if remote_status in ("succeeded", "failed"):
                break
            time.sleep(2)
        if remote_status != "succeeded":
            raise RuntimeError(
                f"生产导出未成功: status={remote_status} err={((remote_summary or {}) if isinstance(remote_summary, dict) else {})}"
            )

        # 下载分片
        dest = ensure_job_dirs(job_id)
        update_job(db, job_id, artifact_dir=str(dest), stage="downloading", progress=45, message="下载分片")
        parts = []
        if isinstance(remote_summary, dict):
            parts = ((remote_summary.get("manifest") or {}).get("parts")) or []
        if not parts:
            # 再拉一次 job 详情
            st = remote_http.get(status_url, headers=headers, timeout=30.0)
            info = st.json() or {}
            parts = (((info.get("summary") or {}).get("manifest") or {}).get("parts")) or []
        if not parts:
            raise RuntimeError("生产 manifest 无分片")

        parts_dir = dest / "parts"
        parts_dir.mkdir(parents=True, exist_ok=True)
        total = len(parts)
        for i, meta in enumerate(parts):
            name = meta["name"]
            url = f"{base}/api/env-sync/v1/jobs/{remote_id}/parts/{name}"
            update_job(
                db,
                job_id,
                progress=45 + int(25 * (i / max(total, 1))),
                message=f"下载 {i + 1}/{total}: {name}",
            )
            raw = remote_http.get_bytes(url, headers=headers, timeout=600.0)
            if raw.status_code != 200:
                raise RuntimeError(
                    f"下载分片失败 HTTP {raw.status_code}: {name}"
                )
            path = parts_dir / name
            path.write_bytes(raw.content)
            expect = meta.get("sha256")
            if expect and sha256_file(path) != expect:
                raise RuntimeError(f"分片校验失败: {name}")

        # 本地导入
        update_job(db, job_id, stage="importing", progress=75, message="本地导入")
        merged: Dict[str, Any] = {}
        for i, meta in enumerate(parts):
            row = get_job(db, job_id)
            if row and row.cancel_requested:
                update_job(db, job_id, status="failed", stage="cancelled", error_message="已取消")
                return
            name = meta["name"]
            payload = read_part_json(parts_dir / name)
            result = import_modules(
                db,
                payload.get("bundles") or {},
                modules=payload.get("modules"),
            )
            _merge_results(merged, result.get("results") or result or {})
            update_job(
                db,
                job_id,
                progress=75 + int(20 * ((i + 1) / max(total, 1))),
                message=f"导入 {i + 1}/{total}: {name}",
            )

        update_job(
            db,
            job_id,
            status="succeeded",
            stage="succeeded",
            progress=100,
            message=f"Pull 完成，共 {total} 片",
            summary={"results": merged, "part_count": total, "remote_job_id": remote_id},
        )
    except Exception as e:
        logger.exception("async_pull failed job=%s", job_id)
        try:
            update_job(
                db,
                job_id,
                status="failed",
                stage="failed",
                error_message=f"{type(e).__name__}: {e}",
            )
        except Exception:
            pass
    finally:
        release_running_slot(direction, job_id)
        db.close()
