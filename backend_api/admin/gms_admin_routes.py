"""
GMS 回测管理端 API 路由
前缀: /api/admin/gms
"""

import copy
import logging
import sys
import copy
from typing import Optional, List, Literal, Tuple, Any, Dict

from fastapi import APIRouter, HTTPException, Query, Body, Depends
from fastapi.responses import JSONResponse, Response
from urllib.parse import quote
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import String as SAString, bindparam, func, text

from backend_api.database import get_db
from backend_api.models import (
    Watchlist,
    User,
    GMSStrategyVersion,
    GMSStrategyVersionStock,
    StockBasicInfo,
    StockBasicInfoHK,
    StockRealtimeQuote,
    StockRealtimeQuoteHK,
)
from backend_api.utils.industry_board_query import (
    batch_industry_board_names_by_stock_codes,
    get_industry_board_name_by_stock_code,
)
from backend_api.services.gms_signal_trace_selection import query_gms_signal_trace_selection
from backend_api.services.gms_job_tracker import (
    check_precompute_alert,
    get_latest_precompute_runs,
    get_recent_job_runs,
    maybe_send_gms_alert,
    screening_stats_summary,
)
from backend_api.services.gms_audit_service import write_gms_audit
from backend_core.strategies.gms import admin_interface
from backend_core.strategies.gms import backtest_storage as gms_backtest_storage
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
        func.lower(func.trim(func.coalesce(GMSStrategyVersionStock.status, ""))) == "active",
    )
    if market and market != "all":
        norm_m = _normalize_market(market)
        q = q.filter(GMSStrategyVersionStock.market == norm_m)
    rows = q.distinct().all()
    codes = {str(r[0]).strip() for r in rows if r[0] is not None and str(r[0]).strip()}
    return sorted(codes)


def _normalize_backtest_cn_board_segment(raw: Optional[str]) -> Optional[str]:
    """校验并规范化回测 A 股板块参数；无效返回 None 表示不筛选，ALL 亦返回 None。"""
    from backend_api.utils.cn_listed_board_filter import normalize_list_board_segment

    seg = (raw or "").strip().upper()
    if not seg or seg == "ALL":
        return None
    if not normalize_list_board_segment(seg):
        raise HTTPException(
            status_code=400,
            detail="cn_board_segment 无效，可选: ALL/MAIN/CYB/SZ_SME/KCB/BJ",
        )
    return seg


def _apply_backtest_cn_board_segment(
    codes: List[str],
    market: str,
    board_segment: Optional[str],
) -> List[str]:
    """在回测股票池内按 A 股板块过滤；港股市场忽略。"""
    m = (market or "all").strip().lower()
    if m == "hk":
        return codes
    seg = _normalize_backtest_cn_board_segment(board_segment)
    if not seg:
        return codes
    from backend_api.utils.cn_listed_board_filter import filter_stock_codes_by_board_segment

    return filter_stock_codes_by_board_segment(codes, seg)


def _normalize_backtest_board_codes(
    raw: Optional[List[str]],
    *,
    upper: bool = False,
) -> List[str]:
    """解析行业/概念板块代码列表（支持逗号分隔）。"""
    if not raw:
        return []
    out: List[str] = []
    for item in raw:
        for part in str(item or "").split(","):
            code = part.strip()
            if not code:
                continue
            if upper:
                code = code.upper()
            if code not in out:
                out.append(code)
    return out


def _normalize_backtest_stock_code(code: str) -> str:
    """与 GMS 选股池一致：归一化 A 股/港股代码。"""
    s = str(code).strip()
    if not s:
        return s
    if s.isdigit():
        if len(s) == 6 and s[0] in "603":
            return s.zfill(6)
        if len(s) <= 5:
            return s.zfill(5)
        return s.zfill(6)
    return s


def _resolve_industry_board_backtest_codes(
    db: Session,
    raw_board_codes: List[str],
) -> Tuple[List[str], List[str]]:
    """按行业板块代码解析成分股，返回 (板块代码, 股票代码)。"""
    from backend_api.models import IndustryBoardConstituent
    from backend_api.utils.bk_board_code import resolve_industry_board_codes

    bcodes = resolve_industry_board_codes(db, raw_board_codes)
    if not bcodes:
        return [], []
    rows = (
        db.query(IndustryBoardConstituent.stock_code)
        .filter(IndustryBoardConstituent.board_code.in_(bcodes))
        .distinct()
        .all()
    )
    pool = list(
        dict.fromkeys(
            _normalize_backtest_stock_code(str(r[0]))
            for r in rows
            if r[0] is not None and str(r[0]).strip()
        )
    )
    pool = [c for c in pool if c]
    return bcodes, sorted(pool)


