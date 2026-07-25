"""
板块成分股管理（行业 / 概念）— 管理端 API
"""

from __future__ import annotations

import csv
import logging
import threading
from datetime import datetime
from io import BytesIO, StringIO
from typing import Any, Iterable, List, Literal, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from backend_api.admin.board_constituents_import import (
    align_all_import_constituent_rows,
    parse_all_constituents_file,
    parse_constituents_file,
    resolve_rows_stock_codes,
)
from backend_api.auth import get_current_admin
from backend_api.database import get_db
from backend_api.models import ConceptBoardConstituent, IndustryBoardConstituent
from backend_api.utils.board_code_source import (
    BOARD_CODE_SOURCE_OPTIONS,
    DEFAULT_BOARD_CODE_SOURCE,
    LEGACY_DEFAULT_BOARD_CODE_SOURCE,
    board_code_source_label,
    normalize_board_code_source,
    resolve_board_code_source,
)
from backend_api.utils.bk_board_code import (
    assert_bk_available_for_board_type,
    generate_next_bk_board_code,
    is_valid_bk_board_code,
    is_valid_concept_board_code,
    is_valid_industry_board_code,
    normalize_bk_board_code,
    normalize_concept_board_code,
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
    return normalize_concept_board_code(raw)


def _is_valid_board_code_for_type(board_type: BoardType, code: str) -> bool:
    if board_type == "industry":
        return is_valid_industry_board_code(code)
    return is_valid_concept_board_code(code)


def _resolve_delete_board_code(board_type: BoardType, raw: Any) -> str:
    """删除时使用：按板块类型规范化代码。"""
    """删除时使用：按板块类型规范化（支持 BK / 纯数字等）。"""
    return _normalize_board_code_for_type(board_type, raw)


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


def _board_basic_select_cols() -> str:
    return """
        board_code, board_name, create_date,
        COALESCE(trade_observe_flag, FALSE) AS trade_observe_flag,
        COALESCE(frontend_visible_flag, TRUE) AS frontend_visible_flag,
        board_code_source
    """


def _industry_board_src_sql(t: dict[str, str]) -> str:
    """管理端行业板块列表：仅 industry_board_basic_info，不含实时行情表。"""
    cols = _board_basic_select_cols()
    return f"""
        SELECT {cols}
        FROM {t['basic']}
    """


def _industry_board_list_src_sql(t: dict[str, str]) -> str:
    """管理端行业板块列表：基础信息 + 仅存在于成分股表中的板块（导入后可见）。"""
    cols = _board_basic_select_cols()
    return f"""
        SELECT {cols}
        FROM {t['basic']}
        UNION ALL
        SELECT
            orphan.board_code,
            orphan.board_name,
            orphan.create_date,
            orphan.trade_observe_flag,
            orphan.frontend_visible_flag,
            orphan.board_code_source
        FROM (
            SELECT DISTINCT ON (c.board_code)
                c.board_code,
                NULL::varchar AS board_name,
                NULL::timestamp AS create_date,
                FALSE AS trade_observe_flag,
                TRUE AS frontend_visible_flag,
                NULL::varchar AS board_code_source
            FROM {t['constituents']} c
            WHERE c.board_code IS NOT NULL AND TRIM(c.board_code) <> ''
              AND NOT EXISTS (
                  SELECT 1 FROM {t['basic']} b WHERE b.board_code = c.board_code
              )
            ORDER BY c.board_code
        ) orphan
    """


def _board_list_src_sql(board_type: BoardType, t: dict[str, str]) -> str:
    if board_type == "industry":
        return _industry_board_list_src_sql(t)
    return f"""
        SELECT {_board_basic_select_cols().strip()}
        FROM {t['basic']}
    """


def _board_list_filtered_cte(board_src_sql: str, kw_filter: str) -> str:
    """板块列表公共 CTE：聚合后按关键字过滤。"""
    return f"""
        WITH src AS (
            SELECT
                board_code,
                MAX(board_name) AS board_name,
                MAX(create_date) AS create_date,
                BOOL_OR(trade_observe_flag) AS trade_observe_flag,
                BOOL_OR(frontend_visible_flag) AS frontend_visible_flag,
                MAX(board_code_source) AS board_code_source
            FROM ({board_src_sql}) u
            WHERE board_code IS NOT NULL AND board_code <> ''
            GROUP BY board_code
        ),
        filtered AS (
            SELECT * FROM src WHERE 1=1 {kw_filter}
        )
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


def _resolve_stock_lookup_codes(
    db: Session,
    keyword: str,
) -> tuple[List[str], List[str], Optional[str]]:
    """按股票代码或名称解析查询目标，返回 (代码列表, 名称列表, 错误信息)。"""
    kw = (keyword or "").strip()
    if not kw:
        return [], [], "请输入股票代码或名称"

    norm = _normalize_stock_code(kw)
    if norm and norm.isdigit() and len(norm) == 6:
        name_row = db.execute(
            text(
                """
                SELECT name FROM stock_basic_info
                WHERE LPAD(CAST(code AS TEXT), 6, '0') = :code
                LIMIT 1
                """
            ),
            {"code": norm},
        ).fetchone()
        display_name = str(name_row[0]).strip() if name_row and name_row[0] else ""
        return [norm], [display_name] if display_name else [], None

    codes: set[str] = set()
    names: List[str] = []
    like_kw = f"%{kw}%"
    basic_rows = db.execute(
        text(
            """
            SELECT LPAD(CAST(code AS TEXT), 6, '0') AS stock_code, name
            FROM stock_basic_info
            WHERE TRIM(name) = :kw OR name ILIKE :like_kw
            ORDER BY CASE WHEN TRIM(name) = :kw THEN 0 ELSE 1 END, code
            LIMIT 30
            """
        ),
        {"kw": kw, "like_kw": like_kw},
    ).fetchall()
    for code, name in basic_rows:
        sc = _normalize_stock_code(code)
        if not sc:
            continue
        codes.add(sc)
        n = str(name or "").strip()
        if n and n not in names:
            names.append(n)

    if not codes:
        cons_rows = db.execute(
            text(
                """
                SELECT DISTINCT stock_code, stock_name FROM (
                    SELECT stock_code, stock_name FROM industry_board_constituents
                    UNION ALL
                    SELECT stock_code, stock_name FROM concept_board_constituents
                ) u
                WHERE stock_name ILIKE :like_kw
                   OR stock_code ILIKE :like_kw
                LIMIT 30
                """
            ),
            {"like_kw": like_kw},
        ).fetchall()
        for code, name in cons_rows:
            sc = _normalize_stock_code(code)
            if not sc:
                continue
            codes.add(sc)
            n = str(name or "").strip()
            if n and n not in names:
                names.append(n)

    if not codes:
        return [], [], f"未找到股票「{kw}」"
    return sorted(codes), names, None


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


_board_schema_lock = threading.Lock()
_board_schema_ensured = False


def ensure_board_trade_observe_columns(db: Session) -> None:
    """确保行业/概念板块基础表存在 trade_observe / frontend_visible / board_code_source 列。"""
    global _board_schema_ensured
    if _board_schema_ensured:
        return
    with _board_schema_lock:
        if _board_schema_ensured:
            return
        _ensure_board_trade_observe_columns_once(db)
        _board_schema_ensured = True


def _ensure_board_trade_observe_columns_once(db: Session) -> None:
    for table in ("industry_board_basic_info", "concept_board_basic_info"):
        db.execute(
            text(
                f"""
                ALTER TABLE {table}
                ADD COLUMN IF NOT EXISTS trade_observe_flag BOOLEAN NOT NULL DEFAULT FALSE
                """
            )
        )
        db.execute(
            text(
                f"""
                ALTER TABLE {table}
                ADD COLUMN IF NOT EXISTS frontend_visible_flag BOOLEAN NOT NULL DEFAULT TRUE
                """
            )
        )
        db.execute(
            text(
                f"""
                ALTER TABLE {table}
                ADD COLUMN IF NOT EXISTS board_code_source VARCHAR(32)
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
    """兼容旧名：生成全局未占用的数字编码（不加 BK）。"""
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
        detail = "行业板块代码须为数字、BK+数字、中文或英文字符（1~20 位）"
    else:
        detail = "概念板块代码须为 BK+数字或纯数字（1~20 位）"
    raise HTTPException(status_code=400, detail=detail)


class SaveBoardInfoBody(BaseModel):
    board_type: BoardType
    board_code: Optional[str] = Field(None, description="保存后的板块代码；新增可留空自动生成数字编码")
    board_name: Optional[str] = None
    trade_observe_flag: Optional[bool] = Field(
        None,
        description="交易观察标志；编辑保存时传入则更新",
    )
    frontend_visible_flag: Optional[bool] = Field(
        None,
        description="是否对网站前端显示；编辑保存时传入则更新",
    )
    board_code_source: Optional[str] = Field(
        None,
        description="板块代码来源：eastmoney/tonghuashun/huatai/manual/other",
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
                    raise ValueError("行业板块代码须为数字、BK+数字、中文或英文字符")
                raise ValueError("概念板块代码须为 BK+数字或纯数字")
            self.board_code = code
        if self.board_code_source is not None and str(self.board_code_source).strip():
            src = normalize_board_code_source(self.board_code_source)
            if not src:
                raise ValueError("板块代码来源无效")
            self.board_code_source = src
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


class SetBoardFrontendVisibleBody(BaseModel):
    board_type: BoardType
    board_code: str
    frontend_visible_flag: bool

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
    return _read_board_flags(db, board_type, board_code)[0]


def _read_board_flags(db: Session, board_type: BoardType, board_code: str) -> tuple[bool, bool]:
    ensure_board_trade_observe_columns(db)
    t = _tables(board_type)
    row = db.execute(
        text(
            f"""
            SELECT trade_observe_flag, frontend_visible_flag
            FROM {t['basic']} WHERE board_code = :code LIMIT 1
            """
        ),
        {"code": board_code},
    ).fetchone()
    if not row:
        return False, True
    trade_observe = bool(row[0]) if row[0] is not None else False
    frontend_visible = bool(row[1]) if row[1] is not None else True
    return trade_observe, frontend_visible


def _read_board_code_source(db: Session, board_type: BoardType, board_code: str) -> str:
    ensure_board_trade_observe_columns(db)
    t = _tables(board_type)
    row = db.execute(
        text(f"SELECT board_code_source FROM {t['basic']} WHERE board_code = :code LIMIT 1"),
        {"code": board_code},
    ).fetchone()
    if not row:
        # 无记录时用管理端新增/导入默认（同花顺），避免导入新建被标成「东方财富」
        return DEFAULT_BOARD_CODE_SOURCE
    # 有记录但来源为空：按历史默认东方财富（LEGACY）
    return resolve_board_code_source(row[0])


def _upsert_board_basic(
    db: Session,
    board_type: BoardType,
    board_code: str,
    board_name: Optional[str],
    now: datetime,
    trade_observe_flag: Optional[bool] = None,
    frontend_visible_flag: Optional[bool] = None,
    board_code_source: Optional[str] = None,
) -> None:
    ensure_board_trade_observe_columns(db)
    t = _tables(board_type)
    cur_trade, cur_visible = _read_board_flags(db, board_type, board_code)
    cur_source = _read_board_code_source(db, board_type, board_code)
    to_save_trade = cur_trade if trade_observe_flag is None else trade_observe_flag
    to_save_visible = cur_visible if frontend_visible_flag is None else frontend_visible_flag
    to_save_source = cur_source if board_code_source is None else resolve_board_code_source(
        board_code_source, fallback=DEFAULT_BOARD_CODE_SOURCE
    )
    db.execute(
        text(
            f"""
            INSERT INTO {t['basic']} (
                board_code, board_name, create_date,
                trade_observe_flag, frontend_visible_flag, board_code_source
            )
            VALUES (
                :board_code, :board_name, :create_date,
                :trade_observe_flag, :frontend_visible_flag, :board_code_source
            )
            ON CONFLICT (board_code) DO UPDATE SET
                board_name = COALESCE(EXCLUDED.board_name, {t['basic']}.board_name),
                trade_observe_flag = EXCLUDED.trade_observe_flag,
                frontend_visible_flag = EXCLUDED.frontend_visible_flag,
                board_code_source = EXCLUDED.board_code_source
            """
        ),
        {
            "board_code": board_code,
            "board_name": board_name,
            "create_date": now,
            "trade_observe_flag": to_save_trade,
            "frontend_visible_flag": to_save_visible,
            "board_code_source": to_save_source,
        },
    )


def _assert_board_name_source_unique(
    db: Session,
    board_type: BoardType,
    board_name: str,
    board_code_source: str,
    exclude_codes: Optional[list[str]] = None,
) -> None:
    """同名且同代码来源不可重复；名称本身允许重复（靠 board_code_source 区分）。"""
    name = (board_name or "").strip()
    if not name:
        return
    source = resolve_board_code_source(board_code_source, fallback=DEFAULT_BOARD_CODE_SOURCE)
    excludes = {
        _normalize_board_code_for_type(board_type, c) for c in (exclude_codes or []) if c
    }
    t = _tables(board_type)
    row = db.execute(
        text(
            f"""
            SELECT board_code FROM {t['basic']}
            WHERE TRIM(board_name) = :name
              AND COALESCE(NULLIF(TRIM(board_code_source), ''), :legacy) = :source
            LIMIT 1
            """
        ),
        {
            "name": name,
            "source": source,
            "legacy": LEGACY_DEFAULT_BOARD_CODE_SOURCE,
        },
    ).fetchone()
    if not row:
        return
    code = _normalize_board_code_for_type(board_type, row[0])
    if code not in excludes:
        label = board_code_source_label(source)
        raise HTTPException(
            status_code=400,
            detail=f"板块名称「{name}」在代码来源「{label}」下已存在（{code}）",
        )


def _assert_concept_board_name_unique(
    db: Session,
    board_name: str,
    exclude_codes: Optional[list[str]] = None,
    board_code_source: str = DEFAULT_BOARD_CODE_SOURCE,
) -> None:
    """兼容旧调用：概念板按「名称 + 代码来源」唯一。"""
    _assert_board_name_source_unique(
        db,
        "concept",
        board_name,
        board_code_source,
        exclude_codes=exclude_codes,
    )


def _find_same_name_source_board(
    db: Session,
    board_type: BoardType,
    board_name: str,
    board_code_source: str,
    exclude_code: str,
) -> Optional[str]:
    """查找同名且同代码来源的其它板块代码；无则返回 None。"""
    name = (board_name or "").strip()
    if not name:
        return None
    source = resolve_board_code_source(board_code_source, fallback=DEFAULT_BOARD_CODE_SOURCE)
    t = _tables(board_type)
    row = db.execute(
        text(
            f"""
            SELECT board_code FROM {t['basic']}
            WHERE TRIM(board_name) = :name
              AND board_code <> :code
              AND COALESCE(NULLIF(TRIM(board_code_source), ''), :legacy) = :source
            LIMIT 1
            """
        ),
        {
            "name": name,
            "code": exclude_code,
            "source": source,
            "legacy": LEGACY_DEFAULT_BOARD_CODE_SOURCE,
        },
    ).fetchone()
    if not row:
        return None
    return _normalize_board_code_for_type(board_type, row[0])


def _clear_all_concept_boards(db: Session) -> tuple[int, int]:
    """清空全部概念板块基本信息与成分股。"""
    Model = _constituent_model("concept")
    cons_deleted = db.query(Model).delete(synchronize_session=False)
    basic_deleted = db.execute(text("DELETE FROM concept_board_basic_info")).rowcount
    return int(cons_deleted or 0), int(basic_deleted or 0)


def _clear_all_industry_boards(db: Session) -> tuple[int, int, int]:
    """清空全部行业板块基本信息、成分股与实时行情。"""
    Model = _constituent_model("industry")
    cons_deleted = db.query(Model).delete(synchronize_session=False)
    basic_deleted = db.execute(text("DELETE FROM industry_board_basic_info")).rowcount
    realtime_deleted = db.execute(text("DELETE FROM industry_board_realtime_quotes")).rowcount
    return int(cons_deleted or 0), int(basic_deleted or 0), int(realtime_deleted or 0)


def _sync_industry_board_basic_from_import(
    db: Session,
    rows: List[Dict[str, str]],
    now: datetime,
    issues: List[Dict[str, Any]],
) -> int:
    """从全量导入数据同步 industry_board_basic_info（按板块代码聚合名称）。"""
    board_names: dict[str, str] = {}
    for r in rows:
        code = _normalize_board_code_for_type("industry", r.get("board_code"))
        if not code:
            continue
        name = (r.get("board_name") or "").strip()
        if code not in board_names:
            board_names[code] = name
        elif name and not board_names[code]:
            board_names[code] = name

    # 文件中常见「中文名既当代码又当名称」的别名行：若已有其它代码占用同名，则跳过该别名板，避免冲掉数字码名称
    name_owners: dict[str, str] = {}
    for code, name in board_names.items():
        n = (name or "").strip()
        if not n:
            continue
        owner = name_owners.get(n)
        if owner is None:
            name_owners[n] = code
        elif owner == n and code != n:
            # 优先由数字/业务代码代表该名称，而不是「名称当代码」的别名行
            name_owners[n] = code

    synced = 0
    for code in sorted(board_names.keys()):
        raw_name = (board_names[code] or "").strip()
        upsert_name: Optional[str] = raw_name or None

        # 跳过纯别名行：board_code == board_name，且同名已由其它代码代表
        if (
            upsert_name
            and code == upsert_name
            and name_owners.get(upsert_name) not in (None, code)
        ):
            issues.append({
                "row_no": 0,
                "board_code": code,
                "message": (
                    f"跳过别名板块「{code}」：同名已由 {name_owners[upsert_name]} 导入"
                ),
            })
            continue

        # 导入新建默认手动维护；已存在记录保留原代码来源（_upsert 在 source=None 时保留）
        effective_source = _read_board_code_source(db, "industry", code)
        if upsert_name:
            dup_code = _find_same_name_source_board(
                db, "industry", upsert_name, effective_source, code
            )
            if dup_code:
                issues.append({
                    "row_no": 0,
                    "board_code": code,
                    "message": (
                        f"板块名称「{upsert_name}」与 {dup_code} 同名且同代码来源，仍写入名称"
                    ),
                })

        _upsert_board_basic(
            db,
            "industry",
            code,
            upsert_name,
            now,
            board_code_source=None,
        )
        synced += 1
    return synced


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
        # 允许同名；仅同名+同代码来源时告警，绝不因同名清空名称
        effective_source = _read_board_code_source(db, "concept", code)
        if upsert_name:
            dup_code = _find_same_name_source_board(
                db, "concept", upsert_name, effective_source, code
            )
            if dup_code:
                issues.append({
                    "row_no": 0,
                    "board_code": code,
                    "message": (
                        f"板块名称「{upsert_name}」与 {dup_code} 同名且同代码来源，仍写入名称"
                    ),
                })
        _upsert_board_basic(
            db,
            "concept",
            code,
            upsert_name,
            now,
            board_code_source=None,
        )
        synced += 1
    return synced


def _rename_board_records(
    db: Session,
    board_type: BoardType,
    old_code: str,
    new_code: str,
    board_name: Optional[str],
    trade_observe_flag: Optional[bool] = None,
    frontend_visible_flag: Optional[bool] = None,
    board_code_source: Optional[str] = None,
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

    preserved_trade, preserved_visible = _read_board_flags(db, board_type, old_code)
    preserved_source = _read_board_code_source(db, board_type, old_code)
    flag_to_save_trade = trade_observe_flag if trade_observe_flag is not None else preserved_trade
    flag_to_save_visible = frontend_visible_flag if frontend_visible_flag is not None else preserved_visible
    source_to_save = (
        resolve_board_code_source(board_code_source, fallback=DEFAULT_BOARD_CODE_SOURCE)
        if board_code_source is not None
        else preserved_source
    )

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
        trade_observe_flag=flag_to_save_trade,
        frontend_visible_flag=flag_to_save_visible,
        board_code_source=source_to_save,
    )
    if board_type == "industry" and t.get("realtime") and board_name and old_code == new_code:
        db.execute(
            text(f"UPDATE {t['realtime']} SET board_name = :name WHERE board_code = :code"),
            {"name": board_name, "code": new_code},
        )


@router.get("/boards/code-sources")
async def list_board_code_sources(
    current_user: Any = Depends(get_current_admin),
):
    """板块代码来源选项（管理端下拉）。"""
    _ = current_user
    return {"success": True, "data": BOARD_CODE_SOURCE_OPTIONS}


@router.get("/boards/next-code")
async def get_next_board_code(
    board_type: BoardType = Query(...),
    after_code: Optional[str] = Query(
        None,
        description="当前预览编码；传入后返回其后的下一个可用数字编码（不加 BK）",
    ),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_admin),
):
    """预览下一个可用数字编码（行业/概念均全局唯一，不加 BK）。"""
    _ = current_user
    code = generate_next_bk_board_code(db, after_code=after_code)
    return {"success": True, "data": {"board_code": code}}


@router.post("/boards/save")
async def save_board_info(
    body: SaveBoardInfoBody,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_admin),
):
    """新增或编辑板块基础信息（支持修改板块代码并联动成分股）。"""
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
        new_code = _generate_next_industry_board_code(db)
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

    source_to_save = (
        resolve_board_code_source(body.board_code_source, fallback=DEFAULT_BOARD_CODE_SOURCE)
        if body.board_code_source is not None
        else (
            DEFAULT_BOARD_CODE_SOURCE
            if not body.original_board_code
            else _read_board_code_source(db, body.board_type, old_code)
        )
    )
    if board_name:
        _assert_board_name_source_unique(
            db,
            body.board_type,
            board_name,
            source_to_save,
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
            frontend_visible_flag=body.frontend_visible_flag,
            board_code_source=source_to_save,
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
            frontend_visible_flag=body.frontend_visible_flag,
            board_code_source=source_to_save,
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
    saved_trade, saved_visible = _read_board_flags(db, body.board_type, new_code)
    saved_source = _read_board_code_source(db, body.board_type, new_code)
    if body.trade_observe_flag is not None:
        saved_trade = body.trade_observe_flag
    if body.frontend_visible_flag is not None:
        saved_visible = body.frontend_visible_flag
    if body.board_code_source is not None:
        saved_source = resolve_board_code_source(body.board_code_source, fallback=DEFAULT_BOARD_CODE_SOURCE)
    return {
        "success": True,
        "message": "板块信息已保存",
        "data": {
            "action": action,
            "board_code": new_code,
            "board_name": board_name,
            "trade_observe_flag": saved_trade,
            "frontend_visible_flag": saved_visible,
            "board_code_source": saved_source,
            "board_code_source_label": board_code_source_label(saved_source),
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


@router.post("/boards/frontend-visible")
async def set_board_frontend_visible_flag(
    body: SetBoardFrontendVisibleBody,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_admin),
):
    """设置板块是否对网站前端显示（列表内快捷开关）。"""
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
        frontend_visible_flag=body.frontend_visible_flag,
    )
    db.commit()
    return {
        "success": True,
        "message": "前端显示标志已更新",
        "data": {
            "board_code": bcode,
            "frontend_visible_flag": body.frontend_visible_flag,
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

    board_src_sql = _board_list_src_sql(board_type, t)
    filtered_cte = _board_list_filtered_cte(board_src_sql, kw_filter)

    count_sql = text(f"{filtered_cte} SELECT COUNT(*) FROM filtered")
    total = db.execute(count_sql, params).scalar() or 0

    # 仅对当前页板块做成分股统计，避免全表 GROUP BY industry_board_constituents
    list_sql = text(
        f"""
        {filtered_cte}
        SELECT
            page.board_code,
            page.board_name,
            COALESCE(cnt.cnt, 0) AS constituent_count,
            cnt.last_updated,
            page.create_date,
            page.trade_observe_flag,
            page.frontend_visible_flag,
            page.board_code_source
        FROM (
            SELECT * FROM filtered
            ORDER BY create_date DESC NULLS LAST, board_code
            LIMIT :limit OFFSET :offset
        ) page
        LEFT JOIN LATERAL (
            SELECT COUNT(*)::bigint AS cnt, MAX(updated_at) AS last_updated
            FROM {t['constituents']} c
            WHERE c.board_code = page.board_code
        ) cnt ON TRUE
        ORDER BY page.create_date DESC NULLS LAST, page.board_code
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
            "frontend_visible_flag": bool(r[6]),
            "board_code_source": resolve_board_code_source(r[7]),
            "board_code_source_label": board_code_source_label(r[7]),
        }
        for r in rows
    ]
    return {"success": True, "data": data, "total": total, "page": page, "page_size": page_size}


@router.get("/boards/by-stock")
async def list_boards_by_stock(
    board_type: BoardType = Query(..., description="industry 或 concept"),
    stock: str = Query(..., min_length=1, description="股票代码或名称"),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_admin),
):
    """按股票代码或名称反查所属行业/概念板块。"""
    _ = current_user
    ensure_board_trade_observe_columns(db)
    stock_codes, stock_names, err = _resolve_stock_lookup_codes(db, stock)
    if err:
        raise HTTPException(status_code=400, detail=err)

    t = _tables(board_type)
    sql = text(
        f"""
        SELECT
            c.board_code,
            COALESCE(NULLIF(TRIM(MAX(b.board_name)), ''), '') AS board_name,
            MAX(c.updated_at) AS last_updated,
            COALESCE(BOOL_OR(b.trade_observe_flag), FALSE) AS trade_observe_flag
        FROM {t['constituents']} c
        LEFT JOIN {t['basic']} b ON b.board_code = c.board_code
        WHERE c.stock_code IN :codes
        GROUP BY c.board_code
        ORDER BY board_name, c.board_code
        """
    ).bindparams(bindparam("codes", expanding=True))
    rows = db.execute(sql, {"codes": stock_codes}).fetchall()
    boards = [
        {
            "board_code": r[0],
            "board_name": r[1] or None,
            "last_updated": r[2].isoformat() if r[2] else None,
            "trade_observe_flag": bool(r[3]),
        }
        for r in rows
    ]
    label = "行业" if board_type == "industry" else "概念"
    if not boards:
        msg = f"股票 {'/'.join(stock_codes)} 未归入任何{label}板块"
    else:
        msg = f"共 {len(boards)} 个{label}板块"
    return {
        "success": True,
        "message": msg,
        "data": {
            "stock_codes": stock_codes,
            "stock_names": stock_names,
            "boards": boards,
            "total": len(boards),
        },
    }


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


EXPORT_ALL_COLUMNS = [
    "board_code",
    "board_name",
    "board_code_source",
    "stock_code",
    "stock_name",
    "updated_at",
]


def _export_all_board_src_sql(board_type: BoardType, t: dict[str, str]) -> str:
    """导出全部用的板块源：含 board_name / board_code_source。"""
    if board_type == "industry":
        return f"""
            SELECT
                board_code,
                MAX(board_name) AS board_name,
                MAX(board_code_source) AS board_code_source
            FROM (
                SELECT board_code, board_name, board_code_source FROM {t['basic']}
                UNION ALL
                SELECT DISTINCT
                    board_code,
                    NULL::varchar AS board_name,
                    NULL::varchar AS board_code_source
                FROM {t['constituents']}
                WHERE board_code IS NOT NULL AND board_code <> ''
            ) u
            WHERE board_code IS NOT NULL AND board_code <> ''
            GROUP BY board_code
        """
    return f"""
        SELECT
            board_code,
            MAX(board_name) AS board_name,
            MAX(board_code_source) AS board_code_source
        FROM (
            SELECT board_code, board_name, board_code_source FROM {t['basic']}
            UNION ALL
            SELECT
                board_code,
                NULL AS board_name,
                NULL AS board_code_source
            FROM {t['constituents']}
        ) u
        WHERE board_code IS NOT NULL AND board_code <> ''
        GROUP BY board_code
    """


def _format_export_board_code_source(raw: Any) -> str:
    """导出「代码来源」：与列表一致，输出中文标签。"""
    return board_code_source_label(resolve_board_code_source(raw))


@router.get("/export/all")
async def export_all_constituents(
    board_type: BoardType = Query(...),
    format: str = Query("xlsx", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_admin),
):
    """导出当前类型下全部板块成分股（含无成分股的板块基本信息行）。"""
    _ = current_user
    ensure_board_trade_observe_columns(db)
    t = _tables(board_type)
    label = "industry" if board_type == "industry" else "concept"
    board_src_sql = _export_all_board_src_sql(board_type, t)
    sql = text(
        f"""
        SELECT
            b.board_code,
            COALESCE(b.board_name, '') AS board_name,
            b.board_code_source,
            COALESCE(c.stock_code, '') AS stock_code,
            COALESCE(c.stock_name, '') AS stock_name,
            c.updated_at
        FROM ({board_src_sql}) b
        LEFT JOIN {t['constituents']} c ON c.board_code = b.board_code
        ORDER BY b.board_code, c.stock_code NULLS FIRST
        """
    )
    rows = db.execute(sql).fetchall()
    cols = list(EXPORT_ALL_COLUMNS)
    data = [
        [
            str(r[0] or ""),
            str(r[1] or ""),
            _format_export_board_code_source(r[2]),
            str(r[3] or ""),
            str(r[4] or ""),
            r[5].strftime("%Y-%m-%d %H:%M:%S") if r[5] else "",
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
    cols = ["board_code", "board_name", "board_code_source", "stock_code", "stock_name"]
    sample = [
        ["IT服务", "IT服务", "手动维护", "000001", "平安银行"],
        ["IT服务", "IT服务", "手动维护", "", "神州数码"],
        ["半导体", "半导体", "东方财富", "688981", "中芯国际"],
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
    clear_existing: bool = Query(
        False,
        description="行业板块：导入前清空全部基础信息/成分股/实时行情；概念板块固定清空",
    ),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_admin),
):
    """Excel/CSV 全量导入多板块成分股。概念板块会先清空原有数据再导入；行业板块可选清空。"""
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
    cleared_realtime = 0
    basic_synced = 0
    now = datetime.now().replace(microsecond=0)

    if board_type == "concept":
        cleared_cons, cleared_basic = _clear_all_concept_boards(db)
        basic_synced = _sync_concept_board_basic_from_import(db, rows, now, issues)
    elif board_type == "industry" and clear_existing:
        cleared_cons, cleared_basic, cleared_realtime = _clear_all_industry_boards(db)

    if board_type == "industry":
        basic_synced = _sync_industry_board_basic_from_import(db, rows, now, issues)

    aligned, board_only_count, stock_row_count = align_all_import_constituent_rows(
        db, rows, board_type, issues
    )

    if not aligned:
        if basic_synced or (board_type == "industry" and board_only_count > 0):
            db.commit()
            uname = getattr(current_user, "username", None) or "admin"
            if board_only_count > 0 and stock_row_count == 0:
                msg = (
                    f"已同步板块基本信息 {basic_synced} 个，但文件中没有有效成分股数据"
                    f"（仅含 {board_only_count} 行板块定义）。"
                    f"请使用「导出全部」格式的完整文件（含股票代码/名称列），"
                    f"或导入板块列表后点击「同步全部成分」从东财拉取成分股。"
                )
            elif stock_row_count > 0:
                msg = (
                    f"已同步板块基本信息 {basic_synced} 个，但有效成分股 0 条"
                    f"（共 {stock_row_count} 行股票数据未能匹配入库）"
                )
            else:
                msg = f"已同步板块基本信息 {basic_synced} 个（无有效成分股行可导入）"
            if board_type == "concept":
                msg = (
                    f"已清空原概念板块 {cleared_basic} 个、成分股 {cleared_cons} 条；"
                    + msg
                )
            elif clear_existing and (cleared_basic or cleared_cons):
                msg = (
                    f"已清空原行业板块 {cleared_basic} 个、成分股 {cleared_cons} 条"
                    f"，实时行情 {cleared_realtime} 条；"
                    + msg
                )
            if issues:
                msg += f"，告警 {len(issues)} 条"
            return {
                "success": stock_row_count > 0,
                "message": msg,
                "data": {
                    "boards_processed": 0,
                    "basic_synced": basic_synced,
                    "cleared_basic": cleared_basic,
                    "cleared_constituents": cleared_cons,
                    "cleared_realtime": cleared_realtime if board_type == "industry" else 0,
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
    elif clear_existing and (cleared_basic or cleared_cons):
        msg = (
            f"已清空原行业板块 {cleared_basic} 个、成分股 {cleared_cons} 条"
            f"，实时行情 {cleared_realtime} 条；"
            + msg
        )
    if basic_synced:
        msg += f"，同步板块基本信息 {basic_synced} 个"
    if issues:
        msg += f"，跳过/告警 {len(issues)} 条"
    return {
        "success": True,
        "message": msg,
        "data": {
            "boards_processed": len(board_stats),
            "basic_synced": basic_synced,
            "cleared_basic": cleared_basic,
            "cleared_constituents": cleared_cons,
            "cleared_realtime": cleared_realtime if board_type == "industry" else 0,
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
