"""
板块成分股管理（行业 / 概念）— 管理端 API
"""

from __future__ import annotations

import csv
import logging
from datetime import datetime
from io import BytesIO, StringIO
from typing import Any, List, Literal, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend_api.admin.board_constituents_import import (
    parse_all_constituents_file,
    parse_constituents_file,
    resolve_rows_stock_codes,
)
from backend_api.auth import get_current_admin
from backend_api.database import get_db
from backend_api.models import ConceptBoardConstituent, IndustryBoardConstituent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/board-constituents", tags=["admin_board_constituents"])

BoardType = Literal["industry", "concept"]


def _normalize_board_code(raw: Any) -> str:
    s = str(raw or "").strip().upper()
    s = s.lstrip("'").lstrip("’").strip()
    return s


def _normalize_stock_code(raw: Any) -> str:
    s = str(raw or "").strip().upper()
    s = s.lstrip("'").lstrip("’").strip()
    if not s:
        return ""
    while s and s[0].isalpha():
        s = s[1:]
    if "." in s:
        s = s.split(".")[0]
    if s.isdigit() and len(s) < 6:
        s = s.zfill(6)
    return s


def _tables(board_type: BoardType) -> dict[str, str]:
    if board_type == "industry":
        return {
            "basic": "industry_board_basic_info",
            "constituents": "industry_board_constituents",
            "realtime": "industry_board_realtime_quotes",
        }
    return {
        "basic": "concept_board_basic_info",
        "constituents": "concept_board_constituents",
        "realtime": "",
    }


def _constituent_model(board_type: BoardType):
    return IndustryBoardConstituent if board_type == "industry" else ConceptBoardConstituent


def _upsert_constituents(
    db: Session,
    board_type: BoardType,
    board_code: str,
    stocks: List[BoardStockItem],
) -> tuple[int, int]:
    """返回 (处理条数, 新增条数)。"""
    bcode = _normalize_board_code(board_code)
    Model = _constituent_model(board_type)
    now = datetime.now().replace(microsecond=0)
    added = 0
    processed = 0
    for item in stocks:
        scode = _normalize_stock_code(item.stock_code)
        if not scode:
            continue
        processed += 1
        row = db.query(Model).filter(Model.board_code == bcode, Model.stock_code == scode).first()
        name = (item.stock_name or "").strip() or None
        if row:
            if name:
                row.stock_name = name
            row.updated_at = now
        else:
            db.add(
                Model(
                    board_code=bcode,
                    stock_code=scode,
                    stock_name=name,
                    updated_at=now,
                )
            )
            added += 1
    return processed, added


class BoardStockItem(BaseModel):
    stock_code: str
    stock_name: Optional[str] = None


class AddBoardConstituentsBody(BaseModel):
    board_type: BoardType
    board_code: str
    stocks: List[BoardStockItem] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _validate(self):
        if not _normalize_board_code(self.board_code):
            raise ValueError("板块代码无效")
        return self


class RemoveBoardConstituentsBody(BaseModel):
    board_type: BoardType
    board_code: str
    scope: Literal["selected", "all"] = "selected"
    stock_codes: Optional[List[str]] = None

    @model_validator(mode="after")
    def _validate(self):
        if not _normalize_board_code(self.board_code):
            raise ValueError("板块代码无效")
        if self.scope == "selected" and not self.stock_codes:
            raise ValueError("请选择要删除的成分股")
        return self


class SyncBoardConstituentsBody(BaseModel):
    board_type: BoardType
    board_codes: Optional[List[str]] = None
    sync_board_list: bool = False


