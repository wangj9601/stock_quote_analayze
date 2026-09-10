# -*- coding: utf-8 -*-
"""CSB 前台：单股信号历史（预计算查询 / 强制重算）。"""

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

from backend_api.database import SessionLocal, get_db
from backend_core.strategies.csb.config import CSBConfigManager
from backend_core.strategies.csb.trace_store import query_trace_by_code, upsert_trace_rows

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stock", tags=["CSB Signal"])

_recompute_tasks: Dict[str, Dict[str, Any]] = {}
_recompute_lock = threading.Lock()


def _normalize_code(code: str) -> str:
    s = str(code or "").strip()
    if s.isdigit() and len(s) <= 6:
        return s.zfill(6)
    return s


def _resolve_config_id(db: Session, cm: CSBConfigManager, config_id: Optional[int]) -> int:
    if config_id is not None:
        row = cm.get_config_row(db, int(config_id))
        if not row:
            raise HTTPException(status_code=404, detail=f"参数版本不存在: {config_id}")
        return int(config_id)
    cm.ensure_default_row(db)
    from backend_api.models import CSBStrategyConfig

    row = (
        db.query(CSBStrategyConfig)
        .filter(CSBStrategyConfig.is_default.is_(True))
        .order_by(CSBStrategyConfig.id.asc())
        .first()
    )
    if not row:
        row = (
            db.query(CSBStrategyConfig)
            .filter(CSBStrategyConfig.is_active.is_(True))
            .order_by(CSBStrategyConfig.id.asc())
            .first()
        )
    if not row:
        raise HTTPException(status_code=400, detail="无可用 CSB 参数版本")
    return int(row.id)


def _config_display_name(cm: CSBConfigManager, db: Session, config_id: int) -> str:
    configs = cm.list_configs(db, active_only=False)
    for c in configs:
        if int(c.get("id") or 0) == int(config_id):
            name = c.get("name") or f"配置{config_id}"
            return f"{name} (默认)" if c.get("is_default") else str(name)
    return f"配置{config_id}"


def _update_recompute_task(task_id: str, **fields) -> None:
    with _recompute_lock:
        task = _recompute_tasks.get(task_id)
        if not task:
            return
        task.update(fields)
        task["updated_at"] = datetime.now().isoformat(timespec="seconds")


def _get_recompute_task(task_id: str) -> Optional[Dict[str, Any]]:
    with _recompute_lock:
        task = _recompute_tasks.get(task_id)
        return dict(task) if task else None


def _find_running_recompute(code: str, config_id: int) -> Optional[str]:
    with _recompute_lock:
        for tid, task in _recompute_tasks.items():
            if (
                task.get("code") == code
                and int(task.get("config_id") or 0) == int(config_id)
                and task.get("status") in ("pending", "running")
            ):
                return tid
    return None


def _recompute_csb_trace_for_stock(
    db: Session,
    *,
    code: str,
    config_id: int,
    config: dict,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    progress_cb=None,
) -> int:
    from sqlalchemy import cast, String

    from backend_api.models import CSBSignalTrace, HistoricalQuotes
    from backend_core.strategies.csb.data_loader import CSBDataLoader
    from backend_core.strategies.csb.strategy_engine import CSBStrategyEngine

    code_n = _normalize_code(code)
    q = db.query(HistoricalQuotes.date).filter(HistoricalQuotes.code == code_n)
    if start_date:
        q = q.filter(cast(HistoricalQuotes.date, String) >= str(start_date)[:10])
    if end_date:
        q = q.filter(cast(HistoricalQuotes.date, String) <= str(end_date)[:10])
    dates = sorted(str(r[0])[:10] for r in q.distinct().order_by(HistoricalQuotes.date).all() if r[0])
    if not dates:
        return 0

    (
        db.query(CSBSignalTrace)
        .filter(CSBSignalTrace.code == code_n, CSBSignalTrace.config_id == int(config_id))
        .delete(synchronize_session=False)
    )
    db.commit()

    loader = CSBDataLoader(db)
    engine = CSBStrategyEngine(loader, config)
    rows_to_write = []
    total = len(dates)
    for i, d in enumerate(dates):
        if progress_cb:
            progress_cb(i + 1, total, f"计算 {code_n} @ {d}")
        row = engine.evaluate_code(code_n, date=d, config=config)
        if row:
            rows_to_write.append(row)
    written = upsert_trace_rows(db, config_id=int(config_id), rows=rows_to_write)
    return int(written)


