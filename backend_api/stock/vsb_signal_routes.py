"""
3倍量缩量突破 — 信号历史查询（读 volume_shrink_breakout_signals）
路径：/api/stock/vsb-signals*（与 /api/screening/vsb-signals* 同源逻辑，便于网关只代理其一）
"""

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend_api.database import get_db
from backend_api.services.vsb_signals_service import (
    query_vsb_signals_by_code,
    query_vsb_signals_by_signal_date,
)


def _model_unavailable_response():
    return JSONResponse(
        status_code=503,
        content={"success": False, "message": "VSB 信号模型不可用", "data": [], "total": 0},
    )


router = APIRouter(prefix="/api/stock", tags=["VSB信号历史"])


@router.get("/vsb-signals")
async def get_vsb_signals_by_code(
    code: str = Query(..., description="股票代码"),
    start_date: Optional[str] = Query(None, description="signal_date 起（含）"),
    end_date: Optional[str] = Query(None, description="signal_date 止（含）"),
    limit: int = Query(200, ge=1, le=2000, description="最大条数"),
    db: Session = Depends(get_db),
):
    """按股票查询 VSB 信号历史（按 signal_date 降序）。"""
    try:
        payload, err = query_vsb_signals_by_code(
            db, code=code, start_date=start_date, end_date=end_date, limit=limit
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if err == "model_unavailable":
        return _model_unavailable_response()
    if err == "table_missing":
        return JSONResponse(status_code=503, content=payload)
    if err == "bad_code":
        raise HTTPException(status_code=400, detail="股票代码不能为空")
    return JSONResponse(payload)


@router.get("/vsb-signals/by-date")
async def get_vsb_signals_by_signal_date(
    signal_date: str = Query(..., description="信号日（突破日）YYYY-MM-DD"),
    limit: int = Query(500, ge=1, le=5000, description="最大条数"),
    db: Session = Depends(get_db),
):
    """按 signal_date 查询当日全市场已落库的 VSB 信号。"""
    try:
        payload, err = query_vsb_signals_by_signal_date(db, signal_date=signal_date, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if err == "model_unavailable":
        return _model_unavailable_response()
    if err == "table_missing":
        return JSONResponse(status_code=503, content=payload)
    return JSONResponse(payload)


VSB_RECALCULATE_TIMEOUT_SEC = 120
VSB_REPLAY_TIMEOUT_SEC = 600


@router.post("/vsb-signals/recalculate")
async def post_vsb_signals_recalculate(
    code: str = Query(..., description="6 位股票代码"),
    name: Optional[str] = Query(None, description="证券简称，可空"),
    search_date: Optional[str] = Query(None, description="落库 run_search_date，默认今日"),
    replay_range: bool = Query(False, description="为 true 时对 start_date～end_date 逐日切片重算并落库"),
    start_date: Optional[str] = Query(None, description="逐日回放起始 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="逐日回放结束 YYYY-MM-DD"),
    volume_ratio: Optional[float] = Query(None, ge=1.0, le=30.0),
    boom_lookback_min: Optional[int] = Query(None, ge=1, le=250),
    boom_lookback_max: Optional[int] = Query(None, ge=1, le=250),
    db: Session = Depends(get_db),
):
    """单股重算 VSB 并落库（与 POST /api/vsb/signals/recalculate 同源）。"""
    try:
        from backend_core.strategies.volume_shrink_breakout import VolumeShrinkBreakoutFrontendInterface
    except ImportError:
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "message": "3倍量缩量突破策略模块不可用",
                "saved": 0,
                "hit": False,
                "data": [],
            },
        )

    if replay_range:
        rs = (start_date or "").strip()[:10]
        re = (end_date or "").strip()[:10]
        if not rs or not re:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "replay_range=true 时必须同时提供 start_date 与 end_date（YYYY-MM-DD）",
                    "saved": 0,
                    "hit": False,
                    "data": [],
                },
            )

    loop = asyncio.get_event_loop()
    timeout_sec = VSB_REPLAY_TIMEOUT_SEC if replay_range else VSB_RECALCULATE_TIMEOUT_SEC

    def _run():
        if replay_range:
            return VolumeShrinkBreakoutFrontendInterface.recalculate_range_replay_and_persist(
                db,
                code=code,
                name=name,
                search_date=search_date,
                replay_start=rs,
                replay_end=re,
                volume_ratio=volume_ratio,
                boom_lookback_min=boom_lookback_min,
                boom_lookback_max=boom_lookback_max,
            )
        return VolumeShrinkBreakoutFrontendInterface.recalculate_single_and_persist(
            db,
            code=code,
            name=name,
            search_date=search_date,
            volume_ratio=volume_ratio,
            boom_lookback_min=boom_lookback_min,
            boom_lookback_max=boom_lookback_max,
        )

    try:
        out = await asyncio.wait_for(loop.run_in_executor(None, _run), timeout=timeout_sec)
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=504,
            content={
                "success": False,
                "message": (
                    f"VSB 逐日回放超时（>{timeout_sec}s）"
                    if replay_range
                    else f"单股重算超时（>{timeout_sec}s）"
                ),
                "saved": 0,
                "hit": False,
                "data": [],
            },
        )
    if not out.get("success"):
        return JSONResponse(status_code=400, content=out)
    return JSONResponse(content=out)
