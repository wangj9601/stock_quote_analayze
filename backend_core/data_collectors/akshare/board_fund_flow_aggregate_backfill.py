# -*- coding: utf-8 -*-
"""根据个股资金流向（stock_fund_flow_daily）上卷回填板块资金流向。

覆盖：行业板块（industry）+ 概念板块（concept）→ board_fund_flow_daily，
source=aggregate。默认仅补缺（无行或 main_net_inflow 为空）；
--force 可覆盖已有 aggregate 行；--force-all 可覆盖任意来源。
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import text

from backend_api.utils.board_code_source import DEFAULT_BOARD_CODE_SOURCE
from backend_core.data_collectors.akshare.board_fund_flow_daily import (
    SOURCE_AGGREGATE,
    UPSERT_SQL,
    _empty_row,
)
from backend_core.database.db import SessionLocal

logger = logging.getLogger(__name__)

# 不覆盖的主路径来源（除非 --force-all）
PROTECTED_SOURCES = frozenset({"ths_fund_flow", "ths_summary", "em_rank"})

# 回填专用：已由 Python 过滤冲突后，允许用 aggregate 覆盖已有金额
AGGREGATE_FORCE_UPSERT_SQL = text(
    """
    INSERT INTO board_fund_flow_daily (
        board_kind, board_code_source, board_code, trade_date, board_name,
        change_percent, inflow_amount, outflow_amount, main_net_inflow,
        main_net_inflow_pct, super_large_net_inflow, large_net_inflow,
        mid_net_inflow, small_net_inflow, source, em_board_code,
        created_at, updated_at
    ) VALUES (
        :board_kind, :board_code_source, :board_code, :trade_date, :board_name,
        :change_percent, :inflow_amount, :outflow_amount, :main_net_inflow,
        :main_net_inflow_pct, :super_large_net_inflow, :large_net_inflow,
        :mid_net_inflow, :small_net_inflow, :source, :em_board_code,
        :created_at, :updated_at
    )
    ON CONFLICT (board_kind, board_code_source, board_code, trade_date) DO UPDATE SET
        board_name = COALESCE(EXCLUDED.board_name, board_fund_flow_daily.board_name),
        inflow_amount = COALESCE(
            EXCLUDED.inflow_amount, board_fund_flow_daily.inflow_amount
        ),
        outflow_amount = COALESCE(
            EXCLUDED.outflow_amount, board_fund_flow_daily.outflow_amount
        ),
        main_net_inflow = COALESCE(
            EXCLUDED.main_net_inflow, board_fund_flow_daily.main_net_inflow
        ),
        source = EXCLUDED.source,
        em_board_code = COALESCE(
            EXCLUDED.em_board_code, board_fund_flow_daily.em_board_code
        ),
        updated_at = EXCLUDED.updated_at
    """
)

KIND_TABLES = {
    "industry": {
        "basic": "industry_board_basic_info",
        "cons": "industry_board_constituents",
        "kind": "industry",
    },
    "concept": {
        "basic": "concept_board_basic_info",
        "cons": "concept_board_constituents",
        "kind": "concept",
    },
}


def _parse_ymd(raw: str) -> date:
    return datetime.strptime(str(raw).strip()[:10], "%Y-%m-%d").date()


def resolve_date_range(
    *,
    trade_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    days: Optional[int] = None,
) -> Tuple[date, date]:
    """解析回填日期区间。优先级：单日 > start/end > days（默认 30）。"""
    if trade_date:
        d = _parse_ymd(trade_date)
        return d, d
    if start_date or end_date:
        if not (start_date and end_date):
            raise ValueError("start_date 与 end_date 必须同时提供")
        start = _parse_ymd(start_date)
        end = _parse_ymd(end_date)
        if start > end:
            raise ValueError("start_date 不能晚于 end_date")
        return start, end
    n = int(days) if days is not None else 30
    if n <= 0:
        raise ValueError("days 必须为正整数")
    end = datetime.now().date()
    start = end - timedelta(days=n - 1)
    return start, end


def _aggregate_sql(board_kind: str) -> Any:
    meta = KIND_TABLES[board_kind]
    basic = meta["basic"]
    cons = meta["cons"]
    # 成分码：优先同花顺 board_code 下已有成分；否则走东财映射码
    return text(
        f"""
        WITH board_cons AS (
            SELECT
                b.board_code,
                b.board_name,
                CASE
                    WHEN EXISTS (
                        SELECT 1 FROM {cons} c0
                        WHERE c0.board_code = b.board_code
                        LIMIT 1
                    )
                    THEN b.board_code
                    ELSE COALESCE(m.em_board_code, b.board_code)
                END AS cons_board_code,
                m.em_board_code
            FROM {basic} b
            LEFT JOIN industry_board_code_map m
              ON m.board_kind = :kind
             AND m.ths_board_code = b.board_code
             AND m.is_active IS TRUE
            WHERE COALESCE(NULLIF(TRIM(b.board_code_source), ''), '') = :src
        )
        SELECT
            bc.board_code,
            bc.board_name,
            bc.em_board_code,
            f.trade_date AS trade_date,
            SUM(f.inflow_amount) AS inflow_sum,
            SUM(f.outflow_amount) AS outflow_sum,
            SUM(f.net_amount) AS net_sum,
            COUNT(f.code)::int AS member_count
        FROM board_cons bc
        JOIN {cons} c ON c.board_code = bc.cons_board_code
        JOIN stock_fund_flow_daily f
          ON f.code = c.stock_code
         AND f.trade_date >= :start_td
         AND f.trade_date <= :end_td
        GROUP BY bc.board_code, bc.board_name, bc.em_board_code, f.trade_date
        HAVING SUM(f.net_amount) IS NOT NULL
            OR SUM(f.inflow_amount) IS NOT NULL
            OR SUM(f.outflow_amount) IS NOT NULL
        """
    )


def _load_existing(
    session,
    *,
    board_kind: str,
    start: date,
    end: date,
) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """(board_code, trade_date_iso) → {source, main_net_inflow}。"""
    rows = session.execute(
        text(
            """
            SELECT board_code, trade_date, source, main_net_inflow
            FROM board_fund_flow_daily
            WHERE board_kind = :kind
              AND board_code_source = :src
              AND trade_date >= :start_d
              AND trade_date <= :end_d
            """
        ),
        {
            "kind": board_kind,
            "src": DEFAULT_BOARD_CODE_SOURCE,
            "start_d": start,
            "end_d": end,
        },
    ).fetchall()
    out: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for code, td, source, net in rows:
        if hasattr(td, "isoformat"):
            td_s = td.isoformat()
        else:
            td_s = str(td)[:10]
        out[(str(code).strip(), td_s)] = {
            "source": str(source or "").strip(),
            "main_net_inflow": net,
        }
    return out


def _should_write(
    existing: Optional[Dict[str, Any]],
    *,
    force: bool,
    force_all: bool,
) -> bool:
    if existing is None:
        return True
    if force_all:
        return True
    net = existing.get("main_net_inflow")
    src = existing.get("source") or ""
    if net is None:
        return True
    if force and src == SOURCE_AGGREGATE:
        return True
    if force and src not in PROTECTED_SOURCES:
        return True
    return False


def _row_from_agg(
    *,
    board_kind: str,
    board_code: str,
    board_name: str,
    trade_date: date,
    inflow_sum: Any,
    outflow_sum: Any,
    net_sum: Any,
    em_board_code: Any = None,
) -> Dict[str, Any]:
    row = _empty_row(
        board_kind=board_kind,
        board_code=board_code,
        board_name=board_name or board_code,
        trade_date=trade_date,
        source=SOURCE_AGGREGATE,
    )
    if inflow_sum is not None:
        row["inflow_amount"] = float(inflow_sum)
    if outflow_sum is not None:
        row["outflow_amount"] = float(outflow_sum)
    if net_sum is not None:
        row["main_net_inflow"] = float(net_sum)
    if em_board_code:
        row["em_board_code"] = str(em_board_code).strip()
    return row


def _to_trade_date(raw: Any) -> date:
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    return _parse_ymd(str(raw))


def fetch_aggregate_rows(
    session,
    *,
    board_kind: str,
    start: date,
    end: date,
    force: bool = False,
    force_all: bool = False,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """查询上卷结果并按冲突策略过滤，返回待写入行与计数。"""
    if board_kind not in KIND_TABLES:
        raise ValueError(f"不支持的 board_kind: {board_kind}")

    stats = {
        "candidates": 0,
        "written": 0,
        "skipped_protected": 0,
        "skipped_existing": 0,
    }
    try:
        db_rows = session.execute(
            _aggregate_sql(board_kind),
            {
                "kind": board_kind,
                "src": DEFAULT_BOARD_CODE_SOURCE,
                "start_td": start.isoformat(),
                "end_td": end.isoformat(),
            },
        ).fetchall()
    except Exception as e:
        logger.warning("成分上卷查询失败 kind=%s: %s", board_kind, e)
        try:
            session.rollback()
        except Exception:
            pass
        return [], stats

    existing = _load_existing(
        session, board_kind=board_kind, start=start, end=end
    )
    out: List[Dict[str, Any]] = []
    for (
        board_code,
        board_name,
        em_board_code,
        trade_date_raw,
        inflow_sum,
        outflow_sum,
        net_sum,
        _member_count,
    ) in db_rows:
        stats["candidates"] += 1
        code = str(board_code or "").strip()
        if not code:
            continue
        td = _to_trade_date(trade_date_raw)
        td_s = td.isoformat()
        ex = existing.get((code, td_s))
        if not _should_write(ex, force=force, force_all=force_all):
            src = (ex or {}).get("source") or ""
            if src in PROTECTED_SOURCES:
                stats["skipped_protected"] += 1
            else:
                stats["skipped_existing"] += 1
            continue
        out.append(
            _row_from_agg(
                board_kind=board_kind,
                board_code=code,
                board_name=str(board_name or "").strip() or code,
                trade_date=td,
                inflow_sum=inflow_sum,
                outflow_sum=outflow_sum,
                net_sum=net_sum,
                em_board_code=em_board_code,
            )
        )
    stats["written"] = len(out)
    return out, stats


def upsert_aggregate_rows(
    rows: Sequence[Dict[str, Any]],
    batch_size: int = 200,
    *,
    force_overwrite: bool = False,
) -> int:
    """写入上卷结果。force_overwrite=True 时覆盖已有金额（供 --force/--force-all）。"""
    if not rows:
        return 0
    sql = AGGREGATE_FORCE_UPSERT_SQL if force_overwrite else UPSERT_SQL
    session = SessionLocal()
    written = 0
    try:
        for i in range(0, len(rows), batch_size):
            chunk = list(rows[i : i + batch_size])
            session.execute(sql, chunk)
            session.commit()
            written += len(chunk)
        return written
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def backfill_board_fund_flow_from_stocks(
    *,
    trade_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    days: Optional[int] = None,
    board_kinds: Optional[Iterable[str]] = None,
    force: bool = False,
    force_all: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """按个股资金流上卷回填行业/概念板块资金流。"""
    start, end = resolve_date_range(
        trade_date=trade_date,
        start_date=start_date,
        end_date=end_date,
        days=days,
    )
    kinds = list(board_kinds) if board_kinds else ["industry", "concept"]
    for k in kinds:
        if k not in KIND_TABLES:
            raise ValueError(f"不支持的 board_kind: {k}")

    result: Dict[str, Any] = {
        "success": True,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "force": force,
        "force_all": force_all,
        "dry_run": dry_run,
        "kinds": {},
        "total_upserted": 0,
    }

    session = SessionLocal()
    try:
        for kind in kinds:
            rows, stats = fetch_aggregate_rows(
                session,
                board_kind=kind,
                start=start,
                end=end,
                force=force,
                force_all=force_all,
            )
            upserted = 0
            if rows and not dry_run:
                upserted = upsert_aggregate_rows(
                    rows, force_overwrite=bool(force or force_all)
                )
            elif rows and dry_run:
                upserted = 0
            kind_stats = {
                **stats,
                "upserted": upserted if not dry_run else 0,
                "would_upsert": len(rows) if dry_run else upserted,
            }
            result["kinds"][kind] = kind_stats
            result["total_upserted"] += kind_stats["upserted"]
            logger.info(
                "板块资金流上卷回填 kind=%s %s → %s %s",
                kind,
                start.isoformat(),
                end.isoformat(),
                kind_stats,
            )
    finally:
        session.close()
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import json

    print(json.dumps(backfill_board_fund_flow_from_stocks(days=5), ensure_ascii=False, indent=2))