def _run_recompute_background(
    task_id: str,
    code: str,
    config_id: int,
    config: dict,
    config_display: str,
    start_date: Optional[str],
    end_date: Optional[str],
) -> None:
    db = SessionLocal()
    try:
        _update_recompute_task(task_id, status="running", message="正在清除旧记录…", progress=0)

        def progress_cb(current: int, total: int, msg: str) -> None:
            pct = int(round(current * 100 / total)) if total else 0
            _update_recompute_task(
                task_id,
                progress=min(99, pct),
                message=msg,
                current=current,
                total=total,
            )

        count = _recompute_csb_trace_for_stock(
            db,
            code=code,
            config_id=config_id,
            config=config,
            start_date=start_date,
            end_date=end_date,
            progress_cb=progress_cb,
        )
        _update_recompute_task(
            task_id,
            status="completed",
            progress=100,
            saved_count=count,
            current=count,
            total=count,
            message=f"已按「{config_display}」重新计算，写入 {count} 条",
        )
        logger.info("CSB 追溯异步重算完成: %s config_id=%s, 写入 %s 条", code, config_id, count)
    except Exception as e:
        logger.exception("CSB 追溯异步重算失败 task_id=%s", task_id)
        _update_recompute_task(
            task_id,
            status="failed",
            error=str(e),
            message=f"计算失败: {e}",
        )
    finally:
        db.close()


class CsbRecomputeRequest(BaseModel):
    code: str = Field(..., description="股票代码")
    config_id: Optional[int] = Field(None, ge=1, description="CSB 策略参数版本 ID")
    start_date: Optional[str] = Field(None, description="起始日期 YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="结束日期 YYYY-MM-DD")


@router.get("/csb/signal-history")
async def get_csb_signal_history(
    code: str = Query(..., description="股票代码"),
    config_id: Optional[int] = Query(None),
    start: Optional[str] = Query(None, alias="start", description="起始日期 YYYY-MM-DD"),
    end: Optional[str] = Query(None, alias="end", description="结束日期 YYYY-MM-DD"),
    entry_only: bool = Query(False, description="仅入场信号"),
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    """读取 csb_signal_trace 中该股预计算信号序列。"""
    try:
        cm = CSBConfigManager()
        cm.ensure_default_row(db)
        resolved = _resolve_config_id(db, cm, config_id)
        code_n = _normalize_code(code)
        if not code_n:
            raise HTTPException(status_code=400, detail="股票代码不能为空")
        start_s = str(start).strip()[:10] if start else None
        end_s = str(end).strip()[:10] if end else None
        if start_s and end_s and start_s > end_s:
            raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")
        rows = query_trace_by_code(
            db,
            code=code_n,
            config_id=resolved,
            start_date=start_s,
            end_date=end_s,
            limit=limit,
        )
        if entry_only:
            rows = [r for r in rows if r.get("entry_signal")]
        configs = cm.list_configs(db, active_only=True)
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
        logger.exception("csb/signal-history 失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/csb/recompute")
async def start_csb_recompute(
    body: CsbRecomputeRequest,
    db: Session = Depends(get_db),
):
    """异步强制重新计算单股 CSB 信号历史；返回 task_id 供轮询。"""
    code = _normalize_code(body.code)
    if not code:
        raise HTTPException(status_code=400, detail="股票代码不能为空")

    cm = CSBConfigManager()
    resolved_config_id = _resolve_config_id(db, cm, body.config_id)
    config = cm.get_config(resolved_config_id, db=db)
    config_display = _config_display_name(cm, db, resolved_config_id)
    start_s = str(body.start_date).strip()[:10] if body.start_date else None
    end_s = str(body.end_date).strip()[:10] if body.end_date else None

    existing = _find_running_recompute(code, resolved_config_id)
    if existing:
        return JSONResponse(
            {
                "success": True,
                "data": {"task_id": existing, "already_running": True},
                "message": "该股票当前策略版本正在重新计算，请稍候",
            }
        )

    task_id = f"csb_trace_recompute_{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat(timespec="seconds")
    with _recompute_lock:
        _recompute_tasks[task_id] = {
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
            "created_at": now,
            "updated_at": now,
        }

    thread = threading.Thread(
        target=_run_recompute_background,
        args=(task_id, code, resolved_config_id, config, config_display, start_s, end_s),
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


@router.get("/csb/recompute/{task_id}")
async def get_csb_recompute_status(task_id: str):
    """查询 CSB 信号历史强制重算任务进度。"""
    task = _get_recompute_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return JSONResponse({"success": True, "data": task})
