"""
GMS 回测管理端 API 路由
前缀: /api/admin/gms
"""

import logging
import os
import re
from typing import Optional, List, Literal

from fastapi import APIRouter, HTTPException, Query, Body, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend_api.database import get_db
from backend_api.models import StockBasicInfo, StockBasicInfoHK, Watchlist, User
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
    # A股：库中 code 为 text（如 000001）；PostgreSQL 不可与 int 直接比较，只使用字符串形式尝试
    clean = c[2:] if c.startswith(("SZ", "SH")) else c
    if clean.isdigit():
        raw = [clean, clean.zfill(6), f"{int(clean):06d}"]
        try_vals: List[str] = []
        seen: set = set()
        for x in raw:
            if x not in seen:
                seen.add(x)
                try_vals.append(x)
    else:
        try_vals = [clean]
    for try_val in try_vals:
        info = db.query(StockBasicInfo).filter(StockBasicInfo.code == try_val).first()
        if info and info.name:
            return str(info.name).strip()
    return ""


def _distinct_watchlist_codes(db: Session, user_id: Optional[int] = None) -> List[str]:
    """watchlist 表中去重后的股票代码，支持按用户过滤。"""
    q = db.query(Watchlist.stock_code)
    if user_id is not None:
        q = q.filter(Watchlist.user_id == int(user_id))
    rows = q.distinct().all()
    codes = {str(r[0]).strip() for r in rows if r[0] is not None and str(r[0]).strip()}
    return sorted(codes)


def _build_task_name_with_stocks(db: Session, config: dict) -> Optional[str]:
    """
    当股票池为单股、自定义或自选股时，生成包含股票名称和代码的任务名称。
    全市场时返回 None，由 backtest_storage 使用默认命名。
    """
    mode = config.get("stock_pool_mode") or "all"
    if mode == "single":
        code = (config.get("stock_code") or "").strip()
        if not code:
            return None
        name = _get_stock_name(db, code)
        return f"GMS回测_{code}_{name}" if name else f"GMS回测_{code}"
    if mode in ("custom", "watchlist"):
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
    backtest_type: Literal["signal_hit_rate", "trade_simulation"] = Field(
        "signal_hit_rate",
        description="回测类型: signal_hit_rate(策略信号命中率) / trade_simulation(交易回测)",
    )
    stop_loss_pct: float = Field(
        0,
        ge=0,
        le=1,
        description="止损比例，仅 trade_simulation 生效；0 表示不启用",
    )
    commission_bps: float = Field(
        0,
        ge=0,
        le=1000,
        description="单边手续费（bps），仅 trade_simulation 生效",
    )
    slippage_bps: float = Field(
        0,
        ge=0,
        le=1000,
        description="单边滑点（bps），仅 trade_simulation 生效",
    )
    atr_period: int = Field(14, ge=5, le=120, description="ATR周期，仅 trade_simulation 生效")
    init_stop_atr_k: float = Field(2.2, ge=0, le=20, description="初始ATR止损倍数，仅 trade_simulation 生效")
    trail_stop_mode: Literal["atr", "percent"] = Field(
        "atr",
        description="移动止损模式：atr/percent，仅 trade_simulation 生效",
    )
    trail_atr_k: float = Field(3.0, ge=0, le=20, description="ATR移动止损倍数，仅 trade_simulation 生效")
    trail_pct: float = Field(0.08, ge=0, le=1, description="百分比回撤止损比例，仅 trade_simulation 生效")
    breakeven_trigger_r: float = Field(1.0, ge=0, le=20, description="保本触发R倍数，仅 trade_simulation 生效")
    profit_lock_trigger_r: float = Field(2.0, ge=0, le=20, description="锁盈触发R倍数，仅 trade_simulation 生效")
    profit_lock_r: float = Field(0.5, ge=0, le=20, description="锁盈后保留R倍数，仅 trade_simulation 生效")
    partial_take_profit_r: float = Field(2.0, ge=0, le=20, description="分批止盈触发R倍数，仅 trade_simulation 生效")
    partial_take_ratio: float = Field(0.4, ge=0, le=1, description="分批止盈比例，仅 trade_simulation 生效")
    time_stop_bars: int = Field(15, ge=1, le=500, description="时间止损K线数，仅 trade_simulation 生效")
    stock_pool_mode: Optional[str] = Field("all", description="股票池: all / single / custom / watchlist")
    stock_code: Optional[str] = Field(None, description="单股回测时的股票代码，如 000001、00700")
    stock_pool: Optional[List[str]] = Field(None, description="自定义股票池代码列表")
    watchlist_user_id: Optional[int] = Field(None, description="stock_pool_mode=watchlist 时可选：指定用户ID")


