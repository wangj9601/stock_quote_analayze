# -*- coding: utf-8 -*-
"""概念指数分析 API：读概念板块指数表，不走大盘指数、行业指数或个股通道。"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend_api.database import get_db
from backend_api.permissions import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["概念指数分析"])


@router.get("/concept-index-analysis-bundle")
def get_concept_index_analysis_bundle(
    board_code: Optional[str] = Query(None, description="概念板块代码"),
    date: Optional[str] = Query(None, description="基准日 YYYY-MM-DD，可选"),
    use_realtime: bool = Query(
        False,
        description="刷新成分广度；概念无实时指数行情，不改写当日 K",
    ),
    db: Session = Depends(get_db),
    _perm: None = Depends(require_permission("channel.analyze.tab.concept_index")),
):
    raw = (board_code or "").strip()
    if not raw:
        return JSONResponse(
            {"success": False, "message": "请提供概念板块代码"},
            status_code=400,
        )
    try:
        from backend_core.analysis.concept_index_analysis_bundle import (
            build_concept_index_analysis_bundle,
        )

        result = build_concept_index_analysis_bundle(
            db, board_code=raw, date=date, use_realtime=bool(use_realtime)
        )
        if not result.get("success"):
            status = int(result.get("http_status") or 400)
            return JSONResponse(
                {
                    "success": False,
                    "message": result.get("message") or "概念指数分析失败",
                },
                status_code=status,
            )
        return {"success": True, "data": result.get("data")}
    except Exception as e:
        logger.exception("concept-index-analysis-bundle failed")
        try:
            db.rollback()
        except Exception:
            pass
        return JSONResponse(
            {"success": False, "message": f"概念指数分析失败: {e}"},
            status_code=500,
        )
