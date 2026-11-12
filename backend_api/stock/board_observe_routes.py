# -*- coding: utf-8 -*-
"""行业交易观察池自动候选 API。"""

from __future__ import annotations

import json
from typing import Any, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from backend_api.database import get_db
from backend_api.utils.board_code_source import DEFAULT_BOARD_CODE_SOURCE

router = APIRouter(prefix="/api/board_observe", tags=["board_observe"])


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


class AdoptBody(BaseModel):
    trade_date: Optional[str] = Field(None, description="候选交易日；默认最新")
    board_codes: Optional[List[str]] = Field(
        None, description="指定代码；空则采纳当日全部 adoptable"
    )
    actions: Optional[List[str]] = Field(
        None, description="suggest_in / suggest_out；默认两者"
    )
    allow_over_cap: bool = Field(
        False, description="正式池已达软上限时仍允许批量纳入"
    )
    updated_by: Optional[str] = Field(None, description="操作人标记")


@router.get("/candidates")
async def list_observe_candidates(
    trade_date: Optional[str] = Query(None),
    action: Optional[str] = Query(None, description="suggest_in|suggest_out|in_pool|watch"),
    adoptable_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    try:
        from backend_core.board_gates.storage import resolve_asof_trade_date
        from backend_core.board_observe.storage import ensure_board_observe_tables

        ensure_board_observe_tables(db)
        asof = resolve_asof_trade_date(db, trade_date)
        # 候选表可能尚无该日：回退最新有数据日
        has = db.execute(
            text(
                """
                SELECT 1 FROM board_observe_candidate_daily
                WHERE trade_date = CAST(:td AS date) LIMIT 1
                """
            ),
            {"td": asof},
        ).fetchone()
        if not has:
            latest = db.execute(
                text(
                    """
                    SELECT MAX(trade_date) FROM board_observe_candidate_daily
                    """
                )
            ).scalar()
            if latest:
                asof = (
                    latest.strftime("%Y-%m-%d")
                    if hasattr(latest, "strftime")
                    else str(latest)[:10]
                )

        clauses = ["trade_date = CAST(:td AS date)"]
        params: dict = {"td": asof, "lim": int(limit)}
        if action:
            clauses.append("action = :act")
            params["act"] = action.strip()
        if adoptable_only:
            clauses.append("adoptable = TRUE")
        rows = db.execute(
            text(
                f"""
                SELECT board_code, board_name, trade_observe_flag, observe_lock,
                       action, score, sticky_count, adoptable, rank_in,
                       evidence_json, veto_json, trade_date
                FROM board_observe_candidate_daily
                WHERE {' AND '.join(clauses)}
                ORDER BY
                    CASE action
                        WHEN 'suggest_in' THEN 0
                        WHEN 'suggest_out' THEN 1
                        WHEN 'in_pool' THEN 2
                        ELSE 3
                    END,
                    rank_in NULLS LAST,
                    score DESC,
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
            d["veto_json"] = _json_field(d.get("veto_json"))
            td = d.get("trade_date")
            if td is not None:
                d["trade_date"] = (
                    td.strftime("%Y-%m-%d") if hasattr(td, "strftime") else str(td)[:10]
                )
            data.append(d)
        return {"success": True, "trade_date": asof, "data": data, "count": len(data)}
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)


@router.post("/compute")
async def trigger_observe_compute(
    background_tasks: BackgroundTasks,
    trade_date: Optional[str] = Query(None),
    sync: bool = Query(False),
):
    def _job():
        from backend_core.board_observe.compute_daily import (
            run_board_observe_candidates_daily,
        )

        return run_board_observe_candidates_daily(trade_date=trade_date)

    if sync:
        try:
            result = _job()
            return {"success": bool(result.get("success", True)), "data": result}
        except Exception as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=500)
    background_tasks.add_task(_job)
    return {
        "success": True,
        "message": "已后台触发观察池候选计算",
        "trade_date": trade_date,
    }


@router.post("/adopt")
async def adopt_observe_candidates(
    body: AdoptBody,
    db: Session = Depends(get_db),
):
    try:
        from backend_core.board_gates.storage import resolve_asof_trade_date
        from backend_core.board_observe.config import (
            ACTION_SUGGEST_IN,
            ACTION_SUGGEST_OUT,
            SOFT_CAP,
            SOURCE_ADOPTED_AUTO,
        )
        from backend_core.board_observe.storage import (
            apply_observe_flag,
            ensure_board_observe_tables,
        )

        ensure_board_observe_tables(db)
        asof = resolve_asof_trade_date(db, body.trade_date)
        actions = body.actions or [ACTION_SUGGEST_IN, ACTION_SUGGEST_OUT]
        actions = [str(a).strip() for a in actions if a]

        clauses = [
            "trade_date = CAST(:td AS date)",
            "adoptable = TRUE",
            "action IN :acts",
        ]
        params: dict = {"td": asof, "acts": actions}
        sql = f"""
                SELECT board_code, action, observe_lock, evidence_json
                FROM board_observe_candidate_daily
                WHERE {' AND '.join(clauses)}
                ORDER BY
                    CASE action WHEN 'suggest_out' THEN 0 ELSE 1 END,
                    rank_in NULLS LAST,
                    score DESC
                """
        stmt = text(sql).bindparams(bindparam("acts", expanding=True))
        if body.board_codes:
            codes = [str(c).strip() for c in body.board_codes if c]
            sql = sql.replace(
                "WHERE ",
                "WHERE board_code IN :codes AND ",
                1,
            )
            params["codes"] = codes
            stmt = text(sql).bindparams(
                bindparam("acts", expanding=True),
                bindparam("codes", expanding=True),
            )

        rows = db.execute(stmt, params).mappings().all()

        formal_n = db.execute(
            text(
                """
                SELECT COUNT(*) FROM industry_board_basic_info
                WHERE COALESCE(trade_observe_flag, FALSE) = TRUE
                  AND COALESCE(board_code_source, :src) = :src
                """
            ),
            {"src": DEFAULT_BOARD_CODE_SOURCE},
        ).scalar()
        formal_n = int(formal_n or 0)

        adopted = []
        skipped = []
        for r in rows:
            code = str(r["board_code"]).strip()
            act = str(r["action"])
            if act == ACTION_SUGGEST_IN:
                if formal_n >= SOFT_CAP and not body.allow_over_cap:
                    # 逐个指定代码时仍允许
                    if not body.board_codes:
                        skipped.append(
                            {
                                "board_code": code,
                                "reason": "soft_cap",
                                "action": act,
                            }
                        )
                        continue
                res = apply_observe_flag(
                    db,
                    board_code=code,
                    trade_observe_flag=True,
                    observe_source=SOURCE_ADOPTED_AUTO,
                    updated_by=body.updated_by,
                )
                if res.get("ok"):
                    formal_n += 1
                    adopted.append({**res, "action": act})
                else:
                    skipped.append({**res, "action": act})
            elif act == ACTION_SUGGEST_OUT:
                res = apply_observe_flag(
                    db,
                    board_code=code,
                    trade_observe_flag=False,
                    observe_source=SOURCE_ADOPTED_AUTO,
                    updated_by=body.updated_by,
                )
                if res.get("ok"):
                    formal_n = max(0, formal_n - 1)
                    adopted.append({**res, "action": act})
                else:
                    skipped.append({**res, "action": act})
            else:
                skipped.append(
                    {"board_code": code, "reason": "bad_action", "action": act}
                )

        db.commit()
        return {
            "success": True,
            "trade_date": asof,
            "adopted": adopted,
            "skipped": skipped,
            "formal_pool": formal_n,
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)
