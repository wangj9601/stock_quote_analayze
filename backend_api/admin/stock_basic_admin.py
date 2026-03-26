from __future__ import annotations

import csv
from io import BytesIO, StringIO
from typing import Any, Dict, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend_api.auth import get_current_admin
from backend_api.database import get_db
from backend_core.utils.stock_basic_importer import (
    ensure_share_columns,
    execute_import_rows,
    issues_to_dict,
    parse_import_file,
)

router = APIRouter(prefix="/api/admin/stock-basic", tags=["admin-stock-basic"])


def _write_operation_log(db: Session, log_type: str, message: str, status: str, affected: int, error: Optional[str] = None) -> None:
    try:
        db.execute(
            text(
                """
                INSERT INTO operation_logs (log_type, log_message, affected_count, log_status, error_info, log_time)
                VALUES (:log_type, :log_message, :affected_count, :log_status, :error_info, NOW())
                """
            ),
            {
                "log_type": log_type,
                "log_message": message,
                "affected_count": affected,
                "log_status": status,
                "error_info": error,
            },
        )
        db.commit()
    except Exception:
        db.rollback()


@router.get("/pipeline-status")
async def get_pipeline_status(
    db: Session = Depends(get_db),
    _: Any = Depends(get_current_admin),
):
    ensure_share_columns(db)
    cn_missing = db.execute(
        text(
            """
            SELECT COUNT(1) FROM stock_basic_info
            WHERE total_shares IS NULL OR free_float_shares IS NULL
            """
        )
    ).scalar() or 0
    hk_missing = db.execute(
        text(
            """
            SELECT COUNT(1) FROM stock_basic_info_hk
            WHERE total_shares IS NULL OR free_float_shares IS NULL
            """
        )
    ).scalar() or 0
    scheduler = {
        "stock_shares_update": {
            "day_of_week": "sat",
            "hour": 10,
            "minute": 0,
            "env_keys": ["SCHED_STOCK_SHARES_DOW", "SCHED_STOCK_SHARES_HOUR", "SCHED_STOCK_SHARES_MINUTE"],
        },
        "turnover_collect": {
            "day_of_week": "mon-fri",
            "hour": 11,
            "minute": 13,
            "env_keys": ["SCHED_AKSHARE_TURNOVER_DOW", "SCHED_AKSHARE_TURNOVER_HOUR", "SCHED_AKSHARE_TURNOVER_MINUTE"],
        },
    }
    return {
        "success": True,
        "data": {
            "missing_shares": {"CN": cn_missing, "HK": hk_missing},
            "scheduler": scheduler,
            "backfill_suggestion": [
                "python manual_scripts/import_stock_basic_info_offline.py --file <你的CSV或XLSX>",
                "python manual_scripts/update_stock_basic_info_em.py --mode incremental --max 200",
            ],
        },
    }


