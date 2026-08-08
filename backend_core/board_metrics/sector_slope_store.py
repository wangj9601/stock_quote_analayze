# -*- coding: utf-8 -*-
"""板块量权基准斜率：计算、入库、读库。

口径与 RPE/GMS 一致：I_t = Σ(close·volume)/Σ(volume)，近 N 日线性回归斜率。
行业/概念板均无官方日线指数时，用成分股日线合成后写入对应日度指标表，供策略复用。

业务范围：仅处理 board_code_source=tonghuashun（同花顺）的行业板与概念板；
东财/华泰等其它来源一律不计算、不入库。
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import bindparam, text

from backend_api.utils.board_code_source import (
    DEFAULT_BOARD_CODE_SOURCE,
    normalize_board_code_source,
)

logger = logging.getLogger(__name__)

DEFAULT_SECTOR_SLOPE_WINDOW = 60
DEFAULT_LOOKBACK = 120
MIN_MEMBERS = 5
# 斜率业务仅同花顺；与管理端默认来源一致（非 LEGACY 空值→东财）
ALLOWED_SLOPE_BOARD_CODE_SOURCE = DEFAULT_BOARD_CODE_SOURCE  # tonghuashun

TABLE_BY_KIND = {
    "industry": "industry_board_daily_metrics",
    "concept": "concept_board_daily_metrics",
}

_BASIC_INFO_BY_KIND = {
    "industry": "industry_board_basic_info",
    "concept": "concept_board_basic_info",
}


def resolve_slope_board_code_source(raw: Any = None) -> str:
    """斜率链路允许的来源：仅 tonghuashun（参数缺省时用 DEFAULT）。"""
    return normalize_board_code_source(raw) or ALLOWED_SLOPE_BOARD_CODE_SOURCE


def is_allowed_slope_board_source(raw: Any) -> bool:
    return normalize_board_code_source(raw) == ALLOWED_SLOPE_BOARD_CODE_SOURCE


def normalize_member_limit(limit: Any) -> Optional[int]:
    """None/0/负数表示不截断（全成分）；正整数为上限。"""
    if limit is None:
        return None
    try:
        n = int(limit)
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    return n


def _table_for_kind(board_kind: str) -> str:
    kind = (board_kind or "industry").strip().lower()
    if kind not in TABLE_BY_KIND:
        kind = "industry"
    return TABLE_BY_KIND[kind]


def ensure_board_daily_metrics_table(db, board_kind: str = "industry") -> None:
    """幂等建表（采集路径也可调用，避免未跑迁移时失败）。"""
    table = _table_for_kind(board_kind)
    db.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {table} (
                board_code VARCHAR(20) NOT NULL,
                slope_asof_date DATE NOT NULL,
                sector_slope DOUBLE PRECISION,
                sector_slope_window INTEGER NOT NULL DEFAULT 60,
                member_count_used INTEGER,
                updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                PRIMARY KEY (board_code, slope_asof_date)
            )
            """
        )
    )
    db.execute(
        text(
            f"""
            CREATE INDEX IF NOT EXISTS ix_{table}_asof
            ON {table} (slope_asof_date DESC)
            """
        )
    )


