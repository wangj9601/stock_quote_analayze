# -*- coding: utf-8 -*-
"""服务端/客户端配置读写。"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend_api.env_sync.auth import generate_sync_key, hash_sync_key, key_hint, mask_key
from backend_api.models import (
    EnvSyncAuditLog,
    EnvSyncClientConfig,
    EnvSyncServerConfig,
    EnvSyncServerKey,
)

logger = logging.getLogger(__name__)


def ensure_server_row(db: Session) -> EnvSyncServerConfig:
    row = db.query(EnvSyncServerConfig).filter(EnvSyncServerConfig.id == 1).first()
    if not row:
        row = EnvSyncServerConfig(id=1, enabled=False)
        db.add(row)
        db.commit()
        db.refresh(row)
    migrate_legacy_server_key(db, row)
    return row


def ensure_client_row(db: Session) -> EnvSyncClientConfig:
    row = db.query(EnvSyncClientConfig).filter(EnvSyncClientConfig.id == 1).first()
    if not row:
        row = EnvSyncClientConfig(id=1, enabled=False, prod_base_url="")
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def migrate_legacy_server_key(
    db: Session, row: Optional[EnvSyncServerConfig] = None
) -> None:
    """将旧单行 sync_key_hash 迁入多 Key 表（幂等）。"""
    row = row or db.query(EnvSyncServerConfig).filter(EnvSyncServerConfig.id == 1).first()
    if not row or not (row.sync_key_hash or "").strip():
        return
    try:
        exists = (
            db.query(EnvSyncServerKey)
            .filter(EnvSyncServerKey.sync_key_hash == row.sync_key_hash)
            .first()
        )
        if exists:
            return
        db.add(
            EnvSyncServerKey(
                label="legacy",
                sync_key_hash=row.sync_key_hash,
                key_hint=row.key_hint or "",
                enabled=True,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        )
        db.commit()
    except Exception:
        logger.debug("env_sync migrate_legacy_server_key skipped", exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass


def _serialize_key(row: EnvSyncServerKey) -> Dict[str, Any]:
    return {
        "id": row.id,
        "label": row.label or "",
        "key_hint": row.key_hint or "",
        "enabled": bool(row.enabled),
        "created_at": row.created_at.isoformat(sep=" ", timespec="seconds")
        if row.created_at
        else None,
        "updated_at": row.updated_at.isoformat(sep=" ", timespec="seconds")
        if row.updated_at
        else None,
    }


def list_server_keys(db: Session) -> List[Dict[str, Any]]:
    ensure_server_row(db)
    rows = (
        db.query(EnvSyncServerKey)
        .order_by(EnvSyncServerKey.id.asc())
        .all()
    )
    return [_serialize_key(r) for r in rows]


def get_server_config_public(db: Session) -> Dict[str, Any]:
    row = ensure_server_row(db)
    keys = list_server_keys(db)
    return {
        "enabled": bool(row.enabled),
        "has_key": len(keys) > 0 or bool(row.sync_key_hash),
        "key_hint": (keys[0]["key_hint"] if keys else None) or row.key_hint or "",
        "key_count": len(keys),
        "keys": keys,
        "updated_at": row.updated_at.isoformat(sep=" ", timespec="seconds")
        if row.updated_at
        else None,
        "env_fallback": bool((os.getenv("ENV_SYNC_KEY") or "").strip()),
    }


def add_server_key(
    db: Session,
    *,
    label: Optional[str] = None,
    sync_key: Optional[str] = None,
    enabled: bool = True,
) -> Dict[str, Any]:
    """新增一把 Key；未传明文则自动生成。返回含一次性明文 sync_key。"""
    ensure_server_row(db)
    raw = (sync_key or "").strip() or generate_sync_key()
    digest = hash_sync_key(raw)
    dup = (
        db.query(EnvSyncServerKey)
        .filter(EnvSyncServerKey.sync_key_hash == digest)
        .first()
    )
    if dup:
        raise ValueError("该 Sync Key 已存在")
    row = EnvSyncServerKey(
        label=(label or "").strip()[:100],
        sync_key_hash=digest,
        key_hint=key_hint(raw),
        enabled=bool(enabled),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db.add(row)
    # 有 Key 后默认打开校验（与旧 rotate 行为一致）
    cfg = ensure_server_row(db)
    if not cfg.enabled:
        cfg.enabled = True
    cfg.updated_at = datetime.now()
    # 同步旧单行展示字段为最新一把（兼容旧客户端读 key_hint）
    cfg.sync_key_hash = digest
    cfg.key_hint = row.key_hint
    db.commit()
    db.refresh(row)
    return {
        "enabled": bool(cfg.enabled),
        "sync_key": raw,
        "key": _serialize_key(row),
        "key_hint": row.key_hint,
        "message": "请立即保存明文 Sync Key，之后仅显示脱敏提示",
        "config": get_server_config_public(db),
    }


def update_server_key(
    db: Session,
    key_id: int,
    *,
    label: Optional[str] = None,
    enabled: Optional[bool] = None,
) -> Dict[str, Any]:
    row = db.query(EnvSyncServerKey).filter(EnvSyncServerKey.id == key_id).first()
    if not row:
        raise ValueError("Key 不存在")
    if label is not None:
        row.label = str(label).strip()[:100]
    if enabled is not None:
        row.enabled = bool(enabled)
    row.updated_at = datetime.now()
    db.commit()
    db.refresh(row)
    return {"key": _serialize_key(row), "config": get_server_config_public(db)}


def delete_server_key(db: Session, key_id: int) -> Dict[str, Any]:
    row = db.query(EnvSyncServerKey).filter(EnvSyncServerKey.id == key_id).first()
    if not row:
        raise ValueError("Key 不存在")
    digest = row.sync_key_hash
    cfg = db.query(EnvSyncServerConfig).filter(EnvSyncServerConfig.id == 1).first()
    db.delete(row)
    db.flush()
    remaining = (
        db.query(EnvSyncServerKey)
        .order_by(EnvSyncServerKey.id.desc())
        .first()
    )
    if cfg:
        # 先清掉兼容字段，避免 ensure/migrate 把刚删的 legacy Key 再插回来
        if cfg.sync_key_hash == digest or not remaining:
            if remaining:
                cfg.sync_key_hash = remaining.sync_key_hash
                cfg.key_hint = remaining.key_hint
            else:
                cfg.sync_key_hash = None
                cfg.key_hint = None
        cfg.updated_at = datetime.now()
    db.commit()
    return get_server_config_public(db)


def rotate_server_key(db: Session, *, enabled: Optional[bool] = None) -> Dict[str, Any]:
    """兼容旧「生成并轮换」：改为新增一把 Key（不删旧 Key）。"""
    if enabled is not None:
        update_server_config(db, enabled=enabled)
    return add_server_key(db, label="")


def update_server_config(
    db: Session,
    *,
    enabled: Optional[bool] = None,
    sync_key: Optional[str] = None,
) -> Dict[str, Any]:
    row = ensure_server_row(db)
    if enabled is not None:
        row.enabled = bool(enabled)
        row.updated_at = datetime.now()
        db.commit()
    if sync_key is not None and str(sync_key).strip():
        # 兼容旧接口：手动粘贴 Key = 新增一把
        add_server_key(db, sync_key=str(sync_key).strip())
        return get_server_config_public(db)
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
