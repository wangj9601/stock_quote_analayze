from __future__ import annotations

import csv
import math
from datetime import date, datetime
from io import BytesIO, StringIO
from typing import Any, Dict, List, Literal, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from backend_api.auth import get_current_admin
from backend_api.database import get_db
from backend_api.utils.industry_board_query import (
    batch_industry_board_names_by_stock_codes,
    resolve_cn_industry_display,
    sync_a_stock_industry_from_boards,
)
from backend_core.utils.stock_basic_importer import (
    ensure_share_columns,
    execute_import_rows,
    issues_to_dict,
    parse_import_file,
)

router = APIRouter(prefix="/api/admin/stock-basic", tags=["admin-stock-basic"])


class BatchCollectFlagBody(BaseModel):
    market: str = Field(..., pattern="^(CN|HK)$", description="市场")
    codes: List[str] = Field(..., min_length=1, description="股票代码列表")
    collect_enabled: bool = Field(..., description="采集/处理开关")


DelistedFilter = Literal["all", "only", "exclude"]


def _exclude_delisted_name_condition() -> str:
    """与采集链路一致：名称含「退」视为退市等。"""
    return "name NOT LIKE '%退%'"


def _only_delisted_name_condition() -> str:
    return "name LIKE '%退%'"


def _append_common_filters(
    where_parts: list[str],
    *,
    empty_shares: bool,
    collect_enabled: Optional[bool],
    delisted_filter: DelistedFilter,
    params: Dict[str, Any],
) -> None:
    if empty_shares:
        where_parts.append("(total_shares IS NULL OR free_float_shares IS NULL)")
    if collect_enabled is not None:
        where_parts.append("COALESCE(collect_enabled, TRUE) = :collect_enabled")
        params["collect_enabled"] = collect_enabled
    if delisted_filter == "only":
        where_parts.append(_only_delisted_name_condition())
    elif delisted_filter == "exclude":
        where_parts.append(_exclude_delisted_name_condition())


def _normalize_optional_text(v: Any) -> Optional[str]:
    """行业、上市日期等：库内或导入残留的 nan/空串转为 None，便于 JSON/前端展示为空。"""
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, date):
        return v.isoformat()
    s = str(v).strip()
    if not s:
        return None
    low = s.lower()
    if low in ("nan", "none", "null", "<na>", "nat"):
        return None
    return s


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
            "mode": "weekly|monthly|quarterly",
            "day_of_week": "sat",
            "day": 1,
            "quarter_months": "1,4,7,10",
            "hour": 10,
            "minute": 0,
            "env_keys": [
                "SCHED_STOCK_SHARES_MODE",
                "SCHED_STOCK_SHARES_DOW",
                "SCHED_STOCK_SHARES_DAY",
                "SCHED_STOCK_SHARES_QUARTER_MONTHS",
                "SCHED_STOCK_SHARES_HOUR",
                "SCHED_STOCK_SHARES_MINUTE",
            ],
        },
        "turnover_collect": {
            "day_of_week": "mon-fri",
            "hour": 11,
            "minute": 13,
            "env_keys": [
                "SCHED_AKSHARE_TURNOVER_ENABLED",
                "SCHED_AKSHARE_TURNOVER_DOW",
                "SCHED_AKSHARE_TURNOVER_HOUR",
                "SCHED_AKSHARE_TURNOVER_MINUTE",
            ],
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
    delisted_filter: DelistedFilter = Query(
        "all", description="退市筛选：all=全部, only=仅退市, exclude=排除退市"
    ),
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
    _append_common_filters(
        where_cn,
        empty_shares=empty_shares,
        collect_enabled=collect_enabled,
        delisted_filter=delisted_filter,
        params=params,
    )
    _append_common_filters(
        where_hk,
        empty_shares=empty_shares,
        collect_enabled=collect_enabled,
        delisted_filter=delisted_filter,
        params=params,
    )
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
            "industry": _normalize_optional_text(r[5]),
            "listing_date": _normalize_optional_text(r[6]),
            "shares_updated_at": r[7].isoformat() if r[7] else None,
            "collect_enabled": bool(r[8]) if r[8] is not None else True,
        }
        for r in rows
    ]
    if market in ("ALL", "CN") and data:
        cn_codes = [d["code"] for d in data if d["market"] == "CN"]
        board_map = batch_industry_board_names_by_stock_codes(db, cn_codes)
        for d in data:
            if d["market"] == "CN":
                d["industry"] = resolve_cn_industry_display(d.get("industry"), board_map.get(d["code"]))
    return {"success": True, "data": data, "total": total, "page": page, "page_size": page_size}