def _resolve_concept_board_backtest_codes(
    db: Session,
    raw_board_codes: List[str],
) -> Tuple[List[str], List[str]]:
    """按概念板块代码解析成分股，返回 (板块代码, 股票代码)。"""
    from backend_api.models import ConceptBoardConstituent

    bcodes = _normalize_backtest_board_codes(raw_board_codes, upper=True)
    if not bcodes:
        return [], []
    rows = (
        db.query(ConceptBoardConstituent.stock_code)
        .filter(ConceptBoardConstituent.board_code.in_(bcodes))
        .distinct()
        .all()
    )
    pool = list(
        dict.fromkeys(
            _normalize_backtest_stock_code(str(r[0]))
            for r in rows
            if r[0] is not None and str(r[0]).strip()
        )
    )
    pool = [c for c in pool if c]
    return bcodes, sorted(pool)


def _assert_board_stock_pool_market_cn(market: str, pool_label: str) -> None:
    """行业/概念板块仅 A 股；港股暂无该划分。"""
    mkt = (market or "all").strip().lower()
    if mkt != "cn":
        raise HTTPException(
            status_code=400,
            detail=f"{pool_label}回测仅支持 A 股市场（港股暂无行业/概念板块划分）",
        )


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
    if mode == "industry_board":
        bcodes = config.get("industry_board_codes") or []
        if not bcodes:
            return None
        label = "、".join(str(c) for c in bcodes[:3])
        if len(bcodes) > 3:
            label += "等"
        return f"GMS回测_行业板块_{label}"
    if mode == "concept_board":
        bcodes = config.get("concept_board_codes") or []
        if not bcodes:
            return None
        label = "、".join(str(c) for c in bcodes[:3])
        if len(bcodes) > 3:
            label += "等"
        return f"GMS回测_概念板块_{label}"
    return None


def _attach_strategy_config_snapshot(config: dict, strategy_config_id: Optional[int]) -> dict:
    """固化 strategy_config_id 与 config_params_snapshot 到回测任务 config。"""
    mgr = GMSConfigManager()
    if strategy_config_id is not None:
        row = mgr.get_config_row(int(strategy_config_id))
        if not row:
            raise HTTPException(status_code=404, detail="策略参数版本不存在")
        if not row.is_active:
            raise HTTPException(status_code=400, detail="策略参数版本已禁用")
        cid = int(strategy_config_id)
    else:
        cid = mgr.resolve_config_id(None)
        row = mgr.get_config_row(cid)
    cfg = mgr.get_config(cid)
    config["strategy_config_id"] = cid
    config["strategy_config_name"] = row.name if row else "default"
    config["config_params_snapshot"] = copy.deepcopy(cfg)
    return config


def _attach_strategy_config_snapshot(config: dict, strategy_config_id: Optional[int]) -> dict:
    """固化策略参数版本 ID 与快照，供回测可复现。"""
    mgr = GMSConfigManager()
    if strategy_config_id is not None:
        row = mgr.get_config_row(int(strategy_config_id))
        if not row:
            raise HTTPException(status_code=404, detail="策略参数版本不存在")
        if not row.is_active:
            raise HTTPException(status_code=400, detail="策略参数版本已禁用")
        cid = int(row.id)
        cfg_name = row.name
    else:
        cid = mgr.resolve_config_id(None)
        row = mgr.get_config_row(cid)
        cfg_name = row.name if row else "default"
    cfg = mgr.get_config(cid)
    config["strategy_config_id"] = cid
    config["strategy_config_name"] = cfg_name
    config["config_params_snapshot"] = copy.deepcopy(cfg)
    return config


# ---------- 请求体 ----------
class BacktestCreateBody(BaseModel):
    task_name: Optional[str] = Field(None, description="任务名称")
    market: str = Field("all", description="市场: cn / hk / all")
    cn_board_segment: Optional[str] = Field(
        None,
        description="A股板块: ALL/MAIN/CYB/SZ_SME/KCB/BJ；market=cn 或 all 时可选",
    )
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
    stock_pool_mode: Optional[str] = Field(
        "all",
        description="股票池: all / single / custom / watchlist / gms_watchlist / industry_board / concept_board",
    )
    stock_code: Optional[str] = Field(None, description="单股回测时的股票代码，如 000001、00700")
    stock_pool: Optional[List[str]] = Field(None, description="自定义股票池代码列表")
    industry_board_codes: Optional[List[str]] = Field(
        None,
        description="stock_pool_mode=industry_board 时必填：行业板块代码，可多选",
    )
    concept_board_codes: Optional[List[str]] = Field(
        None,
        description="stock_pool_mode=concept_board 时必填：概念板块代码，可多选",
    )
    watchlist_user_id: Optional[int] = Field(None, description="stock_pool_mode=watchlist 时可选：指定用户ID")
    strategy_config_id: Optional[int] = Field(None, ge=1, description="GMS 策略参数版本 ID，不传则用默认版本")


