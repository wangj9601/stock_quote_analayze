# -*- coding: utf-8 -*-
"""SBBR 前台：单股信号历史（预计算查询 / 按日 asof 现算回溯）。"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend_api.database import get_db
from backend_core.strategies.sbbr.config import SBBRConfigManager
from backend_core.strategies.sbbr.signal_storage import query_traces_by_code
from backend_core.strategies.sbbr.strategy_engine import SBBRStrategyEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stock", tags=["SBBR Signal"])

# 性能保护：与前端默认 90 日窗口对齐，硬上限 180 自然日 / 120 交易日
_MAX_CALENDAR_DAYS = 180
_MAX_TRADE_DAYS = 120


def _normalize_code(code: str) -> str:
    s = str(code or "").strip()
    if s.isdigit() and len(s) <= 6:
        return s.zfill(6)
    return s


def _resolve_config_id(cm: SBBRConfigManager, config_id: Optional[int]) -> int:
    if config_id is not None:
        return int(config_id)
    return int(cm.get_default_config_id())


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