@router.get("/boards")
async def list_boards_with_summary(
    board_type: BoardType = Query(..., description="industry 或 concept"),
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_admin),
):
    """板块列表及成分股数量统计。"""
    _ = current_user
    t = _tables(board_type)
    kw = (keyword or "").strip()
    kw_filter = ""
    params: dict[str, Any] = {"limit": page_size, "offset": (page - 1) * page_size}
    if kw:
        kw_filter = "AND (src.board_code ILIKE :kw OR src.board_name ILIKE :kw)"
        params["kw"] = f"%{kw}%"

    if board_type == "industry":
        board_src_sql = f"""
            SELECT board_code, board_name FROM {t['basic']}
            WHERE UPPER(board_code) NOT LIKE 'BK%'
            UNION
            SELECT DISTINCT board_code, board_name FROM {t['realtime']}
            WHERE board_code IS NOT NULL AND board_code <> ''
              AND UPPER(board_code) NOT LIKE 'BK%'
        """
    else:
        board_src_sql = f"SELECT board_code, board_name FROM {t['basic']}"

    count_sql = text(
        f"""
        SELECT COUNT(*) FROM (
            SELECT DISTINCT src.board_code
            FROM ({board_src_sql}) src
            WHERE 1=1 {kw_filter}
        ) x
        """
    )
    total = db.execute(count_sql, params).scalar() or 0

    list_sql = text(
        f"""
        SELECT
            src.board_code,
            src.board_name,
            COALESCE(cnt.cnt, 0) AS constituent_count,
            cnt.last_updated
        FROM (
            SELECT board_code, MAX(board_name) AS board_name
            FROM ({board_src_sql}) u
            WHERE board_code IS NOT NULL AND board_code <> ''
            GROUP BY board_code
        ) src
        LEFT JOIN (
            SELECT board_code, COUNT(*) AS cnt, MAX(updated_at) AS last_updated
            FROM {t['constituents']}
            GROUP BY board_code
        ) cnt ON cnt.board_code = src.board_code
        WHERE 1=1 {kw_filter}
        ORDER BY src.board_code
        LIMIT :limit OFFSET :offset
        """
    )
    rows = db.execute(list_sql, params).fetchall()
    data = [
        {
            "board_code": r[0],
            "board_name": r[1],
            "constituent_count": int(r[2] or 0),
            "last_updated": r[3].isoformat() if r[3] else None,
        }
        for r in rows
    ]
    return {"success": True, "data": data, "total": total, "page": page, "page_size": page_size}


@router.get("/list")
async def list_board_constituents(
    board_type: BoardType = Query(...),
    board_code: str = Query(...),
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_admin),
):
    """某板块成分股分页列表。"""
    _ = current_user
    bcode = _normalize_board_code(board_code)
    if not bcode:
        raise HTTPException(status_code=400, detail="板块代码无效")
    Model = _constituent_model(board_type)
    q = db.query(Model).filter(Model.board_code == bcode)
    kw = (keyword or "").strip()
    if kw:
        q = q.filter(
            (Model.stock_code.ilike(f"%{kw}%")) | (Model.stock_name.ilike(f"%{kw}%"))
        )
    total = q.count()
    items = (
        q.order_by(Model.stock_code)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "success": True,
        "data": [
            {
                "board_code": i.board_code,
                "stock_code": i.stock_code,
                "stock_name": i.stock_name,
                "updated_at": i.updated_at.isoformat() if i.updated_at else None,
            }
            for i in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "board_code": bcode,
    }


@router.post("/add")
async def add_board_constituents(
    body: AddBoardConstituentsBody,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_admin),
):
    """手动添加成分股（存在则更新名称）。"""
    bcode = _normalize_board_code(body.board_code)
    if not bcode:
        raise HTTPException(status_code=400, detail="板块代码无效")
    processed, added = _upsert_constituents(db, body.board_type, bcode, body.stocks)
    db.commit()
    uname = getattr(current_user, "username", None) or "admin"
    return {
        "success": True,
        "message": f"已保存 {processed} 条（新增 {added} 条）",
        "data": {"added": added, "processed": processed, "operator": uname},
    }


@router.post("/remove")
async def remove_board_constituents(
    body: RemoveBoardConstituentsBody,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_admin),
):
    """删除成分股（选中或整板清空）。"""
    bcode = _normalize_board_code(body.board_code)
    Model = _constituent_model(body.board_type)
    q = db.query(Model).filter(Model.board_code == bcode)
    if body.scope == "selected":
        codes = [_normalize_stock_code(c) for c in (body.stock_codes or [])]
        codes = [c for c in codes if c]
        if not codes:
            raise HTTPException(status_code=400, detail="股票代码无效")
        q = q.filter(Model.stock_code.in_(codes))
    deleted = q.delete(synchronize_session=False)
    db.commit()
    uname = getattr(current_user, "username", None) or "admin"
    return {
        "success": True,
        "message": f"已删除 {deleted} 条成分股",
        "data": {"deleted": deleted, "operator": uname},
    }


