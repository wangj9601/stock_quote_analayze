"""板块代码映射（同花顺 ↔ 东方财富），支持行业/概念。

采集源不稳定时，列表/详情默认展示同花顺码，东财侧多为 BKxxxx。
本模块提供持久化 crosswalk（表名历史原因仍为 industry_board_code_map，
以 board_kind 区分 industry / concept），并支持按「同名」自动重建。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend_api.utils.bk_board_code import is_valid_bk_board_code
from backend_api.utils.board_code_source import LEGACY_DEFAULT_BOARD_CODE_SOURCE

TABLE_NAME = "industry_board_code_map"
MATCH_NAME_EXACT = "name_exact"
MATCH_MANUAL = "manual"
MATCH_IMPORT = "import"

_SRC_THS = "tonghuashun"
_SRC_EM = "eastmoney"


def ensure_industry_board_code_map_table(db: Session) -> None:
    """创建映射表（幂等）。"""
    db.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                id              BIGSERIAL PRIMARY KEY,
                board_kind      VARCHAR(16) NOT NULL DEFAULT 'industry',
                board_name      VARCHAR(100),
                ths_board_code  VARCHAR(20) NOT NULL,
                em_board_code   VARCHAR(20) NOT NULL,
                match_method    VARCHAR(32) NOT NULL DEFAULT '{MATCH_NAME_EXACT}',
                confidence      SMALLINT NOT NULL DEFAULT 100,
                is_active       BOOLEAN NOT NULL DEFAULT TRUE,
                note            TEXT,
                created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at      TIMESTAMP NOT NULL DEFAULT NOW(),
                CONSTRAINT uq_industry_board_code_map_ths
                    UNIQUE (board_kind, ths_board_code),
                CONSTRAINT uq_industry_board_code_map_em
                    UNIQUE (board_kind, em_board_code)
            )
            """
        )
    )
    db.execute(
        text(
            f"""
            CREATE INDEX IF NOT EXISTS ix_industry_board_code_map_name
            ON {TABLE_NAME} (board_kind, board_name)
            """
        )
    )
    db.execute(
        text(
            f"""
            CREATE INDEX IF NOT EXISTS ix_industry_board_code_map_active
            ON {TABLE_NAME} (board_kind, is_active)
            """
        )
    )


def _norm_code(raw: Any) -> str:
    return str(raw or "").strip()


def _norm_name(raw: Any) -> str:
    return str(raw or "").strip()


def _looks_like_ths_board_code(code: str) -> bool:
    c = _norm_code(code)
    if not c:
        return False
    if is_valid_bk_board_code(c):
        return False
    # 同花顺行业/概念常见纯数字码（881xxx / 885xxx 等）；也允许其它非 BK 文本码
    return c.isdigit() or (not c.upper().startswith("BK"))


def _looks_like_ths_industry_code(code: str) -> bool:
    """兼容旧名。"""
    return _looks_like_ths_board_code(code)


def _row_to_dict(row: Any) -> Dict[str, Any]:
    m = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
    out: Dict[str, Any] = {}
    for k, v in m.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat(sep=" ", timespec="seconds")
        else:
            out[k] = v
    return out


def load_active_code_maps(
    db: Session,
    *,
    board_kind: str = "industry",
) -> Tuple[Dict[str, str], Dict[str, str]]:
    """返回 (ths->em, em->ths) 活跃映射。表不存在时返回空字典。"""
    ths_to_em: Dict[str, str] = {}
    em_to_ths: Dict[str, str] = {}
    try:
        rows = db.execute(
            text(
                f"""
                SELECT ths_board_code, em_board_code
                FROM {TABLE_NAME}
                WHERE board_kind = :kind
                  AND is_active IS TRUE
                """
            ),
            {"kind": board_kind},
        ).fetchall()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return ths_to_em, em_to_ths

    for r in rows:
        ths = _norm_code(r[0])
        em = _norm_code(r[1])
        if ths and em:
            ths_to_em[ths] = em
            em_to_ths[em] = ths
    return ths_to_em, em_to_ths


def resolve_peer_board_code(
    db: Session,
    board_code: str,
    *,
    board_kind: str = "industry",
) -> Optional[str]:
    """给定一端代码，返回对端代码（无映射则 None）。"""
    code = _norm_code(board_code)
    if not code:
        return None
    ths_to_em, em_to_ths = load_active_code_maps(db, board_kind=board_kind)
    if code in ths_to_em:
        return ths_to_em[code]
    if code in em_to_ths:
        return em_to_ths[code]
    return None


