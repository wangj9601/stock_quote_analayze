# -*- coding: utf-8 -*-
"""URT 上升趋势策略 — 管理端 API（参数版本 + 预计算 + 回测）。"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.database import get_db
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
    stock_code: Optional[str] = None
    stock_pool: Optional[List[str]] = None


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
    date: Optional[str] = Query(None),
    config_id: Optional[int] = Query(None),
    limit: Optional[int] = Query(None, ge=1),
):
    """手动触发 A 股预计算（后台线程）。"""

    def _job():
        from backend_core.strategies.urt.scheduled_precompute import (
            run_urt_precompute_ashare,
            run_urt_precompute_for_config,
        )

        if config_id is not None:
            run_urt_precompute_for_config(int(config_id), trade_date=date, limit=limit)
        else:
            run_urt_precompute_ashare(trade_date=date, limit=limit)

    threading.Thread(target=_job, daemon=True, name="urt-precompute-manual").start()
    return {"success": True, "message": "预计算任务已启动"}


@router.post("/backtests")
async def create_backtest(body: BacktestCreateBody):
    try:
        from backend_core.strategies.urt import backtest_storage, backtest_worker

        config = body.model_dump()
        task_id = backtest_storage.create_task(config, name=body.task_name)
        backtest_worker.start_backtest_task(task_id)
        return {"success": True, "task_id": task_id, "data": backtest_storage.get_task(task_id)}
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
async def get_backtest(task_id: str):
    from backend_core.strategies.urt import backtest_storage

    row = backtest_storage.get_task(task_id)
    if not row:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"success": True, "data": row}


@router.post("/backtests/{task_id}/cancel")
async def cancel_backtest(task_id: str):
    from backend_core.strategies.urt import backtest_storage, backtest_worker

    backtest_worker.request_cancel(task_id)
    ok = backtest_storage.cancel_task(task_id)
    return {"success": ok}


@router.post("/backtests/{task_id}/delete")
async def delete_backtest(task_id: str):
    from backend_core.strategies.urt import backtest_storage

    return {"success": backtest_storage.delete_task(task_id)}


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
