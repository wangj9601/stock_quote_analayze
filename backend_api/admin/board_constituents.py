"""
板块成分股管理（行业 / 概念）— 管理端 API
"""

from __future__ import annotations

import csv
import logging
from datetime import datetime
from io import BytesIO, StringIO
from typing import Any, Iterable, List, Literal, Optional

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
from backend_api.utils.bk_board_code import (
    assert_bk_available_for_board_type,
    generate_next_bk_board_code,
    is_valid_bk_board_code,
    is_valid_industry_board_code,
    normalize_bk_board_code,
    normalize_industry_board_code,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/board-constituents", tags=["admin_board_constituents"])

BoardType = Literal["industry", "concept"]


def _normalize_board_code(raw: Any) -> str:
    return normalize_bk_board_code(raw)


def _normalize_board_code_for_type(board_type: BoardType, raw: Any) -> str:
    if board_type == "industry":
        return normalize_industry_board_code(raw)
    return normalize_bk_board_code(raw)


def _is_valid_board_code_for_type(board_type: BoardType, code: str) -> bool:
    if board_type == "industry":
        return is_valid_industry_board_code(code)
    return is_valid_bk_board_code(code)


def _resolve_delete_board_code(board_type: BoardType, raw: Any) -> str:
    """删除时使用：行业板块走统一规范化；概念板块仅 BK。"""
    if board_type == "industry":
        return normalize_industry_board_code(raw)
    return _normalize_board_code(raw)


def _delete_industry_realtime_quotes(db: Session, board_codes: Iterable[str]) -> int:
    """删除行业板块实时行情（维护删板时可选清理，列表不读 realtime）。"""
    deleted = 0
    for bcode in board_codes:
        code = str(bcode or "").strip()
        if not code:
            continue
        deleted += db.execute(
            text("DELETE FROM industry_board_realtime_quotes WHERE board_code = :code"),
            {"code": code},
        ).rowcount or 0
    return deleted


def _industry_board_src_sql(t: dict[str, str]) -> str:
    """管理端行业板块列表：仅 industry_board_basic_info，不含实时行情表。"""
    return f"""
        SELECT board_code, board_name, create_date,
               COALESCE(trade_observe_flag, FALSE) AS trade_observe_flag
        FROM {t['basic']}
    """


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


def ensure_board_trade_observe_columns(db: Session) -> None:
    """确保行业/概念板块基础表存在 trade_observe_flag 列（兼容未跑迁移的库）。"""
    for table in ("industry_board_basic_info", "concept_board_basic_info"):
        db.execute(
            text(
                f"""
                ALTER TABLE {table}
                ADD COLUMN IF NOT EXISTS trade_observe_flag BOOLEAN NOT NULL DEFAULT FALSE
                """
            )
        )


def _constituent_model(board_type: BoardType):
    return IndustryBoardConstituent if board_type == "industry" else ConceptBoardConstituent


def _upsert_constituents(
    db: Session,
    board_type: BoardType,
    board_code: str,
    stocks: List[BoardStockItem],
) -> tuple[int, int]:
    """返回 (处理条数, 新增条数)。"""
    bcode = _normalize_board_code_for_type(board_type, board_code)
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
        code = _normalize_board_code_for_type(self.board_type, self.board_code)
        if not code:
            raise ValueError("板块代码无效")
        self.board_code = code
        return self


class RemoveBoardConstituentsBody(BaseModel):
    board_type: BoardType
    board_code: str
    scope: Literal["selected", "all"] = "selected"
    stock_codes: Optional[List[str]] = None

    @model_validator(mode="after")
    def _validate(self):
        code = _normalize_board_code_for_type(self.board_type, self.board_code)
        if not code:
            raise ValueError("板块代码无效")
        self.board_code = code
        if self.scope == "selected" and not self.stock_codes:
            raise ValueError("请选择要删除的成分股")
        return self


class SyncBoardConstituentsBody(BaseModel):
    board_type: BoardType
    board_codes: Optional[List[str]] = None
    sync_board_list: bool = False


def _generate_next_concept_board_code(
    db: Session,
    after_code: Optional[str] = None,
) -> str:
    """兼容旧名：生成全局未占用的 BK 编码。"""
    return generate_next_bk_board_code(db, after_code=after_code)


def _generate_next_industry_board_code(
    db: Session,
    after_code: Optional[str] = None,
) -> str:
    return generate_next_bk_board_code(db, after_code=after_code)


def _assert_board_code_format(board_type: BoardType, code: str) -> None:
    if _is_valid_board_code_for_type(board_type, code):
        return
    if board_type == "industry":
        detail = "行业板块代码须为 BK+数字、中文或英文字符（1~20 位）"
    else:
        detail = "板块代码须为 BK+数字 格式（如 BK0428）"
    raise HTTPException(status_code=400, detail=detail)


class SaveBoardInfoBody(BaseModel):
    board_type: BoardType
    board_code: Optional[str] = Field(None, description="保存后的板块代码；概念板块新增可留空自动生成")
    board_name: Optional[str] = None
    trade_observe_flag: Optional[bool] = Field(
        None,
        description="交易观察标志；编辑保存时传入则更新",
    )
    original_board_code: Optional[str] = Field(
        None,
        description="编辑时原板块代码；改名时与 board_code 不同",
    )

    @model_validator(mode="after")
    def _validate(self):
        bt = self.board_type
        if self.original_board_code:
            old = _normalize_board_code_for_type(bt, self.original_board_code)
            if not old:
                raise ValueError("原板块代码无效")
            self.original_board_code = old
        if self.board_code is not None and str(self.board_code).strip():
            code = _normalize_board_code_for_type(bt, self.board_code)
            if not code:
                raise ValueError("板块代码无效")
            if not _is_valid_board_code_for_type(bt, code):
                if bt == "industry":
                    raise ValueError("行业板块代码须为 BK+数字、中文或英文字符")
                raise ValueError("板块代码须为 BK+数字 格式")
            self.board_code = code
        return self


class SetBoardTradeObserveBody(BaseModel):
    board_type: BoardType
    board_code: str
    trade_observe_flag: bool

    @model_validator(mode="after")
    def _validate(self):
        code = _normalize_board_code_for_type(self.board_type, self.board_code)
        if not code:
            raise ValueError("板块代码无效")
        self.board_code = code
        return self


class DeleteBoardBody(BaseModel):
    board_type: BoardType
    board_code: str

    @model_validator(mode="after")
    def _validate(self):
        code = _resolve_delete_board_code(self.board_type, self.board_code)
        if not code:
            raise ValueError("板块代码无效")
        self.board_code = code
        return self


class DeleteBoardsBatchBody(BaseModel):
    board_type: BoardType
    board_codes: List[str] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _validate(self):
        codes = list(dict.fromkeys(
            c for x in self.board_codes
            if (c := _resolve_delete_board_code(self.board_type, x))
        ))
        if not codes:
            raise ValueError("板块代码无效")
        self.board_codes = codes
        return self


def _read_board_trade_observe_flag(db: Session, board_type: BoardType, board_code: str) -> bool:
    ensure_board_trade_observe_columns(db)
    t = _tables(board_type)
    row = db.execute(
        text(f"SELECT trade_observe_flag FROM {t['basic']} WHERE board_code = :code LIMIT 1"),
        {"code": board_code},
    ).fetchone()
    if not row or row[0] is None:
        return False
    return bool(row[0])


def _upsert_board_basic(
    db: Session,
    board_type: BoardType,
    board_code: str,
    board_name: Optional[str],
    now: datetime,
    trade_observe_flag: Optional[bool] = None,
) -> None:
    ensure_board_trade_observe_columns(db)
    t = _tables(board_type)
    if trade_observe_flag is not None:
        db.execute(
            text(
                f"""
                INSERT INTO {t['basic']} (board_code, board_name, create_date, trade_observe_flag)
                VALUES (:board_code, :board_name, :create_date, :trade_observe_flag)
                ON CONFLICT (board_code) DO UPDATE SET
                    board_name = COALESCE(EXCLUDED.board_name, {t['basic']}.board_name),
                    trade_observe_flag = EXCLUDED.trade_observe_flag
                """
            ),
            {
                "board_code": board_code,
                "board_name": board_name,
                "create_date": now,
                "trade_observe_flag": trade_observe_flag,
            },
        )
        return
    db.execute(
        text(
            f"""
            INSERT INTO {t['basic']} (board_code, board_name, create_date, trade_observe_flag)
            VALUES (:board_code, :board_name, :create_date, FALSE)
            ON CONFLICT (board_code) DO UPDATE SET
                board_name = EXCLUDED.board_name
            """
        ),
        {
            "board_code": board_code,
            "board_name": board_name,
            "create_date": now,
        },
    )


def _assert_concept_board_name_unique(
    db: Session,
    board_name: str,
    exclude_codes: Optional[list[str]] = None,
) -> None:
    """概念板块名称不可与其它板块重复（编辑时排除当前板块代码）。"""
    name = (board_name or "").strip()
    if not name:
        return
    excludes = {_normalize_board_code(c) for c in (exclude_codes or []) if c}
    row = db.execute(
        text(
            """
            SELECT board_code FROM concept_board_basic_info
            WHERE TRIM(board_name) = :name
            LIMIT 1
            """
        ),
        {"name": name},
    ).fetchone()
    if not row:
        return
    code = _normalize_board_code(row[0])
    if code not in excludes:
        raise HTTPException(
            status_code=400,
            detail=f"概念板块名称「{name}」已存在（{code}）",
        )


def _clear_all_concept_boards(db: Session) -> tuple[int, int]:
    """清空全部概念板块基本信息与成分股。"""
    Model = _constituent_model("concept")
    cons_deleted = db.query(Model).delete(synchronize_session=False)
    basic_deleted = db.execute(text("DELETE FROM concept_board_basic_info")).rowcount
    return int(cons_deleted or 0), int(basic_deleted or 0)


def _sync_concept_board_basic_from_import(
    db: Session,
    rows: List[Dict[str, str]],
    now: datetime,
    issues: List[Dict[str, Any]],
) -> int:
    """从全量导入数据同步 concept_board_basic_info（按板块代码聚合名称）。"""
    board_names: dict[str, str] = {}
    for r in rows:
        code = _normalize_board_code(r.get("board_code"))
        if not code:
            continue
        name = (r.get("board_name") or "").strip()
        if code not in board_names:
            board_names[code] = name
        elif name and not board_names[code]:
            board_names[code] = name

    synced = 0
    for code in sorted(board_names.keys()):
        raw_name = board_names[code]
        upsert_name: Optional[str] = raw_name.strip() or None if raw_name else None
        if upsert_name:
            dup = db.execute(
                text(
                    """
                    SELECT board_code FROM concept_board_basic_info
                    WHERE TRIM(board_name) = :name AND board_code <> :code
                    LIMIT 1
                    """
                ),
                {"name": upsert_name, "code": code},
            ).fetchone()
            if dup:
                dup_code = _normalize_board_code(dup[0])
                issues.append({
                    "row_no": 0,
                    "board_code": code,
                    "message": f"板块名称「{upsert_name}」已与 {dup_code} 重复，仅写入板块代码",
                })
                upsert_name = None
        _upsert_board_basic(db, "concept", code, upsert_name, now)
        synced += 1
    return synced


def _rename_board_records(
    db: Session,
    board_type: BoardType,
    old_code: str,
    new_code: str,
    board_name: Optional[str],
    trade_observe_flag: Optional[bool] = None,
) -> None:
    t = _tables(board_type)
    exists = db.execute(
        text(f"SELECT 1 FROM {t['basic']} WHERE board_code = :code LIMIT 1"),
        {"code": new_code},
    ).scalar()
    if exists and new_code != old_code:
        raise HTTPException(status_code=400, detail=f"板块代码「{new_code}」已存在")

    cons_exists = db.execute(
        text(f"SELECT 1 FROM {t['constituents']} WHERE board_code = :code LIMIT 1"),
        {"code": new_code},
    ).scalar()
    if cons_exists and new_code != old_code:
        raise HTTPException(status_code=400, detail=f"板块代码「{new_code}」在成分股表中已存在")

    preserved_flag = _read_board_trade_observe_flag(db, board_type, old_code)
    flag_to_save = trade_observe_flag if trade_observe_flag is not None else preserved_flag

    if old_code != new_code:
        db.execute(
            text(f"UPDATE {t['constituents']} SET board_code = :new WHERE board_code = :old"),
            {"new": new_code, "old": old_code},
        )
        if board_type == "industry" and t.get("realtime"):
            db.execute(
                text(
                    f"""
                    UPDATE {t['realtime']}
                    SET board_code = :new, board_name = COALESCE(:name, board_name)
                    WHERE board_code = :old
                    """
                ),
                {"new": new_code, "old": old_code, "name": board_name},
            )
        db.execute(
            text(f"DELETE FROM {t['basic']} WHERE board_code = :old"),
            {"old": old_code},
        )

    now = datetime.now().replace(microsecond=0)
    _upsert_board_basic(
        db,
        board_type,
        new_code,
        board_name,
        now,
        trade_observe_flag=flag_to_save,
    )
    if board_type == "industry" and t.get("realtime") and board_name and old_code == new_code:
        db.execute(
            text(f"UPDATE {t['realtime']} SET board_name = :name WHERE board_code = :code"),
            {"name": board_name, "code": new_code},
        )


@router.get("/boards/next-code")
async def get_next_board_code(
    board_type: BoardType = Query(...),
    after_code: Optional[str] = Query(
        None,
        description="当前预览编码；传入后返回其后的下一个可用 BK 编码",
    ),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_admin),
):
    """预览下一个可用 BK 编码（行业/概念均全局唯一）。"""
    _ = current_user
    code = generate_next_bk_board_code(db, after_code=after_code)
    return {"success": True, "data": {"board_code": code}}


