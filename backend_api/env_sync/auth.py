# -*- coding: utf-8 -*-
"""Sync Key 生成、哈希与校验。"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from typing import List, Optional

from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session

from backend_api.database import get_db
from backend_api.models import EnvSyncServerConfig, EnvSyncServerKey


def hash_sync_key(raw: str) -> str:
    return hashlib.sha256((raw or "").encode("utf-8")).hexdigest()


def generate_sync_key() -> str:
    return secrets.token_urlsafe(32)


def key_hint(raw: str) -> str:
    s = (raw or "").strip()
    if len(s) <= 8:
        return s[:2] + "***" if s else ""
    return f"{s[:4]}...{s[-4:]}"


def mask_key(raw: Optional[str]) -> str:
    if not raw:
        return ""
    return key_hint(raw)


def _extract_key(
    authorization: Optional[str],
    x_env_sync_key: Optional[str],
) -> str:
    if x_env_sync_key and x_env_sync_key.strip():
        return x_env_sync_key.strip()
    if authorization:
        parts = authorization.strip().split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
        if len(parts) == 1:
            return parts[0].strip()
    return ""


def _collect_expected_hashes(db: Session) -> tuple[bool, List[str]]:
    """返回 (enabled, hashes)。多 Key 表优先；兼容旧单行 hash 与 ENV_SYNC_KEY。"""
    row = db.query(EnvSyncServerConfig).filter(EnvSyncServerConfig.id == 1).first()
    enabled = bool(row.enabled) if row else False
    hashes: List[str] = []

    try:
        key_rows = (
            db.query(EnvSyncServerKey)
            .filter(EnvSyncServerKey.enabled.is_(True))
            .all()
        )
        for kr in key_rows:
            h = (kr.sync_key_hash or "").strip()
            if h and h not in hashes:
                hashes.append(h)
    except Exception:
        # 表尚未迁移时降级到旧逻辑
        db.rollback()

    if row and row.sync_key_hash:
        h = (row.sync_key_hash or "").strip()
        if h and h not in hashes:
            hashes.append(h)

    if not hashes:
        env_key = (os.getenv("ENV_SYNC_KEY") or "").strip()
        if env_key:
            return True, [hash_sync_key(env_key)]
        return enabled, []

    # 有 DB Key 时以服务端开关为准；无 config 行但有 keys 时默认开启
    if row is None and hashes:
        return True, hashes
    return enabled, hashes


def get_server_expected_hash(db: Session):
    """兼容旧调用：返回 (enabled, 首个 hash 或 None)。"""
    enabled, hashes = _collect_expected_hashes(db)
    return enabled, hashes[0] if hashes else None


def verify_sync_key(db: Session, presented: str) -> bool:
    enabled, expected_list = _collect_expected_hashes(db)
    if not enabled or not expected_list or not presented:
        return False
    got = hash_sync_key(presented)
    return any(hmac.compare_digest(got, expected) for expected in expected_list)


def require_env_sync_key(
    authorization: Optional[str] = Header(None),
    x_env_sync_key: Optional[str] = Header(None, alias="X-Env-Sync-Key"),
    db: Session = Depends(get_db),
) -> str:
    """网关依赖：校验 Sync Key，返回明文 key（仅用于日志脱敏）。"""
    presented = _extract_key(authorization, x_env_sync_key)
    if not verify_sync_key(db, presented):
        raise HTTPException(status_code=401, detail="Invalid or missing env sync key")
    return presented
