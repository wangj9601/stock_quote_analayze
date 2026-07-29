# -*- coding: utf-8 -*-
"""服务端/客户端配置读写。"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from backend_api.env_sync.auth import generate_sync_key, hash_sync_key, key_hint, mask_key
from backend_api.models import EnvSyncClientConfig, EnvSyncServerConfig, EnvSyncAuditLog

logger = logging.getLogger(__name__)


def ensure_server_row(db: Session) -> EnvSyncServerConfig:
    row = db.query(EnvSyncServerConfig).filter(EnvSyncServerConfig.id == 1).first()
    if not row:
        row = EnvSyncServerConfig(id=1, enabled=False)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def ensure_client_row(db: Session) -> EnvSyncClientConfig:
    row = db.query(EnvSyncClientConfig).filter(EnvSyncClientConfig.id == 1).first()
    if not row:
        row = EnvSyncClientConfig(id=1, enabled=False, prod_base_url="")
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def get_server_config_public(db: Session) -> Dict[str, Any]:
    row = ensure_server_row(db)
    return {
        "enabled": bool(row.enabled),
        "has_key": bool(row.sync_key_hash),
        "key_hint": row.key_hint or "",
        "updated_at": row.updated_at.isoformat(sep=" ", timespec="seconds")
        if row.updated_at
        else None,
        "env_fallback": bool((os.getenv("ENV_SYNC_KEY") or "").strip()),
    }


def rotate_server_key(db: Session, *, enabled: Optional[bool] = None) -> Dict[str, Any]:
    row = ensure_server_row(db)
    raw = generate_sync_key()
    row.sync_key_hash = hash_sync_key(raw)
    row.key_hint = key_hint(raw)
    if enabled is not None:
        row.enabled = bool(enabled)
    elif not row.enabled:
        row.enabled = True
    row.updated_at = datetime.now()
    db.commit()
    return {
        "enabled": bool(row.enabled),
        "sync_key": raw,
        "key_hint": row.key_hint,
        "message": "请立即保存明文 Sync Key，之后仅显示脱敏提示",
    }


def update_server_config(
    db: Session,
    *,
    enabled: Optional[bool] = None,
    sync_key: Optional[str] = None,
) -> Dict[str, Any]:
    row = ensure_server_row(db)
    if enabled is not None:
        row.enabled = bool(enabled)
    if sync_key is not None and str(sync_key).strip():
        raw = str(sync_key).strip()
        row.sync_key_hash = hash_sync_key(raw)
        row.key_hint = key_hint(raw)
    row.updated_at = datetime.now()
    db.commit()
    return get_server_config_public(db)


def get_client_config_public(db: Session) -> Dict[str, Any]:
    row = ensure_client_row(db)
    env_url = (os.getenv("ENV_SYNC_PROD_BASE_URL") or "").strip()
    return {
        "enabled": bool(row.enabled),
        "prod_base_url": row.prod_base_url or env_url or "",
        "has_key": bool(row.sync_key),
        "sync_key_masked": mask_key(row.sync_key),
        "updated_at": row.updated_at.isoformat(sep=" ", timespec="seconds")
        if row.updated_at
        else None,
        "env_fallback_url": bool(env_url),
    }


def update_client_config(
    db: Session,
    *,
    enabled: Optional[bool] = None,
    prod_base_url: Optional[str] = None,
    sync_key: Optional[str] = None,
) -> Dict[str, Any]:
    row = ensure_client_row(db)
    if enabled is not None:
        row.enabled = bool(enabled)
    if prod_base_url is not None:
        row.prod_base_url = str(prod_base_url).strip().rstrip("/")
    if sync_key is not None and str(sync_key).strip():
        row.sync_key = str(sync_key).strip()
    row.updated_at = datetime.now()
    db.commit()
    return get_client_config_public(db)


def resolve_client_credentials(db: Session) -> Dict[str, str]:
    """返回本地调生产所需的 base_url + key。"""
    row = ensure_client_row(db)
    url = (row.prod_base_url or "").strip().rstrip("/")
    key = (row.sync_key or "").strip()
    if not url:
        url = (os.getenv("ENV_SYNC_PROD_BASE_URL") or "").strip().rstrip("/")
    if not key:
        key = (os.getenv("ENV_SYNC_KEY") or "").strip()
    if not row.enabled:
        raise ValueError("环境同步客户端未启用，请先在管理端开启")
    if not url or not key:
        raise ValueError("请配置生产 Base URL 与 Sync Key")
    return {"prod_base_url": url, "sync_key": key}


def write_audit(
    db: Session,
    *,
    direction: str,
    modules: Any,
    operator: Optional[str],
    success: bool,
    summary: Any = None,
    error_message: Optional[str] = None,
) -> None:
    """写入审计。先 rollback 清掉失败事务，避免 InFailedSqlTransaction 掩盖真实错误。

    约定：业务数据须在调用前已 commit（export 只读；import 各模块内已 commit）。
    """
    try:
        db.rollback()
    except Exception:
        logger.debug("env_sync write_audit: pre-rollback ignored", exc_info=True)
    try:
        db.add(
            EnvSyncAuditLog(
                direction=direction,
                modules=modules,
                operator=operator,
                success=success,
                summary=summary,
                error_message=(error_message or "")[:4000] if error_message else None,
                created_at=datetime.now(),
            )
        )
        db.commit()
    except Exception:
        logger.exception("env_sync write_audit failed")
        try:
            db.rollback()
        except Exception:
            pass