@router.post("/boards/save")
async def save_board_info(
    body: SaveBoardInfoBody,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_admin),
):
    """新增或编辑板块基础信息（支持改名并联动成分股）。"""
    raw_code = (body.board_code or "").strip()
    board_name = (body.board_name or "").strip() or None
    now = datetime.now().replace(microsecond=0)

    if body.original_board_code:
        if not raw_code:
            raise HTTPException(status_code=400, detail="编辑时板块代码不能为空")
        new_code = _normalize_board_code_for_type(body.board_type, raw_code)
        old_code = _normalize_board_code_for_type(body.board_type, body.original_board_code)
    elif raw_code:
        new_code = _normalize_board_code_for_type(body.board_type, raw_code)
        old_code = new_code
    elif body.board_type == "concept":
        new_code = _generate_next_concept_board_code(db)
        old_code = new_code
    elif body.board_type == "industry":
        name_code = normalize_industry_board_code(board_name) if board_name else ""
        new_code = name_code or _generate_next_industry_board_code(db)
        old_code = new_code
    else:
        raise HTTPException(status_code=400, detail="板块代码无效")

    _assert_board_code_format(body.board_type, new_code)
    if is_valid_bk_board_code(new_code):
        assert_bk_available_for_board_type(
            db,
            body.board_type,
            new_code,
            exclude_codes=[c for c in {new_code, old_code} if c],
        )

    if body.board_type == "concept" and board_name:
        _assert_concept_board_name_unique(
            db,
            board_name,
            exclude_codes=[c for c in {new_code, old_code} if c],
        )

    if old_code != new_code:
        _rename_board_records(
            db,
            body.board_type,
            old_code,
            new_code,
            board_name,
            trade_observe_flag=body.trade_observe_flag,
        )
        action = "rename"
    else:
        t = _tables(body.board_type)
        had_basic = bool(
            db.execute(
                text(f"SELECT 1 FROM {t['basic']} WHERE board_code = :code LIMIT 1"),
                {"code": new_code},
            ).scalar()
        )
        _upsert_board_basic(
            db,
            body.board_type,
            new_code,
            board_name,
            now,
            trade_observe_flag=body.trade_observe_flag,
        )
        if body.board_type == "industry" and t.get("realtime") and board_name:
            db.execute(
                text(f"UPDATE {t['realtime']} SET board_name = :name WHERE board_code = :code"),
                {"name": board_name, "code": new_code},
            )
        if body.original_board_code:
            action = "update"
        else:
            action = "update" if had_basic else "create"

    db.commit()
    uname = getattr(current_user, "username", None) or "admin"
    saved_flag = (
        body.trade_observe_flag
        if body.trade_observe_flag is not None
        else _read_board_trade_observe_flag(db, body.board_type, new_code)
    )
    return {
        "success": True,
        "message": "板块信息已保存",
        "data": {
            "action": action,
            "board_code": new_code,
            "board_name": board_name,
            "trade_observe_flag": saved_flag,
            "original_board_code": old_code if old_code != new_code else None,
            "operator": uname,
        },
    }


