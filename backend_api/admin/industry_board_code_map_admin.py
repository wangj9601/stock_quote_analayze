"""
板块代码映射管理（同花顺 ↔ 东财，行业/概念）— 管理端 API
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.auth import get_current_admin
from backend_api.database import get_db
from backend_api.utils.industry_board_code_map import (
    MATCH_MANUAL,
    deactivate_code_map,
    list_code_maps,
    rebuild_name_exact_maps,
    resolve_peer_board_code,
    upsert_code_map,
)

router = APIRouter(
    prefix="/api/admin/industry-board-code-map",
    tags=["admin_board_code_map"],
)

BoardKind = Literal["industry", "concept"]


def _normalize_kind(raw: Optional[str]) -> str:
    k = str(raw or "industry").strip().lower()
    if k not in ("industry", "concept"):
        raise HTTPException(status_code=400, detail="board_kind 须为 industry 或 concept")
    return k


class UpsertMapBody(BaseModel):
    ths_board_code: str = Field(..., min_length=1, max_length=20)
    em_board_code: str = Field(..., min_length=1, max_length=20)
    board_name: Optional[str] = Field(None, max_length=100)
    board_kind: BoardKind = "industry"
    note: Optional[str] = None
    confidence: int = Field(100, ge=0, le=100)
    is_active: bool = True


class RebuildBody(BaseModel):
    replace_auto: bool = True
    board_kind: BoardKind = "industry"


@router.get("")
def api_list_maps(
    keyword: Optional[str] = Query(None),
    active_only: bool = Query(False),
    board_kind: BoardKind = Query("industry"),
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: Any = Depends(get_current_admin),
):
    kind = _normalize_kind(board_kind)
    try:
        items = list_code_maps(
            db,
            board_kind=kind,
            active_only=active_only,
            keyword=keyword,
            limit=limit,
            offset=offset,
        )
        db.commit()
        return {"success": True, "data": items, "total": len(items), "board_kind": kind}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/resolve")
def api_resolve_peer(
    board_code: str = Query(..., min_length=1),
    board_kind: BoardKind = Query("industry"),
    db: Session = Depends(get_db),
    _: Any = Depends(get_current_admin),
):
    kind = _normalize_kind(board_kind)
    try:
        peer = resolve_peer_board_code(db, board_code, board_kind=kind)
        db.commit()
        return {
            "success": True,
            "data": {
                "board_code": board_code.strip(),
                "peer_board_code": peer,
                "board_kind": kind,
            },
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("")
def api_upsert_map(
    body: UpsertMapBody,
    db: Session = Depends(get_db),
    _: Any = Depends(get_current_admin),
):
    kind = _normalize_kind(body.board_kind)
    try:
        row = upsert_code_map(
            db,
            ths_board_code=body.ths_board_code,
            em_board_code=body.em_board_code,
            board_name=body.board_name,
            match_method=MATCH_MANUAL,
            confidence=body.confidence,
            is_active=body.is_active,
            note=body.note,
            board_kind=kind,
        )
        db.commit()
        return {"success": True, "data": row}
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/rebuild")
def api_rebuild_maps(
    body: RebuildBody = RebuildBody(),
    db: Session = Depends(get_db),
    _: Any = Depends(get_current_admin),
):
    kind = _normalize_kind(body.board_kind)
    try:
        stats = rebuild_name_exact_maps(
            db, board_kind=kind, replace_auto=body.replace_auto
        )
        db.commit()
        return {"success": True, "data": stats, "board_kind": kind}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{map_id}")
def api_deactivate_map(
    map_id: int,
    db: Session = Depends(get_db),
    _: Any = Depends(get_current_admin),
):
    try:
        ok = deactivate_code_map(db, map_id)
        if not ok:
            raise HTTPException(status_code=404, detail="映射不存在")
        db.commit()
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e
