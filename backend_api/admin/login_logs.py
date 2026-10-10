# -*- coding: utf-8 -*-
"""管理端：登录日志查询。"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend_api.auth import get_current_admin
from backend_api.database import get_db
from backend_api.models import Admin
from backend_api.services import login_log_service

router = APIRouter(prefix="/api/admin/login-logs", tags=["admin-login-logs"])


class LoginLogItem(BaseModel):
    id: int
    channel: str
    user_id: Optional[int] = None
    username: str
    success: bool
    failure_reason: Optional[str] = None
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: Optional[str] = None


class LoginLogListResponse(BaseModel):
    items: List[LoginLogItem]
    total: int
    page: int
    page_size: int


@router.get("", response_model=LoginLogListResponse)
def list_login_logs(
    channel: Optional[str] = Query(None, description="user | admin"),
    username: Optional[str] = Query(None, description="用户名模糊匹配"),
    success: Optional[bool] = Query(None, description="是否成功"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_admin
    return login_log_service.query_login_logs(
        db,
        channel=channel,
        username=username,
        success=success,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
