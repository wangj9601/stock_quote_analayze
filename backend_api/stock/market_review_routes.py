# -*- coding: utf-8 -*-
"""每日复盘 / 涨停池采集 API。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from urllib.parse import quote

from backend_api.database import get_db
from backend_core.data_collectors.akshare.zt_pool_em import collect_zt_pool_em
from backend_core.market_review.compute import (
    build_review_snapshot,
    get_review_snapshot,
    update_review_text,
)
from backend_core.market_review.render import export_markdown_file, render_markdown
from backend_core.market_review.pdf_export import (
    build_daily_review_pdf_bytes,
    export_pdf_file,
)

router = APIRouter(prefix="/api/market_review", tags=["market_review"])


class ReviewTextBody(BaseModel):
    viewpoint_md: Optional[str] = None
    advice_md: Optional[str] = None


def _norm_date(trade_date: Optional[str]) -> str:
    if not trade_date:
        return datetime.now().strftime("%Y-%m-%d")
    s = str(trade_date).strip().replace("/", "-")
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s[:10]


@router.post("/zt_pool/collect")
async def api_collect_zt_pool(
    background_tasks: BackgroundTasks,
    trade_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    sync: bool = Query(False, description="true 则同步执行"),
):
    d = _norm_date(trade_date)
    if sync:
        result = collect_zt_pool_em(d)
        status = 200 if result.get("success") else 200  # 失败也 200，带 success=False
        return JSONResponse(result, status_code=status)
    background_tasks.add_task(collect_zt_pool_em, d)
    return {
        "success": True,
        "message": "涨停股池采集已在后台启动",
        "trade_date": d,
    }


@router.post("/compute")
async def api_compute_review(
    background_tasks: BackgroundTasks,
    trade_date: Optional[str] = Query(None),
    collect_zt: bool = Query(True, description="计算前是否先采涨停池"),
    export_md: bool = Query(True),
    sync: bool = Query(True, description="默认同步计算"),
    db: Session = Depends(get_db),
):
    d = _norm_date(trade_date)

    def _run():
        zt = collect_zt_pool_em(d) if collect_zt else None
        # 新 session，避免 background 里用请求 session
        from backend_core.database.db import SessionLocal

        session = SessionLocal()
        try:
            snap = build_review_snapshot(session, d, export_md=export_md)
            return {
                "success": True,
                "trade_date": d,
                "zt_pool": zt,
                "data": {
                    "limit_source": snap.get("limit_source"),
                    "season": snap.get("season"),
                    "hard_gates": snap.get("hard_gates"),
                    "vol_trillion": snap.get("vol_trillion"),
                    "cb_count": snap.get("cb_count"),
                    "height": snap.get("height"),
                    "lo_value": snap.get("lo_value"),
                    "hi_value": snap.get("hi_value"),
                    "sp_value": snap.get("sp_value"),
                    "export_path": snap.get("export_path"),
                },
            }
        finally:
            session.close()

    if sync:
        try:
            if collect_zt:
                zt = collect_zt_pool_em(d)
            else:
                zt = None
            snap = build_review_snapshot(db, d, export_md=export_md)
            return {
                "success": True,
                "trade_date": d,
                "zt_pool": zt,
                "data": snap,
            }
        except Exception as e:
            return JSONResponse(
                {"success": False, "message": f"复盘计算失败: {e}"}, status_code=500
            )

    background_tasks.add_task(_run)
    return {"success": True, "message": "每日复盘计算已在后台启动", "trade_date": d}


@router.get("/daily")
async def api_get_daily(
    trade_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    d = _norm_date(trade_date)
    snap = get_review_snapshot(db, d)
    if not snap:
        return JSONResponse(
            {"success": False, "message": f"无 {d} 的复盘快照，请先 compute"},
            status_code=404,
        )
    return {"success": True, "data": snap}


@router.put("/daily")
async def api_put_daily(
    body: ReviewTextBody,
    trade_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    d = _norm_date(trade_date)
    if body.viewpoint_md is None and body.advice_md is None:
        return JSONResponse(
            {"success": False, "message": "请提供 viewpoint_md 或 advice_md"},
            status_code=400,
        )
    snap = update_review_text(
        db, d, viewpoint_md=body.viewpoint_md, advice_md=body.advice_md
    )
    if not snap:
        return JSONResponse(
            {"success": False, "message": f"无 {d} 快照"}, status_code=404
        )
    return {"success": True, "data": snap}


@router.get("/export.md")
async def api_export_md(
    trade_date: Optional[str] = Query(None),
    save: bool = Query(True, description="是否写入 exported_docs"),
    db: Session = Depends(get_db),
):
    d = _norm_date(trade_date)
    snap = get_review_snapshot(db, d)
    if not snap:
        return JSONResponse(
            {"success": False, "message": f"无 {d} 快照"}, status_code=404
        )
    md = render_markdown(snap)
    path = None
    if save:
        path = str(export_markdown_file(snap))
    if save:
        return {"success": True, "path": path, "markdown": md}
    return PlainTextResponse(md, media_type="text/markdown; charset=utf-8")


@router.get("/export.pdf")
async def api_export_pdf(
    trade_date: Optional[str] = Query(None),
    save: bool = Query(True, description="是否同时写入 exported_docs"),
    db: Session = Depends(get_db),
):
    d = _norm_date(trade_date)
    snap = get_review_snapshot(db, d)
    if not snap:
        return JSONResponse(
            {"success": False, "message": f"无 {d} 快照"}, status_code=404
        )
    try:
        pdf_bytes = build_daily_review_pdf_bytes(snap)
        saved_path = None
        if save:
            saved_path = str(export_pdf_file(snap, pdf_bytes=pdf_bytes))
    except Exception as e:
        return JSONResponse(
            {"success": False, "message": f"PDF 导出失败: {e}"}, status_code=500
        )

    parts = d.split("-")
    if len(parts) == 3:
        fname = f"{parts[0]}年{parts[1]}月{parts[2]}日 股市复盘报告.pdf"
    else:
        fname = f"{d} 股市复盘报告.pdf"
    # 浏览器下载文件名：ASCII fallback + RFC5987 filename*
    ascii_name = f"daily_review_{d}.pdf"
    headers = {
        "Content-Disposition": (
            f"attachment; filename=\"{ascii_name}\"; "
            f"filename*=UTF-8''{quote(fname)}"
        ),
    }
    if saved_path:
        # HTTP 头须为 latin-1：路径含中文时用 percent-encoding
        headers["X-Export-Path"] = quote(saved_path, safe="/:\\")
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)
