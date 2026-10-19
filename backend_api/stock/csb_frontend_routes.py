# -*- coding: utf-8 -*-
"""CSB 前台：单股信号历史（优先预计算，缺口补算 / 强制重算）。"""

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
from backend_core.strategies.csb.frontend_interface import CSBFrontendInterface
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


def _lookup_stock_name(db: Session, code: str) -> str:
    """按代码取证券简称；没有记录时返回空串。"""
    from backend_api.models import StockBasicInfo, StockBasicInfoHK

    code_n = _normalize_code(code)
    if not code_n:
        return ""
    row = db.query(StockBasicInfo.name).filter(StockBasicInfo.code == code_n).first()
    if row and row[0]:
        return str(row[0]).strip()
    row = db.query(StockBasicInfoHK.name).filter(StockBasicInfoHK.code == code_n).first()
    if row and row[0]:
        return str(row[0]).strip()
    return ""


def _resolve_config_id(db: Session, cm: CSBConfigManager, config_id: Optional[int]):
    """返回 (实际版本 ID, 提示)。请求的版本不存在时改用默认版本，避免整页失败。"""
    warning = None
    if config_id is not None:
        row = cm.get_config_row(db, int(config_id))
        if row:
            return int(config_id), None
        warning = f"参数版本不存在: {config_id}，已改用默认版本"
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
    return int(row.id), warning


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
    start_d = None
    end_d = None
    if start_date:
        start_d = datetime.strptime(str(start_date)[:10], "%Y-%m-%d").date()
    if end_date:
        end_d = datetime.strptime(str(end_date)[:10], "%Y-%m-%d").date()
    scoped = start_d is not None or end_d is not None

    q = db.query(HistoricalQuotes.date).filter(HistoricalQuotes.code == code_n)
    if start_d is not None:
        q = q.filter(cast(HistoricalQuotes.date, String) >= start_d.isoformat())
    if end_d is not None:
        q = q.filter(cast(HistoricalQuotes.date, String) <= end_d.isoformat())
    dates = sorted(str(r[0])[:10] for r in q.distinct().order_by(HistoricalQuotes.date).all() if r[0])

    del_q = db.query(CSBSignalTrace).filter(
        CSBSignalTrace.code == code_n,
        CSBSignalTrace.config_id == int(config_id),
    )
    if scoped:
        if start_d is not None:
            del_q = del_q.filter(CSBSignalTrace.trade_date >= start_d)
        if end_d is not None:
            del_q = del_q.filter(CSBSignalTrace.trade_date <= end_d)
    del_q.delete(synchronize_session=False)
    db.commit()

    if not dates:
        return 0

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
        span = ""
        if start_date or end_date:
            span = f"{str(start_date or '')[:10] or '…'}～{str(end_date or '')[:10] or '…'}"
        done = f"已按「{config_display}」重新计算"
        if span:
            done += f" {span}"
        done += f"，写入 {count} 条"
        _update_recompute_task(
            task_id,
            status="completed",
            progress=100,
            saved_count=count,
            current=count,
            total=count,
            message=done,
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
    fill_missing: bool = Query(True, description="区间内无预计算的交易日按 asof 补算并落库"),
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    """单股历史追溯：优先读预计算；fill_missing 时对缺口交易日补算。"""
    try:
        cm = CSBConfigManager()
        cm.ensure_default_row(db)
        resolved, config_warning = _resolve_config_id(db, cm, config_id)
        code_n = _normalize_code(code)
        if not code_n:
            raise HTTPException(status_code=400, detail="股票代码不能为空")
        start_s = str(start).strip()[:10] if start else None
        end_s = str(end).strip()[:10] if end else None
        if start_s and end_s and start_s > end_s:
            raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")
        configs = cm.list_configs(db, active_only=True)
        stock_name = _lookup_stock_name(db, code_n)
        if fill_missing:
            if not start_s or not end_s:
                raise HTTPException(status_code=400, detail="补算缺口需要填写开始与结束日期")
            cfg = cm.get_config(resolved, db=db)
            try:
                filled = CSBFrontendInterface.backfill_signal_history(
                    db,
                    code=code_n,
                    config=cfg,
                    config_id=resolved,
                    start_date=start_s,
                    end_date=end_s,
                    entry_only=entry_only,
                    limit=limit,
                )
            except ValueError as ve:
                raise HTTPException(status_code=400, detail=str(ve))
            return {
                "success": True,
                "code": filled.get("code") or code_n,
                "name": stock_name,
                "config_id": resolved,
                "config_warning": config_warning,
                "configs": configs,
                "start_date": filled.get("start_date") or start_s,
                "end_date": filled.get("end_date") or end_s,
                "trade_days": filled.get("trade_days"),
                "cached_days": filled.get("cached_days"),
                "recomputed_days": filled.get("recomputed_days"),
                "source": filled.get("source") or "trace",
                "source_label": filled.get("source_label") or "预计算",
                "data": filled.get("data") or [],
                "total": int(filled.get("total") or 0),
            }
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
        return {
            "success": True,
            "code": code_n,
            "name": stock_name,
            "config_id": resolved,
            "config_warning": config_warning,
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
    resolved_config_id, config_warning = _resolve_config_id(db, cm, body.config_id)
    config = cm.get_config(resolved_config_id, db=db)
    config_display = _config_display_name(cm, db, resolved_config_id)
    start_s = str(body.start_date).strip()[:10] if body.start_date else None
    end_s = str(body.end_date).strip()[:10] if body.end_date else None

    existing = _find_running_recompute(code, resolved_config_id)
    if existing:
        return JSONResponse(
            {
                "success": True,
                "data": {
                    "task_id": existing,
                    "already_running": True,
                    "config_id": resolved_config_id,
                },
                "message": config_warning or "该股票当前策略版本正在重新计算，请稍候",
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
            "message": config_warning,
        }
    )


@router.get("/csb/recompute/{task_id}")
async def get_csb_recompute_status(task_id: str):
    """查询 CSB 信号历史强制重算任务进度。"""
    task = _get_recompute_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return JSONResponse({"success": True, "data": task})
