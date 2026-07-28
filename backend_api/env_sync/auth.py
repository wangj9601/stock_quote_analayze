# -*- coding: utf-8 -*-
"""Sync Key 生成、哈希与校验。"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from typing import Optional, Tuple

from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session

from backend_api.database import get_db
from backend_api.models import EnvSyncServerConfig


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


def get_server_expected_hash(db: Session) -> Tuple[bool, Optional[str]]:
    """返回 (enabled, hash)。DB 优先，否则 ENV_SYNC_KEY。"""
    row = db.query(EnvSyncServerConfig).filter(EnvSyncServerConfig.id == 1).first()
    if row and row.sync_key_hash:
        return bool(row.enabled), row.sync_key_hash
    env_key = (os.getenv("ENV_SYNC_KEY") or "").strip()
    if env_key:
        return True, hash_sync_key(env_key)
    return False, None


def verify_sync_key(db: Session, presented: str) -> bool:
    enabled, expected = get_server_expected_hash(db)
    if not enabled or not expected or not presented:
        return False
    got = hash_sync_key(presented)
    return hmac.compare_digest(got, expected)


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
