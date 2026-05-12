"""
VSB 选股同步观察股表 vsb_observe_stocks：列表、导出。
与「日终爆量 → triple_volume_observe_stocks」区分；选股 persist 命中由 signal_storage 写入本表。
"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend_api.auth import get_current_user_or_admin
from backend_api.database import get_db
from backend_api.models import User, Admin, VsbObserveStock
from backend_api.utils.cn_listed_board_filter import filter_query_by_market_and_board

router = APIRouter(prefix="/api/stock/vsb-observe-stocks", tags=["vsb-observe-stocks"])


def _display_status(r: VsbObserveStock) -> str:
    """列表「状态」：策略阶段（来自落库快照）+ 强度档，与日终观察股的待观察/复核不同。"""
    snap: Dict[str, Any] = r.screen_snapshot_json if isinstance(r.screen_snapshot_json, dict) else {}
    raw_phase = snap.get("strategy_phase")
    phase = str(raw_phase).strip() if raw_phase is not None else ""
    if phase == "three_phase_v1":
        mode = "三阶段"
    elif phase == "legacy":
        mode = "旧版"
    elif phase:
        mode = phase
    else:
        mode = ""
    lvl = (r.signal_strength_level or "").strip()
    parts = [p for p in (mode, lvl) if p]
    if parts:
        return " · ".join(parts)
    return "策略命中"


class VsbObserveListItem(BaseModel):
    id: int
    market: str
    code: str
    name: Optional[str]
    display_status: str
    signal_date: date
    boom_date: Optional[str]
    run_search_date: Optional[str]
    signal_strength: Optional[int]
    signal_strength_level: Optional[str]
    buy_signal_text: Optional[str]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class VsbObserveListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[VsbObserveListItem]


def _row_to_item(r: VsbObserveStock) -> VsbObserveListItem:
    return VsbObserveListItem(
        id=r.id,
        market=r.market or "CN",
        code=r.code,
        name=r.name,
        display_status=_display_status(r),
        signal_date=r.signal_date,
        boom_date=r.boom_date,
        run_search_date=r.run_search_date,
        signal_strength=r.signal_strength,
        signal_strength_level=r.signal_strength_level,
        buy_signal_text=r.buy_signal_text,
        created_at=r.created_at.isoformat() if r.created_at else "",
        updated_at=r.updated_at.isoformat() if r.updated_at else "",
    )


def _list_impl(
    db: Session,
    market: Optional[str],
    page: int,
    page_size: int,
    board_segment: Optional[str] = None,
) -> VsbObserveListResponse:
    q = db.query(VsbObserveStock)
    q = filter_query_by_market_and_board(
        q,
        VsbObserveStock.market,
        VsbObserveStock.code,
        market,
        board_segment,
    )
    total = q.count()
    rows = (
        q.order_by(VsbObserveStock.signal_date.desc(), VsbObserveStock.code)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return VsbObserveListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[_row_to_item(r) for r in rows],
    )


def _export_impl(
    db: Session,
    market: Optional[str],
    principal: Union[User, Admin],
    board_segment: Optional[str] = None,
):
    import pandas as pd

    q = db.query(VsbObserveStock)
    q = filter_query_by_market_and_board(
        q,
        VsbObserveStock.market,
        VsbObserveStock.code,
        market,
        board_segment,
    )
    rows = q.order_by(
        VsbObserveStock.signal_date.desc(),
        VsbObserveStock.market,
        VsbObserveStock.code,
    ).all()
    owner = str(principal.id) if isinstance(principal, User) else f"admin_{principal.id}"
    data = []
    for r in rows:
        sd = r.signal_date.strftime("%Y-%m-%d") if hasattr(r.signal_date, "strftime") else str(r.signal_date)[:10]
        data.append(
            {
                "市场": r.market or "CN",
                "代码": r.code,
                "名称": r.name or "",
                "状态": _display_status(r),
                "突破日": sd,
                "爆量日": r.boom_date or "",
                "检索日": r.run_search_date or "",
                "信号强度": r.signal_strength,
                "强度档": r.signal_strength_level or "",
                "参考买点": r.buy_signal_text or "",
                "创建时间": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
                "更新时间": r.updated_at.strftime("%Y-%m-%d %H:%M:%S") if r.updated_at else "",
            }
        )
    report_dir = "reports/csv"
    os.makedirs(report_dir, exist_ok=True)
    fn = f"vsb_observe_export_{owner}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    path = os.path.join(report_dir, fn)
    pd.DataFrame(data).to_excel(path, index=False, sheet_name="VSB选股观察股")
    return FileResponse(
        path,
        filename=fn,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/list", response_model=VsbObserveListResponse)
def list_vsb_observe_stocks(
    market: Optional[str] = Query(None, description="CN 或 HK"),
    board: Optional[str] = Query(None, description="A股代码段：CYB SZ_SME KCB MAIN"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    _principal: Union[User, Admin] = Depends(get_current_user_or_admin),
    db: Session = Depends(get_db),
):
    return _list_impl(db, market, page, page_size, board)


@router.get("/export")
def export_vsb_observe_stocks(
    market: Optional[str] = Query(None),
    board: Optional[str] = Query(None),
    principal: Union[User, Admin] = Depends(get_current_user_or_admin),
    db: Session = Depends(get_db),
):
    return _export_impl(db, market, principal, board)
