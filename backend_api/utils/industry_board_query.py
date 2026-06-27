"""行业板块成分股查询工具。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from backend_api.models import IndustryBoardConstituent


def dedupe_industry_board_catalog(items: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """同名板块只保留一条：优先 BK 编码，避免 GMS 选择器出现重复名称。"""
    from backend_api.utils.bk_board_code import is_valid_bk_board_code

    buckets: Dict[str, List[Dict[str, str]]] = {}
    for raw in items:
        code = str(raw.get("board_code") or "").strip()
        if not code:
            continue
        name = str(raw.get("board_name") or "").strip() or code
        buckets.setdefault(name, []).append({"board_code": code, "board_name": name})

    out: List[Dict[str, str]] = []
    for name, group in buckets.items():
        if len(group) == 1:
            out.append(group[0])
            continue
        group.sort(
            key=lambda x: (
                0 if is_valid_bk_board_code(x["board_code"]) else 1,
                x["board_code"],
            )
        )
        out.append(group[0])
    out.sort(key=lambda x: (x["board_name"], x["board_code"]))
    return out


def fetch_industry_board_catalog(db: Session) -> List[Dict[str, str]]:
    """GMS 等行业板块选择器：仅 basic_info，并按展示名称去重。"""
    rows = db.execute(
        text(
            """
            SELECT board_code, board_name
            FROM industry_board_basic_info
            WHERE board_code IS NOT NULL AND TRIM(board_code) <> ''
            ORDER BY board_name NULLS LAST, board_code
            """
        )
    ).fetchall()
    items = [{"board_code": str(r[0]), "board_name": r[1]} for r in rows]
    return dedupe_industry_board_catalog(items)


def _normalize_code(code: str) -> str:
    s = str(code).strip()
    if s.isdigit() and len(s) < 6:
        return s.zfill(6)
    return s


def get_stock_codes_by_board_codes(
    db: Session, board_codes: List[str]
) -> Set[str]:
    """按板块代码列表取成分股代码并集（行业 + 概念）。"""
    if not board_codes:
        return set()
    codes = [str(c).strip() for c in board_codes if c and str(c).strip()]
    if not codes:
        return set()
    out: Set[str] = set()
    normalized = [str(c).strip() for c in codes if c and str(c).strip()]
    if not normalized:
        return set()
    rows = (
        db.query(IndustryBoardConstituent.stock_code)
        .filter(IndustryBoardConstituent.board_code.in_(normalized))
        .distinct()
        .all()
    )
    out |= {str(r[0]).strip() for r in rows if r[0]}
    rows_con = db.execute(
        text(
            """
            SELECT DISTINCT stock_code
            FROM concept_board_constituents
            WHERE board_code = ANY(:codes)
            """
        ),
        {"codes": normalized},
    ).fetchall()
    out |= {str(r[0]).strip() for r in rows_con if r[0]}
    return {_normalize_code(c) for c in out if c}


def get_boards_by_stock_code(db: Session, stock_code: str) -> List[Dict]:
    """反查股票所属行业/概念板块（含板块名称）。"""
    code = _normalize_code(stock_code)
    sql = text(
        """
        SELECT c.board_code, COALESCE(b.board_name, c.board_code) AS board_name, c.updated_at, 'industry' AS board_type
        FROM industry_board_constituents c
        LEFT JOIN industry_board_basic_info b ON b.board_code = c.board_code
        WHERE c.stock_code = :stock_code
        UNION ALL
        SELECT c.board_code, COALESCE(b.board_name, c.board_code) AS board_name, c.updated_at, 'concept' AS board_type
        FROM concept_board_constituents c
        LEFT JOIN concept_board_basic_info b ON b.board_code = c.board_code
        WHERE c.stock_code = :stock_code
        ORDER BY board_name NULLS LAST, board_code
        """
    )
    rows = db.execute(sql, {"stock_code": code}).fetchall()
    return [
        {
            "board_code": str(r[0]),
            "board_name": str(r[1]) if r[1] else str(r[0]),
            "updated_at": r[2].isoformat() if hasattr(r[2], "isoformat") else str(r[2]) if r[2] else None,
            "board_type": str(r[3]) if len(r) > 3 else "industry",
        }
        for r in rows
    ]


def get_board_names_by_stock_code(db: Session, stock_code: str) -> List[str]:
    boards = get_boards_by_stock_code(db, stock_code)
    return [b["board_name"] for b in boards if b.get("board_name")]


def get_industry_board_name_by_stock_code(db: Session, stock_code: str) -> Optional[str]:
    """A 股：从行业板块成分股 + 基本信息表取板块名称（不含概念板块）。"""
    code = _normalize_code(stock_code)
    if not code:
        return None
    sql = text(
        """
        SELECT COALESCE(b.board_name, c.board_code) AS board_name
        FROM industry_board_constituents c
        LEFT JOIN industry_board_basic_info b ON b.board_code = c.board_code
        WHERE c.stock_code = :stock_code
        ORDER BY board_name, c.board_code
        """
    )
    try:
        rows = db.execute(sql, {"stock_code": code}).fetchall()
    except Exception:
        return None
    names: List[str] = []
    for row in rows:
        bn = str(row[0]).strip() if row and row[0] else ""
        if bn and bn not in names:
            names.append(bn)
    return ",".join(names) if names else None


def batch_industry_board_names_by_stock_codes(
    db: Session, stock_codes: List[str]
) -> Dict[str, str]:
    """批量 A 股行业板块名称（stock_code -> 逗号分隔的 board_name）。"""
    if not stock_codes:
        return {}
    codes = list(dict.fromkeys(_normalize_code(c) for c in stock_codes if c and str(c).strip()))
    if not codes:
        return {}
    stmt = text(
        """
        SELECT c.stock_code, COALESCE(b.board_name, c.board_code) AS board_name
        FROM industry_board_constituents c
        LEFT JOIN industry_board_basic_info b ON b.board_code = c.board_code
        WHERE c.stock_code IN :codes
        ORDER BY c.stock_code, board_name, c.board_code
        """
    ).bindparams(bindparam("codes", expanding=True))
    try:
        board_rows = db.execute(stmt, {"codes": codes}).fetchall()
    except Exception:
        return {}
    grouped: Dict[str, List[str]] = {}
    for stock_code, board_name in board_rows:
        sc = _normalize_code(str(stock_code))
        bn = str(board_name).strip() if board_name else sc
        bucket = grouped.setdefault(sc, [])
        if bn not in bucket:
            bucket.append(bn)
    return {code: ",".join(names) for code, names in grouped.items() if names}


def sync_a_stock_industry_from_boards(
    db: Session,
    *,
    only_empty: bool = True,
    stock_codes: Optional[List[str]] = None,
) -> Dict[str, int]:
    """
    将行业板块成分映射写回 stock_basic_info.industry（A 股）。
    only_empty=True 时仅更新 industry 为空/无效占位的记录。
    """
    params: Dict[str, Any] = {}
    code_filter = ""
    if stock_codes:
        codes = list(dict.fromkeys(_normalize_code(c) for c in stock_codes if c and str(c).strip()))
        if not codes:
            return {"updated": 0, "matched": 0}
        params["codes"] = codes
        code_filter = "AND c.stock_code IN :codes"

    empty_filter = ""
    if only_empty:
        empty_filter = """
            AND (
                s.industry IS NULL
                OR TRIM(s.industry) = ''
                OR LOWER(TRIM(s.industry)) IN ('nan', 'none', 'null', '<na>', 'nat')
            )
        """

    sql = text(
        f"""
        WITH dedup AS (
            SELECT DISTINCT
                c.stock_code,
                COALESCE(b.board_name, c.board_code) AS board_name
            FROM industry_board_constituents c
            LEFT JOIN industry_board_basic_info b ON b.board_code = c.board_code
            WHERE 1 = 1 {code_filter}
        ),
        board_agg AS (
            SELECT
                stock_code,
                string_agg(board_name, ',' ORDER BY board_name) AS industry_name
            FROM dedup
            GROUP BY stock_code
        )
        UPDATE stock_basic_info AS s
        SET industry = board_agg.industry_name
        FROM board_agg
        WHERE LPAD(CAST(s.code AS TEXT), 6, '0') = board_agg.stock_code
          {empty_filter}
        """
    )
    if stock_codes:
        sql = sql.bindparams(bindparam("codes", expanding=True))

    try:
        matched = db.execute(
            text(
                f"""
                SELECT COUNT(DISTINCT c.stock_code)
                FROM industry_board_constituents c
                WHERE 1 = 1 {code_filter}
                """
            ).bindparams(bindparam("codes", expanding=True)) if stock_codes else text(
                "SELECT COUNT(DISTINCT stock_code) FROM industry_board_constituents"
            ),
            params,
        ).scalar() or 0
        result = db.execute(sql, params)
        db.commit()
        return {"updated": int(result.rowcount or 0), "matched": int(matched)}
    except Exception:
        db.rollback()
        raise


def resolve_cn_industry_display(
    stored: Optional[str], board_industry: Optional[str]
) -> Optional[str]:
    """A 股列表展示：优先行业板块名称，其次库内 industry。"""
    if board_industry and str(board_industry).strip():
        return str(board_industry).strip()
    if stored is None:
        return None
    s = str(stored).strip()
    if not s:
        return None
    low = s.lower()
    if low in ("nan", "none", "null", "<na>", "nat"):
        return None
    return s


def stock_matches_industry_filter(
    db: Session,
    stock_code: str,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
) -> bool:
    """include/exclude 可填 board_code 或 board_name。"""
    boards = get_boards_by_stock_code(db, stock_code)
    if not boards:
        return not bool(include)
    keys = set()
    for b in boards:
        keys.add(b["board_code"])
        keys.add(b["board_name"])
    if include:
        inc = set(include)
        if not keys.intersection(inc):
            return False
    if exclude:
        exc = set(exclude)
        if keys.intersection(exc):
            return False
    return True


def lookup_leading_code_from_constituents(
    db: Session, board_code: str, leading_stock_name: str
) -> Optional[str]:
    """在成分股表中按名称匹配领涨股代码。"""
    if not leading_stock_name or not str(leading_stock_name).strip():
        return None
    name = str(leading_stock_name).strip()
    row = (
        db.query(IndustryBoardConstituent.stock_code)
        .filter(
            IndustryBoardConstituent.board_code == board_code,
            IndustryBoardConstituent.stock_name == name,
        )
        .first()
    )
    if row:
        return str(row[0]).strip()
    row = (
        db.query(IndustryBoardConstituent.stock_code)
        .filter(
            IndustryBoardConstituent.board_code == board_code,
            IndustryBoardConstituent.stock_name.like(f"%{name}%"),
        )
        .first()
    )
    return str(row[0]).strip() if row else None