def list_code_maps(
    db: Session,
    *,
    board_kind: str = "industry",
    active_only: bool = False,
    keyword: Optional[str] = None,
    limit: int = 500,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    ensure_industry_board_code_map_table(db)
    where = ["board_kind = :kind"]
    params: Dict[str, Any] = {
        "kind": board_kind,
        "limit": max(1, min(int(limit), 2000)),
        "offset": max(0, int(offset)),
    }
    if active_only:
        where.append("is_active IS TRUE")
    kw = _norm_name(keyword)
    if kw:
        where.append(
            "(board_name ILIKE :kw OR ths_board_code ILIKE :kw OR em_board_code ILIKE :kw)"
        )
        params["kw"] = f"%{kw}%"
    sql = f"""
        SELECT id, board_kind, board_name, ths_board_code, em_board_code,
               match_method, confidence, is_active, note, created_at, updated_at
        FROM {TABLE_NAME}
        WHERE {' AND '.join(where)}
        ORDER BY board_name NULLS LAST, ths_board_code
        LIMIT :limit OFFSET :offset
    """
    rows = db.execute(text(sql), params).fetchall()
    return [_row_to_dict(r) for r in rows]


def upsert_code_map(
    db: Session,
    *,
    ths_board_code: str,
    em_board_code: str,
    board_name: Optional[str] = None,
    match_method: str = MATCH_MANUAL,
    confidence: int = 100,
    is_active: bool = True,
    note: Optional[str] = None,
    board_kind: str = "industry",
) -> Dict[str, Any]:
    """手工或导入写入一条映射（按 ths / em 唯一约束 upsert）。"""
    ensure_industry_board_code_map_table(db)
    ths = _norm_code(ths_board_code)
    em = _norm_code(em_board_code)
    if not ths or not em:
        raise ValueError("ths_board_code 与 em_board_code 均不能为空")
    if ths == em:
        raise ValueError("两端代码不能相同")
    name = _norm_name(board_name) or None
    method = _norm_code(match_method) or MATCH_MANUAL
    conf = max(0, min(int(confidence), 100))
    now = datetime.now().replace(microsecond=0)

    # 若另一端已被其它映射占用，先停用冲突行（手工优先）
    db.execute(
        text(
            f"""
            UPDATE {TABLE_NAME}
            SET is_active = FALSE, updated_at = :now,
                note = COALESCE(note, '') || ' [被新映射覆盖]'
            WHERE board_kind = :kind
              AND is_active IS TRUE
              AND (
                    (ths_board_code = :ths AND em_board_code <> :em)
                 OR (em_board_code = :em AND ths_board_code <> :ths)
              )
            """
        ),
        {"kind": board_kind, "ths": ths, "em": em, "now": now},
    )

    db.execute(
        text(
            f"""
            INSERT INTO {TABLE_NAME} (
                board_kind, board_name, ths_board_code, em_board_code,
                match_method, confidence, is_active, note, created_at, updated_at
            ) VALUES (
                :kind, :name, :ths, :em, :method, :conf, :active, :note, :now, :now
            )
            ON CONFLICT (board_kind, ths_board_code) DO UPDATE SET
                board_name = COALESCE(EXCLUDED.board_name, {TABLE_NAME}.board_name),
                em_board_code = EXCLUDED.em_board_code,
                match_method = EXCLUDED.match_method,
                confidence = EXCLUDED.confidence,
                is_active = EXCLUDED.is_active,
                note = EXCLUDED.note,
                updated_at = EXCLUDED.updated_at
            """
        ),
        {
            "kind": board_kind,
            "name": name,
            "ths": ths,
            "em": em,
            "method": method,
            "conf": conf,
            "active": bool(is_active),
            "note": note,
            "now": now,
        },
    )
    row = db.execute(
        text(
            f"""
            SELECT id, board_kind, board_name, ths_board_code, em_board_code,
                   match_method, confidence, is_active, note, created_at, updated_at
            FROM {TABLE_NAME}
            WHERE board_kind = :kind AND ths_board_code = :ths
            LIMIT 1
            """
        ),
        {"kind": board_kind, "ths": ths},
    ).fetchone()
    return _row_to_dict(row) if row else {}


def deactivate_code_map(db: Session, map_id: int) -> bool:
    ensure_industry_board_code_map_table(db)
    res = db.execute(
        text(
            f"""
            UPDATE {TABLE_NAME}
            SET is_active = FALSE, updated_at = :now
            WHERE id = :id
            """
        ),
        {"id": int(map_id), "now": datetime.now().replace(microsecond=0)},
    )
    return bool(res.rowcount)


def rebuild_name_exact_maps(
    db: Session,
    *,
    board_kind: str = "industry",
    replace_auto: bool = True,
) -> Dict[str, int]:
    """按 basic_info 同名精确匹配自动生成/刷新映射。

    - 仅匹配 (tonghuashun ↔ eastmoney) 且名称 TRIM 后完全一致
    - 同侧同名多码时：THS 优先非 BK 数字码；东财优先合法 BK
    - replace_auto=True 时刷新 match_method=name_exact 的活跃行；保留 manual/import
    """
    ensure_industry_board_code_map_table(db)
    kind = board_kind if board_kind in ("industry", "concept") else "industry"
    basic = (
        "industry_board_basic_info"
        if kind == "industry"
        else "concept_board_basic_info"
    )

    rows = db.execute(
        text(
            f"""
            SELECT board_code, board_name,
                   COALESCE(NULLIF(TRIM(board_code_source), ''), :legacy) AS src
            FROM {basic}
            WHERE board_name IS NOT NULL AND TRIM(board_name) <> ''
            """
        ),
        {"legacy": LEGACY_DEFAULT_BOARD_CODE_SOURCE},
    ).fetchall()

    ths_by_name: Dict[str, List[str]] = {}
    em_by_name: Dict[str, List[str]] = {}
    for r in rows:
        code = _norm_code(r[0])
        name = _norm_name(r[1])
        src = str(r[2] or "").strip().lower()
        if not code or not name:
            continue
        if src == _SRC_THS:
            ths_by_name.setdefault(name, []).append(code)
        elif src == _SRC_EM:
            em_by_name.setdefault(name, []).append(code)

    def _pick_ths(codes: List[str]) -> Optional[str]:
        non_bk = [c for c in codes if _looks_like_ths_board_code(c)]
        pool = non_bk or codes
        # 881/885 等同花顺风格数字码优先
        pool_sorted = sorted(
            pool,
            key=lambda c: (
                0 if c.startswith(("881", "885", "886")) else 1,
                0 if c.isdigit() else 1,
                len(c),
                c,
            ),
        )
        return pool_sorted[0] if pool_sorted else None

    def _pick_em(codes: List[str]) -> Optional[str]:
        bk = [c for c in codes if is_valid_bk_board_code(c)]
        pool = bk or codes
        pool_sorted = sorted(pool, key=lambda c: (0 if is_valid_bk_board_code(c) else 1, c))
        return pool_sorted[0] if pool_sorted else None

    pairs: List[Tuple[str, str, str]] = []
    for name in sorted(set(ths_by_name) & set(em_by_name)):
        ths = _pick_ths(ths_by_name[name])
        em = _pick_em(em_by_name[name])
        if ths and em and ths != em:
            pairs.append((name, ths, em))

    now = datetime.now().replace(microsecond=0)
    deactivated = 0
    if replace_auto:
        res = db.execute(
            text(
                f"""
                UPDATE {TABLE_NAME}
                SET is_active = FALSE, updated_at = :now
                WHERE board_kind = :kind
                  AND match_method = :method
                  AND is_active IS TRUE
                """
            ),
            {"kind": kind, "method": MATCH_NAME_EXACT, "now": now},
        )
        deactivated = int(res.rowcount or 0)

    inserted = 0
    updated = 0
    skipped_manual = 0
    for name, ths, em in pairs:
        existing = db.execute(
            text(
                f"""
                SELECT id, match_method, is_active, em_board_code
                FROM {TABLE_NAME}
                WHERE board_kind = :kind AND ths_board_code = :ths
                LIMIT 1
                """
            ),
            {"kind": kind, "ths": ths},
        ).fetchone()
        if existing:
            method = str(existing[1] or "")
            if method in (MATCH_MANUAL, MATCH_IMPORT) and bool(existing[2]):
                skipped_manual += 1
                continue
            db.execute(
                text(
                    f"""
                    UPDATE {TABLE_NAME}
                    SET board_name = :name,
                        em_board_code = :em,
                        match_method = :method,
                        confidence = 100,
                        is_active = TRUE,
                        updated_at = :now
                    WHERE id = :id
                    """
                ),
                {
                    "id": int(existing[0]),
                    "name": name,
                    "em": em,
                    "method": MATCH_NAME_EXACT,
                    "now": now,
                },
            )
            updated += 1
        else:
            # em 端若被手工映射占用则跳过
            em_hit = db.execute(
                text(
                    f"""
                    SELECT match_method, is_active FROM {TABLE_NAME}
                    WHERE board_kind = :kind AND em_board_code = :em
                    LIMIT 1
                    """
                ),
                {"kind": kind, "em": em},
            ).fetchone()
            if em_hit and bool(em_hit[1]) and str(em_hit[0] or "") in (
                MATCH_MANUAL,
                MATCH_IMPORT,
            ):
                skipped_manual += 1
                continue
            db.execute(
                text(
                    f"""
                    INSERT INTO {TABLE_NAME} (
                        board_kind, board_name, ths_board_code, em_board_code,
                        match_method, confidence, is_active, created_at, updated_at
                    ) VALUES (
                        :kind, :name, :ths, :em, :method, 100, TRUE, :now, :now
                    )
                    ON CONFLICT (board_kind, em_board_code) DO UPDATE SET
                        board_name = EXCLUDED.board_name,
                        ths_board_code = EXCLUDED.ths_board_code,
                        match_method = EXCLUDED.match_method,
                        confidence = 100,
                        is_active = TRUE,
                        updated_at = EXCLUDED.updated_at
                    WHERE {TABLE_NAME}.match_method = :method
                       OR {TABLE_NAME}.is_active IS FALSE
                    """
                ),
                {
                    "kind": kind,
                    "name": name,
                    "ths": ths,
                    "em": em,
                    "method": MATCH_NAME_EXACT,
                    "now": now,
                },
            )
            inserted += 1

    return {
        "pair_candidates": len(pairs),
        "inserted": inserted,
        "updated": updated,
        "deactivated_auto": deactivated,
        "skipped_manual": skipped_manual,
    }