@router.post("/sync")
async def sync_board_constituents(
    body: SyncBoardConstituentsBody,
    current_user: Any = Depends(get_current_admin),
):
    """从东财同步成分股（可选先同步板块列表）。"""
    uname = getattr(current_user, "username", None) or "admin"
    try:
        if body.sync_board_list and body.board_type == "concept":
            from backend_core.data_collectors.akshare.concept_board_basic_ak import (
                ConceptBoardBasicCollector,
            )

            ConceptBoardBasicCollector().run()

        codes = body.board_codes if body.board_codes else None
        if body.board_type == "industry":
            from backend_core.data_collectors.akshare.industry_board_constituents_ak import (
                IndustryBoardConstituentsCollector,
            )

            IndustryBoardConstituentsCollector().run(board_codes=codes)
        else:
            from backend_core.data_collectors.akshare.concept_board_constituents_ak import (
                ConceptBoardConstituentsCollector,
            )

            ConceptBoardConstituentsCollector().run(board_codes=codes)
        scope = "全部" if not codes else f"{len(codes)} 个板块"
        return {
            "success": True,
            "message": f"{'行业' if body.board_type == 'industry' else '概念'}成分股同步完成（{scope}，操作人 {uname}）",
        }
    except Exception as e:
        logger.exception("板块成分股同步失败")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.get("/export/all")
async def export_all_constituents(
    board_type: BoardType = Query(...),
    format: str = Query("xlsx", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_admin),
):
    """导出当前类型下全部板块成分股。"""
    _ = current_user
    t = _tables(board_type)
    label = "industry" if board_type == "industry" else "concept"
    sql = text(
        f"""
        SELECT
            c.board_code,
            COALESCE(b.board_name, '') AS board_name,
            c.stock_code,
            COALESCE(c.stock_name, '') AS stock_name,
            c.updated_at
        FROM {t['constituents']} c
        LEFT JOIN (
            SELECT board_code, MAX(board_name) AS board_name
            FROM {t['basic']}
            GROUP BY board_code
        ) b ON b.board_code = c.board_code
        ORDER BY c.board_code, c.stock_code
        """
    )
    rows = db.execute(sql).fetchall()
    cols = ["board_code", "board_name", "stock_code", "stock_name", "updated_at"]
    data = [
        [
            r[0],
            r[1],
            r[2],
            r[3],
            r[4].strftime("%Y-%m-%d %H:%M:%S") if r[4] else "",
        ]
        for r in rows
    ]
    if format == "csv":
        sio = StringIO()
        writer = csv.writer(sio)
        writer.writerow(cols)
        writer.writerows(data)
        return StreamingResponse(
            iter([sio.getvalue().encode("utf-8-sig")]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={label}_board_constituents_all.csv",
            },
        )
    df = pd.DataFrame(data, columns=cols)
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="constituents")
    bio.seek(0)
    return StreamingResponse(
        bio,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={label}_board_constituents_all.xlsx",
        },
    )


@router.get("/import/all/template")
async def download_all_constituents_template(
    format: str = Query("xlsx", pattern="^(csv|xlsx)$"),
    _: Any = Depends(get_current_admin),
):
    """下载全量成分股导入模板。"""
    cols = ["board_code", "board_name", "stock_code", "stock_name"]
    sample = [
        ["IT服务", "IT服务", "000001", "平安银行"],
        ["IT服务", "IT服务", "", "神州数码"],
        ["半导体", "半导体", "688981", "中芯国际"],
    ]
    if format == "csv":
        sio = StringIO()
        writer = csv.writer(sio)
        writer.writerow(cols)
        writer.writerows(sample)
        return StreamingResponse(
            iter([sio.getvalue().encode("utf-8-sig")]),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=board_constituents_all_template.csv",
            },
        )
    df = pd.DataFrame(sample, columns=cols)
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="constituents")
    bio.seek(0)
    return StreamingResponse(
        bio,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=board_constituents_all_template.xlsx",
        },
    )


