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
from backend_core.market_review.render import render_markdown
from backend_core.market_review.pdf_export import (
    build_daily_review_pdf_bytes,
)
from backend_core.market_review.period import (
    build_period_snapshot,
    get_period_snapshot,
    update_period_text,
)
from backend_core.market_review.period_render import (
    build_period_review_pdf_bytes,
    period_title,
    render_period_markdown,
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
    db: Session = Depends(get_db),
):
    """下载 Markdown 到浏览器默认下载目录，不写入工程目录。"""
    d = _norm_date(trade_date)
    snap = get_review_snapshot(db, d)
    if not snap:
        return JSONResponse(
            {"success": False, "message": f"无 {d} 快照"}, status_code=404
        )
    md = render_markdown(snap)
    fname, ascii_name = _review_download_names(d, "md")
    return PlainTextResponse(
        md,
        media_type="text/markdown; charset=utf-8",
        headers=_attachment_headers(fname, ascii_name),
    )


@router.get("/export.pdf")
async def api_export_pdf(
    trade_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """下载 PDF 到浏览器默认下载目录，不写入工程目录。"""
    d = _norm_date(trade_date)
    snap = get_review_snapshot(db, d)
    if not snap:
        return JSONResponse(
            {"success": False, "message": f"无 {d} 快照"}, status_code=404
        )
    try:
        pdf_bytes = build_daily_review_pdf_bytes(snap)
    except Exception as e:
        return JSONResponse(
            {"success": False, "message": f"PDF 导出失败: {e}"}, status_code=500
        )

    fname, ascii_name = _review_download_names(d, "pdf")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers=_attachment_headers(fname, ascii_name),
    )


def _review_download_names(trade_date: str, ext: str) -> tuple:
    parts = trade_date.split("-")
    if len(parts) == 3:
        fname = f"{parts[0]}年{parts[1]}月{parts[2]}日 股市复盘报告.{ext}"
    else:
        fname = f"{trade_date} 股市复盘报告.{ext}"
    return fname, f"daily_review_{trade_date}.{ext}"


def _norm_kind(kind: Optional[str]) -> str:
    return "month" if str(kind or "").strip().lower() == "month" else "week"


@router.get("/period")
async def api_get_period(
    type: str = Query("week", description="week 或 month"),
    date: Optional[str] = Query(None, description="区间内任一日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    kind = _norm_kind(type)
    anchor = _norm_date(date)
    snap = get_period_snapshot(db, kind, anchor)
    if not snap:
        label = "月" if kind == "month" else "周"
        return JSONResponse(
            {"success": False, "message": f"无该{label}复盘，请先重算"},
            status_code=404,
        )
    return {"success": True, "data": snap}


@router.post("/period")
async def api_compute_period(
    type: str = Query("week"),
    date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    kind = _norm_kind(type)
    anchor = _norm_date(date)
    try:
        snap = build_period_snapshot(db, kind, anchor)
    except Exception as e:
        return JSONResponse(
            {"success": False, "message": f"复盘计算失败: {e}"},
            status_code=500,
        )
    return {"success": True, "data": snap}


@router.put("/period")
async def api_put_period(
    body: ReviewTextBody,
    type: str = Query("week"),
    date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    kind = _norm_kind(type)
    anchor = _norm_date(date)
    if body.viewpoint_md is None and body.advice_md is None:
        return JSONResponse(
            {"success": False, "message": "请提供 viewpoint_md 或 advice_md"},
            status_code=400,
        )
    snap = update_period_text(
        db,
        kind,
        anchor,
        viewpoint_md=body.viewpoint_md,
        advice_md=body.advice_md,
    )
    if not snap:
        label = "月" if kind == "month" else "周"
        return JSONResponse(
            {"success": False, "message": f"无该{label}复盘，请先重算"},
            status_code=404,
        )
    return {"success": True, "data": snap}


@router.get("/period/export.md")
async def api_export_period_md(
    type: str = Query("week"),
    date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    kind = _norm_kind(type)
    anchor = _norm_date(date)
    snap = get_period_snapshot(db, kind, anchor)
    if not snap:
        return JSONResponse(
            {"success": False, "message": "无该区间快照，请先重算"},
            status_code=404,
        )
    md = render_period_markdown(snap)
    fname = f"{period_title(snap)}.md"
    ascii_name = f"period_review_{snap.get('period_key') or anchor}.md"
    return PlainTextResponse(
        md,
        media_type="text/markdown; charset=utf-8",
        headers=_attachment_headers(fname, ascii_name),
    )


@router.get("/period/export.pdf")
async def api_export_period_pdf(
    type: str = Query("week"),
    date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    kind = _norm_kind(type)
    anchor = _norm_date(date)
    snap = get_period_snapshot(db, kind, anchor)
    if not snap:
        return JSONResponse(
            {"success": False, "message": "无该区间快照，请先重算"},
            status_code=404,
        )
    try:
        pdf_bytes = build_period_review_pdf_bytes(snap)
    except Exception as e:
        return JSONResponse(
            {"success": False, "message": f"PDF 导出失败: {e}"},
            status_code=500,
        )
    fname = f"{period_title(snap)}.pdf"
    ascii_name = f"period_review_{snap.get('period_key') or anchor}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers=_attachment_headers(fname, ascii_name),
    )


def _attachment_headers(fname: str, ascii_name: str) -> dict:
    return {
        "Content-Disposition": (
            f"attachment; filename=\"{ascii_name}\"; "
            f"filename*=UTF-8''{quote(fname)}"
        ),
    }
