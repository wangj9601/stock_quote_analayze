"""
3倍量观察股：列表、导出、管理员手动触发扫描/复核。
提供两套前缀：/api/stock/...（用户站、选股页）与 /api/admin/triple-volume-observe/...（管理端与统一 /api/admin 反代）。
"""

from datetime import date, datetime
from typing import List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend_api.auth import get_current_user_or_admin, get_current_admin
from backend_api.database import get_db
from backend_api.models import TripleVolumeObserveStock, User, Admin
from backend_api.utils.cn_listed_board_filter import filter_query_by_market_and_board
import os

router = APIRouter(prefix="/api/stock/triple-volume-observe", tags=["triple-volume-observe"])
admin_router = APIRouter(prefix="/api/admin/triple-volume-observe", tags=["admin-triple-volume-observe"])


class ObserveRow(BaseModel):
    id: int
    market: str
    code: str
    name: Optional[str]
    observe_trade_date: date
    prev_trade_date: Optional[date]
    prev_volume: Optional[float]
    curr_volume: Optional[float]
    volume_ratio_actual: Optional[float]
    status: str
    vsb_evaluated_at: Optional[str]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ObserveListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[ObserveRow]


def _row_to_schema(r: TripleVolumeObserveStock) -> ObserveRow:
    return ObserveRow(
        id=r.id,
        market=r.market,
        code=r.code,
        name=r.name,
        observe_trade_date=r.observe_trade_date,
        prev_trade_date=r.prev_trade_date,
        prev_volume=r.prev_volume,
        curr_volume=r.curr_volume,
        volume_ratio_actual=r.volume_ratio_actual,
        status=r.status,
        vsb_evaluated_at=r.vsb_evaluated_at.isoformat() if r.vsb_evaluated_at else None,
        created_at=r.created_at.isoformat() if r.created_at else "",
        updated_at=r.updated_at.isoformat() if r.updated_at else "",
    )


def _export_owner_id(principal: Union[User, Admin]) -> str:
    if isinstance(principal, User):
        return str(principal.id)
    return f"admin_{principal.id}"


def _list_observe_impl(
    db: Session,
    market: Optional[str],
    status: Optional[str],
    page: int,
    page_size: int,
    board_segment: Optional[str] = None,
) -> ObserveListResponse:
    q = db.query(TripleVolumeObserveStock)
    q = filter_query_by_market_and_board(
        q,
        TripleVolumeObserveStock.market,
        TripleVolumeObserveStock.code,
        market,
        board_segment,
    )
    if status:
        q = q.filter(TripleVolumeObserveStock.status == status)
    total = q.count()
    rows = (
        q.order_by(TripleVolumeObserveStock.observe_trade_date.desc(), TripleVolumeObserveStock.code)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return ObserveListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[_row_to_schema(r) for r in rows],
    )


def _export_observe_impl(
    db: Session,
    market: Optional[str],
    status: Optional[str],
    principal: Union[User, Admin],
    board_segment: Optional[str] = None,
):
    import pandas as pd

    q = db.query(TripleVolumeObserveStock)
    q = filter_query_by_market_and_board(
        q,
        TripleVolumeObserveStock.market,
        TripleVolumeObserveStock.code,
        market,
        board_segment,
    )
    if status:
        q = q.filter(TripleVolumeObserveStock.status == status)
    rows = q.order_by(
        TripleVolumeObserveStock.observe_trade_date.desc(),
        TripleVolumeObserveStock.market,
        TripleVolumeObserveStock.code,
    ).all()
    data = []
    for r in rows:
        vd = r.vsb_detail_json if isinstance(r.vsb_detail_json, dict) else {}
        data.append(
            {
                "市场": r.market,
                "代码": r.code,
                "名称": r.name or "",
                "观察日": r.observe_trade_date.strftime("%Y-%m-%d")
                if hasattr(r.observe_trade_date, "strftime")
                else str(r.observe_trade_date)[:10],
                "状态": r.status,
                "量比": r.volume_ratio_actual,
                "复核时间": r.vsb_evaluated_at.strftime("%Y-%m-%d %H:%M:%S") if r.vsb_evaluated_at else "",
                "VSB摘要": str(vd) if vd else "",
            }
        )
    report_dir = "reports/csv"
    os.makedirs(report_dir, exist_ok=True)
    fn = f"tvo_export_{_export_owner_id(principal)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    path = os.path.join(report_dir, fn)
    pd.DataFrame(data).to_excel(path, index=False, sheet_name="观察股")
    return FileResponse(
        path,
        filename=fn,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/list", response_model=ObserveListResponse)
def list_observe_stocks(
    market: Optional[str] = Query(None, description="CN 或 HK；与 board 组合见说明"),
    board: Optional[str] = Query(
        None,
        description="A股代码段：CYB创业板 SZ_SME中小板 KCB科创板 MAIN沪深主板；仅 market=CN 或未传 market 时生效",
    ),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    _principal: Union[User, Admin] = Depends(get_current_user_or_admin),
    db: Session = Depends(get_db),
):
    return _list_observe_impl(db, market, status, page, page_size, board)


@admin_router.get("/list", response_model=ObserveListResponse)
def admin_list_observe_stocks(
    market: Optional[str] = Query(None, description="CN 或 HK"),
    board: Optional[str] = Query(None, description="CYB SZ_SME KCB MAIN"),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    _principal: Union[User, Admin] = Depends(get_current_user_or_admin),
    db: Session = Depends(get_db),
):
    return _list_observe_impl(db, market, status, page, page_size, board)


@router.get("/export")
def export_observe_stocks(
    market: Optional[str] = Query(None),
    board: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    principal: Union[User, Admin] = Depends(get_current_user_or_admin),
    db: Session = Depends(get_db),
):
    """导出当前筛选条件下全部观察股为 xlsx（与推送报告列风格接近）。"""
    return _export_observe_impl(db, market, status, principal, board)


@admin_router.get("/export")
def admin_export_observe_stocks(
    market: Optional[str] = Query(None),
    board: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    principal: Union[User, Admin] = Depends(get_current_user_or_admin),
    db: Session = Depends(get_db),
):
    return _export_observe_impl(db, market, status, principal, board)


def _admin_run_scan_impl(db: Session):
    from backend_core.strategies.triple_volume_observe.scan_job import run_triple_volume_scan

    try:
        return run_triple_volume_scan(db)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


def _admin_run_eval_impl(db: Session):
    from backend_core.strategies.triple_volume_observe.eval_job import run_triple_volume_eval

    try:
        return run_triple_volume_eval(db)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/run-scan")
def admin_run_scan(
    _admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return _admin_run_scan_impl(db)


@router.post("/admin/run-eval")
def admin_run_eval(
    _admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return _admin_run_eval_impl(db)


@admin_router.post("/run-scan")
def admin_portal_run_scan(
    _admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理端路径：与 /api/stock/.../admin/run-scan 等价。"""
    return _admin_run_scan_impl(db)


@admin_router.post("/run-eval")
def admin_portal_run_eval(
    _admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理端路径：与 /api/stock/.../admin/run-eval 等价。"""
    return _admin_run_eval_impl(db)

