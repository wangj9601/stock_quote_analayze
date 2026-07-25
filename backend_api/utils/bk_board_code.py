"""管理端/采集侧板块编码工具。

自动生成规则：纯数字（至少 4 位），不强制加 BK。
兼容存量：仍接受并保留 BK+数字 编码。
"""
from __future__ import annotations

import re
from typing import Iterable, List, Optional, Set

from sqlalchemy import text
from sqlalchemy.orm import Session

BK_BOARD_CODE_RE = re.compile(r"^BK(\d+)$", re.IGNORECASE)
NUMERIC_BOARD_CODE_RE = re.compile(r"^\d{1,20}$")
# BK+数字 或 纯数字（用于解析序号、占用检测）
BOARD_NUM_CODE_RE = re.compile(r"^(?:BK)?(\d+)$", re.IGNORECASE)
INDUSTRY_BOARD_CODE_MAX_LEN = 20
# 行业板块：BK/纯数字，或含中文/英文字母的业务代码（可含数字与 ._-·）
INDUSTRY_TEXT_BOARD_CODE_RE = re.compile(
    r"^[\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9._\-·]{0,19}$"
)

_BK_USAGE_SQL = """
    SELECT board_code FROM concept_board_basic_info
    WHERE UPPER(board_code) LIKE 'BK%%' OR board_code ~ '^[0-9]+$'
    UNION
    SELECT DISTINCT board_code FROM concept_board_constituents
    WHERE UPPER(board_code) LIKE 'BK%%' OR board_code ~ '^[0-9]+$'
    UNION
    SELECT board_code FROM industry_board_basic_info
    WHERE UPPER(board_code) LIKE 'BK%%' OR board_code ~ '^[0-9]+$'
    UNION
    SELECT DISTINCT board_code FROM industry_board_constituents
    WHERE UPPER(board_code) LIKE 'BK%%' OR board_code ~ '^[0-9]+$'
"""


def format_bk_board_code(num: int) -> str:
    """自动生成编码：纯数字，至少 4 位，不加 BK 前缀。"""
    if num < 0:
        num = 0
    if num < 10000:
        return f"{num:04d}"
    return str(num)


def normalize_bk_board_code(raw: object) -> str:
    """规范化「数字型」板块代码：BK+数字保留大写 BK；纯数字原样保留（不加 BK）。"""
    s = str(raw or "").strip()
    s = s.lstrip("'").lstrip("’").strip()
    if not s:
        return ""
    if BK_BOARD_CODE_RE.match(s.upper()):
        return s.upper()
    if NUMERIC_BOARD_CODE_RE.fullmatch(s):
        return s
    return ""


def is_valid_bk_board_code(code: object) -> bool:
    return bool(normalize_bk_board_code(code))


def normalize_industry_board_code(raw: object) -> str:
    """行业板块代码：BK/纯数字，或中文/英文字符组成的业务编码。"""
    num_like = normalize_bk_board_code(raw)
    if num_like:
        return num_like
    s = str(raw or "").strip()
    s = s.lstrip("'").lstrip("’").strip()
    if not s or len(s) > INDUSTRY_BOARD_CODE_MAX_LEN:
        return ""
    if INDUSTRY_TEXT_BOARD_CODE_RE.fullmatch(s):
        return s
    return ""


def is_valid_industry_board_code(code: object) -> bool:
    return bool(normalize_industry_board_code(code))


def parse_bk_num(code: object) -> Optional[int]:
    s = str(code or "").strip()
    m = BOARD_NUM_CODE_RE.match(s)
    if not m:
        return None
    return int(m.group(1))


def collect_used_bk_numbers(db: Session) -> Set[int]:
    rows = db.execute(text(_BK_USAGE_SQL)).fetchall()
    used: Set[int] = set()
    for (code,) in rows:
        n = parse_bk_num(code)
        if n is not None:
            used.add(n)
    return used


def collect_used_bk_codes(db: Session) -> Set[str]:
    rows = db.execute(text(_BK_USAGE_SQL)).fetchall()
    return {normalize_bk_board_code(c) for (c,) in rows if normalize_bk_board_code(c)}


def collect_concept_bk_codes(db: Session) -> Set[str]:
    rows = db.execute(
        text(
            """
            SELECT board_code FROM concept_board_basic_info
            WHERE UPPER(board_code) LIKE 'BK%%' OR board_code ~ '^[0-9]+$'
            UNION
            SELECT DISTINCT board_code FROM concept_board_constituents
            WHERE UPPER(board_code) LIKE 'BK%%' OR board_code ~ '^[0-9]+$'
            """
        )
    ).fetchall()
    return {normalize_bk_board_code(c) for (c,) in rows if normalize_bk_board_code(c)}


