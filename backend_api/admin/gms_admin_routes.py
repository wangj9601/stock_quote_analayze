"""
GMS 回测管理端 API 路由
前缀: /api/admin/gms
"""

import logging
import os
import re
import sys
from typing import Optional, List, Literal, Tuple, Any

from fastapi import APIRouter, HTTPException, Query, Body, Depends
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import String as SAString, bindparam, func, text

from backend_api.database import get_db
from backend_api.models import (
    Watchlist,
    User,
    GMSStrategyVersion,
    GMSStrategyVersionStock,
    StockRealtimeQuote,
    StockRealtimeQuoteHK,
)
from backend_api.services.gms_signal_trace_selection import query_gms_signal_trace_selection
from backend_core.strategies.gms import admin_interface
from backend_core.strategies.gms.config import GMSConfigManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/gms", tags=["GMS回测管理"])


@router.get("/health/stock-code-orm-check")
async def health_stock_code_orm_check():
    """自检：当前进程里 StockBasicInfo.code == 2709 编译出的 PG SQL 是否含 CAST（用于确认是否已重启、是否旧 worker）。"""
    from sqlalchemy import select
    from sqlalchemy.dialects import postgresql

    from backend_api.models import StockBasicInfo

    stmt = select(StockBasicInfo).where(StockBasicInfo.code == 2709).limit(1)
    compiled = stmt.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    upper = sql.upper()
    return {
        "stock_code_type": type(StockBasicInfo.code.type).__name__,
        "postgresql_sql_contains_cast": "CAST(" in upper and "VARCHAR" in upper,
        "sample_sql": sql,
    }


def _txt_select_name_cn():
    """PostgreSQL 上 :code 若被推断为 integer 会与 text 列比较失败；显式按字符串绑定。"""
    return text("SELECT name FROM stock_basic_info WHERE code = :code LIMIT 1").bindparams(
        bindparam("code", type_=SAString())
    )


def _txt_select_name_hk():
    return text("SELECT name FROM stock_basic_info_hk WHERE code = :code LIMIT 1").bindparams(
        bindparam("code", type_=SAString())
    )


def _txt_dup_version_stock():
    return text(
        """
        SELECT 1 FROM gms_strategy_version_stocks
        WHERE version_id = :vid AND market = :m AND stock_code = :sc
        LIMIT 1
        """
    ).bindparams(
        bindparam("vid"),
        bindparam("m", type_=SAString()),
        bindparam("sc", type_=SAString()),
    )


def _txt_dup_version_stock_exclude_row():
    return text(
        """
        SELECT 1 FROM gms_strategy_version_stocks
        WHERE id <> :sid AND version_id = :vid AND market = :m AND stock_code = :sc
        LIMIT 1
        """
    ).bindparams(
        bindparam("sid"),
        bindparam("vid"),
        bindparam("m", type_=SAString()),
        bindparam("sc", type_=SAString()),
    )


def _get_stock_name(db: Session, code: str) -> str:
    """根据股票代码查询名称，A股/港股分别查对应表。"""
    c = str(code).strip()
    if not c:
        return ""
    # 港股：5位数字或字母开头
    is_hk = len(c) < 6 or not (c.isdigit() and c[0] in "6039")
    if is_hk:
        row = db.execute(_txt_select_name_hk(), {"code": str(c)}).fetchone()
        if not row and c.isdigit():
            row = db.execute(_txt_select_name_hk(), {"code": str(c.zfill(5))}).fetchone()
        return str(row[0]).strip() if row and row[0] else ""
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
        row = db.execute(_txt_select_name_cn(), {"code": str(try_val)}).fetchone()
        if row and row[0]:
            return str(row[0]).strip()
    return ""


