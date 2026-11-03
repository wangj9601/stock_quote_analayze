# -*- coding: utf-8 -*-
"""env_sync_jobs 读写与进程内运行槽。"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend_api.models import EnvSyncJob

_lock = threading.Lock()
_running: Dict[str, str] = {}  # direction_key -> job_id


def _direction_slot(direction: str) -> str:
    """同族方向互斥：async_push / async_pull / async_export / async_import 各自一把锁。"""
    return (direction or "").strip() or "unknown"


def claim_running_slot(direction: str, job_id: str) -> bool:
    key = _direction_slot(direction)
    with _lock:
        cur = _running.get(key)
        if cur and cur != job_id:
            return False
        _running[key] = job_id
        return True


def is_direction_busy(direction: str) -> bool:
    key = _direction_slot(direction)
    with _lock:
        return bool(_running.get(key))


def release_running_slot(direction: str, job_id: str) -> None:
    key = _direction_slot(direction)
    with _lock:
        if _running.get(key) == job_id:
            _running.pop(key, None)


def new_job_id() -> str:
    return str(uuid.uuid4())


def create_job(
    db: Session,
    *,
    direction: str,
    modules: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    created_by: Optional[str] = None,
    job_id: Optional[str] = None,
    artifact_dir: Optional[str] = None,
) -> EnvSyncJob:
    jid = job_id or new_job_id()
    row = EnvSyncJob(
        id=jid,
        direction=direction,
        status="pending",
        modules=modules,
        start_date=start_date,
        end_date=end_date,
        progress=0,
        stage="pending",
        message=None,
        artifact_dir=artifact_dir,
        created_by=created_by,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_job(db: Session, job_id: str) -> Optional[EnvSyncJob]:
    return db.query(EnvSyncJob).filter(EnvSyncJob.id == job_id).first()


def update_job(
    db: Session,
    job_id: str,
    *,
    status: Optional[str] = None,
    progress: Optional[int] = None,
    stage: Optional[str] = None,
    message: Optional[str] = None,
    artifact_dir: Optional[str] = None,
    remote_job_id: Optional[str] = None,
    summary: Any = None,
    error_message: Optional[str] = None,
    cancel_requested: Optional[bool] = None,
) -> Optional[EnvSyncJob]:
    row = get_job(db, job_id)
    if not row:
        return None
    if status is not None:
        row.status = status
    if progress is not None:
        row.progress = max(0, min(100, int(progress)))
    if stage is not None:
        row.stage = stage
    if message is not None:
        row.message = message
    if artifact_dir is not None:
        row.artifact_dir = artifact_dir
    if remote_job_id is not None:
        row.remote_job_id = remote_job_id
    if summary is not None:
        row.summary = summary
    if error_message is not None:
        row.error_message = error_message
    if cancel_requested is not None:
        row.cancel_requested = bool(cancel_requested)
    row.updated_at = datetime.now()
    db.commit()
    db.refresh(row)
    return row


def list_jobs(db: Session, *, limit: int = 30) -> List[EnvSyncJob]:
    lim = max(1, min(200, int(limit)))
    return (
        db.query(EnvSyncJob)
        .order_by(EnvSyncJob.created_at.desc())
        .limit(lim)
        .all()
    )


def job_public(row: EnvSyncJob) -> Dict[str, Any]:
    return {
        "job_id": row.id,
        "direction": row.direction,
        "status": row.status,
        "modules": row.modules,
        "start_date": row.start_date,
        "end_date": row.end_date,
        "progress": row.progress,
        "stage": row.stage,
        "message": row.message,
        "remote_job_id": row.remote_job_id,
        "summary": row.summary,
        "error_message": row.error_message,
        "cancel_requested": bool(row.cancel_requested),
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat(sep=" ", timespec="seconds")
        if row.created_at
        else None,
        "updated_at": row.updated_at.isoformat(sep=" ", timespec="seconds")
        if row.updated_at
        else None,
    }
