# -*- coding: utf-8 -*-
"""CUPB 选股只读接口：读 cupb_signal_trace，不触发预计算。

    GET /api/stock/cupb/signals  按日或日期区间分页查询默认配置信号
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
    "MAIN": "主板",
    "SZ_SME": "中小板",
    "CYB": "创业板",
    "KCB": "科创板",
    "BJ": "北证",
}
_BOARD_ALLOW = set(_BOARD_LABELS.keys())


def _parse_board_segments(
    repeated: Optional[List[str]],
    csv: Optional[str],
) -> List[str]:
    from backend_core.strategies.cup_bottom.universe import normalize_cn_board_segments

    raw: List[str] = []
    if repeated:
        raw.extend(repeated)
    if csv and str(csv).strip():
        raw.append(str(csv).strip())
    board_segs = normalize_cn_board_segments(raw)
    return [s for s in board_segs if s in _BOARD_ALLOW]


@router.get("/signals")
def get_cupb_signals(
    trade_date: Optional[str] = Query(None, description="YYYY-MM-DD；单日。与区间二选一；都空则用最新有信号日"),
    start_date: Optional[str] = Query(None, description="历史区间起 YYYY-MM-DD（含）"),
    end_date: Optional[str] = Query(None, description="历史区间止 YYYY-MM-DD（含）"),
    status: Optional[str] = Query(
        None, description="forming / confirmed；空或 both 表示全部"
    ),
    code: Optional[str] = Query(None, description="股票代码过滤"),
    cn_board_segment: Optional[List[str]] = Query(
        None,
        description="A股板型多选：MAIN/SZ_SME/CYB/KCB/BJ；可重复传参",
    ),
    cn_board_segments: Optional[str] = Query(
        None,
        description="A股板型，逗号分隔：MAIN,SZ_SME,CYB,KCB,BJ；不传=不限",
    ),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    for label, raw in (
        ("trade_date", trade_date),
        ("start_date", start_date),
        ("end_date", end_date),
    ):
        if raw and not _DATE_RE.match(str(raw).strip()):
            return JSONResponse(
                {"success": False, "message": f"{label} 格式应为 YYYY-MM-DD"},
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
            load_stock_signal_history,
            load_traces,
            resolve_screening_trade_date,
        )

        board_segs = _parse_board_segments(cn_board_segment, cn_board_segments)

        cid = CupbConfigManager().get_default_config_id()
        ranged = bool((start_date or "").strip() or (end_date or "").strip())
        explicit_day = bool((trade_date or "").strip())
        code_s = (code or "").strip()
        # 只给代码、不给日期：查这只股票已入库的全部信号，避免只卡在最新市场日，也不去扫 historical_quotes。
        stock_all = bool(code_s) and not ranged and not explicit_day
        date_s = None
        if not stock_all and not ranged:
            date_s = resolve_screening_trade_date(
                db, trade_date=trade_date, config_id=cid
            )
        page_size = int(limit)
        if page_size not in _PAGE_SIZES:
            # 允许任意 1..500，但提示常用档
            page_size = max(1, min(500, page_size))
        payload = load_traces(
            db,
            trade_date=None if stock_all else date_s,
            start_date=None if stock_all else (start_date if ranged else None),
            end_date=None if stock_all else (end_date if ranged else None),
            config_id=cid,
            status=status_norm,
            code=code_s or None,
            cn_board_segments=board_segs or None,
            limit=page_size,
            offset=offset,
        )
        return {
            "success": True,
            "data": {
                "trade_date": payload.get("trade_date") or date_s,
                "start_date": payload.get("start_date"),
                "end_date": payload.get("end_date"),
                "mode": payload.get("mode") or ("stock" if stock_all else "range"),
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


@router.get("/signal-history")
def get_cupb_signal_history(
    code: str = Query(..., description="股票代码"),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD；空则不限制开始日"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD；空则不限制结束日"),
    db: Session = Depends(get_db),
):
    """个股杯底历史：只读默认配置下的 cupb_signal_trace。"""
    for label, raw in (("start_date", start_date), ("end_date", end_date)):
        if raw and not _DATE_RE.match(str(raw).strip()):
            return JSONResponse(
                {"success": False, "message": f"{label} 格式应为 YYYY-MM-DD"},
                status_code=400,
            )
    try:
        from backend_core.strategies.cup_bottom.config import CupbConfigManager
        from backend_core.strategies.cup_bottom.signal_storage import load_stock_signal_history

        cid = CupbConfigManager().get_default_config_id()
        payload = load_stock_signal_history(
            db,
            code=code,
            start_date=start_date,
            end_date=end_date,
            config_id=cid,
        )
        payload["source"] = "cupb_signal_trace"
        return {"success": True, "data": payload}
    except ValueError as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=400)
    except Exception as e:
        logger.exception("CUPB 个股历史查询失败")
        return JSONResponse(
            {"success": False, "message": f"查询失败: {e}"},
            status_code=500,
        )