def _distinct_watchlist_codes(db: Session, user_id: Optional[int] = None) -> List[str]:
    """watchlist 表中去重后的股票代码，支持按用户过滤。"""
    q = db.query(Watchlist.stock_code)
    if user_id is not None:
        q = q.filter(Watchlist.user_id == int(user_id))
    rows = q.distinct().all()
    codes = {str(r[0]).strip() for r in rows if r[0] is not None and str(r[0]).strip()}
    return sorted(codes)


def _distinct_gms_strategy_stock_codes(db: Session, market: Optional[str] = None) -> List[str]:
    """从 GMSStrategyVersionStock 表中读取对应市场、且所属版本已启用且股票状态为 active 的代码。"""
    q = db.query(GMSStrategyVersionStock.stock_code).join(
        GMSStrategyVersion, GMSStrategyVersion.id == GMSStrategyVersionStock.version_id
    ).filter(
        GMSStrategyVersion.is_active == True,
        GMSStrategyVersionStock.status == "active"
    )
    if market and market != "all":
        norm_m = _normalize_market(market)
        q = q.filter(GMSStrategyVersionStock.market == norm_m)
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
    if mode in ("custom", "watchlist", "gms_watchlist"):
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
    position_fraction: float = Field(
        1.0,
        gt=0,
        le=1,
        description="单笔仓位：每笔投入占组合权益的比例(0~1]，仅 trade_simulation；1 为全仓",
    )
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


@router.get("/selection-results")
async def get_gms_selection_results_from_trace(
    date: Optional[str] = Query(None, description="目标日期 YYYY-MM-DD，不传则使用 gms_signal_trace 表内最新日期"),
    limit: Optional[int] = Query(None, ge=1, description="最大返回条数"),
    min_strength: float = Query(0.3, ge=0.0, le=1.0, description="最低信号强度 0~1（对应总分 ×100）"),
    db: Session = Depends(get_db),
):
    """
    管理端「GMS策略管理 → 选股结果」数据源：**gms_signal_trace** 表。
    数据来自 **gms_signal_trace**；公开接口见 `GET /api/frontend/gms/selection-results`（同源逻辑）。
    """
    try:
        payload, fallback_message = query_gms_signal_trace_selection(db, date, min_strength, limit)
        if fallback_message:
            payload["message"] = fallback_message
        return JSONResponse(payload)
    except Exception as e:
        logger.exception("GMS 管理端选股结果（gms_signal_trace）查询失败")
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
            "position_fraction": body.position_fraction,
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
        elif mode == "gms_watchlist":
            codes = _distinct_gms_strategy_stock_codes(db, market=body.market)
            if not codes:
                m_desc = "全部市场" if body.market == "all" else ("A股" if body.market == "cn" else "港股")
                raise HTTPException(status_code=400, detail=f"GMS观察股({m_desc})中无有效状态数据，无法创建回测任务")
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
@router.post("/backtests/{task_id}/delete")
async def delete_backtest(task_id: str):
    """删除任务。同时支持 DELETE 和 POST /delete 兼容生产环境。"""
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
@router.post("/config/update")
async def update_config(body: ConfigUpdateBody):
    """更新 GMS 策略配置。同时支持 PUT 和 POST /update 兼容生产环境。"""
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


# ---------- GMS 策略版本与观察股管理 ----------
class StrategyVersionCreateBody(BaseModel):
    strategy_code: str = Field("GMS", description="策略编码")
    version_name: str = Field(..., description="版本名称")
    version_no: int = Field(..., ge=1, description="版本号")
    description: Optional[str] = Field(None, description="版本描述")
    is_active: bool = Field(True, description="是否启用")
    created_by: Optional[str] = Field(None, description="创建人")


class StrategyVersionUpdateBody(BaseModel):
    strategy_code: Optional[str] = Field(None, description="策略编码")
    version_name: Optional[str] = Field(None, description="版本名称")
    version_no: Optional[int] = Field(None, ge=1, description="版本号")
    description: Optional[str] = Field(None, description="版本描述")
    is_active: Optional[bool] = Field(None, description="是否启用")
    created_by: Optional[str] = Field(None, description="创建人")


