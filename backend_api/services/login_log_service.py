# -*- coding: utf-8 -*-
"""用户/管理员登录日志：写入与查询。"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend_api.database import SessionLocal

logger = logging.getLogger(__name__)

VALID_CHANNELS = frozenset({"user", "admin"})


def record_login_log(
    *,
    channel: str,
    username: str,
    success: bool,
    user_id: Optional[int] = None,
    failure_reason: Optional[str] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """独立会话写入登录日志；失败不影响登录主流程。"""
    ch = (channel or "").strip().lower()
    if ch not in VALID_CHANNELS:
        ch = "user"
    name = (username or "").strip() or "(unknown)"
    db = SessionLocal()
    try:
        from backend_api.models import UserLoginLog

        if UserLoginLog is None:
            logger.warning("UserLoginLog 模型未就绪，跳过登录日志写入")
            return
        row = UserLoginLog(
            channel=ch,
            user_id=user_id,
            username=name[:128],
            success=bool(success),
            failure_reason=str(failure_reason)[:500] if failure_reason else None,
            ip=str(ip)[:64] if ip else None,
            user_agent=str(user_agent)[:512] if user_agent else None,
            created_at=datetime.now(),
        )
        db.add(row)
        db.commit()
    except Exception:
        logger.exception(
            "写入登录日志失败 channel=%s username=%s success=%s",
            ch,
            name,
            success,
        )
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


def _row_to_dict(row: Any) -> Dict[str, Any]:
    created = getattr(row, "created_at", None)
    return {
        "id": row.id,
        "channel": row.channel,
        "user_id": row.user_id,
        "username": row.username,
        "success": bool(row.success),
        "failure_reason": row.failure_reason,
        "ip": row.ip,
        "user_agent": row.user_agent,
        "created_at": created.isoformat() if hasattr(created, "isoformat") else created,
    }


def query_login_logs(
    db: Session,
    *,
    channel: Optional[str] = None,
    username: Optional[str] = None,
    success: Optional[bool] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    from backend_api.models import UserLoginLog

    if UserLoginLog is None:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or 20), 1), 200)

    q = db.query(UserLoginLog)
    if channel:
        ch = channel.strip().lower()
        if ch in VALID_CHANNELS:
            q = q.filter(UserLoginLog.channel == ch)
    if username:
        kw = f"%{username.strip()}%"
        q = q.filter(UserLoginLog.username.ilike(kw))
    if success is not None:
        q = q.filter(UserLoginLog.success == bool(success))
    if start_date is not None:
        q = q.filter(UserLoginLog.created_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date is not None:
        q = q.filter(UserLoginLog.created_at <= datetime.combine(end_date, datetime.max.time()))

    total = q.count()
    rows: List[Any] = (
        q.order_by(UserLoginLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [_row_to_dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
