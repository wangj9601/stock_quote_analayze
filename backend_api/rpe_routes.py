"""RPE 用户端：交易观察 / 正式交易 / 配置 / 信号追溯 / 强制重算。"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.auth import get_current_user
from backend_api.database import SessionLocal, engine, get_db
from backend_api.models import (
    RPEFormalTrade,
    RPESignalTrace,
    RPETraceRecomputeTask,
    RPETradeObserveHistory,
    RPETradeObserveStock,
    StockRealtimeQuote,
    User,
)
from backend_core.strategies.rpe.config import RPEConfigManager
from backend_core.strategies.rpe.signal_storage import recompute_trace_for_stock
from backend_core.strategies.rpe.strategy_engine import RPEStrategyEngine

logger = logging.getLogger(__name__)

stock_router = APIRouter(prefix="/api/stock", tags=["rpe-stock"])
frontend_router = APIRouter(prefix="/api/frontend/rpe", tags=["rpe-frontend"])

_trace_recompute_table_ready = False
_trace_recompute_table_lock = threading.Lock()
_observe_schema_ready = False
_observe_schema_lock = threading.Lock()


def _norm_code(code: str) -> str:
    s = str(code or "").strip()
    if s.isdigit() and len(s) <= 6:
        return s.zfill(6)
    return s


def _ensure_rpe_trade_observe_schema() -> None:
    """确保观察池相关表存在（生产漏跑迁移时给出可预期错误，避免请求挂死）。"""
    global _observe_schema_ready
    if _observe_schema_ready:
        return
    with _observe_schema_lock:
        if _observe_schema_ready:
            return
        try:
            RPETradeObserveStock.__table__.create(bind=engine, checkfirst=True)
            RPETradeObserveHistory.__table__.create(bind=engine, checkfirst=True)
            RPEFormalTrade.__table__.create(bind=engine, checkfirst=True)
        except Exception as e:
            logger.error("创建 RPE 观察/交易表失败: %s", e, exc_info=True)
            raise HTTPException(
                status_code=503,
                detail=f"RPE 观察表未就绪，请执行 migrations/add_rpe_tables.py: {e}",
            )
        _observe_schema_ready = True


def _ensure_trace_recompute_task_table() -> None:
    global _trace_recompute_table_ready
    if _trace_recompute_table_ready:
        return
    with _trace_recompute_table_lock:
        if _trace_recompute_table_ready:
            return
        try:
            RPETraceRecomputeTask.__table__.create(bind=engine, checkfirst=True)
        except Exception as e:
            logger.warning("创建 rpe_trace_recompute_tasks 表失败: %s", e)
            raise
        _trace_recompute_table_ready = True


def _task_row_to_dict(row: RPETraceRecomputeTask) -> dict:
    return {
        "task_id": row.task_id,
        "status": row.status,
        "progress": row.progress,
        "message": row.message,
        "code": row.code,
        "config_id": row.config_id,
        "config_name": row.config_name,
        "current": row.current,
        "total": row.total,
        "saved_count": row.saved_count,
        "error": row.error,
        "created_at": row.created_at.isoformat(timespec="seconds") if row.created_at else None,
    }


def _find_running_trace_recompute(code: str, config_id: int) -> Optional[str]:
    _ensure_trace_recompute_task_table()
    db = SessionLocal()
    try:
        row = (
            db.query(RPETraceRecomputeTask)
            .filter(
                RPETraceRecomputeTask.code == code,
                RPETraceRecomputeTask.config_id == int(config_id),
                RPETraceRecomputeTask.status.in_(("pending", "running")),
            )
            .order_by(RPETraceRecomputeTask.created_at.desc())
            .first()
        )
        return row.task_id if row else None
    finally:
        db.close()


def _create_trace_recompute_task(task_id: str, fields: dict) -> None:
    _ensure_trace_recompute_task_table()
    db = SessionLocal()
    now = datetime.now()
    try:
        row = RPETraceRecomputeTask(
            task_id=task_id,
            status=fields.get("status", "pending"),
            progress=int(fields.get("progress") or 0),
            message=fields.get("message"),
            code=fields.get("code"),
            config_id=int(fields.get("config_id") or 0),
            config_name=fields.get("config_name"),
            current=int(fields.get("current") or 0),
            total=int(fields.get("total") or 0),
            saved_count=fields.get("saved_count"),
            error=fields.get("error"),
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("创建 RPE 重算任务失败 task_id=%s: %s", task_id, e)
        raise
    finally:
        db.close()


def _update_trace_recompute_task(task_id: str, **fields) -> None:
    _ensure_trace_recompute_task_table()
    db = SessionLocal()
    try:
        row = db.query(RPETraceRecomputeTask).filter(RPETraceRecomputeTask.task_id == task_id).first()
        if not row:
            return
        for key, val in fields.items():
            if hasattr(row, key):
                setattr(row, key, val)
        row.updated_at = datetime.now()
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("更新 RPE 重算任务失败 task_id=%s: %s", task_id, e)
    finally:
        db.close()


def _get_trace_recompute_task(task_id: str) -> Optional[dict]:
    _ensure_trace_recompute_task_table()
    db = SessionLocal()
    try:
        row = db.query(RPETraceRecomputeTask).filter(RPETraceRecomputeTask.task_id == task_id).first()
        if not row:
            return None
        return _task_row_to_dict(row)
    finally:
        db.close()


def _config_display_name(cm: RPEConfigManager, config_id: int) -> str:
    for c in cm.list_configs(active_only=False):
        if int(c.get("id") or 0) == int(config_id):
            name = c.get("name") or f"配置{config_id}"
            return f"{name} (默认)" if c.get("is_default") else str(name)
    return f"配置{config_id}"


def _run_trace_recompute_background(
    task_id: str,
    code: str,
    config_id: int,
    config: dict,
    config_display: str,
) -> None:
    db = SessionLocal()
    try:
        _update_trace_recompute_task(task_id, status="running", message="正在清除旧记录…", progress=0)

        def progress_cb(current: int, total: int, msg: str) -> None:
            pct = int(round(current * 100 / total)) if total else 0
            _update_trace_recompute_task(
                task_id,
                progress=min(99, pct),
                message=msg,
                current=current,
                total=total,
            )

        count = recompute_trace_for_stock(
            db,
            code=code,
            config_id=config_id,
            config=config,
            progress_cb=progress_cb,
        )
        _update_trace_recompute_task(
            task_id,
            status="completed",
            progress=100,
            saved_count=count,
            current=count,
            total=count,
            message=f"已按「{config_display}」全量重算，写入 {count} 条",
        )
        logger.info("RPE 追溯异步重算完成: %s config_id=%s, 写入 %s 条", code, config_id, count)
    except Exception as e:
        logger.exception("RPE 追溯异步重算失败 task_id=%s", task_id)
        _update_trace_recompute_task(
            task_id,
            status="failed",
            error=str(e),
            message=f"计算失败: {e}",
        )
    finally:
        db.close()


class ObserveAddReq(BaseModel):
    code: str
    name: Optional[str] = None
    market: str = "CN"
    signal_date: Optional[str] = None
    signal_snapshot: Optional[Dict[str, Any]] = None


class RpeTraceRecomputeRequest(BaseModel):
    code: str = Field(..., description="股票代码")
    config_id: Optional[int] = Field(None, ge=1, description="RPE 策略参数版本 ID")


class FormalFromObserveReq(BaseModel):
    entry_price: float
    notes: Optional[str] = None


class FormalPatchReq(BaseModel):
    exit_price: Optional[float] = None
    status: Optional[str] = None
    exit_reason: Optional[str] = None
    notes: Optional[str] = None
    structure_support: Optional[float] = None
    structure_resistance: Optional[float] = None


@frontend_router.get("/strategy-configs")
def list_frontend_configs():
    return {"items": RPEConfigManager().list_configs(active_only=True)}


@stock_router.get("/rpe-trade-observe/list")
def list_trade_observe(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_rpe_trade_observe_schema()
    rows = (
        db.query(RPETradeObserveStock)
        .filter(RPETradeObserveStock.user_id == current_user.id)
        .order_by(RPETradeObserveStock.created_at.desc())
        .all()
    )
    items = []
    for r in rows:
        snap = r.signal_snapshot_json or {}
        support = snap.get("nearest_support")
        # 盘中二次确认：现价是否仍在支撑上方
        above_support = None
        try:
            rq = (
                db.query(StockRealtimeQuote)
                .filter(StockRealtimeQuote.code == r.code)
                .order_by(StockRealtimeQuote.trade_date.desc())
                .first()
            )
            px = getattr(rq, "current_price", None) or getattr(rq, "price", None) or getattr(rq, "close", None)
            if px is not None and support is not None:
                above_support = float(px) >= float(support)
        except Exception:
            above_support = None
        items.append(
            {
                "id": r.id,
                "market": r.market,
                "code": r.code,
                "name": r.name,
                "signal_date": r.signal_date.isoformat() if r.signal_date else None,
                "signal_snapshot": snap,
                # 最初信号关键字段（便于列表直接展示；完整快照仍在 signal_snapshot）
                "sector_id": snap.get("sector_id"),
                "sector_name": snap.get("sector_name"),
                "z_score": snap.get("z_score"),
                "signal_type": snap.get("signal_type"),
                "entry_signal": snap.get("entry_signal"),
                "close": snap.get("close"),
                "nearest_support": support,
                "nearest_resistance": snap.get("nearest_resistance"),
                "structure_valid": snap.get("structure_valid"),
                "liquidity_ok": snap.get("liquidity_ok"),
                "ratio": snap.get("ratio"),
                "sector_slope": snap.get("sector_slope"),
                "above_support": above_support,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
        )
    return {"items": items}


@stock_router.post("/rpe-trade-observe/add")
def add_trade_observe(
    body: ObserveAddReq,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_rpe_trade_observe_schema()
    code = _norm_code(body.code)
    try:
        existing = (
            db.query(RPETradeObserveStock)
            .filter(
                RPETradeObserveStock.user_id == current_user.id,
                RPETradeObserveStock.market == (body.market or "CN"),
                RPETradeObserveStock.code == code,
            )
            .first()
        )
        if existing:
            return {"id": existing.id, "ok": True, "duplicated": True}
        sd = None
        if body.signal_date:
            try:
                sd = datetime.strptime(body.signal_date[:10], "%Y-%m-%d").date()
            except ValueError:
                sd = None
        row = RPETradeObserveStock(
            user_id=current_user.id,
            market=body.market or "CN",
            code=code,
            name=body.name,
            signal_snapshot_json=body.signal_snapshot,
            signal_date=sd,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"id": row.id, "ok": True}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("RPE 加入观察失败 code=%s: %s", code, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"加入观察失败: {e}")


@stock_router.delete("/rpe-trade-observe/{item_id}")
def delete_trade_observe(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_rpe_trade_observe_schema()
    row = (
        db.query(RPETradeObserveStock)
        .filter(RPETradeObserveStock.id == item_id, RPETradeObserveStock.user_id == current_user.id)
        .first()
    )
    if not row:
        raise HTTPException(404, "not found")
    db.add(
        RPETradeObserveHistory(
            user_id=current_user.id,
            market=row.market,
            code=row.code,
            name=row.name,
            signal_snapshot_json=row.signal_snapshot_json,
            signal_date=row.signal_date,
            source_observe_id=row.id,
            removed_at=datetime.now(),
        )
    )
    db.delete(row)
    db.commit()
    return {"ok": True}


@stock_router.get("/rpe-formal-trade/list")
def list_formal_trades(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_rpe_trade_observe_schema()
    q = db.query(RPEFormalTrade).filter(RPEFormalTrade.user_id == current_user.id)
    if status:
        q = q.filter(RPEFormalTrade.status == status)
    rows = q.order_by(RPEFormalTrade.created_at.desc()).all()
    engine = RPEStrategyEngine()
    items = []
    for r in rows:
        item = {
            "id": r.id,
            "market": r.market,
            "code": r.code,
            "name": r.name,
            "entry_price": r.entry_price,
            "exit_price": r.exit_price,
            "status": r.status,
            "structure_support": r.structure_support,
            "structure_resistance": r.structure_resistance,
            "exit_reason": r.exit_reason,
            "pnl_amount": r.pnl_amount,
            "pnl_percent": r.pnl_percent,
            "signal_date": r.signal_date.isoformat() if r.signal_date else None,
            "last_eval": r.last_eval_json,
            "notes": r.notes,
            "entry_at": r.entry_at.isoformat() if r.entry_at else None,
            "exit_at": r.exit_at.isoformat() if r.exit_at else None,
        }
        if r.status == "open":
            try:
                item["live_eval"] = engine.evaluate_position(
                    r.code, structure_support=r.structure_support
                )
            except Exception:
                item["live_eval"] = None
        items.append(item)
    return {"items": items}


@stock_router.post("/rpe-formal-trade/from-observe/{observe_id}")
def formal_from_observe(
    observe_id: int,
    body: FormalFromObserveReq,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_rpe_trade_observe_schema()
    obs = (
        db.query(RPETradeObserveStock)
        .filter(RPETradeObserveStock.id == observe_id, RPETradeObserveStock.user_id == current_user.id)
        .first()
    )
    if not obs:
        raise HTTPException(404, "observe not found")
    snap = obs.signal_snapshot_json or {}
    row = RPEFormalTrade(
        user_id=current_user.id,
        market=obs.market,
        code=obs.code,
        name=obs.name,
        source_observe_id=obs.id,
        entry_price=float(body.entry_price),
        status="open",
        signal_date=obs.signal_date,
        signal_snapshot_json=snap,
        notes=body.notes,
        structure_support=snap.get("nearest_support"),
        structure_resistance=snap.get("nearest_resistance"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "ok": True}


@stock_router.patch("/rpe-formal-trade/{trade_id}")
def patch_formal_trade(
    trade_id: int,
    body: FormalPatchReq,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        db.query(RPEFormalTrade)
        .filter(RPEFormalTrade.id == trade_id, RPEFormalTrade.user_id == current_user.id)
        .first()
    )
    if not row:
        raise HTTPException(404, "not found")

    # 禁止把固定百分比止损当作唯一离场理由
    if body.exit_reason and str(body.exit_reason).lower() in (
        "fixed_pct",
        "percent_stop",
        "pct_stop",
        "fixed_stop",
    ):
        raise HTTPException(400, "RPE 禁止使用固定百分比止损作为离场理由，请使用 structure_break")

    if body.notes is not None:
        row.notes = body.notes
    if body.structure_support is not None:
        row.structure_support = body.structure_support
    if body.structure_resistance is not None:
        row.structure_resistance = body.structure_resistance
    if body.exit_reason is not None:
        row.exit_reason = body.exit_reason
    if body.exit_price is not None:
        row.exit_price = float(body.exit_price)
        if row.entry_price:
            row.pnl_percent = (float(body.exit_price) / float(row.entry_price) - 1.0) * 100.0
    if body.status is not None:
        row.status = body.status
        if body.status == "closed":
            row.exit_at = datetime.now()
            if not row.exit_reason:
                row.exit_reason = "structure_break"
    row.updated_at = datetime.now()
    db.commit()
    return {"ok": True, "id": row.id}


@stock_router.delete("/rpe-formal-trade/{trade_id}")
def delete_formal_trade(
    trade_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        db.query(RPEFormalTrade)
        .filter(RPEFormalTrade.id == trade_id, RPEFormalTrade.user_id == current_user.id)
        .first()
    )
    if not row:
        raise HTTPException(404, "not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


@stock_router.get("/rpe-signal-trace")
def get_signal_trace(
    code: str = Query(...),
    config_id: Optional[int] = None,
    limit: int = Query(120, ge=1, le=500),
    db: Session = Depends(get_db),
):
    cm = RPEConfigManager()
    cid = int(config_id) if config_id is not None else cm.get_default_config_id()
    code_n = _norm_code(code)
    rows = (
        db.query(RPESignalTrace)
        .filter(RPESignalTrace.code == code_n, RPESignalTrace.config_id == cid)
        .order_by(RPESignalTrace.trade_date.desc())
        .limit(limit)
        .all()
    )
    return {
        "code": code_n,
        "config_id": cid,
        "items": [
            {
                "date": r.trade_date.isoformat() if r.trade_date else None,
                "z_score": r.z_score,
                "signal_type": r.signal_type,
                "entry_signal": r.entry_signal,
                "sector_id": r.sector_id,
                "sector_name": r.sector_name,
                "nearest_support": r.nearest_support,
                "nearest_resistance": r.nearest_resistance,
                "structure_valid": r.structure_valid,
                "close": r.close_price,
                "detail": r.detail,
            }
            for r in rows
        ],
    }


@stock_router.post("/rpe-signal-trace/recompute")
def start_rpe_signal_trace_recompute(
    body: RpeTraceRecomputeRequest,
    db: Session = Depends(get_db),
):
    """
    异步强制重新计算单股 RPE 全量历史信号（当前 config_id）。
    返回 task_id，前端轮询 GET /rpe-signal-trace/recompute/{task_id} 获取进度。
    """
    code = _norm_code(body.code)
    if not code:
        raise HTTPException(status_code=400, detail="股票代码不能为空")

    cm = RPEConfigManager()
    resolved_config_id = (
        int(body.config_id) if body.config_id is not None else cm.get_default_config_id()
    )
    config = cm.get_config(resolved_config_id)
    config_display = _config_display_name(cm, resolved_config_id)

    existing = _find_running_trace_recompute(code, resolved_config_id)
    if existing:
        return JSONResponse(
            {
                "success": True,
                "data": {"task_id": existing, "already_running": True},
                "message": "该股票当前策略版本正在重新计算，请稍候",
            }
        )

    task_id = f"rpe_trace_recompute_{uuid.uuid4().hex[:12]}"
    _create_trace_recompute_task(
        task_id,
        {
            "status": "pending",
            "progress": 0,
            "message": "任务已创建，等待执行…",
            "code": code,
            "config_id": resolved_config_id,
            "config_name": config_display,
            "current": 0,
            "total": 0,
            "saved_count": None,
            "error": None,
        },
    )

    thread = threading.Thread(
        target=_run_trace_recompute_background,
        args=(task_id, code, resolved_config_id, config, config_display),
        daemon=True,
    )
    thread.start()

    return JSONResponse(
        {
            "success": True,
            "data": {
                "task_id": task_id,
                "config_id": resolved_config_id,
                "config_name": config_display,
            },
        }
    )


@stock_router.get("/rpe-signal-trace/recompute/{task_id}")
def get_rpe_signal_trace_recompute_status(task_id: str):
    """查询 RPE 信号追溯强制重算任务进度。"""
    task = _get_trace_recompute_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return JSONResponse({"success": True, "data": task})