class BatchDeleteBacktestsBody(BaseModel):
    task_ids: List[str] = Field(..., min_length=1, description="回测任务 ID 列表")


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
async def get_system_status(db: Session = Depends(get_db)):
    """系统状态：运行中任务数、报告总数、预计算/选股健康度等。"""
    try:
        running = gms_backtest_storage.count_running_tasks()
        total_reports = gms_backtest_storage.count_completed_reports()
        tasks = admin_interface.list_backtest_tasks(limit=200, offset=0) or []
        pending = sum(1 for t in tasks if str(t.get("status") or "").lower() in ("pending", "queued"))
        failed = sum(1 for t in tasks if str(t.get("status") or "").lower() == "failed")
        screening = screening_stats_summary()
        precompute_runs = get_latest_precompute_runs(db, limit=8)
        recent_jobs = get_recent_job_runs(db, limit=10)
        alert = check_precompute_alert(db)
        if alert:
            maybe_send_gms_alert(db, alert)
        health = "ok"
        if screening.get("timeout_count", 0) > 3 or alert:
            health = "degraded"
        return {
            "success": True,
            "data": {
                "runningBacktests": running,
                "totalReports": total_reports,
                "pendingBacktests": pending,
                "failedBacktests": failed,
                "systemHealth": health,
                "screeningStats": screening,
                "latestPrecomputeRuns": precompute_runs,
                "recentJobRuns": recent_jobs,
                "alertMessage": alert,
            },
        }
    except Exception as e:
        logger.exception("GMS system/status 失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit-logs")
async def list_gms_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    log_type: Optional[str] = Query(None, description="如 gms_config_update"),
    db: Session = Depends(get_db),
):
    """GMS 操作审计（operation_logs 中 log_type 以 gms_ 开头）。"""
    try:
        where = "WHERE log_type LIKE 'gms_%'"
        params: Dict[str, Any] = {"lim": limit, "off": offset}
        if log_type:
            where += " AND log_type = :lt"
            params["lt"] = log_type if log_type.startswith("gms_") else f"gms_{log_type}"
        rows = db.execute(
            text(
                f"""
                SELECT id, log_type, log_message, affected_count, log_status, error_info, log_time
                FROM operation_logs
                {where}
                ORDER BY log_time DESC
                LIMIT :lim OFFSET :off
                """
            ),
            params,
        ).mappings().all()
        items = []
        for r in rows:
            d = dict(r)
            if d.get("log_time") and hasattr(d["log_time"], "isoformat"):
                d["log_time"] = d["log_time"].isoformat()
            items.append(d)
        return {"success": True, "data": {"items": items, "limit": limit, "offset": offset}}
    except Exception as e:
        logger.exception("GMS audit-logs 查询失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/selection-results")