@router.get("/watchlist-users")
async def list_watchlist_users(db: Session = Depends(get_db)):
    """返回有自选股的用户列表（用于“自选股”按用户筛选）。"""
    try:
        rows = (
            db.query(
                Watchlist.user_id.label("user_id"),
                func.count(Watchlist.id).label("watchlist_count"),
                User.username.label("username"),
            )
            .join(User, User.id == Watchlist.user_id)
            .group_by(Watchlist.user_id, User.username)
            .order_by(Watchlist.user_id.asc())
            .all()
        )
        users = []
        for r in rows:
            users.append({
                "user_id": int(getattr(r, "user_id", 0) or 0),
                "username": str(getattr(r, "username", "") or ""),
                "watchlist_count": int(getattr(r, "watchlist_count", 0) or 0),
            })
        return {"success": True, "data": {"users": users}}
    except Exception as e:
        logger.exception("GMS watchlist-users 查询失败")
        raise HTTPException(status_code=500, detail=str(e))


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
    """创建回测任务，返回 task_id。任务名称未填写时，单股/自定义/自选股股票池时自动包含股票名称和代码。"""
    try:
        mode = (body.stock_pool_mode or "all").strip()
        config = {
            "task_name": body.task_name,
            "market": body.market,
            "start_date": body.start_date,
            "end_date": body.end_date,
            "target_pct": body.target_pct,
            "horizon_days": body.horizon_days,
            "min_score": body.min_score,
            "backtest_type": body.backtest_type,
            "stop_loss_pct": body.stop_loss_pct,
            "commission_bps": body.commission_bps,
            "slippage_bps": body.slippage_bps,
            "atr_period": body.atr_period,
            "init_stop_atr_k": body.init_stop_atr_k,
            "trail_stop_mode": body.trail_stop_mode,
            "trail_atr_k": body.trail_atr_k,
            "trail_pct": body.trail_pct,
            "breakeven_trigger_r": body.breakeven_trigger_r,
            "profit_lock_trigger_r": body.profit_lock_trigger_r,
            "profit_lock_r": body.profit_lock_r,
            "partial_take_profit_r": body.partial_take_profit_r,
            "partial_take_ratio": body.partial_take_ratio,
            "time_stop_bars": body.time_stop_bars,
            "stock_pool_mode": mode,
        }
        if mode == "watchlist":
            wl_uid = body.watchlist_user_id
            if wl_uid is not None:
                config["watchlist_user_id"] = int(wl_uid)
            codes = _distinct_watchlist_codes(db, user_id=wl_uid)
            if not codes:
                if wl_uid is None:
                    raise HTTPException(status_code=400, detail="当前无自选股，无法创建回测任务")
                raise HTTPException(status_code=400, detail=f"用户ID={wl_uid}无自选股，无法创建回测任务")
            config["stock_pool"] = codes
        else:
            if body.stock_code:
                config["stock_code"] = body.stock_code.strip()
            if body.stock_pool:
                config["stock_pool"] = [str(c).strip() for c in body.stock_pool if str(c).strip()]
        # 任务名称：用户填写则用用户的；否则单股/自定义/自选股时生成含股票代码和名称的默认名
        task_name = (body.task_name or "").strip()
        if not task_name:
            task_name = _build_task_name_with_stocks(db, config)
        task_id = admin_interface.create_backtest(config, name=task_name or None)
        return {"success": True, "data": {"task_id": task_id}}
    except HTTPException:
        raise
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


@router.post("/backtests/{task_id}/rerun")
async def rerun_backtest(task_id: str):
    """使用与原任务相同的参数创建并启动新回测任务（已完成/失败/已取消时可重跑）。"""
    try:
        new_id = admin_interface.rerun_backtest(task_id)
        return {"success": True, "data": {"task_id": new_id}}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("GMS 重新执行回测失败")
        raise HTTPException(status_code=500, detail=str(e))


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
async def download_report(
    report_id: str,
    variant: Optional[str] = Query(
        None,
        description="不填：报告记录的主文件；csv：UTF-8 中文表头 CSV；xlsx：Excel 含列宽",
    ),
):
    """下载报告明细：默认与报告记录一致；variant=csv / xlsx 可指定格式（与 Excel 列语义一致）。"""
    path = admin_interface.download_report(report_id, variant=variant)
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="报告或明细文件不存在")
    report = admin_interface.get_report(report_id) or {}
    base_name = (report.get("name") or f"gms_backtest_{report_id[:8]}").strip()
    # 移除文件名非法字符
    safe_name = re.sub(r'[<>:"/\\|?*]', "_", base_name)
    ext = os.path.splitext(path)[1].lower()
    if ext == ".xlsx":
        filename = (
            f"{safe_name}.xlsx" if safe_name else f"gms_backtest_{report_id[:8]}.xlsx"
        )
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        filename = f"{safe_name}.csv" if safe_name else f"gms_backtest_{report_id[:8]}.csv"
        media_type = "text/csv; charset=utf-8"
    return FileResponse(
        path,
        media_type=media_type,
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