@router.post("/import/all")
async def import_all_board_constituents(
    board_type: BoardType = Query(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_admin),
):
    """Excel/CSV 全量导入多板块成分股。"""
    content = await file.read()
    rows, issues = parse_all_constituents_file(file.filename or "", content)
    if not rows:
        return {
            "success": False,
            "message": "未导入任何有效数据",
            "data": {"issues": issues[:200]},
        }

    stock_rows = [{"stock_code": r["stock_code"], "stock_name": r["stock_name"]} for r in rows]
    resolved, resolve_issues = resolve_rows_stock_codes(db, stock_rows)
    issues.extend(resolve_issues)

    issue_row_nos = {
        int(iss["row_no"])
        for iss in resolve_issues
        if iss.get("row_no") is not None
    }
    aligned: List[Dict[str, str]] = []
    res_idx = 0
    for i, src in enumerate(rows):
        row_no = i + 2
        if row_no in issue_row_nos:
            continue
        if res_idx >= len(resolved):
            break
        item = resolved[res_idx]
        res_idx += 1
        aligned.append({
            "board_code": src["board_code"],
            "stock_code": item["stock_code"],
            "stock_name": item.get("stock_name") or src.get("stock_name") or "",
        })

    if not aligned:
        return {
            "success": False,
            "message": "未导入任何有效数据",
            "data": {"issues": issues[:200]},
        }

    board_stats: dict[str, dict[str, int]] = {}
    total_processed = 0
    total_added = 0
    for bcode in sorted({r["board_code"] for r in aligned}):
        group = [r for r in aligned if r["board_code"] == bcode]
        stocks = [
            BoardStockItem(stock_code=r["stock_code"], stock_name=r.get("stock_name") or None)
            for r in group
        ]
        processed, added = _upsert_constituents(db, board_type, bcode, stocks)
        board_stats[bcode] = {"processed": processed, "added": added}
        total_processed += processed
        total_added += added
    db.commit()

    uname = getattr(current_user, "username", None) or "admin"
    msg = (
        f"全量导入完成：{len(board_stats)} 个板块，"
        f"有效 {total_processed} 条，新增 {total_added} 条"
    )
    if issues:
        msg += f"，跳过/告警 {len(issues)} 条"
    return {
        "success": True,
        "message": msg,
        "data": {
            "boards_processed": len(board_stats),
            "processed": total_processed,
            "added": total_added,
            "skipped_issues": len(issues),
            "issues": issues[:50],
            "board_stats": [
                {"board_code": k, **v} for k, v in sorted(board_stats.items())
            ],
            "operator": uname,
        },
    }


@router.get("/import/template")
async def download_constituents_template(
    format: str = Query("xlsx", pattern="^(csv|xlsx)$"),
    _: Any = Depends(get_current_admin),
):
    """下载成分股导入模板（stock_code, stock_name）。"""
    cols = ["stock_code", "stock_name"]
    sample = [["000001", "平安银行"], ["600519", "贵州茅台"]]
    if format == "csv":
        sio = StringIO()
        writer = csv.writer(sio)
        writer.writerow(cols)
        writer.writerows(sample)
        return StreamingResponse(
            iter([sio.getvalue().encode("utf-8-sig")]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=board_constituents_template.csv"},
        )
    df = pd.DataFrame(sample, columns=cols)
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="constituents")
    bio.seek(0)
    return StreamingResponse(
        bio,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=board_constituents_template.xlsx"},
    )


@router.post("/import")
async def import_board_constituents(
    board_type: BoardType = Query(...),
    board_code: str = Query(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_admin),
):
    """Excel/CSV 导入成分股到指定板块。"""
    bcode = _normalize_board_code(board_code)
    if not bcode:
        raise HTTPException(status_code=400, detail="板块代码无效")
    content = await file.read()
    rows, issues = parse_constituents_file(file.filename or "", content)
    rows, resolve_issues = resolve_rows_stock_codes(db, rows)
    issues.extend(resolve_issues)
    if not rows:
        return {
            "success": False,
            "message": "未导入任何有效数据",
            "data": {"issues": issues[:200]},
        }
    stocks = [BoardStockItem(stock_code=r["stock_code"], stock_name=r.get("stock_name") or None) for r in rows]
    processed, added = _upsert_constituents(db, board_type, bcode, stocks)
    db.commit()
    uname = getattr(current_user, "username", None) or "admin"
    msg = f"导入完成：有效 {processed} 条，新增 {added} 条"
    if issues:
        msg += f"，跳过/告警 {len(issues)} 条"
    return {
        "success": True,
        "message": msg,
        "data": {
            "processed": processed,
            "added": added,
            "skipped_issues": len(issues),
            "issues": issues[:50],
            "operator": uname,
        },
    }
