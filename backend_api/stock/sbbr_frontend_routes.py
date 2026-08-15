# -*- coding: utf-8 -*-
"""SBBR 前台：单股信号历史（预计算查询 / 按日 asof 现算回溯 / 强制重算）。"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.database import SessionLocal, engine, get_db
from backend_api.models import SBBRTraceRecomputeTask
from backend_core.strategies.sbbr.config import SBBRConfigManager
from backend_core.strategies.sbbr.signal_storage import (
    query_traces_by_code,
    recompute_trace_for_stock,
)
from backend_core.strategies.sbbr.strategy_engine import SBBRStrategyEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stock", tags=["SBBR Signal"])

# 性能保护：与前端默认 90 日窗口对齐，硬上限 180 自然日 / 120 交易日
_MAX_CALENDAR_DAYS = 180
_MAX_TRADE_DAYS = 120

_trace_recompute_table_ready = False
_trace_recompute_table_lock = threading.Lock()


def _ensure_trace_recompute_task_table() -> None:
    global _trace_recompute_table_ready
    if _trace_recompute_table_ready:
        return
    with _trace_recompute_table_lock:
        if _trace_recompute_table_ready:
            return
        try:
            SBBRTraceRecomputeTask.__table__.create(bind=engine, checkfirst=True)
        except Exception as e:
            logger.warning("创建 sbbr_trace_recompute_tasks 表失败: %s", e)
            raise
        _trace_recompute_table_ready = True


def _normalize_code(code: str) -> str:
    s = str(code or "").strip()
    if s.isdigit() and len(s) <= 6:
        return s.zfill(6)
    return s


def _resolve_config_id(cm: SBBRConfigManager, config_id: Optional[int]) -> int:
    if config_id is not None:
        return int(config_id)
    return int(cm.get_default_config_id())


def _config_display_name(cm: SBBRConfigManager, config_id: int) -> str:
    configs = cm.list_configs(active_only=False)
    for c in configs:
        if int(c.get("id") or 0) == int(config_id):
            name = c.get("name") or f"配置{config_id}"
            return f"{name} (默认)" if c.get("is_default") else str(name)
    return f"配置{config_id}"


def _task_row_to_dict(row: SBBRTraceRecomputeTask) -> dict:
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
            db.query(SBBRTraceRecomputeTask)
            .filter(
                SBBRTraceRecomputeTask.code == code,
                SBBRTraceRecomputeTask.config_id == int(config_id),
                SBBRTraceRecomputeTask.status.in_(("pending", "running")),
            )
            .order_by(SBBRTraceRecomputeTask.created_at.desc())
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
        row = SBBRTraceRecomputeTask(
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
        logger.warning("创建 SBBR 重算任务失败 task_id=%s: %s", task_id, e)
        raise
    finally:
        db.close()


def _update_trace_recompute_task(task_id: str, **fields) -> None:
    _ensure_trace_recompute_task_table()
    db = SessionLocal()
    try:
        row = (
            db.query(SBBRTraceRecomputeTask)
            .filter(SBBRTraceRecomputeTask.task_id == task_id)
            .first()
        )
        if not row:
            return
        for key, val in fields.items():
            if hasattr(row, key):
                setattr(row, key, val)
        row.updated_at = datetime.now()
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("更新 SBBR 重算任务失败 task_id=%s: %s", task_id, e)
    finally:
        db.close()


def _get_trace_recompute_task(task_id: str) -> Optional[dict]:
    _ensure_trace_recompute_task_table()
    db = SessionLocal()
    try:
        row = (
            db.query(SBBRTraceRecomputeTask)
            .filter(SBBRTraceRecomputeTask.task_id == task_id)
            .first()
        )
        if not row:
            return None
        return _task_row_to_dict(row)
    finally:
        db.close()


class SbbrTraceRecomputeRequest(BaseModel):
    code: str = Field(..., description="股票代码")
    config_id: Optional[int] = Field(None, ge=1, description="SBBR 策略参数版本 ID")


def _run_trace_recompute_background(
    task_id: str,
    code: str,
    config_id: int,
    config: dict,
    config_display: str,
) -> None:
    db = SessionLocal()
    try:
        _update_trace_recompute_task(
            task_id, status="running", message="正在清除旧记录…", progress=0
        )

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
            message=f"已按「{config_display}」重新计算，写入 {count} 条",
        )
        logger.info(
            "SBBR 追溯异步重算完成: %s config_id=%s, 写入 %s 条", code, config_id, count
        )
    except Exception as e:
        logger.exception("SBBR 追溯异步重算失败 task_id=%s", task_id)
        _update_trace_recompute_task(
            task_id,
            status="failed",
            error=str(e),
            message=f"计算失败: {e}",
        )
    finally:
        db.close()


@router.get("/sbbr-signal-trace")
async def get_sbbr_signal_trace(
    code: str = Query(..., description="股票代码"),
    config_id: Optional[int] = Query(None),
    start_date: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    entry_only: bool = Query(False, description="仅入场信号"),
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    """读取 sbbr_signal_trace 中该股预计算信号序列（对齐 URT /urt-signal-trace）。"""
    try:
        cm = SBBRConfigManager()
        configs = cm.list_configs(active_only=True)
        resolved = _resolve_config_id(cm, config_id)
        code_n = _normalize_code(code)
        if not code_n:
            raise HTTPException(status_code=400, detail="股票代码不能为空")
        start_s = str(start_date).strip()[:10] if start_date else None
        end_s = str(end_date).strip()[:10] if end_date else None
        if start_s and end_s and start_s > end_s:
            raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")
        rows = query_traces_by_code(
            db,
            code=code_n,
            config_id=resolved,
            start_date=start_s,
            end_date=end_s,
            entry_only=entry_only,
            limit=limit,
        )
        return {
            "success": True,
            "code": code_n,
            "config_id": resolved,
            "configs": configs,
            "start_date": start_s,
            "end_date": end_s,
            "source": "trace",
            "source_label": "预计算",
            "data": rows,
            "total": len(rows),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("sbbr-signal-trace 失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sbbr-signal-trace/recompute")
async def start_sbbr_signal_trace_recompute(
    body: SbbrTraceRecomputeRequest,
    db: Session = Depends(get_db),
):
    """
    异步强制重新计算单股 SBBR 信号历史（当前 config_id）。
    返回 task_id，前端轮询 GET /sbbr-signal-trace/recompute/{task_id} 获取进度。
    """
    code = _normalize_code(body.code)
    if not code:
        raise HTTPException(status_code=400, detail="股票代码不能为空")

    cm = SBBRConfigManager()
    resolved_config_id = _resolve_config_id(cm, body.config_id)
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

    task_id = f"sbbr_trace_recompute_{uuid.uuid4().hex[:12]}"
    _create_trace_recompute_task(
        task_id,
        {
            "task_id": task_id,
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


@router.get("/sbbr-signal-trace/recompute/{task_id}")
async def get_sbbr_signal_trace_recompute_status(task_id: str):
    """查询 SBBR 信号历史强制重算任务进度。"""
    task = _get_trace_recompute_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return JSONResponse({"success": True, "data": task})


@router.get("/sbbr-signal-history")
async def get_sbbr_signal_history(
    code: str = Query(..., description="股票代码"),
    start_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    config_id: Optional[int] = Query(None),
    entry_only: bool = Query(False, description="仅返回入场信号日"),
    require_bottom: bool = Query(False, description="仅返回筑底命中日"),
    require_size: bool = Query(False, description="仅返回做小通过日"),
    db: Session = Depends(get_db),
):
    """
    单股历史信号按日 asof 现算回溯。

    仅使用 ≤ 各交易日的 K 线；日期跨度上限 180 自然日、最多 120 个交易日。
    """
    try:
        cm = SBBRConfigManager()
        configs = cm.list_configs(active_only=True)
        resolved = _resolve_config_id(cm, config_id)
        cfg = cm.get_config(resolved)
        code_n = _normalize_code(code)
        if not code_n:
            raise HTTPException(status_code=400, detail="股票代码不能为空")
        start_s = str(start_date).strip()[:10]
        end_s = str(end_date).strip()[:10]
        try:
            engine = SBBRStrategyEngine(db_session=db, config=cfg)
            result = engine.evaluate_history(
                code_n,
                start_date=start_s,
                end_date=end_s,
                config=cfg,
                entry_only=entry_only,
                require_bottom=require_bottom,
                require_size=require_size,
                max_calendar_days=_MAX_CALENDAR_DAYS,
                max_trade_days=_MAX_TRADE_DAYS,
            )
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        return {
            "success": True,
            "code": result.get("code") or code_n,
            "config_id": resolved,
            "configs": configs,
            "start_date": result.get("start_date") or start_s,
            "end_date": result.get("end_date") or end_s,
            "end_date_effective": result.get("end_date_effective"),
            "trade_days": result.get("trade_days"),
            "calendar_span_days": result.get("calendar_span_days"),
            "max_calendar_days": _MAX_CALENDAR_DAYS,
            "max_trade_days": _MAX_TRADE_DAYS,
            "source": "live",
            "source_label": "实时回溯",
            "data": result.get("data") or [],
            "total": int(result.get("total") or 0),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("sbbr-signal-history 失败")
        raise HTTPException(status_code=500, detail=str(e))