@router.post("/boards/trade-observe")
async def set_board_trade_observe_flag(
    body: SetBoardTradeObserveBody,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_admin),
):
    """设置板块交易观察标志（列表内快捷开关）。"""
    _ = current_user
    bcode = body.board_code
    now = datetime.now().replace(microsecond=0)
    t = _tables(body.board_type)
    existing_name = db.execute(
        text(f"SELECT board_name FROM {t['basic']} WHERE board_code = :code LIMIT 1"),
        {"code": bcode},
    ).scalar()
    if existing_name is None and body.board_type == "industry" and t.get("realtime"):
        existing_name = db.execute(
            text(
                f"""
                SELECT MAX(board_name) FROM {t['realtime']}
                WHERE board_code = :code
                """
            ),
            {"code": bcode},
        ).scalar()
    _upsert_board_basic(
        db,
        body.board_type,
        bcode,
        (str(existing_name).strip() if existing_name else None) or None,
        now,
        trade_observe_flag=body.trade_observe_flag,
    )
    db.commit()
    return {
        "success": True,
        "message": "交易观察标志已更新",
        "data": {
            "board_code": bcode,
            "trade_observe_flag": body.trade_observe_flag,
        },
    }


@router.post("/boards/delete")
async def delete_board_info(
    body: DeleteBoardBody,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_admin),
):
    """删除板块基础信息、成分股；行业板块同时删实时行情表。"""
    bcode = body.board_code
    t = _tables(body.board_type)
    Model = _constituent_model(body.board_type)
    cons_deleted = db.query(Model).filter(Model.board_code == bcode).delete(synchronize_session=False)
    basic_deleted = db.execute(
        text(f"DELETE FROM {t['basic']} WHERE board_code = :code"),
        {"code": bcode},
    ).rowcount
    realtime_deleted = 0
    if body.board_type == "industry":
        realtime_deleted = _delete_industry_realtime_quotes(db, [bcode])
    db.commit()
    uname = getattr(current_user, "username", None) or "admin"
    extra = f"，实时行情 {realtime_deleted} 条" if body.board_type == "industry" else ""
    return {
        "success": True,
        "message": f"已删除板块「{bcode}」（成分股 {cons_deleted} 条{extra}）",
        "data": {
            "board_code": bcode,
            "constituents_deleted": cons_deleted,
            "basic_deleted": basic_deleted,
            "realtime_deleted": realtime_deleted,
            "operator": uname,
        },
    }