async def get_gms_selection_results_from_trace(
    date: Optional[str] = Query(None, description="目标日期 YYYY-MM-DD，不传则使用 gms_signal_trace 表内最新日期"),
    limit: Optional[int] = Query(None, ge=1, description="最大返回条数"),
    min_strength: float = Query(0.3, ge=0.0, le=1.0, description="最低信号强度 0~1（对应总分 ×100）"),
    config_id: Optional[int] = Query(None, ge=1, description="GMS 策略参数版本 ID，不传则用默认版本"),
    db: Session = Depends(get_db),
):
    """
    管理端「GMS策略管理 → 选股结果」数据源：**gms_signal_trace** 表。
    数据来自 **gms_signal_trace**；公开接口见 `GET /api/frontend/gms/selection-results`（同源逻辑）。
    """
    try:
        resolved_config_id = GMSConfigManager().resolve_config_id(config_id)
        payload, fallback_message = query_gms_signal_trace_selection(
            db, date, min_strength, limit, config_id=resolved_config_id
        )
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
        mkt = (body.market or "all").strip().lower()
        cn_seg = None
        if body.cn_board_segment:
            if mkt == "hk":
                raise HTTPException(status_code=400, detail="港股市场回测不支持 A 股板块筛选")
            cn_seg = _normalize_backtest_cn_board_segment(body.cn_board_segment)
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
        if cn_seg:
            config["cn_board_segment"] = cn_seg
        if mode == "watchlist":
            wl_uid = body.watchlist_user_id
            if wl_uid is not None:
                config["watchlist_user_id"] = int(wl_uid)
            codes = _distinct_watchlist_codes(db, user_id=wl_uid)
            if not codes:
                if wl_uid is None:
                    raise HTTPException(status_code=400, detail="当前无自选股，无法创建回测任务")
                raise HTTPException(status_code=400, detail=f"用户ID={wl_uid}无自选股，无法创建回测任务")
            codes = _apply_backtest_cn_board_segment(codes, mkt, cn_seg)
            if not codes:
                raise HTTPException(status_code=400, detail="自选股在选定 A 股板块下无匹配股票")
            config["stock_pool"] = codes
        elif mode == "gms_watchlist":
            codes = _distinct_gms_strategy_stock_codes(db, market=body.market)
            if not codes:
                m_desc = "全部市场" if body.market == "all" else ("A股" if body.market == "cn" else "港股")
                raise HTTPException(status_code=400, detail=f"GMS观察股({m_desc})中无有效状态数据，无法创建回测任务")
            codes = _apply_backtest_cn_board_segment(codes, mkt, cn_seg)
            if not codes:
                raise HTTPException(status_code=400, detail="GMS观察股在选定 A 股板块下无匹配股票")
            config["stock_pool"] = codes
        elif mode == "industry_board":
            _assert_board_stock_pool_market_cn(mkt, "行业板块")
            raw_bcodes = _normalize_backtest_board_codes(body.industry_board_codes)
            if not raw_bcodes:
                raise HTTPException(status_code=400, detail="请选择至少一个行业板块")
            bcodes, codes = _resolve_industry_board_backtest_codes(db, raw_bcodes)
            if not bcodes:
                raise HTTPException(
                    status_code=400,
                    detail=f"未找到行业板块：{'、'.join(raw_bcodes)}",
                )
            if not codes:
                raise HTTPException(status_code=400, detail="所选行业板块成分股为空，请在管理端维护板块成分股")
            codes = _apply_backtest_cn_board_segment(codes, "cn", cn_seg)
            if not codes:
                raise HTTPException(status_code=400, detail="行业板块在选定 A 股板块下无匹配成分股")
            config["market"] = "cn"
            config["industry_board_codes"] = bcodes
            config["stock_pool"] = codes
        elif mode == "concept_board":
            _assert_board_stock_pool_market_cn(mkt, "概念板块")
            raw_bcodes = _normalize_backtest_board_codes(body.concept_board_codes, upper=True)
            if not raw_bcodes:
                raise HTTPException(status_code=400, detail="请选择至少一个概念板块")
            bcodes, codes = _resolve_concept_board_backtest_codes(db, raw_bcodes)
            if not codes:
                raise HTTPException(status_code=400, detail="所选概念板块成分股为空，请在管理端维护板块成分股")
            codes = _apply_backtest_cn_board_segment(codes, "cn", cn_seg)
            if not codes:
                raise HTTPException(status_code=400, detail="概念板块在选定 A 股板块下无匹配成分股")
            config["market"] = "cn"
            config["concept_board_codes"] = bcodes
            config["stock_pool"] = codes
        else:
            if body.stock_code:
                config["stock_code"] = body.stock_code.strip()
            if body.stock_pool:
                pool = [str(c).strip() for c in body.stock_pool if str(c).strip()]
                pool = _apply_backtest_cn_board_segment(pool, mkt, cn_seg)
                if cn_seg and not pool:
                    raise HTTPException(status_code=400, detail="自定义股票池在选定 A 股板块下无匹配股票")
                config["stock_pool"] = pool
        # 任务名称：用户填写则用用户的；否则单股/自定义/自选股时生成含股票代码和名称的默认名
        task_name = (body.task_name or "").strip()
        if not task_name:
            task_name = _build_task_name_with_stocks(db, config)
        _attach_strategy_config_snapshot(config, body.strategy_config_id)
        task_id = admin_interface.create_backtest(config, name=task_name or None)
        write_gms_audit(
            db,
            "gms_backtest_create",
            {"task_id": task_id, "task_name": task_name, "market": body.market, "mode": mode},
            affected_count=len(config.get("stock_pool") or []),
        )
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


@router.post("/backtests/batch-delete")
async def batch_delete_backtests(body: BatchDeleteBacktestsBody):
    """批量删除回测任务及关联报告。"""
    task_ids = [str(t).strip() for t in body.task_ids if str(t).strip()]
    if not task_ids:
        raise HTTPException(status_code=400, detail="task_ids 不能为空")
    data = admin_interface.delete_tasks_batch(task_ids)
    return {"success": True, "data": data}


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
    payload = admin_interface.download_report(report_id, variant=variant)
    if not payload:
        raise HTTPException(status_code=404, detail="报告或明细文件不存在")
    data, filename, media_type = payload
    disp = f"attachment; filename*=UTF-8''{quote(filename)}"
    return Response(content=data, media_type=media_type, headers={"Content-Disposition": disp})


@router.delete("/reports/{report_id}")
@router.post("/reports/{report_id}/delete")
async def delete_report(report_id: str):
    """删除历史报告。同时支持 DELETE 和 POST /delete 兼容生产环境。"""
    ok = admin_interface.delete_report(report_id)
    if not ok:
        raise HTTPException(status_code=404, detail="报告不存在")
    return {"success": True}