def collect_industry_bk_codes(db: Session) -> Set[str]:
    rows = db.execute(
        text(
            """
            SELECT board_code FROM industry_board_basic_info
            WHERE UPPER(board_code) LIKE 'BK%%' OR board_code ~ '^[0-9]+$'
            UNION
            SELECT DISTINCT board_code FROM industry_board_constituents
            WHERE UPPER(board_code) LIKE 'BK%%' OR board_code ~ '^[0-9]+$'
            """
        )
    ).fetchall()
    return {normalize_bk_board_code(c) for (c,) in rows if normalize_bk_board_code(c)}


def generate_next_bk_board_code(
    db: Session,
    after_code: Optional[str] = None,
    exclude_codes: Optional[Iterable[str]] = None,
) -> str:
    """生成全局未占用的数字编码（不加 BK；行业/概念均计入）。"""
    used = collect_used_bk_numbers(db)
    for raw in exclude_codes or []:
        n = parse_bk_num(raw)
        if n is not None:
            used.add(n)
    max_num = max(used) if used else 0
    start = max_num
    if after_code:
        n = parse_bk_num(after_code)
        if n is not None:
            start = max(start, n)
    candidate = start + 1
    while candidate in used:
        candidate += 1
    return format_bk_board_code(candidate)


def allocate_bk_board_code(
    db: Session,
    preferred: Optional[str] = None,
    *,
    exclude: Optional[Iterable[str]] = None,
) -> str:
    """优先使用 preferred（未被占用且不在 exclude 中），否则自动分配纯数字编码。"""
    excluded = {normalize_bk_board_code(c) for c in (exclude or []) if normalize_bk_board_code(c)}
    used = collect_used_bk_codes(db) | excluded
    pref = normalize_bk_board_code(preferred)
    if pref and pref not in used:
        return pref
    return generate_next_bk_board_code(db, exclude_codes=used)


def assert_bk_available_for_board_type(
    db: Session,
    board_type: str,
    code: str,
    *,
    exclude_codes: Optional[Iterable[str]] = None,
) -> None:
    """保存前校验数字型编码（BK 或纯数字）不与对侧板块类型冲突。"""
    from fastapi import HTTPException

    bcode = normalize_bk_board_code(code)
    if not bcode:
        raise HTTPException(status_code=400, detail="板块代码须为数字或 BK+数字 格式")
    excludes = {normalize_bk_board_code(c) for c in (exclude_codes or []) if normalize_bk_board_code(c)}
    if board_type == "industry":
        in_concept = db.execute(
            text(
                """
                SELECT 1 FROM concept_board_basic_info WHERE board_code = :code
                UNION ALL
                SELECT 1 FROM concept_board_constituents WHERE board_code = :code
                LIMIT 1
                """
            ),
            {"code": bcode},
        ).scalar()
        if in_concept and bcode not in excludes:
            raise HTTPException(
                status_code=400,
                detail=f"板块代码「{bcode}」已被概念板块占用，请使用其它编码",
            )
    elif board_type == "concept":
        in_industry = db.execute(
            text(
                """
                SELECT 1 FROM industry_board_basic_info WHERE board_code = :code
                UNION ALL
                SELECT 1 FROM industry_board_constituents WHERE board_code = :code
                LIMIT 1
                """
            ),
            {"code": bcode},
        ).scalar()
        if in_industry and bcode not in excludes:
            raise HTTPException(
                status_code=400,
                detail=f"板块代码「{bcode}」已被行业板块占用，请使用其它编码",
            )


def resolve_industry_board_codes(db: Session, raw_codes: List[str]) -> List[str]:
    """将 BK/纯数字、中文/英文板块代码或板块名称解析为 industry_board_basic_info 中的 board_code。"""
    out: List[str] = []
    for raw in raw_codes:
        s = str(raw or "").strip()
        if not s:
            continue
        code = normalize_industry_board_code(s)
        if code:
            hit = db.execute(
                text(
                    """
                    SELECT board_code FROM industry_board_basic_info WHERE board_code = :code
                    UNION
                    SELECT DISTINCT board_code FROM industry_board_constituents
                    WHERE board_code = :code LIMIT 1
                    """
                ),
                {"code": code},
            ).fetchone()
            if hit:
                resolved = normalize_industry_board_code(hit[0])
                if resolved and resolved not in out:
                    out.append(resolved)
                continue
        row = db.execute(
            text(
                """
                SELECT board_code FROM industry_board_basic_info
                WHERE TRIM(board_name) = :name OR board_code = :name
                ORDER BY CASE WHEN UPPER(board_code) LIKE 'BK%%' THEN 0 ELSE 1 END
                LIMIT 1
                """
            ),
            {"name": s},
        ).fetchone()
        if row:
            resolved = normalize_industry_board_code(row[0])
            if resolved and resolved not in out:
                out.append(resolved)
    return out