@router.post("/boards/delete-batch")
async def delete_boards_batch(
    body: DeleteBoardsBatchBody,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_admin),
):
    """批量删除板块基础信息、成分股；行业板块同时删实时行情表。"""
    codes = body.board_codes
    t = _tables(body.board_type)
    Model = _constituent_model(body.board_type)
    cons_deleted = (
        db.query(Model)
        .filter(Model.board_code.in_(codes))
        .delete(synchronize_session=False)
    )
    basic_deleted = 0
    for bcode in codes:
        basic_deleted += db.execute(
            text(f"DELETE FROM {t['basic']} WHERE board_code = :code"),
            {"code": bcode},
        ).rowcount
    realtime_deleted = 0
    if body.board_type == "industry":
        realtime_deleted = _delete_industry_realtime_quotes(db, codes)
    db.commit()
    uname = getattr(current_user, "username", None) or "admin"
    label = "行业板块" if body.board_type == "industry" else "概念板块"
    extra = f"，实时行情 {realtime_deleted} 条" if body.board_type == "industry" else ""
    return {
        "success": True,
        "message": f"已删除 {len(codes)} 个{label}（成分股 {cons_deleted} 条{extra}）",
        "data": {
            "board_codes": codes,
            "boards_deleted": len(codes),
            "constituents_deleted": cons_deleted,
            "basic_deleted": basic_deleted,
            "realtime_deleted": realtime_deleted,
            "operator": uname,
        },
    }


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
    ensure_board_trade_observe_columns(db)
    t = _tables(board_type)
    kw = (keyword or "").strip()
    kw_filter = ""
    params: dict[str, Any] = {"limit": page_size, "offset": (page - 1) * page_size}
    if kw:
        kw_filter = "AND (src.board_code ILIKE :kw OR src.board_name ILIKE :kw)"
        params["kw"] = f"%{kw}%"

    if board_type == "industry":
        board_src_sql = _industry_board_src_sql(t)
    else:
        board_src_sql = f"""
            SELECT board_code, board_name, create_date,
                   COALESCE(trade_observe_flag, FALSE) AS trade_observe_flag
            FROM {t['basic']}
        """

    count_sql = text(
        f"""
        SELECT COUNT(*) FROM (
            SELECT DISTINCT src.board_code
            FROM (
                SELECT board_code, MAX(board_name) AS board_name
                FROM ({board_src_sql}) u
                WHERE board_code IS NOT NULL AND board_code <> ''
                GROUP BY board_code
            ) src
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
            cnt.last_updated,
            src.create_date,
            src.trade_observe_flag
        FROM (
            SELECT
                board_code,
                MAX(board_name) AS board_name,
                MAX(create_date) AS create_date,
                BOOL_OR(trade_observe_flag) AS trade_observe_flag
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
        ORDER BY src.create_date DESC NULLS LAST, src.board_code
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
            "create_date": r[4].isoformat() if r[4] else None,
            "trade_observe_flag": bool(r[5]),
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
    bcode = _normalize_board_code_for_type(board_type, board_code)
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
    bcode = body.board_code
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
    bcode = body.board_code
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
    """导出当前类型下全部板块成分股（含无成分股的板块基本信息行）。"""
    _ = current_user
    t = _tables(board_type)
    label = "industry" if board_type == "industry" else "concept"
    if board_type == "industry":
        board_src_sql = f"""
            SELECT board_code, MAX(board_name) AS board_name
            FROM (
                SELECT board_code, board_name FROM {t['basic']}
                UNION ALL
                SELECT DISTINCT board_code, NULL::varchar AS board_name
                FROM {t['constituents']}
                WHERE board_code IS NOT NULL AND board_code <> ''
            ) u
            WHERE board_code IS NOT NULL AND board_code <> ''
            GROUP BY board_code
        """
    else:
        board_src_sql = f"""
            SELECT board_code, MAX(board_name) AS board_name
            FROM (
                SELECT board_code, board_name FROM {t['basic']}
                UNION ALL
                SELECT board_code, NULL AS board_name FROM {t['constituents']}
            ) u
            WHERE board_code IS NOT NULL AND board_code <> ''
            GROUP BY board_code
        """
    sql = text(
        f"""
        SELECT
            b.board_code,
            COALESCE(b.board_name, '') AS board_name,
            COALESCE(c.stock_code, '') AS stock_code,
            COALESCE(c.stock_name, '') AS stock_name,
            c.updated_at
        FROM ({board_src_sql}) b
        LEFT JOIN {t['constituents']} c ON c.board_code = b.board_code
        ORDER BY b.board_code, c.stock_code NULLS FIRST
        """
    )
    rows = db.execute(sql).fetchall()
    cols = ["board_code", "board_name", "stock_code", "stock_name", "updated_at"]
    data = [
        [
            str(r[0] or ""),
            str(r[1] or ""),
            str(r[2] or ""),
            str(r[3] or ""),
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
    """Excel/CSV 全量导入多板块成分股。概念板块会先清空原有数据再导入。"""
    content = await file.read()
    rows, issues = parse_all_constituents_file(file.filename or "", content, board_type=board_type)
    if not rows:
        return {
            "success": False,
            "message": "未导入任何有效数据",
            "data": {"issues": issues[:200]},
        }

    cleared_cons = 0
    cleared_basic = 0
    if board_type == "concept":
        cleared_cons, cleared_basic = _clear_all_concept_boards(db)

    stock_rows = [
        {"stock_code": r["stock_code"], "stock_name": r["stock_name"]}
        for r in rows
        if (r.get("stock_code") or "").strip() or (r.get("stock_name") or "").strip()
    ]
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
        if not (src.get("stock_code") or "").strip() and not (src.get("stock_name") or "").strip():
            continue
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

    now = datetime.now().replace(microsecond=0)
    basic_synced = 0
    if board_type == "concept":
        basic_synced = _sync_concept_board_basic_from_import(db, rows, now, issues)

    if not aligned:
        if basic_synced:
            db.commit()
            uname = getattr(current_user, "username", None) or "admin"
            msg = f"已同步板块基本信息 {basic_synced} 个（无有效成分股行可导入）"
            if board_type == "concept":
                msg = (
                    f"已清空原概念板块 {cleared_basic} 个、成分股 {cleared_cons} 条；"
                    + msg
                )
            if issues:
                msg += f"，告警 {len(issues)} 条"
            return {
                "success": True,
                "message": msg,
                "data": {
                    "boards_processed": 0,
                    "basic_synced": basic_synced,
                    "cleared_basic": cleared_basic,
                    "cleared_constituents": cleared_cons,
                    "processed": 0,
                    "added": 0,
                    "skipped_issues": len(issues),
                    "issues": issues[:50],
                    "board_stats": [],
                    "operator": uname,
                },
            }
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
    if board_type == "concept":
        msg = (
            f"已清空原概念板块 {cleared_basic} 个、成分股 {cleared_cons} 条；"
            + msg
        )
    if board_type == "concept" and basic_synced:
        msg += f"，同步板块基本信息 {basic_synced} 个"
    if issues:
        msg += f"，跳过/告警 {len(issues)} 条"
    return {
        "success": True,
        "message": msg,
        "data": {
            "boards_processed": len(board_stats),
            "basic_synced": basic_synced,
            "cleared_basic": cleared_basic if board_type == "concept" else 0,
            "cleared_constituents": cleared_cons if board_type == "concept" else 0,
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
    bcode = _normalize_board_code_for_type(board_type, board_code)
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
