# -*- coding: utf-8 -*-
"""板块资金流向 API：读库日序列 + 手动触发采集。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend_api.database import get_db
from backend_api.utils.board_code_source import DEFAULT_BOARD_CODE_SOURCE
from backend_core.data_collectors.akshare.board_fund_flow_daily import (
    collect_board_fund_flow_daily,
)

router = APIRouter(prefix="/api/board_fund_flow", tags=["board_fund_flow"])


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value in (None, "", "-"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


@router.get("/daily")
async def get_board_fund_flow_daily(
    board_code: str = Query(..., description="板块代码"),
    board_kind: str = Query("industry", description="industry | concept"),
    board_code_source: str = Query(
        DEFAULT_BOARD_CODE_SOURCE, description="默认 tonghuashun"
    ),
    days: int = Query(20, ge=1, le=120, description="最近 N 个交易日"),
    db: Session = Depends(get_db),
):
    """查询单板近 N 日资金流（升序）。金额单位：元。"""
    kind = (board_kind or "industry").strip().lower()
    if kind not in ("industry", "concept"):
        return JSONResponse(
            {"success": False, "message": "board_kind 应为 industry 或 concept"},
            status_code=400,
        )
    code = str(board_code or "").strip()
    if not code:
        return JSONResponse(
            {"success": False, "message": "缺少 board_code"}, status_code=400
        )
    src = str(board_code_source or DEFAULT_BOARD_CODE_SOURCE).strip() or DEFAULT_BOARD_CODE_SOURCE

    try:
        rows = db.execute(
            text(
                """
                SELECT trade_date, board_name, change_percent,
                       inflow_amount, outflow_amount, main_net_inflow,
                       main_net_inflow_pct,
                       super_large_net_inflow, large_net_inflow,
                       mid_net_inflow, small_net_inflow,
                       source, em_board_code
                FROM board_fund_flow_daily
                WHERE board_kind = :kind
                  AND board_code_source = :src
                  AND board_code = :code
                ORDER BY trade_date DESC
                LIMIT :lim
                """
            ),
            {"kind": kind, "src": src, "code": code, "lim": int(days)},
        ).mappings().all()

        series_desc: List[Dict[str, Any]] = []
        for r in rows:
            td = r["trade_date"]
            if hasattr(td, "isoformat"):
                td_s = td.isoformat()
            else:
                td_s = str(td)[:10]
            series_desc.append(
                {
                    "trade_date": td_s,
                    "board_name": r["board_name"],
                    "change_percent": _safe_float(r["change_percent"]),
                    "inflow_amount": _safe_float(r["inflow_amount"]),
                    "outflow_amount": _safe_float(r["outflow_amount"]),
                    "main_net_inflow": _safe_float(r["main_net_inflow"]),
                    "main_net_inflow_pct": _safe_float(r["main_net_inflow_pct"]),
                    "super_large_net_inflow": _safe_float(r["super_large_net_inflow"]),
                    "large_net_inflow": _safe_float(r["large_net_inflow"]),
                    "mid_net_inflow": _safe_float(r["mid_net_inflow"]),
                    "small_net_inflow": _safe_float(r["small_net_inflow"]),
                    "source": r["source"],
                    "em_board_code": r["em_board_code"],
                }
            )
        series_asc = list(reversed(series_desc))
        latest = series_asc[-1] if series_asc else None
        return {
            "success": True,
            "data": {
                "board_kind": kind,
                "board_code": code,
                "board_code_source": src,
                "days_requested": days,
                "series_source": "board_fund_flow_daily",
                "latest": latest,
                "series": series_asc,
            },
        }
    except Exception as e:
        return JSONResponse(
            {"success": False, "message": f"查询板块资金流失败: {e}"},
            status_code=500,
        )


@router.get("/today")
async def get_board_fund_flow_today(
    board_kind: Optional[str] = Query(None, description="industry | concept；空=全部"),
    board_code_source: str = Query(DEFAULT_BOARD_CODE_SOURCE),
    trade_date: Optional[str] = Query(None, description="YYYY-MM-DD，默认最新有数据日"),
    db: Session = Depends(get_db),
):
    """当日（或指定日）全表板块资金流。"""
    src = str(board_code_source or DEFAULT_BOARD_CODE_SOURCE).strip() or DEFAULT_BOARD_CODE_SOURCE
    kind = (board_kind or "").strip().lower() or None
    if kind and kind not in ("industry", "concept"):
        return JSONResponse(
            {"success": False, "message": "board_kind 应为 industry 或 concept"},
            status_code=400,
        )
    td = None
    if trade_date:
        try:
            datetime.strptime(trade_date, "%Y-%m-%d")
            td = trade_date
        except ValueError:
            return JSONResponse(
                {"success": False, "message": "trade_date 格式应为 YYYY-MM-DD"},
                status_code=400,
            )
    try:
        if not td:
            row = db.execute(
                text(
                    """
                    SELECT MAX(trade_date) FROM board_fund_flow_daily
                    WHERE board_code_source = :src
                    """
                ),
                {"src": src},
            ).scalar()
            if row is None:
                return {
                    "success": True,
                    "data": {"trade_date": None, "items": [], "count": 0},
                }
            td = row.isoformat() if hasattr(row, "isoformat") else str(row)[:10]

        params: Dict[str, Any] = {"src": src, "td": td}
        kind_sql = ""
        if kind:
            kind_sql = "AND board_kind = :kind"
            params["kind"] = kind
        rows = db.execute(
            text(
                f"""
                SELECT board_kind, board_code, board_name, trade_date,
                       change_percent, inflow_amount, outflow_amount,
                       main_net_inflow, source
                FROM board_fund_flow_daily
                WHERE board_code_source = :src
                  AND trade_date = CAST(:td AS date)
                  {kind_sql}
                ORDER BY main_net_inflow DESC NULLS LAST
                """
            ),
            params,
        ).mappings().all()
        items = []
        for r in rows:
            items.append(
                {
                    "board_kind": r["board_kind"],
                    "board_code": r["board_code"],
                    "board_name": r["board_name"],
                    "trade_date": td,
                    "change_percent": _safe_float(r["change_percent"]),
                    "inflow_amount": _safe_float(r["inflow_amount"]),
                    "outflow_amount": _safe_float(r["outflow_amount"]),
                    "main_net_inflow": _safe_float(r["main_net_inflow"]),
                    "source": r["source"],
                }
            )
        return {
            "success": True,
            "data": {"trade_date": td, "items": items, "count": len(items)},
        }
    except Exception as e:
        return JSONResponse(
            {"success": False, "message": f"查询失败: {e}"}, status_code=500
        )


@router.post("/daily/collect")
async def trigger_board_fund_flow_collect(
    background_tasks: BackgroundTasks,
    trade_date: Optional[str] = Query(None, description="交易日 YYYY-MM-DD，默认今天"),
    sync: bool = Query(False, description="true 则同步执行"),
):
    """触发板块资金流日采。"""
    if trade_date:
        try:
            datetime.strptime(trade_date, "%Y-%m-%d")
        except ValueError:
            return JSONResponse(
                {"success": False, "message": "trade_date 格式应为 YYYY-MM-DD"},
                status_code=400,
            )
    if sync:
        try:
            result = collect_board_fund_flow_daily(trade_date=trade_date)
            return {"success": True, "data": result}
        except Exception as e:
            return JSONResponse(
                {"success": False, "message": f"采集失败: {e}"}, status_code=500
            )
    background_tasks.add_task(collect_board_fund_flow_daily, trade_date)
    return {
        "success": True,
        "message": "板块资金流采集已在后台启动",
        "data": {"trade_date": trade_date or datetime.now().strftime("%Y-%m-%d")},
    }
