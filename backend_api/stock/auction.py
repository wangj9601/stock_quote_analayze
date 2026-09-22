# -*- coding: utf-8 -*-
"""A 股集合竞价：同花顺 Fuyao 采集与查询。"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.database import SessionLocal, get_db
from backend_api.services import auction_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/market/auction", tags=["market-auction"])

_collect_tasks: dict[str, dict] = {}
_collect_lock = threading.Lock()


class AuctionCollectRequest(BaseModel):
    stage: str = Field(default="final", description="live | final")
    trade_date: Optional[str] = Field(default=None, description="YYYY-MM-DD，省略为上海时区当日")
    stock_codes: Optional[List[str]] = Field(default=None, description="指定代码；省略为全量可采集股票")
    refresh_benchmark: bool = Field(default=True, description="是否同步采集短线风向标基准")


def _run_collect_task(task_id: str, payload: AuctionCollectRequest) -> None:
    db = SessionLocal()
    try:
        with _collect_lock:
            if task_id in _collect_tasks:
                _collect_tasks[task_id]["status"] = "running"
        result = auction_service.collect_auction_snapshot(
            db,
            codes=payload.stock_codes,
            stage=payload.stage,
            trade_date=payload.trade_date,
            refresh_benchmark=payload.refresh_benchmark,
        )
        with _collect_lock:
            if task_id in _collect_tasks:
                _collect_tasks[task_id].update(
                    {
                        "status": "completed" if result.get("success") else "failed",
                        "end_time": datetime.now().isoformat(),
                        "result": result,
                        "message": result.get("message"),
                    }
                )
    except Exception as exc:
        logger.exception("集合竞价采集任务失败 task_id=%s", task_id)
        with _collect_lock:
            if task_id in _collect_tasks:
                _collect_tasks[task_id].update(
                    {
                        "status": "failed",
                        "end_time": datetime.now().isoformat(),
                        "message": str(exc),
                    }
                )
    finally:
        db.close()


@router.get("/list")
async def get_auction_list(
    date: Optional[str] = Query(None, description="交易日 YYYY-MM-DD"),
    stage: str = Query("final", description="live | final"),
    keyword: Optional[str] = Query(None, description="代码/名称关键字"),
    sort_by: str = Query("auction_pct", description="排序字段"),
    sort_order: str = Query("desc", description="asc | desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """查询已落库的集合竞价列表（默认按竞价涨跌幅降序）。"""
    out = auction_service.query_auction_list(
        db,
        trade_date=date,
        auction_phase=stage,
        keyword=keyword,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    return out


@router.get("/benchmark")
async def get_auction_benchmark(
    date: Optional[str] = Query(None, description="交易日 YYYY-MM-DD"),
    live: bool = Query(False, description="为 true 时优先拉取同花顺实时基准"),
    db: Session = Depends(get_db),
):
    """短线风向标竞价基准。"""
    out = auction_service.query_auction_benchmark(db, trade_date=date, live=live)
    if not out.get("success"):
        return JSONResponse(out, status_code=502)
    return out


@router.get("/stock/{code}")
async def get_auction_stock(
    code: str,
    date: Optional[str] = Query(None, description="交易日 YYYY-MM-DD"),
    stage: str = Query("final", description="live | final"),
    live: bool = Query(False, description="为 true 时优先拉取同花顺实时快照"),
    db: Session = Depends(get_db),
):
    """单股集合竞价详情。"""
    out = auction_service.query_auction_stock(
        db,
        code,
        trade_date=date,
        auction_phase=stage,
        live=live,
    )
    if not out.get("success"):
        status = 400 if "无效" in str(out.get("message") or "") else 502
        return JSONResponse(out, status_code=status)
    return out


@router.post("/collect")
async def collect_auction(
    request: AuctionCollectRequest,
    background_tasks: BackgroundTasks,
):
    """后台采集集合竞价（全量或指定代码，每批最多 100 只）。"""
    stage = (request.stage or "final").strip().lower()
    if stage not in ("live", "final"):
        return JSONResponse(
            {"success": False, "message": "stage 应为 live 或 final"},
            status_code=400,
        )

    task_id = f"auction_collect_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{threading.get_ident()}"
    with _collect_lock:
        _collect_tasks[task_id] = {
            "status": "started",
            "start_time": datetime.now().isoformat(),
            "stage": stage,
            "trade_date": request.trade_date,
        }

    background_tasks.add_task(_run_collect_task, task_id, request)
    return {
        "success": True,
        "task_id": task_id,
        "status": "started",
        "message": "集合竞价采集任务已启动",
    }


@router.get("/collect/status/{task_id}")
async def get_auction_collect_status(task_id: str):
    with _collect_lock:
        task = _collect_tasks.get(task_id)
    if not task:
        return JSONResponse({"success": False, "message": "任务不存在"}, status_code=404)
    return {"success": True, "task_id": task_id, **task}
