# -*- coding: utf-8 -*-
"""URT 上升趋势策略 — 管理端 API（参数版本 + 预计算 + 回测）。"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from backend_api.database import get_db
from backend_api.services.urt_audit_service import write_urt_audit
from backend_core.strategies.urt.config import URTConfigManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/urt", tags=["URT Admin"])


class StrategyConfigCreateBody(BaseModel):
    name: str = Field(..., description="版本名称")
    config_params: Optional[Dict[str, Any]] = None
    version_label: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    is_default: bool = False
    precompute_enabled: bool = False
    created_by: Optional[str] = None


class StrategyConfigUpdateBody(BaseModel):
    name: Optional[str] = None
    config_params: Optional[Dict[str, Any]] = None
    version_label: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    precompute_enabled: Optional[bool] = None


class BacktestCreateBody(BaseModel):
    start_date: str
    end_date: str
    task_name: Optional[str] = None
    strategy_config_id: Optional[int] = None
    target_pct: float = 0.10
    horizon_days: int = 20
    min_score: Optional[float] = None
    use_trace: bool = True
    exit_mode: str = Field(
        "hit_rate",
        description=(
            "出场模式: hit_rate=命中率(不止损) | risk_exit=纪律出场(止损/连跌/回撤) "
            "| structure_exit=结构出场(支撑止损/阻力止盈)"
        ),
    )
    stock_pool_mode: Optional[str] = Field(
        "all",
        description="股票池: all / single / custom / watchlist / industry_board / concept_board",
    )
    stock_code: Optional[str] = None
    stock_pool: Optional[List[str]] = None
    watchlist_user_id: Optional[int] = None
    industry_board_codes: Optional[List[str]] = None
    concept_board_codes: Optional[List[str]] = None
    cn_board_segment: Optional[str] = Field(
        None, description="A股板块: ALL/MAIN/CYB/SZ_SME/KCB/BJ"
    )
    compare_hit_rate: Optional[bool] = Field(
        None,
        description="结构/纪律出场完成后是否自动再跑一条同配置命中率对照；默认对非 hit_rate 开启",
    )


class BatchDeleteBody(BaseModel):
    task_ids: List[str] = Field(default_factory=list)


def _normalize_a_code(code: str) -> str:
    s = str(code or "").strip()
    if s.isdigit() and len(s) <= 6:
        return s.zfill(6)
    return s


def _normalize_board_codes(raw: Optional[List[str]], *, upper: bool = False) -> List[str]:
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


def _normalize_cn_board_segment(raw: Optional[str]) -> Optional[str]:
    from backend_api.utils.cn_listed_board_filter import normalize_list_board_segment

    seg = (raw or "").strip().upper()
    if not seg or seg == "ALL":
        return None
    if not normalize_list_board_segment(seg):
        raise HTTPException(status_code=400, detail="cn_board_segment 无效，可选: ALL/MAIN/CYB/SZ_SME/KCB/BJ")
    return seg


def _apply_cn_board_segment(codes: List[str], board_segment: Optional[str]) -> List[str]:
    seg = _normalize_cn_board_segment(board_segment)
    if not seg:
        return codes
    from backend_api.utils.cn_listed_board_filter import filter_stock_codes_by_board_segment

    return filter_stock_codes_by_board_segment(codes, seg)


def _distinct_watchlist_codes(db: Session, user_id: Optional[int] = None) -> List[str]:
    from backend_api.models import Watchlist

    q = db.query(Watchlist.stock_code)
    if user_id is not None:
        q = q.filter(Watchlist.user_id == int(user_id))
    rows = q.distinct().all()
    return sorted({_normalize_a_code(str(r[0])) for r in rows if r[0] and str(r[0]).strip()})


def _resolve_industry_codes(db: Session, raw: List[str]) -> tuple:
    from backend_api.models import IndustryBoardConstituent
    from backend_api.utils.bk_board_code import resolve_industry_board_codes

    bcodes = resolve_industry_board_codes(db, raw)
    if not bcodes:
        return [], []
    rows = (
        db.query(IndustryBoardConstituent.stock_code)
        .filter(IndustryBoardConstituent.board_code.in_(bcodes))
        .distinct()
        .all()
    )
    pool = sorted({_normalize_a_code(str(r[0])) for r in rows if r[0] and str(r[0]).strip()})
    return bcodes, pool


def _resolve_concept_codes(db: Session, raw: List[str]) -> tuple:
    from backend_api.models import ConceptBoardConstituent

    bcodes = _normalize_board_codes(raw, upper=True)
    if not bcodes:
        return [], []
    rows = (
        db.query(ConceptBoardConstituent.stock_code)
        .filter(ConceptBoardConstituent.board_code.in_(bcodes))
        .distinct()
        .all()
    )
    pool = sorted({_normalize_a_code(str(r[0])) for r in rows if r[0] and str(r[0]).strip()})
    return bcodes, pool


def _attach_urt_trade_meta(db: Session, config: Dict[str, Any]) -> Dict[str, Any]:
    """将交易逻辑说明与风控参数快照写入任务 config，供详情页展示。"""
    from backend_core.strategies.urt.backtest_runner import build_urt_trade_meta

    mgr = URTConfigManager()
    mgr.ensure_default_row(db)
    sid = config.get("strategy_config_id")
    strategy_cfg = mgr.get_config(int(sid) if sid is not None else None, db=db)
    min_score = config.get("min_score")
    if min_score is None:
        min_score = strategy_cfg.get("min_score")
    meta = build_urt_trade_meta(
        target_pct=float(config.get("target_pct", 0.10)),
        horizon_days=int(config.get("horizon_days", 20)),
        min_score=min_score,
        use_trace=bool(config.get("use_trace", True)),
        risk=strategy_cfg.get("risk") if isinstance(strategy_cfg.get("risk"), dict) else {},
        exit_mode=str(config.get("exit_mode") or "hit_rate"),
        structure_stop_buffer_pct=float(strategy_cfg.get("structure_stop_buffer_pct") or 0.02),
        structure_rr_min_upside_pct=float(strategy_cfg.get("structure_rr_min_upside_pct") or 0.03),
        structure_cfg=strategy_cfg,
    )
    config["risk_params"] = meta["risk_params"]
    config["trade_logic"] = meta["trade_logic"]
    config["strategy_risk"] = meta["risk_params"]
    return config


def _build_backtest_config(db: Session, body: BacktestCreateBody) -> Dict[str, Any]:
    mode = (body.stock_pool_mode or "all").strip() or "all"
    cn_seg = _normalize_cn_board_segment(body.cn_board_segment)
    config: Dict[str, Any] = {
        "start_date": body.start_date,
        "end_date": body.end_date,
        "task_name": body.task_name,
        "strategy_config_id": body.strategy_config_id,
        "target_pct": body.target_pct,
        "horizon_days": body.horizon_days,
        "min_score": body.min_score,
        "use_trace": body.use_trace,
        "exit_mode": (
            em
            if (em := (body.exit_mode or "hit_rate").strip().lower())
            in ("hit_rate", "risk_exit", "structure_exit")
            else "hit_rate"
        ),
        "stock_pool_mode": mode,
        "market": "cn",
    }
    if body.compare_hit_rate is None:
        config["compare_hit_rate"] = config["exit_mode"] in ("structure_exit", "risk_exit")
    else:
        config["compare_hit_rate"] = bool(body.compare_hit_rate)
    if cn_seg:
        config["cn_board_segment"] = cn_seg

    if mode == "all":
        # 全市场：若指定板块，则先取全市场候选再过滤不现实；板块过滤在无 pool 时由 runner 全扫
        # 有 cn_board_segment 时展开为代码池（从 stock_basic_info）
        if cn_seg:
            from backend_api.models import StockBasicInfo
            from backend_api.utils.cn_listed_board_filter import filter_stock_codes_by_board_segment

            rows = (
                db.query(StockBasicInfo.code)
                .filter(func.length(StockBasicInfo.code) == 6)
                .all()
            )
            codes = [_normalize_a_code(str(r[0])) for r in rows if r[0]]
            codes = filter_stock_codes_by_board_segment(codes, cn_seg)
            if not codes:
                raise HTTPException(status_code=400, detail="所选 A 股板块下无股票")
            config["stock_pool"] = codes
    elif mode == "single":
        code = _normalize_a_code(body.stock_code or "")
        if not code:
            raise HTTPException(status_code=400, detail="单股回测请填写股票代码")
        codes = _apply_cn_board_segment([code], body.cn_board_segment)
        if not codes:
            raise HTTPException(status_code=400, detail="股票代码不在所选 A 股板块内")
        config["stock_code"] = code
        config["stock_pool"] = codes
    elif mode == "custom":
        raw = body.stock_pool or []
        codes = [_normalize_a_code(c) for c in raw if str(c).strip()]
        codes = list(dict.fromkeys(codes))
        codes = _apply_cn_board_segment(codes, body.cn_board_segment)
        if not codes:
            raise HTTPException(status_code=400, detail="自定义股票列表为空")
        config["stock_pool"] = codes
    elif mode == "watchlist":
        uid = body.watchlist_user_id
        if uid is not None:
            config["watchlist_user_id"] = int(uid)
        codes = _distinct_watchlist_codes(db, user_id=uid)
        codes = _apply_cn_board_segment(codes, body.cn_board_segment)
        if not codes:
            raise HTTPException(status_code=400, detail="自选股列表为空")
        config["stock_pool"] = codes
    elif mode == "industry_board":
        raw = _normalize_board_codes(body.industry_board_codes)
        if not raw:
            raise HTTPException(status_code=400, detail="请选择行业板块")
        bcodes, codes = _resolve_industry_codes(db, raw)
        codes = _apply_cn_board_segment(codes, body.cn_board_segment)
        if not codes:
            raise HTTPException(status_code=400, detail="行业板块下无成分股")
        config["industry_board_codes"] = bcodes
        config["stock_pool"] = codes
    elif mode == "concept_board":
        raw = _normalize_board_codes(body.concept_board_codes, upper=True)
        if not raw:
            raise HTTPException(status_code=400, detail="请选择概念板块")
        bcodes, codes = _resolve_concept_codes(db, raw)
        codes = _apply_cn_board_segment(codes, body.cn_board_segment)
        if not codes:
            raise HTTPException(status_code=400, detail="概念板块下无成分股")
        config["concept_board_codes"] = bcodes
        config["stock_pool"] = codes
    else:
        raise HTTPException(status_code=400, detail=f"不支持的股票池模式: {mode}")

    return _attach_urt_trade_meta(db, config)


@router.get("/system/status")
async def get_system_status(db: Session = Depends(get_db)):
    """系统状态：运行中回测数、pending、failed、报告数。"""
    try:
        from backend_core.strategies.urt import backtest_storage

        running = backtest_storage.count_running_tasks()
        total_reports = backtest_storage.count_completed_reports()
        tasks = backtest_storage.list_tasks(limit=200)
        pending = sum(
            1 for t in tasks if str(t.get("status") or "").lower() in ("pending", "queued")
        )
        failed = sum(1 for t in tasks if str(t.get("status") or "").lower() == "failed")
        health = "ok"
        if failed > 3:
            health = "degraded"
        return {
            "success": True,
            "data": {
                "runningBacktests": running,
                "totalReports": total_reports,
                "pendingBacktests": pending,
                "failedBacktests": failed,
                "systemHealth": health,
            },
        }
    except Exception as e:
        logger.exception("URT system/status 失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit-logs")
async def list_urt_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    log_type: Optional[str] = Query(None, description="如 urt_config_update"),
    db: Session = Depends(get_db),
):
    """URT 操作审计（operation_logs 中 log_type 以 urt_ 开头）。"""
    try:
        where = "WHERE log_type LIKE 'urt_%'"
        params: Dict[str, Any] = {"lim": limit, "off": offset}
        if log_type:
            where += " AND log_type = :lt"
            params["lt"] = log_type if log_type.startswith("urt_") else f"urt_{log_type}"
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
        logger.exception("URT audit-logs 查询失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategy-configs")
async def list_strategy_configs(
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
):
    try:
        mgr = URTConfigManager()
        mgr.ensure_default_row(db)
        return {"success": True, "data": mgr.list_configs(db, active_only=active_only)}
    except Exception as e:
        logger.exception("URT strategy-configs list 失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategy-configs/{config_id}")
async def get_strategy_config(config_id: int, db: Session = Depends(get_db)):
    try:
        mgr = URTConfigManager()
        row = mgr.get_config_row(db, config_id)
        if not row:
            raise HTTPException(status_code=404, detail="策略参数版本不存在")
        data = mgr._serialize_row(row)
        data["config_params"] = mgr.get_config(config_id, db=db)
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("URT strategy-config get 失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/strategy-configs")
async def create_strategy_config(body: StrategyConfigCreateBody, db: Session = Depends(get_db)):
    try:
        mgr = URTConfigManager()
        mgr.ensure_default_row(db)
        new_id = mgr.create_config(
            db,
            name=body.name,
            config_params=body.config_params,
            version_label=body.version_label,
            description=body.description,
            is_active=body.is_active,
            is_default=body.is_default,
            precompute_enabled=body.precompute_enabled,
            created_by=body.created_by,
        )
        row = mgr.get_config_row(db, new_id)
        data = mgr._serialize_row(row)
        data["config_params"] = mgr.get_config(new_id, db=db)
        write_urt_audit(
            db,
            "urt_config_create",
            {"config_id": new_id, "name": body.name, "action": "create"},
        )
        return {"success": True, "data": data}
    except Exception as e:
        logger.exception("URT strategy-config create 失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/strategy-configs/{config_id}")
@router.post("/strategy-configs/{config_id}/update")
async def update_strategy_config(
    config_id: int,
    body: StrategyConfigUpdateBody,
    db: Session = Depends(get_db),
):
    try:
        mgr = URTConfigManager()
        if not mgr.get_config_row(db, config_id):
            raise HTTPException(status_code=404, detail="策略参数版本不存在")
        ok = mgr.update_config(
            db,
            config_id,
            name=body.name,
            version_label=body.version_label,
            description=body.description,
            config_params=body.config_params,
            is_active=body.is_active,
            is_default=body.is_default,
            precompute_enabled=body.precompute_enabled,
        )
        if not ok:
            raise HTTPException(status_code=400, detail="更新失败")
        row = mgr.get_config_row(db, config_id)
        data = mgr._serialize_row(row)
        data["config_params"] = mgr.get_config(config_id, db=db)
        write_urt_audit(
            db,
            "urt_config_update",
            {"config_id": config_id, "name": data.get("name"), "action": "update"},
        )
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("URT strategy-config update 失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/default-params")
async def get_default_params():
    mgr = URTConfigManager()
    return {"success": True, "data": mgr.load_file_config()}


@router.get("/watchlist-users")
async def list_watchlist_users(db: Session = Depends(get_db)):
    from backend_api.models import User, Watchlist

    try:
        rows = (
            db.query(
                User.id.label("user_id"),
                User.username.label("username"),
                func.count(Watchlist.id).label("watchlist_count"),
            )
            .join(Watchlist, Watchlist.user_id == User.id)
            .group_by(User.id, User.username)
            .having(func.count(Watchlist.id) > 0)
            .order_by(func.count(Watchlist.id).desc())
            .all()
        )
        data = [
            {
                "user_id": int(r.user_id),
                "username": r.username,
                "watchlist_count": int(r.watchlist_count or 0),
            }
            for r in rows
        ]
        return {"success": True, "data": data}
    except Exception as e:
        logger.exception("URT watchlist-users 失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/screen-preview")
async def screen_preview(
    limit: int = Query(50, ge=1, le=500),
    date: Optional[str] = Query(None),
    config_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    try:
        from backend_core.strategies.urt import URTFrontendInterface

        return URTFrontendInterface.screen(
            db,
            scope="all",
            limit=limit,
            screening_date=date,
            config_id=config_id,
        )
    except Exception as e:
        logger.exception("URT screen-preview 失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/precompute/run")
async def run_precompute(
    date: Optional[str] = Query(None, description="交易日 YYYY-MM-DD，空则取行情最新日"),
    config_id: Optional[int] = Query(None, description="参数版本；空则对所有预计算启用版本"),
    limit: Optional[int] = Query(None, ge=1, description="候选股上限（调试用）"),
    market: str = Query("CN", description="CN=A股 / HK=港股"),
):
    mkt = (market or "CN").strip().upper()
    if mkt not in ("CN", "HK"):
        raise HTTPException(status_code=400, detail="market 须为 CN 或 HK")
    trade_date = (date or "").strip()[:10] or None

    def _job():
        from backend_core.strategies.urt.scheduled_precompute import (
            run_urt_precompute_ashare,
            run_urt_precompute_for_config,
            run_urt_precompute_hk,
        )

        if config_id is not None:
            run_urt_precompute_for_config(
                int(config_id),
                trade_date=trade_date,
                limit=limit,
                market=mkt,
            )
        elif mkt == "HK":
            run_urt_precompute_hk(trade_date=trade_date, limit=limit)
        else:
            run_urt_precompute_ashare(trade_date=trade_date, limit=limit)

    threading.Thread(target=_job, daemon=True, name="urt-precompute-manual").start()
    return {
        "success": True,
        "message": "预计算任务已启动",
        "date": trade_date,
        "config_id": config_id,
        "market": mkt,
        "limit": limit,
    }


@router.post("/backtests")
async def create_backtest(body: BacktestCreateBody, db: Session = Depends(get_db)):
    try:
        from backend_core.strategies.urt import backtest_storage, backtest_worker

        config = _build_backtest_config(db, body)
        task_id = backtest_storage.create_task(config, name=body.task_name)
        backtest_worker.start_backtest_task(task_id)
        write_urt_audit(
            db,
            "urt_backtest_create",
            {
                "task_id": task_id,
                "task_name": body.task_name,
                "stock_pool_mode": body.stock_pool_mode or "all",
                "stock_code": body.stock_code,
                "start_date": body.start_date,
                "end_date": body.end_date,
            },
        )
        return {"success": True, "task_id": task_id, "data": backtest_storage.get_task(task_id)}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("创建 URT 回测失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backtests")
async def list_backtests(
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None),
):
    from backend_core.strategies.urt import backtest_storage

    return {"success": True, "data": backtest_storage.list_tasks(limit=limit, status=status)}


@router.get("/backtests/{task_id}")
async def get_backtest(task_id: str, db: Session = Depends(get_db)):
    from backend_core.strategies.urt import backtest_storage

    row = backtest_storage.get_task(task_id)
    if not row:
        raise HTTPException(status_code=404, detail="任务不存在")
    # 旧任务可能无交易逻辑/风控快照，按当前策略参数补齐供详情展示
    cfg = row.get("config") if isinstance(row.get("config"), dict) else {}
    summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
    if not cfg.get("trade_logic") or not cfg.get("risk_params"):
        try:
            patched = _attach_urt_trade_meta(db, dict(cfg))
            cfg = {**cfg, "trade_logic": patched.get("trade_logic"), "risk_params": patched.get("risk_params")}
            row = {**row, "config": cfg}
        except Exception:
            logger.exception("URT 回测详情补齐交易逻辑失败 task=%s", task_id)
    if summary and (not summary.get("trade_logic") or not summary.get("risk_params")):
        row = {
            **row,
            "summary": {
                **summary,
                "trade_logic": summary.get("trade_logic") or cfg.get("trade_logic"),
                "risk_params": summary.get("risk_params") or cfg.get("risk_params"),
            },
        }
    return {"success": True, "data": row}


@router.get("/backtests/{task_id}/logs")
async def get_backtest_logs(task_id: str):
    from backend_core.strategies.urt import backtest_storage

    if not backtest_storage.get_task(task_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"success": True, "data": {"logs": backtest_storage.get_task_logs(task_id)}}


@router.post("/backtests/{task_id}/cancel")
async def cancel_backtest(task_id: str):
    from backend_core.strategies.urt import backtest_storage, backtest_worker

    backtest_worker.request_cancel(task_id)
    ok = backtest_storage.cancel_task(task_id)
    return {"success": ok}


@router.post("/backtests/{task_id}/rerun")
async def rerun_backtest(task_id: str):
    from backend_core.strategies.urt import backtest_storage, backtest_worker

    row = backtest_storage.get_task(task_id)
    if not row:
        raise HTTPException(status_code=404, detail="任务不存在")
    if row.get("status") in ("pending", "running"):
        raise HTTPException(status_code=400, detail="任务仍在运行中")
    if not backtest_storage.reset_task_for_rerun(task_id):
        raise HTTPException(status_code=400, detail="无法重新执行")
    backtest_worker.start_backtest_task(task_id)
    return {"success": True, "data": backtest_storage.get_task(task_id)}


@router.post("/backtests/{task_id}/delete")
async def delete_backtest(task_id: str):
    from backend_core.strategies.urt import backtest_storage

    return {"success": backtest_storage.delete_task(task_id)}


@router.post("/backtests/batch-delete")
async def batch_delete_backtests(body: BatchDeleteBody):
    from backend_core.strategies.urt import backtest_storage

    n = backtest_storage.batch_delete_tasks(body.task_ids or [])
    return {"success": True, "deleted": n}


@router.get("/backtests/{task_id}/export-pdf")
async def export_backtest_pdf(task_id: str, db: Session = Depends(get_db)):
    """导出回测详情 PDF（服务端 xhtml2pdf 生成）。"""
    from urllib.parse import quote

    from backend_core.strategies.urt import backtest_storage
    from backend_core.strategies.urt.backtest_pdf import render_backtest_pdf

    row = backtest_storage.get_task(task_id)
    if not row:
        raise HTTPException(status_code=404, detail="任务不存在")

    cfg = row.get("config") if isinstance(row.get("config"), dict) else {}
    summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
    if not cfg.get("trade_logic") or not cfg.get("risk_params"):
        try:
            patched = _attach_urt_trade_meta(db, dict(cfg))
            cfg = {
                **cfg,
                "trade_logic": patched.get("trade_logic"),
                "risk_params": patched.get("risk_params"),
            }
            row = {**row, "config": cfg}
        except Exception:
            logger.exception("URT PDF 导出补齐交易逻辑失败 task=%s", task_id)
    if summary and (not summary.get("trade_logic") or not summary.get("risk_params")):
        row = {
            **row,
            "summary": {
                **summary,
                "trade_logic": summary.get("trade_logic") or cfg.get("trade_logic"),
                "risk_params": summary.get("risk_params") or cfg.get("risk_params"),
            },
        }

    try:
        pdf_bytes = render_backtest_pdf(row)
    except RuntimeError as e:
        msg = str(e)
        if "xhtml2pdf" in msg and "未安装" in msg:
            raise HTTPException(status_code=501, detail=msg) from e
        raise HTTPException(status_code=500, detail=msg) from e
    except Exception as e:
        logger.exception("URT 回测 PDF 导出失败 task=%s", task_id)
        raise HTTPException(status_code=500, detail=f"导出PDF失败: {e}") from e

    short = (task_id or "")[:8] or "unknown"
    ascii_filename = f"urt_backtest_{short}.pdf"
    utf8_filename = quote(f"URT回测详情_{short}.pdf")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{ascii_filename}"; '
                f"filename*=UTF-8''{utf8_filename}"
            )
        },
    )


@router.get("/backtests/{task_id}/export")
async def export_backtest(task_id: str):
    from backend_core.strategies.urt import backtest_storage

    raw = backtest_storage.get_details_csv(task_id)
    if not raw:
        raise HTTPException(status_code=404, detail="无明细可导出")
    return Response(
        content=raw,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="urt_backtest_{task_id[:8]}.csv"'},
    )


@router.get("/backtests/{task_id}/export-xlsx")
async def export_backtest_xlsx(task_id: str):
    from backend_core.strategies.urt import backtest_storage

    raw = backtest_storage.get_details_xlsx(task_id)
    if not raw:
        raise HTTPException(status_code=404, detail="无明细可导出")
    return Response(
        content=raw,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="urt_backtest_{task_id[:8]}.xlsx"'},
    )


@router.get("/reports")
async def list_reports(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    from backend_core.strategies.urt import backtest_storage

    return {"success": True, "data": {"reports": backtest_storage.list_reports(limit=limit, offset=offset)}}


@router.get("/reports/{report_id}")
async def get_report(report_id: str):
    from backend_core.strategies.urt import backtest_storage

    row = backtest_storage.get_report(report_id)
    if not row:
        raise HTTPException(status_code=404, detail="报告不存在")
    return {"success": True, "data": row}


@router.post("/reports/{report_id}/delete")
async def delete_report(report_id: str):
    from backend_core.strategies.urt import backtest_storage

    return {"success": backtest_storage.delete_task(report_id)}


@router.get("/reports/{report_id}/download")
async def download_report(report_id: str):
    from backend_core.strategies.urt import backtest_storage

    raw = backtest_storage.get_details_csv(report_id)
    if not raw:
        raise HTTPException(status_code=404, detail="无明细可下载")
    return Response(
        content=raw,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="urt_report_{report_id[:8]}.csv"'},
    )


@router.get("/reports/{report_id}/download-xlsx")
async def download_report_xlsx(report_id: str):
    from backend_core.strategies.urt import backtest_storage

    raw = backtest_storage.get_details_xlsx(report_id)
    if not raw:
        raise HTTPException(status_code=404, detail="无明细可下载")
    return Response(
        content=raw,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="urt_report_{report_id[:8]}.xlsx"'},
    )