def _build_shares_export_where(
    market: str,
    keyword: str,
    empty_shares: bool,
    collect_enabled: Optional[bool],
    delisted_filter: DelistedFilter = "all",
) -> tuple[str, Dict[str, Any]]:
    """单市场（CN 或 HK）的 WHERE 子句与参数。"""
    where: list[str] = []
    params: Dict[str, Any] = {}
    kw = (keyword or "").strip()
    if kw:
        if market == "CN":
            where.append("(CAST(code AS TEXT) ILIKE :kw OR name ILIKE :kw)")
        else:
            where.append("(code ILIKE :kw OR name ILIKE :kw)")
        params["kw"] = f"%{kw}%"
    _append_common_filters(
        where,
        empty_shares=empty_shares,
        collect_enabled=collect_enabled,
        delisted_filter=delisted_filter,
        params=params,
    )
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    return where_sql, params


@router.get("/export/shares")
async def export_shares(
    market: str = Query(..., pattern="^(CN|HK)$"),
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    keyword: str = Query("", description="代码或名称关键字"),
    empty_shares: bool = Query(False, description="仅导出缺少股本"),
    collect_enabled: Optional[bool] = Query(None, description="采集处理开关筛选"),
    delisted_filter: DelistedFilter = Query(
        "all", description="退市筛选：all=全部, only=仅退市, exclude=排除退市"
    ),
    db: Session = Depends(get_db),
    _: Any = Depends(get_current_admin),
):
    """导出指定市场股本相关字段（CSV/XLSX），列与导入模板对齐。"""
    ensure_share_columns(db)
    where_sql, params = _build_shares_export_where(
        market, keyword, empty_shares, collect_enabled, delisted_filter
    )
    table = "stock_basic_info" if market == "CN" else "stock_basic_info_hk"
    code_expr = "LPAD(CAST(code AS TEXT), 6, '0')" if market == "CN" else "code"
    sql = f"""
        SELECT {code_expr} AS code, name,
               total_shares, free_float_shares, industry, listing_date,
               shares_updated_at, COALESCE(collect_enabled, TRUE) AS collect_enabled
        FROM {table}
        {where_sql}
        ORDER BY code
    """
    rows = db.execute(text(sql), params).fetchall()
    board_map: Dict[str, str] = {}
    if market == "CN" and rows:
        board_map = batch_industry_board_names_by_stock_codes(db, [str(r[0]) for r in rows])
    cols = [
        "code",
        "name",
        "market",
        "total_shares",
        "free_float_shares",
        "listing_date",
        "industry",
        "shares_updated_at",
        "collect_enabled",
    ]
    data_rows = []
    for r in rows:
        industry = resolve_cn_industry_display(_normalize_optional_text(r[4]), board_map.get(str(r[0])))
        data_rows.append(
            [
                r[0],
                r[1],
                market,
                r[2],
                r[3],
                _normalize_optional_text(r[5]) or "",
                industry or "",
                r[6].isoformat() if r[6] else None,
                bool(r[7]) if r[7] is not None else True,
            ]
        )

    if format == "csv":
        sio = StringIO()
        writer = csv.writer(sio)
        writer.writerow(cols)
        writer.writerows(data_rows)
        fname = f"stock_basic_shares_{market.lower()}.csv"
        return StreamingResponse(
            iter([sio.getvalue().encode("utf-8-sig")]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={fname}"},
        )

    df = pd.DataFrame(data_rows, columns=cols)
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="shares")
    bio.seek(0)
    fname = f"stock_basic_shares_{market.lower()}.xlsx"
    return StreamingResponse(
        bio,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


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


@router.post("/collect-flag/batch")
async def batch_update_collect_flag(
    body: BatchCollectFlagBody,
    db: Session = Depends(get_db),
    admin: Any = Depends(get_current_admin),
):
    """批量更新采集/处理开关。"""
    ensure_share_columns(db)
    market = body.market.upper()
    codes = list(dict.fromkeys(str(c).strip() for c in body.codes if str(c).strip()))
    if not codes:
        raise HTTPException(status_code=400, detail="codes 不能为空")

    if market == "CN":
        norm_codes = [c.zfill(6) for c in codes]
        stmt = text(
            """
            UPDATE stock_basic_info
            SET collect_enabled = :collect_enabled
            WHERE LPAD(CAST(code AS TEXT), 6, '0') IN :codes
            """
        ).bindparams(bindparam("codes", expanding=True))
        result = db.execute(
            stmt,
            {"collect_enabled": body.collect_enabled, "codes": norm_codes},
        )
    else:
        stmt = text(
            """
            UPDATE stock_basic_info_hk
            SET collect_enabled = :collect_enabled
            WHERE code IN :codes
            """
        ).bindparams(bindparam("codes", expanding=True))
        result = db.execute(
            stmt,
            {"collect_enabled": body.collect_enabled, "codes": codes},
        )

    db.commit()
    affected = int(result.rowcount or 0)
    _write_operation_log(
        db,
        log_type="stock_collect_flag_batch",
        message=(
            f"批量更新采集处理标志 market={market} enabled={body.collect_enabled} "
            f"count={len(codes)} by {getattr(admin, 'username', 'admin')}"
        ),
        status="成功",
        affected=affected,
    )
    return {"success": True, "data": {"affected": affected}}


@router.post("/sync-industry")
async def sync_industry_from_boards(
    market: str = Query("CN", pattern="^(CN)$", description="当前仅支持 A 股"),
    only_empty: bool = Query(True, description="True=仅补空行业；False=按板块映射全量覆盖"),
    db: Session = Depends(get_db),
    admin: Any = Depends(get_current_admin),
):
    """从行业板块成分股 + 基本信息表同步 industry 到 stock_basic_info。"""
    ensure_share_columns(db)
    try:
        stats = sync_a_stock_industry_from_boards(db, only_empty=only_empty)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步行业失败: {e}") from e
    _write_operation_log(
        db,
        log_type="stock_basic_industry_sync",
        message=(
            f"同步A股行业 from industry_board only_empty={only_empty} "
            f"by {getattr(admin, 'username', 'admin')}"
        ),
        status="成功",
        affected=stats.get("updated", 0),
    )
    return {"success": True, "data": stats}


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


def _filter_rows_by_scope(rows: list, scope_market: Optional[str]) -> list:
    if not scope_market:
        return rows
    sm = scope_market.upper()
    return [r for r in rows if r.get("market") == sm]


@router.post("/import/validate")
async def validate_import_file(
    file: UploadFile = File(...),
    scope_market: Optional[str] = Query(None, description="仅校验该市场行：CN 或 HK"),
    db: Session = Depends(get_db),
    _: Any = Depends(get_current_admin),
):
    content = await file.read()
    rows, issues = parse_import_file(file.filename or "", content)
    if scope_market:
        rows = _filter_rows_by_scope(rows, scope_market)
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
    scope_market: Optional[str] = Query(None, description="仅导入该市场行：CN 或 HK"),
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
    if scope_market:
        rows = _filter_rows_by_scope(rows, scope_market)

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


@router.get("/rs-ratings")
async def list_rs_ratings(
    keyword: str = Query("", description="代码或名称关键字"),
    date: Optional[str] = Query(None, description="交易日 YYYY-MM-DD；缺省取最新有数据日"),
    min_rating: Optional[int] = Query(None, ge=1, le=99, description="最低 RS 评级过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    _: Any = Depends(get_current_admin),
):
    """A 股股价相对强度列表：按 rs_rating 降序（最高在前），无评级排后。"""
    from backend_core.indicators.rs_rating.config import strength_label

    asof = (date or "").strip()[:10] or None
    if not asof:
        row = db.execute(
            text(
                """
                SELECT MAX(date) FROM rs_ratings
                WHERE market_type = 'CN' AND rs_rating IS NOT NULL
                """
            )
        ).fetchone()
        asof = str(row[0]).strip()[:10] if row and row[0] else None
        if not asof:
            row2 = db.execute(
                text("SELECT MAX(date) FROM rs_ratings WHERE market_type = 'CN'")
            ).fetchone()
            asof = str(row2[0]).strip()[:10] if row2 and row2[0] else None
    if not asof:
        return {
            "success": True,
            "data": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "asof": None,
            "message": "尚无 RS 预计算数据",
        }

    where_parts = ["r.market_type = 'CN'", "r.date = :asof"]
    params: Dict[str, Any] = {"asof": asof}
    kw = (keyword or "").strip()
    if kw:
        where_parts.append("(r.code ILIKE :kw OR COALESCE(b.name, '') ILIKE :kw)")
        params["kw"] = f"%{kw}%"
    if min_rating is not None:
        where_parts.append("r.rs_rating >= :min_rating")
        params["min_rating"] = int(min_rating)

    where_sql = " AND ".join(where_parts)
    total = (
        db.execute(
            text(
                f"""
                SELECT COUNT(1)
                FROM rs_ratings r
                LEFT JOIN stock_basic_info b ON b.code = r.code
                WHERE {where_sql}
                """
            ),
            params,
        ).scalar()
        or 0
    )
    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset
    rows = db.execute(
        text(
            f"""
            SELECT
                r.code,
                b.name,
                r.date,
                r.rs_rating,
                r.rs_raw,
                r.roc_63,
                r.roc_126,
                r.roc_189,
                r.roc_252,
                r.universe_size,
                r.coverage_ratio
            FROM rs_ratings r
            LEFT JOIN stock_basic_info b ON b.code = r.code
            WHERE {where_sql}
            ORDER BY r.rs_rating DESC NULLS LAST, r.rs_raw DESC NULLS LAST, r.code ASC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()

    data = []
    for r in rows:
        rating = r.get("rs_rating")
        data.append(
            {
                "code": r.get("code"),
                "name": r.get("name"),
                "date": str(r.get("date") or "")[:10],
                "rs_rating": int(rating) if rating is not None else None,
                "rs_raw": r.get("rs_raw"),
                "roc_63": r.get("roc_63"),
                "roc_126": r.get("roc_126"),
                "roc_189": r.get("roc_189"),
                "roc_252": r.get("roc_252"),
                "universe_size": r.get("universe_size"),
                "coverage_ratio": r.get("coverage_ratio"),
                "strength_label": strength_label(
                    int(rating) if rating is not None else None
                ),
            }
        )
    return {
        "success": True,
        "data": data,
        "total": int(total),
        "page": page,
        "page_size": page_size,
        "asof": asof,
    }


@router.get("/rs-ratings/history")
async def list_rs_rating_history_admin(
    code: str = Query(..., min_length=1, description="A 股代码"),
    start_date: Optional[str] = Query(None, description="起始日 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日 YYYY-MM-DD"),
    limit: int = Query(120, ge=1, le=500),
    db: Session = Depends(get_db),
    _: Any = Depends(get_current_admin),
):
    """管理端：单只股票 RS 历史追溯（日期降序）。"""
    from backend_core.indicators.rs_rating.service import list_rs_rating_history

    code_n = str(code or "").strip()
    if code_n.isdigit():
        code_n = code_n.zfill(6)
    if len(code_n) != 6 or not code_n.isdigit():
        raise HTTPException(status_code=400, detail="请提供 6 位 A 股代码")
    return list_rs_rating_history(
        db,
        code_n,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )


class RsForcePrecomputeBody(BaseModel):
    trade_date: Optional[str] = Field(
        None, description="单日 YYYY-MM-DD；缺省取行情最新交易日"
    )
    start_date: Optional[str] = Field(None, description="区间起点（需与 end_date 同用）")
    end_date: Optional[str] = Field(None, description="区间终点（需与 start_date 同用）")


@router.post("/rs-ratings/precompute")
async def post_rs_ratings_force_precompute(
    body: RsForcePrecomputeBody,
    db: Session = Depends(get_db),
    admin: Any = Depends(get_current_admin),
):
    """管理端：强制重算指定交易日（或短区间）全市场 RS 截面。"""
    from backend_core.indicators.rs_rating.force_precompute import (
        resolve_force_trade_dates,
        start_precompute,
    )

    try:
        dates = resolve_force_trade_dates(
            trade_date=body.trade_date,
            start_date=body.start_date,
            end_date=body.end_date,
        )
        task_id = start_precompute(dates)
        _write_operation_log(
            db,
            log_type="rs_rating_force_precompute",
            message=(
                f"RS 强制预计算启动 dates={','.join(dates)} "
                f"by {getattr(admin, 'username', 'admin')}"
            ),
            status="成功",
            affected=len(dates),
            error=None,
        )
        return {
            "success": True,
            "task_id": task_id,
            "trade_dates": dates,
            "message": f"已启动全市场强制预计算（{len(dates)} 日）",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.get("/rs-ratings/precompute/{task_id}")
async def get_rs_ratings_force_precompute(
    task_id: str,
    _: Any = Depends(get_current_admin),
):
    """管理端：查询强制预计算任务进度。"""
    from backend_core.indicators.rs_rating.force_precompute import get_task

    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return {"success": True, "data": task}

