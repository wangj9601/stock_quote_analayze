"""
GMS 回测管理端 API 路由
前缀: /api/admin/gms
"""

import logging
import os
import re
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, Body, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.database import get_db
from backend_api.models import StockBasicInfo, StockBasicInfoHK
from backend_core.strategies.gms import admin_interface
from backend_core.strategies.gms.config import GMSConfigManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/gms", tags=["GMS回测管理"])


def _get_stock_name(db: Session, code: str) -> str:
    """根据股票代码查询名称，A股/港股分别查对应表。"""
    c = str(code).strip()
    if not c:
        return ""
    # 港股：5位数字或字母开头
    is_hk = len(c) < 6 or not (c.isdigit() and c[0] in "6039")
    if is_hk:
        info = db.query(StockBasicInfoHK).filter(StockBasicInfoHK.code == c).first()
        if not info and c.isdigit():
            info = db.query(StockBasicInfoHK).filter(StockBasicInfoHK.code == c.zfill(5)).first()
        return (info.name or "").strip() if info else ""
    # A股：code 可能存为整数
    clean = c[2:] if c.startswith(("SZ", "SH")) else c
    for try_val in [clean, int(clean)] if clean.isdigit() else [clean]:
        try:
            info = db.query(StockBasicInfo).filter(StockBasicInfo.code == try_val).first()
        except (ValueError, TypeError):
            info = None
        if info and info.name:
            return str(info.name).strip()
    return ""


def _build_task_name_with_stocks(db: Session, config: dict) -> Optional[str]:
    """
    当股票池为单股或自定义时，生成包含股票名称和代码的任务名称。
    全市场时返回 None，由 backtest_storage 使用默认命名。
    """
    mode = config.get("stock_pool_mode") or "all"
    if mode == "single":
        code = (config.get("stock_code") or "").strip()
        if not code:
            return None
        name = _get_stock_name(db, code)
        return f"GMS回测_{code}_{name}" if name else f"GMS回测_{code}"
    if mode == "custom":
        pool = config.get("stock_pool") or []
        codes = [str(c).strip() for c in pool if str(c).strip()][:5]  # 最多5只
        if not codes:
            return None
        parts = []
        for code in codes:
            n = _get_stock_name(db, code)
            parts.append(f"{code}{n}" if n else code)
        return "GMS回测_" + "_".join(parts)
    return None


# ---------- 请求体 ----------
class BacktestCreateBody(BaseModel):
    task_name: Optional[str] = Field(None, description="任务名称")
    market: str = Field("all", description="市场: cn / hk / all")
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD")
    target_pct: float = Field(0.05, description="目标涨幅，如 0.05 表示 5%")
    horizon_days: int = Field(20, description="持有窗口交易日数")
    min_score: float = Field(0, description="最低总分")
    stock_pool_mode: Optional[str] = Field("all", description="股票池: all / single / custom")
    stock_code: Optional[str] = Field(None, description="单股回测时的股票代码，如 000001、00700")
    stock_pool: Optional[List[str]] = Field(None, description="自定义股票池代码列表")


# ---------- system/status ----------
@router.get("/system/status")
async def get_system_status():
    """系统状态：运行中任务数、报告总数、健康度等。"""
    try:
        tasks = admin_interface.list_backtest_tasks(limit=1000)
        running = sum(1 for t in tasks if t.get("status") in ("pending", "running"))
        reports = admin_interface.list_reports(limit=1)
        total_reports = len(admin_interface.list_reports(limit=10000))
        return {
            "success": True,
            "data": {
                "runningBacktests": running,
                "totalReports": total_reports,
                "systemHealth": "ok",
            },
        }
    except Exception as e:
        logger.exception("GMS system/status 失败")
        raise HTTPException(status_code=500, detail=str(e))


