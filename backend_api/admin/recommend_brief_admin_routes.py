"""管理端：策略推荐简报重跑 / 历史 / 导出 / KPI。"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.auth import get_current_admin
from backend_api.database import get_db
from backend_api.models import Admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/recommend", tags=["管理端-策略推荐"])


class RerunRequest(BaseModel):
    asof_date: Optional[str] = None
    late_run: bool = False
    force_weekly: bool = False
    force_monthly: bool = False
    horizons: Optional[List[str]] = Field(
        default=None, description="默认 daily+按日历 weekly/monthly"
    )


def _require_admin(admin: Admin = Depends(get_current_admin)) -> Admin:
    return admin


@router.get("/brief")
def admin_get_brief(
    horizon: str = Query("daily"),
    asof_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: Admin = Depends(_require_admin),
):
    from backend_core.recommend.store import get_brief

    brief = get_brief(db, horizon=horizon, asof_date=asof_date)
    if not brief:
        raise HTTPException(status_code=404, detail="暂无简报")
    from backend_core.recommend.enrich import enrich_brief_items_for_display
    items = brief.get("items") if isinstance(brief.get("items"), list) else []
    brief = dict(brief)
    brief["items"] = enrich_brief_items_for_display(
        db, items, asof_date=str(brief.get("asof_date") or asof_date or "")
    )
    return {"success": True, "data": brief}


@router.get("/asof-dates")
def admin_list_asof(
    horizon: str = Query("daily"),
    limit: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
    _: Admin = Depends(_require_admin),
):
    from backend_core.recommend.store import list_asof_dates

    return {"success": True, "data": list_asof_dates(db, horizon=horizon, limit=limit)}


@router.post("/rerun")
def admin_rerun(
    body: RerunRequest,
    _: Admin = Depends(_require_admin),
):
    from backend_core.recommend.scheduled import run_recommend_brief_job

    result = run_recommend_brief_job(
        asof_date=body.asof_date,
        late_run=body.late_run,
        force_weekly=body.force_weekly,
        force_monthly=body.force_monthly,
        horizons=body.horizons,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("error") or "重跑失败")
    return {"success": True, "data": result}


@router.get("/export/xlsx")
def admin_export_xlsx(
    horizon: str = Query("daily"),
    asof_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: Admin = Depends(_require_admin),
):
    from backend_core.recommend.export import build_recommend_excel
    from backend_core.recommend.store import get_brief

    brief = get_brief(db, horizon=horizon, asof_date=asof_date)
    if not brief:
        raise HTTPException(status_code=404, detail="暂无简报")
    path = build_recommend_excel(brief)
    return FileResponse(
        path,
        filename=os.path.basename(path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/export/pdf")
def admin_export_pdf(
    horizon: str = Query("daily"),
    asof_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: Admin = Depends(_require_admin),
):
    from backend_core.recommend.export import build_recommend_pdf_bytes
    from backend_core.recommend.store import get_brief

    brief = get_brief(db, horizon=horizon, asof_date=asof_date)
    if not brief:
        raise HTTPException(status_code=404, detail="暂无简报")
    try:
        data = build_recommend_pdf_bytes(brief)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    fname = f"recommend_{horizon}_{brief.get('asof_date')}.pdf"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/kpi/touch-rate")
def admin_kpi_touch(
    asof_date: str = Query(...),
    horizon: str = Query("daily"),
    forward_days: int = Query(3, ge=1, le=10),
    db: Session = Depends(get_db),
    _: Admin = Depends(_require_admin),
):
    from backend_core.recommend.kpi import compute_buy_zone_touch_rate

    return {
        "success": True,
        "data": compute_buy_zone_touch_rate(
            db, asof_date=asof_date, horizon=horizon, forward_days=forward_days
        ),
    }
