"""前台：策略推荐简报 API。"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.auth_routes import get_current_user
from backend_api.database import get_db
from backend_api.models import User
from backend_api.permissions import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/recommend", tags=["策略推荐"])


class AddObserveFromBriefRequest(BaseModel):
    code: str
    name: Optional[str] = None
    asof_date: Optional[str] = None
    horizon: str = "daily"
    snapshot: Optional[Dict[str, Any]] = None


@router.get("/brief")
def get_recommend_brief(
    horizon: str = Query("daily", description="daily|weekly|monthly"),
    asof_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permission("channel.analyze.tab.recommend")),
):
    hz = (horizon or "daily").strip().lower()
    if hz not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="horizon 无效")
    perm = f"channel.recommend.{hz}"
    # 细分权限：有父权限即可；子权限在前端控制 tab。后端宽容校验父权限已过。
    from backend_core.recommend.store import get_brief

    brief = get_brief(db, horizon=hz, asof_date=asof_date)
    if not brief:
        raise HTTPException(status_code=404, detail="暂无该日期简报")
    from backend_core.recommend.enrich import enrich_brief_items_for_display
    items = brief.get("items") if isinstance(brief.get("items"), list) else []
    brief = dict(brief)
    brief["items"] = enrich_brief_items_for_display(
        db, items, asof_date=str(brief.get("asof_date") or asof_date or "")
    )
    return {"success": True, "data": brief}


@router.get("/asof-dates")
def list_recommend_asof_dates(
    horizon: str = Query("daily"),
    limit: int = Query(60, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permission("channel.analyze.tab.recommend")),
):
    from backend_core.recommend.store import list_asof_dates

    hz = (horizon or "daily").strip().lower()
    return {"success": True, "data": list_asof_dates(db, horizon=hz, limit=limit)}


@router.get("/export/xlsx")
def export_recommend_xlsx(
    horizon: str = Query("daily"),
    asof_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permission("channel.analyze.tab.recommend.btn.export")),
):
    from backend_core.recommend.export import build_recommend_excel
    from backend_core.recommend.store import get_brief

    hz = (horizon or "daily").strip().lower()
    brief = get_brief(db, horizon=hz, asof_date=asof_date)
    if not brief:
        raise HTTPException(status_code=404, detail="暂无该日期简报")
    path = build_recommend_excel(brief)
    return FileResponse(
        path,
        filename=os.path.basename(path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/export/pdf")
def export_recommend_pdf(
    horizon: str = Query("daily"),
    asof_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permission("channel.analyze.tab.recommend.btn.export")),
):
    from backend_core.recommend.export import build_recommend_pdf_bytes
    from backend_core.recommend.store import get_brief

    hz = (horizon or "daily").strip().lower()
    brief = get_brief(db, horizon=hz, asof_date=asof_date)
    if not brief:
        raise HTTPException(status_code=404, detail="暂无该日期简报")
    try:
        data = build_recommend_pdf_bytes(brief)
    except Exception as e:
        logger.warning("pdf export failed: %s", e)
        raise HTTPException(status_code=500, detail=f"PDF 导出失败: {e}")
    fname = f"recommend_{hz}_{brief.get('asof_date')}.pdf"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.post("/add-observe")
def add_observe_from_brief(
    body: AddObserveFromBriefRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permission("channel.analyze.tab.recommend.btn.observe")),
):
    from backend_api import trade_observe_service as svc

    code = (body.code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="code 必填")
    snap = body.snapshot if isinstance(body.snapshot, dict) else {}
    if body.asof_date:
        snap = dict(snap)
        snap["brief_asof_date"] = body.asof_date
        snap["brief_horizon"] = body.horizon
    try:
        row = svc.add_observe(
            db,
            current_user,
            source="recommend",
            code=code,
            market="CN",
            name=body.name,
            signal_date=body.asof_date,
            snapshot=snap or None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "data": row}


@router.get("/kpi/touch-rate")
def kpi_touch_rate(
    asof_date: str = Query(...),
    horizon: str = Query("daily"),
    forward_days: int = Query(3, ge=1, le=10),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permission("channel.analyze.tab.recommend")),
):
    from backend_core.recommend.kpi import compute_buy_zone_touch_rate

    data = compute_buy_zone_touch_rate(
        db, asof_date=asof_date, horizon=horizon, forward_days=forward_days
    )
    return {"success": True, "data": data}