@router.get("/list")
async def list_stock_basic(
    market: str = Query("ALL", description="ALL/CN/HK"),
    keyword: str = Query("", description="代码或名称关键字"),
    empty_shares: bool = Query(False, description="仅显示缺少股本"),
    collect_enabled: Optional[bool] = Query(None, description="采集处理开关筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    _: Any = Depends(get_current_admin),
):
    ensure_share_columns(db)
    market = (market or "ALL").upper()
    kw = (keyword or "").strip()

    where_cn = []
    where_hk = []
    params: Dict[str, Any] = {}
    if kw:
        where_cn.append("(CAST(code AS TEXT) ILIKE :kw OR name ILIKE :kw)")
        where_hk.append("(code ILIKE :kw OR name ILIKE :kw)")
        params["kw"] = f"%{kw}%"
    if empty_shares:
        cond = "(total_shares IS NULL OR free_float_shares IS NULL)"
        where_cn.append(cond)
        where_hk.append(cond)
    if collect_enabled is not None:
        where_cn.append("COALESCE(collect_enabled, TRUE) = :collect_enabled")
        where_hk.append("COALESCE(collect_enabled, TRUE) = :collect_enabled")
        params["collect_enabled"] = collect_enabled
    where_cn_sql = (" WHERE " + " AND ".join(where_cn)) if where_cn else ""
    where_hk_sql = (" WHERE " + " AND ".join(where_hk)) if where_hk else ""

    union_parts = []
    if market in ("ALL", "CN"):
        union_parts.append(
            f"""
            SELECT 'CN' AS market, LPAD(CAST(code AS TEXT), 6, '0') AS code, name,
                   total_shares, free_float_shares, industry, listing_date, shares_updated_at, COALESCE(collect_enabled, TRUE) AS collect_enabled
            FROM stock_basic_info
            {where_cn_sql}
            """
        )
    if market in ("ALL", "HK"):
        union_parts.append(
            f"""
            SELECT 'HK' AS market, code, name,
                   total_shares, free_float_shares, industry, listing_date, shares_updated_at, COALESCE(collect_enabled, TRUE) AS collect_enabled
            FROM stock_basic_info_hk
            {where_hk_sql}
            """
        )
    if not union_parts:
        raise HTTPException(status_code=400, detail="market 参数错误")

    union_sql = " UNION ALL ".join(union_parts)
    total = db.execute(text(f"SELECT COUNT(1) FROM ({union_sql}) t"), params).scalar() or 0
    offset = (page - 1) * page_size
    rows = db.execute(
        text(
            f"""
            SELECT * FROM ({union_sql}) t
            ORDER BY shares_updated_at ASC NULLS FIRST, market, code
            LIMIT :limit OFFSET :offset
            """
        ),
        {**params, "limit": page_size, "offset": offset},
    ).fetchall()

    data = [
        {
            "market": r[0],
            "code": r[1],
            "name": r[2],
            "total_shares": r[3],
            "free_float_shares": r[4],
            "industry": r[5],
            "listing_date": r[6],
            "shares_updated_at": r[7].isoformat() if r[7] else None,
            "collect_enabled": bool(r[8]) if r[8] is not None else True,
        }
        for r in rows
    ]
    return {"success": True, "data": data, "total": total, "page": page, "page_size": page_size}


@router.post("/collect-flag")
async def update_collect_flag(
    market: str = Query(..., pattern="^(CN|HK)$"),
    code: str = Query(...),
    collect_enabled: bool = Query(...),
    db: Session = Depends(get_db),
    admin: Any = Depends(get_current_admin),
):
    ensure_share_columns(db)
    if market == "CN":
        result = db.execute(
            text(
                """
                UPDATE stock_basic_info
                SET collect_enabled = :collect_enabled
                WHERE LPAD(CAST(code AS TEXT), 6, '0') = :code
                """
            ),
            {"collect_enabled": collect_enabled, "code": str(code).zfill(6)},
        )
    else:
        result = db.execute(
            text(
                """
                UPDATE stock_basic_info_hk
                SET collect_enabled = :collect_enabled
                WHERE code = :code
                """
            ),
            {"collect_enabled": collect_enabled, "code": str(code).strip()},
        )
    db.commit()
    _write_operation_log(
        db,
        log_type="stock_collect_flag",
        message=f"更新采集处理标志 market={market} code={code} enabled={collect_enabled} by {getattr(admin, 'username', 'admin')}",
        status="成功",
        affected=result.rowcount or 0,
    )
    return {"success": True, "affected": result.rowcount or 0}


@router.get("/import/template")
async def download_template(
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    _: Any = Depends(get_current_admin),
):
    cols = ["code", "name", "market", "total_shares", "free_float_shares", "listing_date", "industry", "asof_date", "collect_enabled"]
    sample = [
        ["000001", "平安银行", "CN", 19405918198, 19405918198, "1991-04-03", "银行", "2026-03-26", True],
        ["00700", "腾讯控股", "HK", 9600000000, 9600000000, "2004-06-16", "互联网", "2026-03-26", True],
    ]

    if format == "csv":
        sio = StringIO()
        writer = csv.writer(sio)
        writer.writerow(cols)
        writer.writerows(sample)
        return StreamingResponse(
            iter([sio.getvalue().encode("utf-8-sig")]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=stock_basic_import_template.csv"},
        )

    df = pd.DataFrame(sample, columns=cols)
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="template")
    bio.seek(0)
    return StreamingResponse(
        bio,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=stock_basic_import_template.xlsx"},
    )


@router.post("/import/validate")
async def validate_import_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: Any = Depends(get_current_admin),
):
    content = await file.read()
    rows, issues = parse_import_file(file.filename or "", content)
    market_count = {"CN": 0, "HK": 0}
    for x in rows:
        market_count[x["market"]] = market_count.get(x["market"], 0) + 1
    ensure_share_columns(db)
    return {
        "success": True,
        "data": {
            "filename": file.filename,
            "valid_rows": len(rows),
            "invalid_rows": len(issues),
            "market_count": market_count,
            "issues": issues_to_dict(issues)[:200],
            "preview": rows[:20],
        },
    }


@router.post("/import/execute")
async def execute_import_file(
    file: UploadFile = File(...),
    mode: str = Query("only_fill_empty", pattern="^only_fill_empty$"),
    dry_run: bool = Query(False),
    max_errors: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    admin: Any = Depends(get_current_admin),
):
    content = await file.read()
    rows, issues = parse_import_file(file.filename or "", content)
    if issues:
        return {
            "success": False,
            "message": "文件校验失败，请先修复数据后导入",
            "data": {"valid_rows": len(rows), "invalid_rows": len(issues), "issues": issues_to_dict(issues)[:200]},
        }

    result = execute_import_rows(db, rows, mode=mode, dry_run=dry_run, max_errors=max_errors)
    _write_operation_log(
        db,
        log_type="stock_basic_import",
        message=f"股票基本信息导入({mode}) by {getattr(admin, 'username', 'admin')}",
        status="成功" if result["failed"] == 0 else "部分失败",
        affected=result["success"],
        error=None if result["failed"] == 0 else f"failed={result['failed']}",
    )
    return {"success": result["failed"] == 0, "data": result}

