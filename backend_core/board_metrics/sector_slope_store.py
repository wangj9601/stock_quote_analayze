# -*- coding: utf-8 -*-
"""板块斜率：计算、入库、读库。

口径（斜率专用，与 RPE 比价 VWAP 拆开）：
  1. 官方同花顺板块指数优先（industry_board_historical_quotes；概念有数亦可）
  2. 不足则前复权等权收益链回退
  3. 对 ln(I_t) 近 N 日 OLS，同时存 R²

业务范围：仅 board_code_source=tonghuashun；东财/华泰等不计算、不入库。
概念板本轮指数通常为空，一律走等权回退。
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
# 短线趋势：近 10 个交易日（约两周）
DEFAULT_SECTOR_SLOPE_SHORT_WINDOW = 10
# 长线 / 短中线 / 超短：与中线、短线一并默认计算并入库
DEFAULT_SECTOR_SLOPE_LONG_WINDOW = 120
DEFAULT_SECTOR_SLOPE_MID_SHORT_WINDOW = 20
DEFAULT_SECTOR_SLOPE_ULTRA_SHORT_WINDOW = 5
# 从长到短：120 / 60 / 20 / 10 / 5
DEFAULT_SLOPE_WINDOWS = (
    DEFAULT_SECTOR_SLOPE_LONG_WINDOW,
    DEFAULT_SECTOR_SLOPE_WINDOW,
    DEFAULT_SECTOR_SLOPE_MID_SHORT_WINDOW,
    DEFAULT_SECTOR_SLOPE_SHORT_WINDOW,
    DEFAULT_SECTOR_SLOPE_ULTRA_SHORT_WINDOW,
)
# 需覆盖最长窗口 120 个交易日，留余量
DEFAULT_LOOKBACK = 180
MIN_MEMBERS = 5
# 斜率业务仅同花顺；与管理端默认来源一致（非 LEGACY 空值→东财）
ALLOWED_SLOPE_BOARD_CODE_SOURCE = DEFAULT_BOARD_CODE_SOURCE  # tonghuashun
# 入库/展示默认对 ln(I_t) 回归（见模块 docstring）
DEFAULT_SLOPE_TRANSFORM = "log"
SLOPE_SOURCE_THS_INDEX = "ths_index"
SLOPE_SOURCE_EQUAL_WEIGHT = "equal_weight_return"
# 短线走强阈值略高于中线，降低噪声误标；窗口越短阈值越高
DEFAULT_SLOPE_SHORT_STRONG_THRESHOLD = 0.0015
DEFAULT_SLOPE_STRONG_THRESHOLD_BY_WINDOW = {
    120: 0.0008,
    60: 0.001,
    20: 0.0012,
    10: DEFAULT_SLOPE_SHORT_STRONG_THRESHOLD,
    5: 0.002,
}
# 走强 R² 下限：窗口越短要求越高
DEFAULT_SLOPE_R2_MIN_BY_WINDOW = {
    120: 0.25,
    60: 0.30,
    20: 0.35,
    10: 0.40,
    5: 0.50,
}

HIST_TABLE_BY_KIND = {
    "industry": "industry_board_historical_quotes",
    "concept": "concept_board_historical_quotes",
}


def slope_strong_threshold_for_window(window: int) -> float:
    """按窗口返回走强阈值；未知窗口回退到中线默认 0.001。"""
    w = int(window or DEFAULT_SECTOR_SLOPE_WINDOW)
    if w in DEFAULT_SLOPE_STRONG_THRESHOLD_BY_WINDOW:
        return float(DEFAULT_SLOPE_STRONG_THRESHOLD_BY_WINDOW[w])
    if w >= 60:
        return 0.001
    if w >= 20:
        return 0.0012
    if w >= 10:
        return float(DEFAULT_SLOPE_SHORT_STRONG_THRESHOLD)
    return 0.002


def slope_r2_min_for_window(window: int) -> float:
    """走强所需最小 R²；未知窗口按最近标准窗回退。"""
    w = int(window or DEFAULT_SECTOR_SLOPE_WINDOW)
    if w in DEFAULT_SLOPE_R2_MIN_BY_WINDOW:
        return float(DEFAULT_SLOPE_R2_MIN_BY_WINDOW[w])
    if w >= 60:
        return 0.30
    if w >= 20:
        return 0.35
    if w >= 10:
        return 0.40
    return 0.50


def min_points_for_slope_window(window: int) -> int:
    """该窗计算斜率所需最少有效点数（与历史门槛对齐）。"""
    w = int(window)
    return max(10 if w >= 20 else 5, int(w) // 2)


def resolve_slope_lookback(
    lookback: Optional[int] = None,
    windows: Optional[Sequence[int]] = None,
) -> int:
    """保证日线回看不少于最长斜率窗口。"""
    wins = [int(w) for w in (windows or DEFAULT_SLOPE_WINDOWS) if int(w) > 0]
    need = max(wins) if wins else DEFAULT_SECTOR_SLOPE_WINDOW
    base = int(lookback) if lookback is not None else DEFAULT_LOOKBACK
    return max(base, need + 20, DEFAULT_LOOKBACK)

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
    """幂等建表，并确保主键含 sector_slope_window、斜率元数据列。"""
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
                slope_source VARCHAR(32),
                slope_r2 DOUBLE PRECISION,
                slope_n INTEGER,
                updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                PRIMARY KEY (board_code, slope_asof_date, sector_slope_window)
            )
            """
        )
    )
    db.execute(
        text(
            f"""
            ALTER TABLE {table}
            ADD COLUMN IF NOT EXISTS sector_slope_window INTEGER NOT NULL DEFAULT 60
            """
        )
    )
    for col, ddl in (
        ("slope_source", "VARCHAR(32)"),
        ("slope_r2", "DOUBLE PRECISION"),
        ("slope_n", "INTEGER"),
    ):
        db.execute(
            text(
                f"""
                ALTER TABLE {table}
                ADD COLUMN IF NOT EXISTS {col} {ddl}
                """
            )
        )
    pk_rows = db.execute(
        text(
            """
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a
              ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = to_regclass(:tbl)
              AND i.indisprimary
            ORDER BY array_position(i.indkey, a.attnum)
            """
        ),
        {"tbl": table},
    ).fetchall()
    pk = [str(r[0]) for r in pk_rows]
    wanted = ["board_code", "slope_asof_date", "sector_slope_window"]
    if pk and pk != wanted:
        # 去重后重建主键，供 ON CONFLICT (board_code, slope_asof_date, sector_slope_window)
        db.execute(
            text(
                f"""
                DELETE FROM {table} a
                USING {table} b
                WHERE a.board_code = b.board_code
                  AND a.slope_asof_date = b.slope_asof_date
                  AND a.sector_slope_window = b.sector_slope_window
                  AND a.ctid < b.ctid
                """
            )
        )
        db.execute(text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_pkey"))
        db.execute(
            text(
                f"""
                ALTER TABLE {table}
                ADD PRIMARY KEY (board_code, slope_asof_date, sector_slope_window)
                """
            )
        )
        logger.info(
            "%s 主键已升级为 (board_code, slope_asof_date, sector_slope_window)",
            table,
        )
    db.execute(
        text(
            f"""
            CREATE INDEX IF NOT EXISTS ix_{table}_asof
            ON {table} (slope_asof_date DESC)
            """
        )
    )
    db.execute(
        text(
            f"""
            CREATE INDEX IF NOT EXISTS ix_{table}_window_asof
            ON {table} (sector_slope_window, slope_asof_date DESC)
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


def _hist_table_for_kind(board_kind: str) -> str:
    kind = (board_kind or "industry").strip().lower()
    return HIST_TABLE_BY_KIND.get(kind) or HIST_TABLE_BY_KIND["industry"]


def load_board_index_closes(
    db,
    board_code: str,
    *,
    board_kind: str = "industry",
    end_date: Optional[str] = None,
    lookback: int = DEFAULT_LOOKBACK,
) -> List[Dict[str, Any]]:
    """读取同花顺板块指数日收盘（close>0），按日期升序。"""
    bc = str(board_code or "").strip()
    if not bc:
        return []
    table = _hist_table_for_kind(board_kind)
    asof = _parse_asof(end_date)
    lim = max(int(lookback or DEFAULT_LOOKBACK), 30)
    try:
        params: Dict[str, Any] = {"bc": bc, "lim": lim}
        if asof is not None:
            params["asof"] = asof
            date_clause = "AND trade_date <= :asof"
        else:
            date_clause = ""
        sql = text(
            f"""
            SELECT trade_date, close
            FROM {table}
            WHERE board_code = :bc
              AND close IS NOT NULL
              AND close > 0
              {date_clause}
            ORDER BY trade_date DESC
            LIMIT :lim
            """
        )
        rows = db.execute(sql, params).fetchall()
        out: List[Dict[str, Any]] = []
        for r in reversed(rows):
            d = r[0]
            ds = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
            try:
                c = float(r[1])
            except (TypeError, ValueError):
                continue
            if c <= 0:
                continue
            out.append({"date": ds, "close": c, "trade_date": ds})
        return out
    except Exception as e:
        logger.debug("load_board_index_closes %s failed: %s", bc, e)
        try:
            db.rollback()
        except Exception:
            pass
        return []


def compute_board_sector_slope_detail(
    loader,
    board_code: str,
    *,
    board_kind: str = "industry",
    end_date: Optional[str] = None,
    window: int = DEFAULT_SECTOR_SLOPE_WINDOW,
    lookback: int = DEFAULT_LOOKBACK,
    member_limit: Optional[int] = None,
    db=None,
) -> Dict[str, Any]:
    """按窗选源算斜率，返回详情（失败时 sector_slope=None）。"""
    rows = compute_board_sector_slope_details_for_windows(
        loader,
        board_code,
        board_kind=board_kind,
        end_date=end_date,
        windows=[int(window)],
        lookback=lookback,
        member_limit=member_limit,
        db=db,
    )
    return rows[0] if rows else {
        "board_code": board_code,
        "board_kind": board_kind or "industry",
        "sector_slope": None,
        "sector_slope_window": int(window),
        "slope_transform": DEFAULT_SLOPE_TRANSFORM,
        "slope_asof_date": None,
        "member_count_used": 0,
        "slope_source": None,
        "slope_r2": None,
        "slope_n": None,
    }


def _empty_slope_rows(
    base: Dict[str, Any], wins: Sequence[int]
) -> List[Dict[str, Any]]:
    return [{**base, "sector_slope_window": w} for w in wins]


def compute_board_sector_slope_details_for_windows(
    loader,
    board_code: str,
    *,
    board_kind: str = "industry",
    end_date: Optional[str] = None,
    windows: Optional[Sequence[int]] = None,
    lookback: int = DEFAULT_LOOKBACK,
    member_limit: Optional[int] = None,
    db=None,
) -> List[Dict[str, Any]]:
    """按多个窗口分别选源并算 ln(I_t) 斜率（官方指数优先，等权收益回退）。"""
    from backend_core.strategies.rpe.sector_benchmark import (
        compute_equal_weight_return_benchmark,
        index_closes_to_benchmark,
        sector_slope_fit,
    )

    wins = [int(w) for w in (windows or DEFAULT_SLOPE_WINDOWS) if int(w) > 0]
    if not wins:
        wins = [DEFAULT_SECTOR_SLOPE_WINDOW]
    lookback = resolve_slope_lookback(lookback, wins)
    kind = (board_kind or "industry").strip().lower()
    base: Dict[str, Any] = {
        "board_code": board_code,
        "board_kind": kind or "industry",
        "sector_slope": None,
        "slope_transform": DEFAULT_SLOPE_TRANSFORM,
        "slope_asof_date": None,
        "member_count_used": 0,
        "slope_source": None,
        "slope_r2": None,
        "slope_n": None,
    }
    try:
        # --- 官方指数序列（行业优先尝试；概念有数也可） ---
        index_bench: List[Dict[str, float]] = []
        session = db
        if session is None:
            session = getattr(loader, "_db", None) or getattr(loader, "db", None)
        if session is not None:
            raw_idx = load_board_index_closes(
                session,
                board_code,
                board_kind=kind,
                end_date=end_date,
                lookback=lookback,
            )
            index_bench = index_closes_to_benchmark(raw_idx)

        # --- 等权收益链（前复权成分）---
        ew_bench: List[Dict[str, float]] = []
        member_count = 0
        members = loader.load_board_members(board_code, board_kind=kind)
        if len(members) >= MIN_MEMBERS:
            codes = [m["code"] for m in members if m.get("code")]
            lim = normalize_member_limit(member_limit)
            if lim is not None:
                codes = codes[: max(MIN_MEMBERS, lim)]
            member_count = len(codes)
            panel = loader.load_sector_panel(
                codes,
                end_date=end_date,
                lookback=lookback,
                adjust="qfq",
            )
            if len(panel) >= MIN_MEMBERS:
                ew_bench = compute_equal_weight_return_benchmark(
                    panel, min_members=MIN_MEMBERS
                )
                if ew_bench:
                    last_mc = ew_bench[-1].get("member_count")
                    if last_mc is not None:
                        member_count = int(last_mc)

        asof_candidates = []
        if index_bench:
            asof_candidates.append(str(index_bench[-1].get("date") or ""))
        if ew_bench:
            asof_candidates.append(str(ew_bench[-1].get("date") or ""))
        asof = None
        for cand in asof_candidates:
            asof = _parse_asof(cand)
            if asof:
                break
        asof = asof or _parse_asof(end_date) or date.today()

        out: List[Dict[str, Any]] = []
        for w in wins:
            need = min_points_for_slope_window(w)
            row: Dict[str, Any] = {
                **base,
                "sector_slope_window": int(w),
                "slope_asof_date": asof,
                "member_count_used": member_count if ew_bench else None,
            }
            # 按窗选源：指数点数够 → ths_index；否则等权
            chosen = None
            source = None
            if len(index_bench) >= need:
                chosen = index_bench
                source = SLOPE_SOURCE_THS_INDEX
                row["member_count_used"] = None
            elif len(ew_bench) >= need:
                chosen = ew_bench
                source = SLOPE_SOURCE_EQUAL_WEIGHT
            if chosen is None or source is None:
                out.append(row)
                continue
            fit = sector_slope_fit(
                chosen, int(w), transform=DEFAULT_SLOPE_TRANSFORM
            )
            if fit is None:
                out.append(row)
                continue
            row["sector_slope"] = float(fit["sector_slope"])
            row["slope_r2"] = float(fit["slope_r2"])
            row["slope_n"] = int(fit["slope_n"])
            row["slope_source"] = source
            # 等权链 asof 取该基准末日
            last_d = chosen[-1].get("date") if chosen else None
            row_asof = _parse_asof(str(last_d) if last_d else None) or asof
            row["slope_asof_date"] = row_asof
            out.append(row)
        return out
    except Exception as e:
        logger.debug(
            "compute_board_sector_slope_details_for_windows %s failed: %s",
            board_code,
            e,
        )
        return _empty_slope_rows(base, wins)

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
            # 行级 savepoint：单行失败不中止整批事务（避免 InFailedSqlTransaction 连锁）
            with db.begin_nested():
                db.execute(
                    text(
                        f"""
                        INSERT INTO {table} (
                            board_code, slope_asof_date, sector_slope,
                            sector_slope_window, member_count_used,
                            slope_source, slope_r2, slope_n, updated_at
                        ) VALUES (
                            :board_code, :slope_asof_date, :sector_slope,
                            :sector_slope_window, :member_count_used,
                            :slope_source, :slope_r2, :slope_n, :updated_at
                        )
                        ON CONFLICT (board_code, slope_asof_date, sector_slope_window) DO UPDATE SET
                            sector_slope = EXCLUDED.sector_slope,
                            member_count_used = EXCLUDED.member_count_used,
                            slope_source = EXCLUDED.slope_source,
                            slope_r2 = EXCLUDED.slope_r2,
                            slope_n = EXCLUDED.slope_n,
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
                        "slope_source": r.get("slope_source"),
                        "slope_r2": r.get("slope_r2"),
                        "slope_n": r.get("slope_n"),
                        "updated_at": now,
                    },
                )
            n += 1
        except Exception as e:
            logger.warning("upsert board slope %s failed: %s", bc, e)
    return n


def _row_to_slope_dict(r) -> Dict[str, Any]:
    """将 metrics 查询行转为斜率字典（兼容旧列缺失）。"""
    # r: board_code, sector_slope, sector_slope_window, slope_asof_date,
    #    member_count_used, updated_at [, slope_source, slope_r2, slope_n]
    out: Dict[str, Any] = {
        "sector_slope": float(r[1]) if r[1] is not None else None,
        "sector_slope_window": int(r[2]) if r[2] is not None else None,
        "slope_asof_date": r[3],
        "member_count_used": int(r[4]) if r[4] is not None else None,
        "updated_at": r[5],
        "slope_source": None,
        "slope_r2": None,
        "slope_n": None,
    }
    if len(r) > 6:
        out["slope_source"] = str(r[6]) if r[6] is not None else None
    if len(r) > 7:
        try:
            out["slope_r2"] = float(r[7]) if r[7] is not None else None
        except (TypeError, ValueError):
            out["slope_r2"] = None
    if len(r) > 8:
        try:
            out["slope_n"] = int(r[8]) if r[8] is not None else None
        except (TypeError, ValueError):
            out["slope_n"] = None
    return out


def load_board_sector_slopes(
    db,
    board_codes: Sequence[str],
    *,
    board_kind: str = "industry",
    asof_date: Optional[str] = None,
    window: Optional[int] = None,
) -> Dict[str, Dict[str, Any]]:
    """读取各板最新（或 ≤ asof_date）斜率。

    返回 {board_code: {sector_slope, sector_slope_window, slope_asof_date,
    member_count_used, slope_source, slope_r2, slope_n}}

    注意：PostgreSQL 在同事务内查询不存在的表会中止事务；失败时必须 rollback，
    否则后续现算路径的 SELECT 也会全部失败。读前幂等建表，避免未跑迁移时误伤。
    """
    codes = [str(c).strip() for c in board_codes if c]
    if not codes:
        return {}
    table = _table_for_kind(board_kind)
    asof = _parse_asof(asof_date)
    # 未指定窗口时默认读中线 60 日，避免与短线窗口行互相覆盖
    win = int(window) if window is not None else DEFAULT_SECTOR_SLOPE_WINDOW
    out: Dict[str, Dict[str, Any]] = {}
    try:
        ensure_board_daily_metrics_table(db, board_kind)
        params: Dict[str, Any] = {"codes": codes, "window": win}
        if asof is not None:
            params["asof"] = asof
            date_clause = "AND slope_asof_date <= :asof"
        else:
            date_clause = ""
        sql = text(
            f"""
            SELECT DISTINCT ON (board_code)
                   board_code, sector_slope, sector_slope_window,
                   slope_asof_date, member_count_used, updated_at,
                   slope_source, slope_r2, slope_n
            FROM {table}
            WHERE board_code IN :codes
              AND sector_slope_window = :window
              {date_clause}
            ORDER BY board_code, slope_asof_date DESC
            """
        ).bindparams(bindparam("codes", expanding=True))
        for r in db.execute(sql, params).fetchall():
            out[str(r[0])] = _row_to_slope_dict(r)
    except Exception as e:
        logger.debug("load_board_sector_slopes failed: %s", e)
        # 清掉失败事务，保证调用方仍可走现算
        try:
            db.rollback()
        except Exception:
            pass
    return out


def load_board_sector_slopes_multi(
    db,
    board_codes: Sequence[str],
    *,
    board_kind: str = "industry",
    asof_date: Optional[str] = None,
    windows: Optional[Sequence[int]] = None,
) -> Dict[int, Dict[str, Dict[str, Any]]]:
    """一次读取多窗口最新斜率。

    返回 {window: {board_code: {sector_slope, ...}}}
    """
    codes = [str(c).strip() for c in board_codes if c]
    wins = [int(w) for w in (windows or DEFAULT_SLOPE_WINDOWS) if int(w) > 0]
    if not codes or not wins:
        return {}
    table = _table_for_kind(board_kind)
    asof = _parse_asof(asof_date)
    out: Dict[int, Dict[str, Dict[str, Any]]] = {w: {} for w in wins}
    try:
        ensure_board_daily_metrics_table(db, board_kind)
        params: Dict[str, Any] = {"codes": codes, "windows": wins}
        if asof is not None:
            params["asof"] = asof
            date_clause = "AND slope_asof_date <= :asof"
        else:
            date_clause = ""
        sql = text(
            f"""
            SELECT DISTINCT ON (board_code, sector_slope_window)
                   board_code, sector_slope, sector_slope_window,
                   slope_asof_date, member_count_used, updated_at,
                   slope_source, slope_r2, slope_n
            FROM {table}
            WHERE board_code IN :codes
              AND sector_slope_window IN :windows
              {date_clause}
            ORDER BY board_code, sector_slope_window, slope_asof_date DESC
            """
        ).bindparams(
            bindparam("codes", expanding=True),
            bindparam("windows", expanding=True),
        )
        for r in db.execute(sql, params).fetchall():
            w = int(r[2]) if r[2] is not None else None
            if w is None or w not in out:
                continue
            out[w][str(r[0])] = _row_to_slope_dict(r)
    except Exception as e:
        logger.debug("load_board_sector_slopes_multi failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        return {w: {} for w in wins}
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
    windows: Optional[Sequence[int]] = None,
    lookback: int = DEFAULT_LOOKBACK,
    member_limit: Optional[int] = None,
    commit: bool = True,
) -> Tuple[int, int]:
    """对同花顺行业/概念板计算斜率并 upsert。

    仅 board_code_source=tonghuashun；其它来源跳过。返回 (成功写入条数, 尝试板数)。
    默认同时写入 120/60/20/10/5；若显式传 window 且未传 windows，则仅算该窗口。
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
    if windows is not None:
        win_list = [int(w) for w in windows if int(w) > 0]
    else:
        # 兼容旧调用：仅传 window 时只刷该窗；默认刷全部标准窗口
        if window != DEFAULT_SECTOR_SLOPE_WINDOW:
            win_list = [int(window)]
        else:
            win_list = list(DEFAULT_SLOPE_WINDOWS)
    if not win_list:
        win_list = [DEFAULT_SECTOR_SLOPE_WINDOW]
    lookback = resolve_slope_lookback(lookback, win_list)
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
                details = compute_board_sector_slope_details_for_windows(
                    loader,
                    bc,
                    board_kind=kind,
                    end_date=end_date,
                    windows=win_list,
                    lookback=lookback,
                    member_limit=member_limit,
                    db=db,
                )
                for detail in details:
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
    """单板：库中无有效中线斜率时现算并 upsert（同时补全部标准窗口），再读回中线。

    非同花顺来源直接返回 None。已有中线斜率则只读库不重算。
    """
    bc = str(board_code or "").strip()
    if not bc:
        return None
    src = resolve_slope_board_code_source(board_code_source)
    if src != ALLOWED_SLOPE_BOARD_CODE_SOURCE:
        return None
    kind = (board_kind or "industry").strip().lower()
    mid_w = int(window) if window else DEFAULT_SECTOR_SLOPE_WINDOW
    try:
        existing = load_board_sector_slopes(
            db, [bc], board_kind=kind, window=mid_w
        ) or {}
        row = existing.get(bc) or {}
        if row.get("sector_slope") is not None:
            return row
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    try:
        win_list = list(dict.fromkeys([mid_w, *DEFAULT_SLOPE_WINDOWS]))
        written, _total = refresh_board_sector_slopes(
            db,
            board_kind=kind,
            board_codes=[bc],
            board_code_source=src,
            end_date=end_date,
            windows=win_list,
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
        loaded = load_board_sector_slopes(
            db, [bc], board_kind=kind, window=mid_w
        ) or {}
        return loaded.get(bc)
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return None
