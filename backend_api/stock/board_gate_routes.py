# -*- coding: utf-8 -*-
"""板块入场闸门 API。"""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend_api.database import get_db
from backend_api.utils.board_code_source import DEFAULT_BOARD_CODE_SOURCE

router = APIRouter(prefix="/api/board_gate", tags=["board_gate"])


def _json_field(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return v
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return v
    return v


@router.get("/daily")
async def get_board_gate_daily(
    board_code: str = Query(..., description="板块代码"),
    board_kind: str = Query("industry", description="industry | concept"),
    board_code_source: str = Query(DEFAULT_BOARD_CODE_SOURCE),
    trade_date: Optional[str] = Query(None, description="交易日 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    kind = (board_kind or "industry").strip().lower()
    code = str(board_code or "").strip()
    src = str(board_code_source or DEFAULT_BOARD_CODE_SOURCE).strip()
    if kind not in ("industry", "concept") or not code:
        return JSONResponse(
            {"success": False, "message": "参数无效"}, status_code=400
        )
    try:
        if trade_date:
            row = db.execute(
                text(
                    """
                    SELECT * FROM board_gate_daily
                    WHERE board_kind = :kind
                      AND board_code_source = :src
                      AND board_code = :code
                      AND trade_date = CAST(:td AS date)
                    """
                ),
                {"kind": kind, "src": src, "code": code, "td": trade_date[:10]},
            ).mappings().first()
        else:
            row = db.execute(
                text(
                    """
                    SELECT * FROM board_gate_daily
                    WHERE board_kind = :kind
                      AND board_code_source = :src
                      AND board_code = :code
                    ORDER BY trade_date DESC
                    LIMIT 1
                    """
                ),
                {"kind": kind, "src": src, "code": code},
            ).mappings().first()
        if not row:
            return {"success": True, "data": None}
        d = dict(row)
        d["evidence_json"] = _json_field(d.get("evidence_json"))
        d["degraded_json"] = _json_field(d.get("degraded_json"))
        if d.get("trade_date"):
            td = d["trade_date"]
            d["trade_date"] = td.strftime("%Y-%m-%d") if hasattr(td, "strftime") else str(td)[:10]
        return {"success": True, "data": d}
    except Exception as e:
        return JSONResponse(
            {"success": False, "message": str(e)}, status_code=500
        )


@router.get("/list")
async def list_board_gates(
    trade_date: Optional[str] = Query(None),
    board_kind: Optional[str] = Query(None),
    short_state: Optional[str] = Query(None),
    midlong_state: Optional[str] = Query(None),
    observe_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    try:
        from backend_core.board_gates.storage import resolve_asof_trade_date

        asof = resolve_asof_trade_date(db, trade_date)
        clauses = ["trade_date = CAST(:td AS date)"]
        params: dict = {"td": asof, "lim": int(limit)}
        if board_kind:
            clauses.append("board_kind = :kind")
            params["kind"] = board_kind.strip().lower()
        if short_state:
            clauses.append("short_state = :ss")
            params["ss"] = short_state
        if midlong_state:
            clauses.append("midlong_state = :ms")
            params["ms"] = midlong_state
        if observe_only:
            clauses.append("trade_observe_flag = TRUE")
        rows = db.execute(
            text(
                f"""
                SELECT board_kind, board_code, board_name, trade_observe_flag,
                       short_state, midlong_state, conflict_action,
                       shadow_hard_filter_hint, v2_enabled,
                       evidence_json, degraded_json
                FROM board_gate_daily
                WHERE {' AND '.join(clauses)}
                ORDER BY
                    CASE short_state WHEN '可配' THEN 0 WHEN '观望' THEN 1 ELSE 2 END,
                    board_code
                LIMIT :lim
                """
            ),
            params,
        ).mappings().all()
        data = []
        for r in rows:
            d = dict(r)
            d["evidence_json"] = _json_field(d.get("evidence_json"))
            d["degraded_json"] = _json_field(d.get("degraded_json"))
            data.append(d)
        return {"success": True, "trade_date": asof, "data": data, "count": len(data)}
    except Exception as e:
        return JSONResponse(
            {"success": False, "message": str(e)}, status_code=500
        )


@router.post("/compute")
async def trigger_board_gate_compute(
    background_tasks: BackgroundTasks,
    trade_date: Optional[str] = Query(None),
    sync: bool = Query(False, description="true 则同步执行"),
):
    def _job():
        from backend_core.board_gates.compute_daily import run_board_gates_daily

        return run_board_gates_daily(trade_date=trade_date)

    if sync:
        try:
            result = _job()
            return {"success": True, "data": result}
        except Exception as e:
            return JSONResponse(
                {"success": False, "message": str(e)}, status_code=500
            )
    background_tasks.add_task(_job)
    return {
        "success": True,
        "message": "已后台触发板块入场闸门计算",
        "trade_date": trade_date,
    }
