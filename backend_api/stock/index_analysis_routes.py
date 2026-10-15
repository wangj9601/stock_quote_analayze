# -*- coding: utf-8 -*-
"""指数分析 API：bundle + K 线（读 index_* 表，不走个股通道）。"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend_api.database import get_db
from backend_api.permissions import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["指数分析"])


@router.get("/index-analysis-bundle")
def get_index_analysis_bundle(
    code: Optional[str] = Query(None, description="指数代码，如 000001 / 000300"),
    index: Optional[str] = Query(None, description="同 code，兼容别名"),
    date: Optional[str] = Query(None, description="基准日 YYYY-MM-DD，可选"),
    use_realtime: bool = Query(
        False, description="实时分析：叠 index_realtime_quotes 当日 bar"
    ),
    db: Session = Depends(get_db),
    _perm: None = Depends(require_permission("channel.analyze.tab.index")),
):
    """指数分析统一入口：PA + 广度/贡献 + 市场环境研判。"""
    raw = (code or index or "").strip()
    if not raw:
        return JSONResponse(
            {"success": False, "message": "请提供指数代码"},
            status_code=400,
        )
    try:
        from backend_core.analysis.index_analysis_bundle import build_index_analysis_bundle

        result = build_index_analysis_bundle(
            db, code=raw, date=date, use_realtime=bool(use_realtime)
        )
        if not result.get("success"):
            status = int(result.get("http_status") or 400)
            return JSONResponse(
                {
                    "success": False,
                    "message": result.get("message") or "指数分析失败",
                },
                status_code=status,
            )
        return {"success": True, "data": result.get("data")}
    except Exception as e:
        logger.exception("index-analysis-bundle failed")
        try:
            db.rollback()
        except Exception:
            pass
        return JSONResponse(
            {"success": False, "message": f"指数综合分析失败: {e}"},
            status_code=500,
        )


@router.get("/index-levels")
def get_index_key_levels(
    code: Optional[str] = Query(None, description="指数代码，如 000001"),
    index: Optional[str] = Query(None, description="同 code"),
    max_levels: int = Query(8, ge=1, le=20),
    kde_lookback: Optional[int] = Query(None, ge=20, le=750),
    kde_from_date: Optional[str] = Query(None),
    vp_lookback: Optional[int] = Query(None, ge=5, le=750),
    vp_from_date: Optional[str] = Query(None),
    use_realtime: bool = Query(False, description="叠指数实时价"),
    date: Optional[str] = Query(None, description="基准日 YYYY-MM-DD"),
    db: Session = Depends(get_db),
    _perm: None = Depends(require_permission("channel.analyze.tab.index")),
):
    """指数 KDE/VP 关位重算（读 index_historical_quotes，禁止个股 000001 通道）。"""
    raw = (code or index or "").strip()
    if not raw:
        return JSONResponse(
            {"success": False, "message": "请提供指数代码"},
            status_code=400,
        )
    try:
        from backend_core.analysis.index_analysis_bundle import compute_index_key_levels

        result = compute_index_key_levels(
            db,
            code=raw,
            max_levels=max_levels,
            kde_lookback=kde_lookback,
            kde_from_date=kde_from_date,
            vp_lookback=vp_lookback,
            vp_from_date=vp_from_date,
            use_realtime=bool(use_realtime),
            asof=date,
        )
        status = int(result.get("http_status") or (200 if result.get("success") else 400))
        body = {
            "success": bool(result.get("success")),
            "message": result.get("message") or "",
            "data": result.get("data") or {},
        }
        if status != 200:
            return JSONResponse(body, status_code=status)
        return body
    except Exception as e:
        logger.exception("index-levels failed")
        try:
            db.rollback()
        except Exception:
            pass
        return JSONResponse(
            {"success": False, "message": f"指数关位计算失败: {e}"},
            status_code=500,
        )