# ---------- config ----------
@router.get("/config")
async def get_config():
    """读取 GMS 默认策略参数版本配置（兼容旧接口）。"""
    try:
        mgr = GMSConfigManager()
        default_id = mgr.resolve_config_id(None)
        cfg = mgr.get_config(default_id)
        return {"success": True, "data": cfg, "config_id": default_id}
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
        default_id = mgr.resolve_config_id(None)
        return {"success": True, "data": mgr.get_config(default_id), "config_id": default_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("GMS config put 失败")
        raise HTTPException(status_code=500, detail=str(e))


# ---------- strategy-configs（GMS 策略参数版本） ----------
class StrategyConfigCreateBody(BaseModel):
    name: str = Field(..., description="版本名称，唯一")
    version_label: Optional[str] = Field(None, description="语义版本号，如 1.0.0")
    description: Optional[str] = Field(None, description="描述")
    config_params: dict = Field(default_factory=dict, description="完整或部分参数，会与默认 merge")
    is_active: bool = Field(True, description="是否启用")
    is_default: bool = Field(False, description="是否设为默认")
    precompute_enabled: bool = Field(False, description="是否参与定时预计算")
    created_by: Optional[str] = Field(None, description="创建人")


class StrategyConfigUpdateBody(BaseModel):
    name: Optional[str] = Field(None, description="版本名称")
    version_label: Optional[str] = Field(None, description="语义版本号")
    description: Optional[str] = Field(None, description="描述")
    config: Optional[dict] = Field(None, description="部分配置，深度合并")
    is_active: Optional[bool] = Field(None, description="是否启用")
    precompute_enabled: Optional[bool] = Field(None, description="是否参与预计算")
    change_note: Optional[str] = Field(None, description="变更说明")


class StrategyConfigCloneBody(BaseModel):
    new_name: str = Field(..., description="新版本名称")
    precompute_enabled: bool = Field(False, description="是否参与预计算")
    created_by: Optional[str] = Field(None, description="创建人")


@router.get("/strategy-configs")
async def list_strategy_configs(
    active_only: bool = Query(False, description="仅返回启用版本"),
    canonical_only: bool = Query(True, description="仅返回共享参数版本 default / gms_penalty"),
):
    try:
        mgr = GMSConfigManager()
        return {"success": True, "data": mgr.list_configs(active_only=active_only, canonical_only=canonical_only)}
    except Exception as e:
        logger.exception("GMS strategy-configs list 失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategy-configs/compare")
async def compare_strategy_configs(
    config_id_a: int = Query(..., ge=1),
    config_id_b: int = Query(..., ge=1),
):
    try:
        mgr = GMSConfigManager()
        return {"success": True, "data": mgr.compare_configs(config_id_a, config_id_b)}
    except Exception as e:
        logger.exception("GMS strategy-configs compare 失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategy-configs/{config_id}")
async def get_strategy_config(config_id: int):
    try:
        mgr = GMSConfigManager()
        row = mgr.get_config_row(config_id)
        if not row:
            raise HTTPException(status_code=404, detail="策略参数版本不存在")
        data = mgr._serialize_config_row(row)
        data["config_params"] = mgr.get_config(config_id)
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("GMS strategy-config get 失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/strategy-configs")
async def create_strategy_config(body: StrategyConfigCreateBody):
    try:
        mgr = GMSConfigManager()
        new_id = mgr.create_config(
            name=body.name,
            config_params=body.config_params,
            version_label=body.version_label,
            description=body.description,
            is_active=body.is_active,
            is_default=body.is_default,
            precompute_enabled=body.precompute_enabled,
            created_by=body.created_by,
        )
        row = mgr.get_config_row(new_id)
        data = mgr._serialize_config_row(row)
        data["config_params"] = mgr.get_config(new_id)
        return {"success": True, "data": data}
    except Exception as e:
        logger.exception("GMS strategy-config create 失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/strategy-configs/{config_id}")
@router.post("/strategy-configs/{config_id}/update")
async def update_strategy_config(config_id: int, body: StrategyConfigUpdateBody, db: Session = Depends(get_db)):
    try:
        mgr = GMSConfigManager()
        if not mgr.get_config_row(config_id):
            raise HTTPException(status_code=404, detail="策略参数版本不存在")
        ok = mgr.update_config(
            config_id,
            body.config or {},
            name=body.name,
            version_label=body.version_label,
            description=body.description,
            is_active=body.is_active,
            precompute_enabled=body.precompute_enabled,
            change_note=body.change_note,
        )
        if not ok:
            raise HTTPException(status_code=500, detail="更新失败")
        row = mgr.get_config_row(config_id)
        data = mgr._serialize_config_row(row)
        data["config_params"] = mgr.get_config(config_id)
        write_gms_audit(
            db,
            "gms_config_update",
            {
                "config_id": config_id,
                "name": data.get("name"),
                "change_note": body.change_note,
                "precompute_enabled": data.get("precompute_enabled"),
            },
        )
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("GMS strategy-config update 失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/strategy-configs/{config_id}/clone")
async def clone_strategy_config(config_id: int, body: StrategyConfigCloneBody):
    try:
        mgr = GMSConfigManager()
        new_id = mgr.clone_config(
            config_id,
            body.new_name,
            created_by=body.created_by,
            precompute_enabled=body.precompute_enabled,
        )
        row = mgr.get_config_row(new_id)
        data = mgr._serialize_config_row(row)
        data["config_params"] = mgr.get_config(new_id)
        return {"success": True, "data": data}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("GMS strategy-config clone 失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/strategy-configs/{config_id}/default")
async def set_strategy_config_default(config_id: int):
    try:
        mgr = GMSConfigManager()
        if not mgr.get_config_row(config_id):
            raise HTTPException(status_code=404, detail="策略参数版本不存在")
        mgr.set_default(config_id)
        row = mgr.get_config_row(config_id)
        data = mgr._serialize_config_row(row)
        data["config_params"] = mgr.get_config(config_id)
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("GMS strategy-config set default 失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/strategy-configs/{config_id}/deactivate")
async def deactivate_strategy_config(config_id: int):
    try:
        mgr = GMSConfigManager()
        mgr.deactivate_config(config_id)
        row = mgr.get_config_row(config_id)
        if not row:
            raise HTTPException(status_code=404, detail="策略参数版本不存在")
        data = mgr._serialize_config_row(row)
        data["config_params"] = mgr.get_config(config_id)
        return {"success": True, "data": data}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("GMS strategy-config deactivate 失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scoring-mechanisms")
async def list_scoring_mechanisms():
    try:
        from backend_core.strategies.gms.scoring import list_mechanisms

        return {"success": True, "data": list_mechanisms()}
    except Exception as e:
        logger.exception("GMS scoring-mechanisms list 失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/penalty-rule-types")
async def list_penalty_rule_types_api():
    try:
        from backend_core.strategies.gms.scoring import list_penalty_rule_types

        return {"success": True, "data": list_penalty_rule_types()}
    except Exception as e:
        logger.exception("GMS penalty-rule-types list 失败")
        raise HTTPException(status_code=500, detail=str(e))


# ---------- GMS 策略版本与观察股管理 ----------
class StrategyVersionCreateBody(BaseModel):
    strategy_code: str = Field("GMS", description="策略编码")
    version_name: str = Field(..., description="GMS策略版本名称")
    version_no: int = Field(..., ge=1, description="版本序号")
    description: Optional[str] = Field(None, description="版本描述")
    config_id: Optional[int] = Field(None, ge=1, description="绑定的参数版本 ID（与 auto_create_config 二选一）")
    is_active: bool = Field(True, description="是否启用")
    created_by: Optional[str] = Field(None, description="创建人")
    auto_create_config: bool = Field(True, description="未传 config_id 时按打分机制绑定共享参数版本（不再新建 auto_gms_*）")
    scoring_mechanism: Optional[str] = Field("tiered_dual_max", description="打分机制")
    penalty_rules: Optional[List[Dict[str, Any]]] = Field(None, description="减分规则（增强版）")
    config_params: Optional[Dict[str, Any]] = Field(None, description="初始策略参数片段（合并到新建 config）")


class StrategyVersionUpdateBody(BaseModel):
    strategy_code: Optional[str] = Field(None, description="策略编码")
    version_name: Optional[str] = Field(None, description="GMS策略版本名称")
    version_no: Optional[int] = Field(None, ge=1, description="版本序号")
    description: Optional[str] = Field(None, description="版本描述")
    config_id: Optional[int] = Field(None, ge=1, description="绑定的 GMS 策略参数版本 ID")
    is_active: Optional[bool] = Field(None, description="是否启用")
    created_by: Optional[str] = Field(None, description="创建人")


class StrategyVersionScoringUpdateBody(BaseModel):
    scoring_mechanism: Optional[str] = Field(None, description="打分机制")
    penalty_rules: Optional[List[Dict[str, Any]]] = Field(None, description="减分规则")
    config: Optional[Dict[str, Any]] = Field(None, description="嵌套 config 片段（深度合并到绑定 config）")


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
    clear_existing: bool = Field(False, description="导入前清空该策略版本下全部观察股")


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


def _serialize_strategy_version(row: GMSStrategyVersion, scoring_summary: Optional[dict] = None) -> dict:
    data = {
        "id": row.id,
        "strategy_code": row.strategy_code,
        "version_name": row.version_name,
        "version_no": row.version_no,
        "description": row.description,
        "config_id": getattr(row, "config_id", None),
        "is_active": bool(row.is_active),
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    if scoring_summary:
        data.update(scoring_summary)
    return data


def _scoring_summary_from_config(config_id: Optional[int]) -> dict:
    if not config_id:
        return {}
    try:
        mgr = GMSConfigManager()
        cfg = mgr.get_config(int(config_id))
        scoring = cfg.get("scoring") or {}
        mechanism = scoring.get("mechanism") or "tiered_dual_max"
        from backend_core.strategies.gms.scoring import get_mechanism_meta

        meta = get_mechanism_meta(mechanism)
        return {
            "scoring_mechanism": mechanism,
            "scoring_mechanism_label": meta.get("label"),
            "penalty_rules": scoring.get("penalty_rules") or [],
        }
    except Exception:
        return {}


def _ensure_config_not_bound(db: Session, config_id: int, exclude_version_id: Optional[int] = None) -> None:
    mgr = GMSConfigManager()
    if mgr.is_canonical_config(config_id):
        return
    q = db.query(GMSStrategyVersion).filter(GMSStrategyVersion.config_id == config_id)
    if exclude_version_id:
        q = q.filter(GMSStrategyVersion.id != exclude_version_id)
    if q.first():
        raise HTTPException(status_code=400, detail="该参数版本已绑定其他 GMS 策略版本（1:1 约束）")


def _canonical_config_label(mechanism: Optional[str]) -> str:
    from backend_core.strategies.gms.config import GMS_CANONICAL_PENALTY_NAME, GMS_CANONICAL_STANDARD_NAME

    mech = (mechanism or "tiered_dual_max").strip()
    if mech == "tiered_dual_penalty":
        return GMS_CANONICAL_PENALTY_NAME
    return GMS_CANONICAL_STANDARD_NAME


def _resolve_version_config_id(
    db: Session,
    row: GMSStrategyVersion,
    body: "StrategyVersionScoringUpdateBody",
) -> int:
    """按打分机制绑定共享参数版本（default / gms_penalty），修改时原地更新，不新建版本。"""
    mechanism = (body.scoring_mechanism or "tiered_dual_max").strip()
    mgr = GMSConfigManager()
    config_id = mgr.resolve_canonical_config_id(mechanism)
    if getattr(row, "config_id", None) != config_id:
        row.config_id = config_id
        db.commit()
        db.refresh(row)
        logger.info(
            "策略版本 %s 绑定共享参数 %s (config_id=%s)",
            row.id,
            _canonical_config_label(mechanism),
            config_id,
        )
    return int(config_id)


def _bind_canonical_config_for_mechanism(
    scoring_mechanism: Optional[str],
    penalty_rules: Optional[List[Dict[str, Any]]] = None,
    config_params: Optional[Dict[str, Any]] = None,
) -> int:
    """新建策略版本时绑定共享参数，不创建 auto_gms_v*。"""
    mgr = GMSConfigManager()
    mechanism = (scoring_mechanism or "tiered_dual_max").strip()
    config_id = mgr.resolve_canonical_config_id(mechanism)
    patch: Dict[str, Any] = copy.deepcopy(config_params or {})
    scoring_patch: Dict[str, Any] = dict(patch.get("scoring") or {})
    scoring_patch["mechanism"] = mechanism
    if penalty_rules is not None:
        scoring_patch["penalty_rules"] = penalty_rules
    if scoring_patch:
        patch["scoring"] = scoring_patch
    if patch:
        mgr.update_config(int(config_id), patch, change_note="strategy_version_bind")
    return int(config_id)


def _serialize_strategy_version_stock(
    row: GMSStrategyVersionStock,
    price: Optional[float] = None,
    industry: Optional[str] = None,
) -> dict:
    return {
        "id": row.id,
        "version_id": row.version_id,
        "market": row.market,
        "stock_code": _as_text_stock_code(row.stock_code),
        "stock_name": row.stock_name,
        "industry": industry,
        "sort_order": row.sort_order,
        "status": row.status,
        "is_verified": bool(row.is_verified),
        "remark": row.remark,
        "current_price": price,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _lookup_stock_industry(db: Session, market: str, stock_code: str) -> Optional[str]:
    code = _as_text_stock_code(stock_code)
    if not code:
        return None
    if market == "A":
        return get_industry_board_name_by_stock_code(db, code)
    row = db.query(StockBasicInfoHK.industry).filter(StockBasicInfoHK.code == code).first()
    if not row or row[0] is None:
        return None
    s = str(row[0]).strip()
    return s or None


def _batch_stock_industries(
    db: Session, rows: List[GMSStrategyVersionStock]
) -> Tuple[Dict[str, str], Dict[str, str]]:
    a_codes = list({str(r.stock_code).strip() for r in rows if r.market == "A" and r.stock_code})
    hk_codes = list({str(r.stock_code).strip() for r in rows if r.market == "HK" and r.stock_code})
    a_map = batch_industry_board_names_by_stock_codes(db, a_codes)
    hk_map: Dict[str, str] = {}
    if hk_codes:
        for code, industry in (
            db.query(StockBasicInfoHK.code, StockBasicInfoHK.industry)
            .filter(StockBasicInfoHK.code.in_(hk_codes))
            .all()
        ):
            if industry:
                s = str(industry).strip()
                if s:
                    hk_map[str(code).strip()] = s
    return a_map, hk_map


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
        "data": [
            _serialize_strategy_version(r, _scoring_summary_from_config(getattr(r, "config_id", None)))
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/strategy-versions/{version_id}")
async def get_strategy_version(version_id: int, db: Session = Depends(get_db)):
    row = db.query(GMSStrategyVersion).filter(GMSStrategyVersion.id == version_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="策略版本不存在")
    return {
        "success": True,
        "data": _serialize_strategy_version(row, _scoring_summary_from_config(getattr(row, "config_id", None))),
    }


@router.get("/strategy-versions/{version_id}/full")
async def get_strategy_version_full(version_id: int, db: Session = Depends(get_db)):
    row = db.query(GMSStrategyVersion).filter(GMSStrategyVersion.id == version_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="策略版本不存在")
    stock_count = (
        db.query(GMSStrategyVersionStock)
        .filter(GMSStrategyVersionStock.version_id == version_id)
        .count()
    )
    config_id = getattr(row, "config_id", None)
    config_data = None
    if config_id:
        mgr = GMSConfigManager()
        cfg_row = mgr.get_config_row(int(config_id))
        if cfg_row:
            config_data = mgr._serialize_config_row(cfg_row)
            config_data["config_params"] = mgr.get_config(int(config_id))
    return {
        "success": True,
        "data": {
            "version": _serialize_strategy_version(row, _scoring_summary_from_config(config_id)),
            "stock_count": stock_count,
            "config": config_data,
        },
    }


@router.post("/strategy-versions/{version_id}/scoring")
@router.put("/strategy-versions/{version_id}/scoring")
async def update_strategy_version_scoring(
    version_id: int,
    body: StrategyVersionScoringUpdateBody,
    db: Session = Depends(get_db),
):
    row = db.query(GMSStrategyVersion).filter(GMSStrategyVersion.id == version_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="策略版本不存在")
    config_id = _resolve_version_config_id(db, row, body)
    patch: Dict[str, Any] = copy.deepcopy(body.config or {})
    scoring_patch: Dict[str, Any] = dict(patch.get("scoring") or {})
    if body.scoring_mechanism is not None:
        scoring_patch["mechanism"] = body.scoring_mechanism
    if body.penalty_rules is not None:
        scoring_patch["penalty_rules"] = body.penalty_rules
    if scoring_patch:
        patch["scoring"] = scoring_patch
    mgr = GMSConfigManager()
    try:
        ok = mgr.update_config(int(config_id), patch, change_note="strategy_version_scoring")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not ok:
        raise HTTPException(status_code=500, detail="更新打分配置失败")
    return {
        "success": True,
        "data": _serialize_strategy_version(row, _scoring_summary_from_config(config_id)),
    }


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
    config_id = body.config_id
    if config_id:
        _ensure_config_not_bound(db, int(config_id))
    elif body.auto_create_config:
        try:
            config_id = _bind_canonical_config_for_mechanism(
                body.scoring_mechanism,
                body.penalty_rules,
                body.config_params,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        mgr = GMSConfigManager()
        config_id = mgr.resolve_config_id(None)
    row = GMSStrategyVersion(
        strategy_code=strategy_code,
        version_name=body.version_name.strip(),
        version_no=body.version_no,
        description=body.description,
        config_id=config_id,
        is_active=body.is_active,
        created_by=(body.created_by or "").strip() or None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "success": True,
        "data": _serialize_strategy_version(row, _scoring_summary_from_config(config_id)),
    }


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
    if body.config_id is not None:
        _ensure_config_not_bound(db, int(body.config_id), exclude_version_id=version_id)
        row.config_id = body.config_id
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
    return {
        "success": True,
        "data": _serialize_strategy_version(row, _scoring_summary_from_config(getattr(row, "config_id", None))),
    }


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

    a_industries, hk_industries = _batch_stock_industries(db, rows)

    return {
        "success": True,
        "data": [
            _serialize_strategy_version_stock(
                r,
                a_prices.get(r.stock_code) if r.market == "A" else hk_prices.get(r.stock_code),
                a_industries.get(str(r.stock_code).strip())
                if r.market == "A"
                else hk_industries.get(str(r.stock_code).strip()),
            )
            for r in rows
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
    return {
        "success": True,
        "data": _serialize_strategy_version_stock(
            row, industry=_lookup_stock_industry(db, row.market, row.stock_code)
        ),
    }


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
    return {
        "success": True,
        "data": _serialize_strategy_version_stock(
            row, industry=_lookup_stock_industry(db, row.market, row.stock_code)
        ),
    }


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

    cleared_count = 0
    if body.clear_existing:
        cleared_count = (
            db.query(GMSStrategyVersionStock)
            .filter(GMSStrategyVersionStock.version_id == body.version_id)
            .delete(synchronize_session=False)
        )
        db.flush()

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
            created_items.append(
                _serialize_strategy_version_stock(
                    row, industry=_lookup_stock_industry(db, row.market, row.stock_code)
                )
            )
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
            "cleared_count": cleared_count,
            "success_count": success_count,
            "skip_count": skip_count,
            "fail_count": fail_count,
            "fail_details": fail_details,
            "created_items": created_items,
        },
    }
