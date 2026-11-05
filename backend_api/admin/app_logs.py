# -*- coding: utf-8 -*-
"""管理端：应用日志文件查询（白名单、尾部窗口）。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend_api.auth import get_current_admin
from backend_api.services import app_log_service

router = APIRouter(prefix="/api/admin/app-logs", tags=["admin-app-logs"])


@router.get("/files")
async def list_app_log_files(current_user=Depends(get_current_admin)):
    """列出白名单内可读的应用日志主文件。"""
    return {"files": app_log_service.list_whitelist_files()}


@router.get("/query")
async def query_app_logs(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    levels: Optional[str] = Query(
        "WARNING,ERROR",
        description="级别，逗号分隔；all 表示不过滤。默认 WARNING,ERROR",
    ),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    keyword: Optional[str] = Query(None, description="关键字（logger/消息/文件名）"),
    source_file: Optional[str] = Query(None, description="白名单主文件名，如 app.log"),
    current_user=Depends(get_current_admin),
):
    """扫描 LOGS_DIR 白名单日志尾部窗口并筛选。"""
    selected = (source_file or "").strip() or None
    if selected:
        if "/" in selected or "\\" in selected or ".." in selected:
            raise HTTPException(status_code=400, detail="非法或不在白名单的 source_file")
        if not app_log_service.is_whitelist_name(selected):
            raise HTTPException(status_code=400, detail="非法或不在白名单的 source_file")
        # 只允许主文件名，不允许 app.log.1
        if selected != app_log_service._primary_log_name(selected):
            raise HTTPException(status_code=400, detail="请使用主日志文件名（勿带轮转后缀）")

    try:
        return app_log_service.scan_app_logs(
            levels=levels,
            start_date=start_date,
            end_date=end_date,
            keyword=keyword,
            source_file=selected,
            page=page,
            page_size=page_size,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取应用日志失败: {e}") from e