def _parse_asof(end_date: Optional[str]) -> Optional[date]:
    if not end_date:
        return None
    s = str(end_date).strip()[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def compute_board_sector_slope_detail(
    loader,
    board_code: str,
    *,
    board_kind: str = "industry",
    end_date: Optional[str] = None,
    window: int = DEFAULT_SECTOR_SLOPE_WINDOW,
    lookback: int = DEFAULT_LOOKBACK,
    member_limit: Optional[int] = None,
) -> Dict[str, Any]:
    """合成板块量权基准并算斜率，返回详情（失败时 sector_slope=None）。"""
    from backend_core.strategies.rpe.sector_benchmark import compute_vwap_benchmark, sector_slope

    out: Dict[str, Any] = {
        "board_code": board_code,
        "board_kind": board_kind or "industry",
        "sector_slope": None,
        "sector_slope_window": int(window),
        "slope_asof_date": None,
        "member_count_used": 0,
    }
    try:
        members = loader.load_board_members(board_code, board_kind=board_kind)
        if len(members) < MIN_MEMBERS:
            return out
        codes = [m["code"] for m in members if m.get("code")]
        lim = normalize_member_limit(member_limit)
        if lim is not None:
            codes = codes[: max(MIN_MEMBERS, lim)]
        out["member_count_used"] = len(codes)
        panel = loader.load_sector_panel(codes, end_date=end_date, lookback=lookback)
        if len(panel) < MIN_MEMBERS:
            return out
        date_members = loader.build_date_members(panel)
        benchmark = compute_vwap_benchmark(date_members)
        if len(benchmark) < max(10, int(window) // 2):
            return out
        slope = sector_slope(benchmark, int(window))
        out["sector_slope"] = float(slope) if slope is not None else None
        last_d = benchmark[-1].get("date") if benchmark else None
        asof = _parse_asof(str(last_d) if last_d else None) or _parse_asof(end_date)
        if asof is None:
            asof = date.today()
        out["slope_asof_date"] = asof
        return out
    except Exception as e:
        logger.debug("compute_board_sector_slope_detail %s failed: %s", board_code, e)
        return out


def upsert_board_sector_slopes(
    db,
    rows: Sequence[Dict[str, Any]],
    *,
    board_kind: str = "industry",
) -> int:
    """批量 upsert 斜率；返回成功写入条数。"""
    if not rows:
        return 0
    ensure_board_daily_metrics_table(db, board_kind)
    table = _table_for_kind(board_kind)
    n = 0
    now = datetime.now()
    for r in rows:
        bc = str(r.get("board_code") or "").strip()
        asof = r.get("slope_asof_date")
        if not bc or asof is None:
            continue
        if isinstance(asof, str):
            asof = _parse_asof(asof)
        if asof is None:
            continue
        try:
            db.execute(
                text(
                    f"""
                    INSERT INTO {table} (
                        board_code, slope_asof_date, sector_slope,
                        sector_slope_window, member_count_used, updated_at
                    ) VALUES (
                        :board_code, :slope_asof_date, :sector_slope,
                        :sector_slope_window, :member_count_used, :updated_at
                    )
                    ON CONFLICT (board_code, slope_asof_date) DO UPDATE SET
                        sector_slope = EXCLUDED.sector_slope,
                        sector_slope_window = EXCLUDED.sector_slope_window,
                        member_count_used = EXCLUDED.member_count_used,
                        updated_at = EXCLUDED.updated_at
                    """
                ),
                {
                    "board_code": bc,
                    "slope_asof_date": asof,
                    "sector_slope": r.get("sector_slope"),
                    "sector_slope_window": int(
                        r.get("sector_slope_window") or DEFAULT_SECTOR_SLOPE_WINDOW
                    ),
                    "member_count_used": r.get("member_count_used"),
                    "updated_at": now,
                },
            )
            n += 1
        except Exception as e:
            logger.warning("upsert board slope %s failed: %s", bc, e)
    return n


def load_board_sector_slopes(
    db,
    board_codes: Sequence[str],
    *,
    board_kind: str = "industry",
    asof_date: Optional[str] = None,
    window: Optional[int] = None,
) -> Dict[str, Dict[str, Any]]:
    """读取各板最新（或 ≤ asof_date）斜率。

    返回 {board_code: {sector_slope, sector_slope_window, slope_asof_date, member_count_used}}

    注意：PostgreSQL 在同事务内查询不存在的表会中止事务；失败时必须 rollback，
    否则后续现算路径的 SELECT 也会全部失败。读前幂等建表，避免未跑迁移时误伤。
    """
    codes = [str(c).strip() for c in board_codes if c]
    if not codes:
        return {}
    table = _table_for_kind(board_kind)
    asof = _parse_asof(asof_date)
    out: Dict[str, Dict[str, Any]] = {}
    try:
        ensure_board_daily_metrics_table(db, board_kind)
        # DISTINCT ON 取每板最新 asof（可选窗口过滤）
        win_clause = ""
        params: Dict[str, Any] = {"codes": codes}
        if window is not None:
            win_clause = "AND sector_slope_window = :window"
            params["window"] = int(window)
        if asof is not None:
            params["asof"] = asof
            date_clause = "AND slope_asof_date <= :asof"
        else:
            date_clause = ""
        sql = text(
            f"""
            SELECT DISTINCT ON (board_code)
                   board_code, sector_slope, sector_slope_window,
                   slope_asof_date, member_count_used, updated_at
            FROM {table}
            WHERE board_code IN :codes
              {date_clause}
              {win_clause}
            ORDER BY board_code, slope_asof_date DESC
            """
        ).bindparams(bindparam("codes", expanding=True))
        for r in db.execute(sql, params).fetchall():
            out[str(r[0])] = {
                "sector_slope": float(r[1]) if r[1] is not None else None,
                "sector_slope_window": int(r[2]) if r[2] is not None else None,
                "slope_asof_date": r[3],
                "member_count_used": int(r[4]) if r[4] is not None else None,
                "updated_at": r[5],
            }
    except Exception as e:
        logger.debug("load_board_sector_slopes failed: %s", e)
        # 清掉失败事务，保证调用方仍可走现算
        try:
            db.rollback()
        except Exception:
            pass
    return out


def filter_board_codes_by_source(
    db,
    board_codes: Sequence[str],
    *,
    board_kind: str = "industry",
    board_code_source: str = ALLOWED_SLOPE_BOARD_CODE_SOURCE,
) -> List[str]:
    """仅保留 board_code_source 匹配的板码；其它来源一律剔除（失败时空列表，宁缺毋滥）。"""
    codes = [str(c).strip() for c in board_codes if c]
    if not codes:
        return []
    src = resolve_slope_board_code_source(board_code_source)
    if src != ALLOWED_SLOPE_BOARD_CODE_SOURCE:
        # 业务只服务同花顺；请求其它来源时直接不处理
        return []
    kind = (board_kind or "industry").strip().lower()
    table = _BASIC_INFO_BY_KIND.get(kind) or _BASIC_INFO_BY_KIND["industry"]
    try:
        sql = text(
            f"""
            SELECT board_code
            FROM {table}
            WHERE board_code IN :codes
              AND LOWER(TRIM(COALESCE(board_code_source, ''))) = :src
            """
        ).bindparams(bindparam("codes", expanding=True))
        allowed = {
            str(r[0])
            for r in db.execute(sql, {"codes": codes, "src": src}).fetchall()
            if r[0]
        }
        return [c for c in codes if c in allowed]
    except Exception as e:
        logger.warning("filter_board_codes_by_source failed: %s", e)
        return []


def list_industry_board_codes(
    db,
    *,
    limit: Optional[int] = None,
    board_code_source: str = ALLOWED_SLOPE_BOARD_CODE_SOURCE,
) -> List[str]:
    """列出待算斜率的行业板：仅 tonghuashun。不回退扫成分表（避免混入东财等）。"""
    src = resolve_slope_board_code_source(board_code_source)
    if src != ALLOWED_SLOPE_BOARD_CODE_SOURCE:
        return []
    sql = (
        "SELECT board_code FROM industry_board_basic_info "
        "WHERE LOWER(TRIM(COALESCE(board_code_source, ''))) = :src "
        "ORDER BY board_code"
    )
    if limit and limit > 0:
        sql += f" LIMIT {int(limit)}"
    try:
        return [
            str(r[0])
            for r in db.execute(text(sql), {"src": src}).fetchall()
            if r[0]
        ]
    except Exception as e:
        logger.warning("list_industry_board_codes failed: %s", e)
        return []


def list_concept_board_codes(
    db,
    *,
    limit: Optional[int] = None,
    board_code_source: str = ALLOWED_SLOPE_BOARD_CODE_SOURCE,
) -> List[str]:
    """列出待算斜率的概念板：仅 tonghuashun。不回退扫成分表（避免混入东财等）。"""
    src = resolve_slope_board_code_source(board_code_source)
    if src != ALLOWED_SLOPE_BOARD_CODE_SOURCE:
        return []
    sql = (
        "SELECT board_code FROM concept_board_basic_info "
        "WHERE LOWER(TRIM(COALESCE(board_code_source, ''))) = :src "
        "ORDER BY board_code"
    )
    if limit and limit > 0:
        sql += f" LIMIT {int(limit)}"
    try:
        return [
            str(r[0])
            for r in db.execute(text(sql), {"src": src}).fetchall()
            if r[0]
        ]
    except Exception as e:
        logger.warning("list_concept_board_codes failed: %s", e)
        return []


def refresh_board_sector_slopes(
    db,
    *,
    board_kind: str = "industry",
    board_codes: Optional[Sequence[str]] = None,
    board_code_source: str = ALLOWED_SLOPE_BOARD_CODE_SOURCE,
    end_date: Optional[str] = None,
    window: int = DEFAULT_SECTOR_SLOPE_WINDOW,
    lookback: int = DEFAULT_LOOKBACK,
    member_limit: Optional[int] = None,
    commit: bool = True,
) -> Tuple[int, int]:
    """对同花顺行业/概念板计算斜率并 upsert。

    仅 board_code_source=tonghuashun；其它来源跳过。返回 (成功写入条数, 尝试板数)。
    失败单板跳过，不抛到外层。board_kind 支持 industry / concept。
    """
    from backend_core.strategies.rpe.data_loader import RPEDataLoader

    kind = (board_kind or "industry").strip().lower()
    src = resolve_slope_board_code_source(board_code_source)
    if src != ALLOWED_SLOPE_BOARD_CODE_SOURCE:
        logger.info(
            "refresh_board_sector_slopes skip: source=%s not allowed (only %s)",
            src,
            ALLOWED_SLOPE_BOARD_CODE_SOURCE,
        )
        return 0, 0
    try:
        ensure_board_daily_metrics_table(db, kind)
        if board_codes is None:
            if kind == "concept":
                codes = list_concept_board_codes(db, board_code_source=src)
            else:
                codes = list_industry_board_codes(db, board_code_source=src)
        else:
            codes = filter_board_codes_by_source(
                db,
                board_codes,
                board_kind=kind,
                board_code_source=src,
            )

        loader = RPEDataLoader(db)
        rows: List[Dict[str, Any]] = []
        for bc in codes:
            try:
                detail = compute_board_sector_slope_detail(
                    loader,
                    bc,
                    board_kind=kind,
                    end_date=end_date,
                    window=window,
                    lookback=lookback,
                    member_limit=member_limit,
                )
                if detail.get("sector_slope") is None or detail.get("slope_asof_date") is None:
                    continue
                rows.append(detail)
            except Exception as e:
                logger.warning("refresh slope skip board %s: %s", bc, e)

        n = upsert_board_sector_slopes(db, rows, board_kind=kind)
        if commit:
            db.commit()
        return n, len(codes)
    except Exception as e:
        # 整批失败必须上抛，由采集/API 写入 fail 操作日志；禁止吞成 (0,0) 被当成成功
        logger.exception("refresh_board_sector_slopes failed: %s", e)
        if commit:
            try:
                db.rollback()
            except Exception:
                pass
        raise


def write_slope_collect_log(
    operation_type: str,
    operation_desc: str,
    affected_rows: int,
    status: str,
    error_message: Optional[str] = None,
) -> None:
    """写入 realtime_collect_operation_logs，供采集挂载与手动刷新核对。"""
    from backend_api.database import SessionLocal

    session = SessionLocal()
    try:
        now = datetime.now().replace(microsecond=0)
        session.execute(
            text(
                """
                INSERT INTO realtime_collect_operation_logs
                    (operation_type, operation_desc, affected_rows, status, error_message, created_at)
                VALUES
                    (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :created_at)
                """
            ),
            {
                "operation_type": operation_type,
                "operation_desc": operation_desc,
                "affected_rows": int(affected_rows or 0),
                "status": status,
                "error_message": error_message or "",
                "created_at": now,
            },
        )
        session.commit()
    except Exception as e:
        logger.warning("write_slope_collect_log failed: %s", e)
        try:
            session.rollback()
        except Exception:
            pass
    finally:
        session.close()


def ensure_board_sector_slope(
    db,
    board_code: str,
    *,
    board_kind: str = "industry",
    board_code_source: str = ALLOWED_SLOPE_BOARD_CODE_SOURCE,
    end_date: Optional[str] = None,
    window: int = DEFAULT_SECTOR_SLOPE_WINDOW,
    lookback: int = DEFAULT_LOOKBACK,
    member_limit: Optional[int] = None,
    commit: bool = True,
) -> Optional[Dict[str, Any]]:
    """单板：库中无有效斜率时现算全成分并 upsert，再读回。

    非同花顺来源直接返回 None。已有斜率则只读库不重算。
    """
    bc = str(board_code or "").strip()
    if not bc:
        return None
    src = resolve_slope_board_code_source(board_code_source)
    if src != ALLOWED_SLOPE_BOARD_CODE_SOURCE:
        return None
    kind = (board_kind or "industry").strip().lower()
    try:
        existing = load_board_sector_slopes(db, [bc], board_kind=kind) or {}
        row = existing.get(bc) or {}
        if row.get("sector_slope") is not None:
            return row
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    try:
        written, _total = refresh_board_sector_slopes(
            db,
            board_kind=kind,
            board_codes=[bc],
            board_code_source=src,
            end_date=end_date,
            window=window,
            lookback=lookback,
            member_limit=member_limit,
            commit=commit,
        )
    except Exception as e:
        logger.warning("ensure_board_sector_slope refresh failed %s: %s", bc, e)
        try:
            db.rollback()
        except Exception:
            pass
        return None
    if written <= 0:
        return None
    try:
        loaded = load_board_sector_slopes(db, [bc], board_kind=kind) or {}
        return loaded.get(bc)
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return None
