# -*- coding: utf-8 -*-
"""CUPB 选股只读接口：读 cupb_signal_trace，不触发预计算。

    GET /api/stock/cupb/signals  按日分页查询默认配置信号
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend_api.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stock/cupb", tags=["cupb"])

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PAGE_SIZES = (50, 100, 200)
_BOARD_LABELS = {
    "CYB": "创业板",
    "KCB": "科创板",
    "BJ": "北证",
}


@router.get("/signals")
def get_cupb_signals(
    trade_date: Optional[str] = Query(None, description="YYYY-MM-DD；空则用默认配置最新有信号日"),
    status: Optional[str] = Query(
        None, description="forming / confirmed；空或 both 表示全部"
    ),
    code: Optional[str] = Query(None, description="股票代码过滤"),
    cn_board_segment: Optional[List[str]] = Query(
        None,
        description="A股板型多选：CYB/KCB/BJ；可重复传参；不传=不限",
    ),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    if trade_date and not _DATE_RE.match(trade_date.strip()):
        return JSONResponse(
            {"success": False, "message": "trade_date 格式应为 YYYY-MM-DD"},
            status_code=400,
        )
    status_norm = (status or "").strip().lower()
    if status_norm in ("", "both", "all"):
        status_norm = None
    elif status_norm not in ("forming", "confirmed"):
        return JSONResponse(
            {"success": False, "message": "status 应为 forming / confirmed / both"},
            status_code=400,
        )

    try:
        from backend_core.strategies.cup_bottom.config import CupbConfigManager
        from backend_core.strategies.cup_bottom.signal_storage import (
            load_traces,
            resolve_screening_trade_date,
        )
        from backend_core.strategies.cup_bottom.universe import normalize_cn_board_segments

        board_segs = normalize_cn_board_segments(cn_board_segment)
        # 选股页仅暴露创业板/科创板/北证；其它键忽略
        board_segs = [s for s in board_segs if s in ("CYB", "KCB", "BJ")]

        cid = CupbConfigManager().get_default_config_id()
        date_s = resolve_screening_trade_date(
            db, trade_date=trade_date, config_id=cid
        )
        page_size = int(limit)
        if page_size not in _PAGE_SIZES:
            # 允许任意 1..500，但提示常用档
            page_size = max(1, min(500, page_size))
        payload = load_traces(
            db,
            trade_date=date_s,
            config_id=cid,
            status=status_norm,
            code=code,
            cn_board_segments=board_segs or None,
            limit=page_size,
            offset=offset,
        )
        return {
            "success": True,
            "data": {
                "trade_date": date_s,
                "config_id": cid,
                "status": status_norm or "both",
                "cn_board_segments": board_segs,
                "cn_board_segment_label": "、".join(
                    _BOARD_LABELS.get(s, s) for s in board_segs
                )
                or "不限板型",
                "total": payload.get("total") or 0,
                "limit": page_size,
                "offset": int(offset),
                "page_sizes": list(_PAGE_SIZES),
                "items": payload.get("items") or [],
                "source": "cupb_signal_trace",
            },
        }
    except ValueError as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=404)
    except Exception as e:
        logger.exception("CUPB 选股信号查询失败")
        return JSONResponse(
            {"success": False, "message": f"查询失败: {e}"},
            status_code=500,
        )