# ---------- backtests ----------
@router.post("/backtests")
async def create_backtest(body: BacktestCreateBody, db: Session = Depends(get_db)):
    """创建回测任务，返回 task_id。任务名称未填写时，单股/自定义股票池时自动包含股票名称和代码。"""
    try:
        config = {
            "task_name": body.task_name,
            "market": body.market,
            "start_date": body.start_date,
            "end_date": body.end_date,
            "target_pct": body.target_pct,
            "horizon_days": body.horizon_days,
            "min_score": body.min_score,
            "stock_pool_mode": body.stock_pool_mode or "all",
        }
        if body.stock_code:
            config["stock_code"] = body.stock_code.strip()
        if body.stock_pool:
            config["stock_pool"] = [str(c).strip() for c in body.stock_pool if str(c).strip()]
        # 任务名称：用户填写则用用户的；否则单股/自定义时生成含股票代码和名称的默认名
        task_name = (body.task_name or "").strip()
        if not task_name:
            task_name = _build_task_name_with_stocks(db, config)
        task_id = admin_interface.create_backtest(config, name=task_name or None)
        return {"success": True, "data": {"task_id": task_id}}
    except Exception as e:
        logger.exception("创建 GMS 回测任务失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backtests")
async def list_backtests(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """任务列表。"""
    try:
        tasks = admin_interface.list_backtest_tasks(status=status, limit=limit, offset=offset)
        return {"success": True, "data": {"tasks": tasks}}
    except Exception as e:
        logger.exception("GMS backtests 列表失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backtests/{task_id}")
async def get_backtest(task_id: str):
    """任务详情（含参数与汇总）。"""
    task = admin_interface.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"success": True, "data": task}


@router.get("/backtests/{task_id}/logs")
async def get_backtest_logs(task_id: str):
    """任务日志。"""
    task = admin_interface.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    logs = admin_interface.get_logs(task_id)
    return {"success": True, "data": {"logs": logs}}


@router.post("/backtests/{task_id}/cancel")
async def cancel_backtest(task_id: str):
    """取消任务。"""
    ok = admin_interface.cancel_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="任务不存在或无法取消")
    return {"success": True}


@router.delete("/backtests/{task_id}")
async def delete_backtest(task_id: str):
    """删除任务。"""
    admin_interface.delete_task(task_id)
    return {"success": True}


# ---------- reports ----------
@router.get("/reports")
async def list_reports(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """报告列表。"""
    try:
        reports = admin_interface.list_reports(limit=limit, offset=offset)
        return {"success": True, "data": {"reports": reports}}
    except Exception as e:
        logger.exception("GMS reports 列表失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/{report_id}")
async def get_report(report_id: str):
    """报告详情。"""
    report = admin_interface.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    return {"success": True, "data": report}


@router.get("/reports/{report_id}/download")
async def download_report(report_id: str):
    """下载报告明细文件（CSV）。文件名包含任务名称（含股票代码和名称时更易识别）。"""
    path = admin_interface.download_report(report_id)
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="报告或明细文件不存在")
    report = admin_interface.get_report(report_id) or {}
    base_name = (report.get("name") or f"gms_backtest_{report_id[:8]}").strip()
    # 移除文件名非法字符
    safe_name = re.sub(r'[<>:"/\\|?*]', "_", base_name)
    filename = f"{safe_name}.csv" if safe_name else f"gms_backtest_{report_id[:8]}.csv"
    return FileResponse(
        path,
        media_type="text/csv",
        filename=filename,
    )


# ---------- config ----------
@router.get("/config")
async def get_config():
    """读取 GMS 策略配置。"""
    try:
        cfg = GMSConfigManager().get_config()
        return {"success": True, "data": cfg}
    except Exception as e:
        logger.exception("GMS config get 失败")
        raise HTTPException(status_code=500, detail=str(e))


class ConfigUpdateBody(BaseModel):
    config: dict = Field(..., description="完整或部分配置，会与现有配置深度合并")


@router.put("/config")
async def update_config(body: ConfigUpdateBody):
    """更新 GMS 策略配置。"""
    try:
        mgr = GMSConfigManager()
        current = mgr.get_config()

        def deep_merge(base: dict, override: dict) -> dict:
            out = base.copy()
            for k, v in override.items():
                if k in out and isinstance(out[k], dict) and isinstance(v, dict):
                    out[k] = deep_merge(out[k], v)
                else:
                    out[k] = v
            return out

        merged = deep_merge(current, body.config)
        if not mgr.save_config(merged):
            raise HTTPException(status_code=500, detail="保存配置失败")
        return {"success": True, "data": mgr.get_config()}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("GMS config put 失败")
        raise HTTPException(status_code=500, detail=str(e))