class StrategyVersionStockCreateBody(BaseModel):
    version_id: int = Field(..., ge=1, description="策略版本ID")
    market: str = Field(..., description="市场类型：A 或 HK")
    stock_code: str = Field(..., description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称（可不传，后端自动补齐）")
    sort_order: int = Field(0, description="排序")
    status: str = Field("active", description="状态 active/inactive")
    is_verified: bool = Field(False, description="审核标志")
    remark: Optional[str] = Field(None, description="备注")

    @field_validator("stock_code", mode="before")
    @classmethod
    def _stock_code_always_str(cls, v):
        if v is None:
            return v
        return str(v).strip()


class StrategyVersionStockUpdateBody(BaseModel):
    market: Optional[str] = Field(None, description="市场类型：A 或 HK")
    stock_code: Optional[str] = Field(None, description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    sort_order: Optional[int] = Field(None, description="排序")
    status: Optional[str] = Field(None, description="状态 active/inactive")
    is_verified: Optional[bool] = Field(None, description="审核标志")
    remark: Optional[str] = Field(None, description="备注")

    @field_validator("stock_code", mode="before")
    @classmethod
    def _stock_code_always_str(cls, v):
        if v is None:
            return v
        return str(v).strip()


class BatchDeleteStocksBody(BaseModel):
    ids: Optional[List[int]] = Field(None, description="观察股关系ID列表")
    stock_codes: Optional[List[str]] = Field(None, description="股票代码列表（需配合 version_id）")
    version_id: Optional[int] = Field(None, description="策略版本ID（按股票代码删除时必填）")
    market: Optional[str] = Field(None, description="可选市场过滤：A/HK")


class BatchImportItem(BaseModel):
    market: str = Field(..., description="市场类型：A/HK")
    stock_code: str = Field(..., description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    sort_order: int = Field(0, description="排序")
    status: str = Field("active", description="状态 active/inactive")
    is_verified: bool = Field(False, description="审核标志")
    remark: Optional[str] = Field(None, description="备注")

    @field_validator("stock_code", mode="before")
    @classmethod
    def _stock_code_always_str(cls, v):
        if v is None:
            return v
        return str(v).strip()


class BatchImportStocksBody(BaseModel):
    version_id: int = Field(..., ge=1, description="策略版本ID")
    items: List[BatchImportItem] = Field(default_factory=list, description="批量导入观察股条目")


def _as_text_stock_code(code: Any) -> str:
    """将股票代码规范为 str，供 text/varchar 列查询绑定（PostgreSQL 禁止 text 与 integer 直接比较）。"""
    if code is None:
        return ""
    return str(code).strip()


def _normalize_market(market: str) -> str:
    raw = (market or "").strip().upper()
    if raw in ("A", "CN", "A股"):
        return "A"
    if raw in ("HK", "H", "港股"):
        return "HK"
    raise HTTPException(status_code=400, detail=f"不支持的市场类型: {market}")


def _normalize_stock_code(market: str, stock_code: str) -> str:
    code = _as_text_stock_code(stock_code).upper()
    if not code:
        raise HTTPException(status_code=400, detail="股票代码不能为空")
    if market == "A":
        code = code.replace("SZ", "").replace("SH", "")
        if not code.isdigit():
            raise HTTPException(status_code=400, detail=f"A股代码格式不合法: {stock_code}")
        return code.zfill(6)
    digits = "".join(ch for ch in code if ch.isdigit())
    if not digits:
        raise HTTPException(status_code=400, detail=f"港股代码格式不合法: {stock_code}")
    return digits.zfill(5)


def _resolve_stock_name(db: Session, market: str, stock_code: str) -> Tuple[bool, str]:
    """校验股票是否存在，并返回标准名称。用 text + 显式字符串 bindparam，避免 PostgreSQL text=integer。"""
    code_s = _as_text_stock_code(stock_code)
    if not code_s:
        return False, ""
    q_cn = _txt_select_name_cn()
    q_hk = _txt_select_name_hk()
    if market == "A":
        row = db.execute(q_cn, {"code": code_s}).fetchone()
        if row is None and code_s.isdigit():
            alt = code_s.zfill(6)
            if alt != code_s:
                row = db.execute(q_cn, {"code": alt}).fetchone()
        if row is None:
            return False, ""
        return True, (str(row[0]).strip() if row[0] else "")
    row = db.execute(q_hk, {"code": code_s}).fetchone()
    if row is None:
        return False, ""
    return True, (str(row[0]).strip() if row[0] else "")


def _serialize_strategy_version(row: GMSStrategyVersion) -> dict:
    return {
        "id": row.id,
        "strategy_code": row.strategy_code,
        "version_name": row.version_name,
        "version_no": row.version_no,
        "description": row.description,
        "is_active": bool(row.is_active),
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_strategy_version_stock(row: GMSStrategyVersionStock, price: Optional[float] = None) -> dict:
    return {
        "id": row.id,
        "version_id": row.version_id,
        "market": row.market,
        "stock_code": _as_text_stock_code(row.stock_code),
        "stock_name": row.stock_name,
        "sort_order": row.sort_order,
        "status": row.status,
        "is_verified": bool(row.is_verified),
        "remark": row.remark,
        "current_price": price,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("/strategy-versions")
async def list_strategy_versions(
    strategy_code: Optional[str] = Query(None, description="策略编码"),
    is_active: Optional[bool] = Query(None, description="是否启用"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(GMSStrategyVersion)
    if strategy_code:
        query = query.filter(GMSStrategyVersion.strategy_code == strategy_code.strip().upper())
    if is_active is not None:
        query = query.filter(GMSStrategyVersion.is_active == bool(is_active))
    total = query.count()
    rows = (
        query.order_by(GMSStrategyVersion.strategy_code.asc(), GMSStrategyVersion.version_no.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "success": True,
        "data": [_serialize_strategy_version(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/strategy-versions/{version_id}")
async def get_strategy_version(version_id: int, db: Session = Depends(get_db)):
    row = db.query(GMSStrategyVersion).filter(GMSStrategyVersion.id == version_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="策略版本不存在")
    return {"success": True, "data": _serialize_strategy_version(row)}


@router.post("/strategy-versions")
async def create_strategy_version(body: StrategyVersionCreateBody, db: Session = Depends(get_db)):
    strategy_code = body.strategy_code.strip().upper()
    dup = (
        db.query(GMSStrategyVersion)
        .filter(
            GMSStrategyVersion.strategy_code == strategy_code,
            GMSStrategyVersion.version_no == body.version_no,
        )
        .first()
    )
    if dup:
        raise HTTPException(status_code=400, detail="同策略下版本号已存在")
    row = GMSStrategyVersion(
        strategy_code=strategy_code,
        version_name=body.version_name.strip(),
        version_no=body.version_no,
        description=body.description,
        is_active=body.is_active,
        created_by=(body.created_by or "").strip() or None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"success": True, "data": _serialize_strategy_version(row)}


@router.put("/strategy-versions/{version_id}")
@router.post("/strategy-versions/{version_id}/update")
async def update_strategy_version(version_id: int, body: StrategyVersionUpdateBody, db: Session = Depends(get_db)):
    """更新策略版本。同时支持 PUT 和 POST /update 兼容生产环境。"""
    row = db.query(GMSStrategyVersion).filter(GMSStrategyVersion.id == version_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="策略版本不存在")

    if body.strategy_code is not None:
        row.strategy_code = body.strategy_code.strip().upper()
    if body.version_name is not None:
        row.version_name = body.version_name.strip()
    if body.version_no is not None:
        row.version_no = body.version_no
    if body.description is not None:
        row.description = body.description
    if body.is_active is not None:
        row.is_active = bool(body.is_active)
    if body.created_by is not None:
        row.created_by = (body.created_by or "").strip() or None

    dup = (
        db.query(GMSStrategyVersion)
        .filter(
            GMSStrategyVersion.id != version_id,
            GMSStrategyVersion.strategy_code == row.strategy_code,
            GMSStrategyVersion.version_no == row.version_no,
        )
        .first()
    )
    if dup:
        raise HTTPException(status_code=400, detail="同策略下版本号已存在")

    db.commit()
    db.refresh(row)
    return {"success": True, "data": _serialize_strategy_version(row)}


@router.patch("/strategy-versions/{version_id}/active")
async def set_strategy_version_active(
    version_id: int,
    is_active: bool = Body(..., embed=True, description="是否启用"),
    db: Session = Depends(get_db),
):
    row = db.query(GMSStrategyVersion).filter(GMSStrategyVersion.id == version_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="策略版本不存在")
    row.is_active = bool(is_active)
    db.commit()
    db.refresh(row)
    return {"success": True, "data": _serialize_strategy_version(row)}


@router.delete("/strategy-versions/{version_id}")
@router.post("/strategy-versions/{version_id}/delete")
async def delete_strategy_version(version_id: int, db: Session = Depends(get_db)):
    """删除策略版本。同时支持 DELETE 和 POST /delete 兼容生产环境。"""
    row = db.query(GMSStrategyVersion).filter(GMSStrategyVersion.id == version_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="策略版本不存在")
    db.delete(row)
    db.commit()
    return {"success": True}


@router.get("/strategy-version-stocks")
async def list_strategy_version_stocks(
    version_id: int = Query(..., ge=1),
    market: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    exists = db.query(GMSStrategyVersion.id).filter(GMSStrategyVersion.id == version_id).first()
    if not exists:
        raise HTTPException(status_code=404, detail="策略版本不存在")

    query = db.query(GMSStrategyVersionStock).filter(GMSStrategyVersionStock.version_id == version_id)
    if market:
        query = query.filter(GMSStrategyVersionStock.market == _normalize_market(market))
    if status:
        query = query.filter(GMSStrategyVersionStock.status == status.strip())
    if keyword:
        kw = f"%{keyword.strip()}%"
        query = query.filter(
            (GMSStrategyVersionStock.stock_code.ilike(kw))
            | (GMSStrategyVersionStock.stock_name.ilike(kw))
        )
    total = query.count()
    rows = (
        query.order_by(GMSStrategyVersionStock.sort_order.asc(), GMSStrategyVersionStock.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # 获取实时价格
    a_prices = {}
    hk_prices = {}
    
    a_codes = [r.stock_code for r in rows if r.market == 'A']
    if a_codes:
        latest_a = db.query(func.max(StockRealtimeQuote.trade_date)).filter(StockRealtimeQuote.code.in_(a_codes)).scalar()
        if latest_a:
            p_rows = db.query(StockRealtimeQuote.code, StockRealtimeQuote.current_price).filter(
                StockRealtimeQuote.code.in_(a_codes),
                StockRealtimeQuote.trade_date == latest_a
            ).all()
            a_prices = {r[0]: r[1] for r in p_rows}
            
    hk_codes = [r.stock_code for r in rows if r.market == 'HK']
    if hk_codes:
        latest_hk = db.query(func.max(StockRealtimeQuoteHK.trade_date)).filter(StockRealtimeQuoteHK.code.in_(hk_codes)).scalar()
        if latest_hk:
            p_rows = db.query(StockRealtimeQuoteHK.code, StockRealtimeQuoteHK.current_price).filter(
                StockRealtimeQuoteHK.code.in_(hk_codes),
                StockRealtimeQuoteHK.trade_date == latest_hk
            ).all()
            hk_prices = {r[0]: r[1] for r in p_rows}

    return {
        "success": True,
        "data": [
            _serialize_strategy_version_stock(
                r, 
                a_prices.get(r.stock_code) if r.market == 'A' else hk_prices.get(r.stock_code)
            ) for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/strategy-version-stocks")
async def create_strategy_version_stock(body: StrategyVersionStockCreateBody, db: Session = Depends(get_db)):
    print("[GMS] create_strategy_version_stock ENTER", flush=True, file=sys.stderr)
    version = db.query(GMSStrategyVersion).filter(GMSStrategyVersion.id == body.version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="策略版本不存在")

    market = _normalize_market(body.market)
    # 显式转 str，避免任何路径上残留 int（JSON/前端数字）进入后续逻辑
    stock_code = _normalize_stock_code(market, str(body.stock_code))
    _log_create = (
        f"[GMS] create_strategy_version_stock version_id={body.version_id} market={market} "
        f"raw_code={body.stock_code!r} type={type(body.stock_code).__name__} normalized={stock_code!r}"
    )
    print(_log_create, flush=True)
    logger.info(
        "GMS create_strategy_version_stock: version_id=%s market=%s raw_code=%r type=%s normalized=%r",
        body.version_id,
        market,
        body.stock_code,
        type(body.stock_code).__name__,
        stock_code,
    )
    exists, resolved_name = _resolve_stock_name(db, market, stock_code)
    if not exists:
        raise HTTPException(status_code=400, detail=f"股票不存在: {stock_code}")

    dup = db.execute(
        _txt_dup_version_stock(),
        {"vid": body.version_id, "m": market, "sc": str(stock_code)},
    ).fetchone()
    if dup:
        raise HTTPException(status_code=400, detail="该观察股已存在于当前策略版本")

    row = GMSStrategyVersionStock(
        version_id=body.version_id,
        market=market,
        stock_code=stock_code,
        stock_name=(body.stock_name or resolved_name or "").strip() or resolved_name,
        sort_order=body.sort_order,
        status=(body.status or "active").strip(),
        is_verified=body.is_verified,
        remark=body.remark,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    _log_ok = (
        f"[GMS] create_strategy_version_stock OK id={row.id} stock_code={row.stock_code!r} stock_name={row.stock_name!r}"
    )
    print(_log_ok, flush=True)
    logger.info(
        "GMS create_strategy_version_stock ok: id=%s stock_code=%r stock_name=%r",
        row.id,
        row.stock_code,
        row.stock_name,
    )
    return {"success": True, "data": _serialize_strategy_version_stock(row)}


@router.put("/strategy-version-stocks/{stock_id}")
@router.post("/strategy-version-stocks/{stock_id}/update")
async def update_strategy_version_stock(
    stock_id: int,
    body: StrategyVersionStockUpdateBody,
    db: Session = Depends(get_db),
):
    """更新观察股。同时支持 PUT 和 POST /update 兼容生产环境。"""
    row = db.query(GMSStrategyVersionStock).filter(GMSStrategyVersionStock.id == stock_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="观察股记录不存在")

    market = _normalize_market(body.market) if body.market is not None else row.market
    stock_code = (
        _normalize_stock_code(market, str(body.stock_code))
        if body.stock_code is not None
        else _as_text_stock_code(row.stock_code)
    )

    exists, resolved_name = _resolve_stock_name(db, market, stock_code)
    if not exists:
        raise HTTPException(status_code=400, detail=f"股票不存在: {stock_code}")

    dup = db.execute(
        _txt_dup_version_stock_exclude_row(),
        {"sid": stock_id, "vid": row.version_id, "m": market, "sc": str(stock_code)},
    ).fetchone()
    if dup:
        raise HTTPException(status_code=400, detail="该观察股已存在于当前策略版本")

    row.market = market
    row.stock_code = stock_code
    if body.stock_name is not None:
        row.stock_name = (body.stock_name or "").strip() or resolved_name
    elif not row.stock_name:
        row.stock_name = resolved_name
    if body.sort_order is not None:
        row.sort_order = body.sort_order
    if body.status is not None:
        row.status = body.status.strip()
    if body.is_verified is not None:
        row.is_verified = bool(body.is_verified)
    if body.remark is not None:
        row.remark = body.remark

    db.commit()
    db.refresh(row)
    return {"success": True, "data": _serialize_strategy_version_stock(row)}


@router.delete("/strategy-version-stocks/{stock_id}")
@router.post("/strategy-version-stocks/{stock_id}/delete")
async def delete_strategy_version_stock(stock_id: int, db: Session = Depends(get_db)):
    """删除观察股。同时支持 DELETE 和 POST /delete 兼容生产环境。"""
    row = db.query(GMSStrategyVersionStock).filter(GMSStrategyVersionStock.id == stock_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="观察股记录不存在")
    db.delete(row)
    db.commit()
    return {"success": True}


@router.post("/strategy-version-stocks/batch-delete")
async def batch_delete_strategy_version_stocks(body: BatchDeleteStocksBody, db: Session = Depends(get_db)):
    if body.ids:
        deleted = (
            db.query(GMSStrategyVersionStock)
            .filter(GMSStrategyVersionStock.id.in_(body.ids))
            .delete(synchronize_session=False)
        )
        db.commit()
        return {"success": True, "data": {"deleted": deleted}}

    if body.stock_codes:
        if not body.version_id:
            raise HTTPException(status_code=400, detail="按股票代码批量删除时 version_id 必填")
        query = db.query(GMSStrategyVersionStock).filter(
            GMSStrategyVersionStock.version_id == body.version_id,
            GMSStrategyVersionStock.stock_code.in_([str(c).strip() for c in body.stock_codes if str(c).strip()]),
        )
        if body.market:
            query = query.filter(GMSStrategyVersionStock.market == _normalize_market(body.market))
        deleted = query.delete(synchronize_session=False)
        db.commit()
        return {"success": True, "data": {"deleted": deleted}}

    raise HTTPException(status_code=400, detail="请提供 ids 或 stock_codes 进行批量删除")


@router.post("/strategy-version-stocks/batch-import")
async def batch_import_strategy_version_stocks(body: BatchImportStocksBody, db: Session = Depends(get_db)):
    version = db.query(GMSStrategyVersion).filter(GMSStrategyVersion.id == body.version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="策略版本不存在")

    success_count = 0
    skip_count = 0
    fail_count = 0
    fail_details: List[dict] = []
    created_items: List[dict] = []

    for idx, item in enumerate(body.items):
        try:
            market = _normalize_market(item.market)
            stock_code = _normalize_stock_code(market, str(item.stock_code))
            exists, resolved_name = _resolve_stock_name(db, market, stock_code)
            if not exists:
                raise HTTPException(status_code=400, detail=f"股票不存在: {stock_code}")

            dup = db.execute(
                _txt_dup_version_stock(),
                {"vid": body.version_id, "m": market, "sc": str(stock_code)},
            ).fetchone()
            if dup:
                skip_count += 1
                continue

            row = GMSStrategyVersionStock(
                version_id=body.version_id,
                market=market,
                stock_code=stock_code,
                stock_name=(item.stock_name or resolved_name or "").strip() or resolved_name,
                sort_order=item.sort_order,
                status=(item.status or "active").strip(),
                is_verified=item.is_verified,
                remark=item.remark,
            )
            db.add(row)
            db.flush()
            created_items.append(_serialize_strategy_version_stock(row))
            success_count += 1
        except Exception as e:
            fail_count += 1
            fail_details.append({
                "index": idx,
                "market": item.market,
                "stock_code": item.stock_code,
                "reason": str(e),
            })

    db.commit()
    return {
        "success": True,
        "data": {
            "success_count": success_count,
            "skip_count": skip_count,
            "fail_count": fail_count,
            "fail_details": fail_details,
            "created_items": created_items,
        },
    }
