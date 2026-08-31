#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量补齐缺失的 A 股前复权因子（stock_adj_factor）。

默认：在指定交易日 RS 候选池内，找出库内无 ``akshare_sina_qfq`` / ``baostock_qfq``
因子的股票，调用 ``ensure_adj_factors`` 外网拉取并 UPSERT。

用法（在项目根目录）::

    python migrations/backfill_missing_adj_factors.py --dry-run
    python migrations/backfill_missing_adj_factors.py --trade-date 2025-11-26
    python migrations/backfill_missing_adj_factors.py --codes 920000,920001
    python migrations/backfill_missing_adj_factors.py --scope all --limit 50
    python migrations/backfill_missing_adj_factors.py --force-refresh --factor-source auto

限速：遵循 ``ADJ_FACTOR_FETCH_THROTTLE_ENABLED`` / ``ADJ_FACTOR_FETCH_INTERVAL_SEC``（默认约 3 秒/票）。
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from typing import List, Optional, Sequence

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_api.database import SessionLocal
from backend_api.utils.adj_quotes import AdjQuotesError, ensure_adj_factors

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("backfill_adj_factor")

RS_SOURCES = ("akshare_sina_qfq", "baostock_qfq")

SQL_MISSING_IN_RS_POOL = """
WITH cand AS (
    SELECT DISTINCT hq.code
    FROM historical_quotes hq
    INNER JOIN stock_basic_info b ON b.code = hq.code
    WHERE hq.date = :trade_date
      AND LENGTH(TRIM(hq.code)) = 6
      AND COALESCE(b.collect_enabled, TRUE) = TRUE
      AND COALESCE(b.name, '') NOT LIKE '%ST%'
      AND COALESCE(b.name, '') NOT LIKE '%退%'
)
SELECT c.code
FROM cand c
WHERE NOT EXISTS (
    SELECT 1
    FROM stock_adj_factor f
    WHERE f.code = c.code
      AND f.source IN :sources
      AND f.trade_date > DATE '1900-01-01'
      AND f.adj_factor > 0
)
ORDER BY c.code
"""

SQL_MISSING_ALL_CN = """
SELECT b.code
FROM stock_basic_info b
WHERE LENGTH(TRIM(b.code)) = 6
  AND COALESCE(b.collect_enabled, TRUE) = TRUE
  AND COALESCE(b.name, '') NOT LIKE '%ST%'
  AND COALESCE(b.name, '') NOT LIKE '%退%'
  AND NOT EXISTS (
      SELECT 1
      FROM stock_adj_factor f
      WHERE f.code = b.code
        AND f.source IN :sources
        AND f.trade_date > DATE '1900-01-01'
        AND f.adj_factor > 0
  )
ORDER BY b.code
"""

SQL_LATEST_TRADE_DATE = """
SELECT MAX(hq.date)
FROM historical_quotes hq
WHERE LENGTH(TRIM(hq.code)) = 6
"""


def _parse_codes(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    out: List[str] = []
    for part in raw.replace(";", ",").split(","):
        c = part.strip()
        if not c:
            continue
        if c.isdigit():
            c = c.zfill(6) if len(c) <= 6 else c
        out.append(c)
    return out


def resolve_trade_date(db: Session, trade_date: Optional[str]) -> str:
    if trade_date:
        return trade_date[:10]
    row = db.execute(text(SQL_LATEST_TRADE_DATE)).scalar()
    if not row:
        raise SystemExit("historical_quotes 无 A 股行情，无法推断 trade_date")
    return str(row)[:10]


def list_missing_codes(
    db: Session,
    *,
    trade_date: Optional[str],
    scope: str,
    codes: Sequence[str],
    limit: Optional[int],
) -> List[str]:
    if codes:
        selected = list(codes)
    elif scope == "all":
        stmt = text(SQL_MISSING_ALL_CN).bindparams(
            bindparam("sources", expanding=True)
        )
        rows = db.execute(stmt, {"sources": list(RS_SOURCES)}).fetchall()
        selected = [str(r[0]).strip() for r in rows if r and r[0]]
    else:
        date_s = resolve_trade_date(db, trade_date)
        stmt = text(SQL_MISSING_IN_RS_POOL).bindparams(
            bindparam("sources", expanding=True)
        )
        rows = db.execute(
            stmt,
            {"trade_date": date_s, "sources": list(RS_SOURCES)},
        ).fetchall()
        selected = [str(r[0]).strip() for r in rows if r and r[0]]
        logger.info("RS 候选池 trade_date=%s 缺因子 %s 只", date_s, len(selected))

    if limit is not None and limit > 0:
        selected = selected[: int(limit)]
    return selected


def backfill(
    codes: Sequence[str],
    *,
    dry_run: bool,
    force_refresh: bool,
    factor_source: str,
    continue_on_error: bool,
) -> int:
    if not codes:
        logger.info("无待补齐股票，退出")
        return 0

    logger.info(
        "待处理 %s 只 dry_run=%s force_refresh=%s factor_source=%s",
        len(codes),
        dry_run,
        force_refresh,
        factor_source,
    )
    if dry_run:
        for i, code in enumerate(codes, 1):
            print(f"  [{i}/{len(codes)}] {code}")
        print(f"dry-run 合计 {len(codes)} 只（未拉取外网）")
        return 0

    db = SessionLocal()
    ok = skipped = failed = 0
    t0 = time.time()
    try:
        for i, code in enumerate(codes, 1):
            try:
                result = ensure_adj_factors(
                    db,
                    code,
                    force_refresh=force_refresh,
                    factor_source=factor_source,
                    prefer_db=not force_refresh,
                )
                db.commit()
                if result.get("factor_fetched"):
                    ok += 1
                    logger.info(
                        "[%s/%s] %s 外网补齐 source=%s rows=%s asof=%s",
                        i,
                        len(codes),
                        code,
                        result.get("source"),
                        len(result.get("factors") or []),
                        result.get("adj_factor_asof"),
                    )
                else:
                    skipped += 1
                    logger.info(
                        "[%s/%s] %s 库内已有 source=%s rows=%s",
                        i,
                        len(codes),
                        code,
                        result.get("source"),
                        len(result.get("factors") or []),
                    )
            except AdjQuotesError as e:
                db.rollback()
                failed += 1
                logger.error("[%s/%s] %s 失败: %s", i, len(codes), code, e.message)
                if not continue_on_error:
                    raise SystemExit(1) from e
            except Exception as e:
                db.rollback()
                failed += 1
                logger.exception("[%s/%s] %s 异常: %s", i, len(codes), code, e)
                if not continue_on_error:
                    raise
    finally:
        db.close()

    elapsed = time.time() - t0
    logger.info(
        "完成 ok=%s skipped=%s failed=%s elapsed=%.1fs",
        ok,
        skipped,
        failed,
        elapsed,
    )
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="批量补齐缺失 A 股前复权因子")
    p.add_argument(
        "--trade-date",
        help="RS 候选池基准交易日 YYYY-MM-DD；scope=rs_pool 时默认取行情最新日",
    )
    p.add_argument(
        "--scope",
        choices=("rs_pool", "all"),
        default="rs_pool",
        help="rs_pool=当日有行情的 RS 候选池（默认）；all=全部 collect_enabled 非 ST A 股",
    )
    p.add_argument(
        "--codes",
        help="指定代码，逗号/分号分隔（6 位 A 股）；指定后忽略 scope/trade-date 筛选",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="仅列出待补齐代码，不访问外网",
    )
    p.add_argument(
        "--force-refresh",
        action="store_true",
        help="强制外网拉取并覆盖写入（默认仅库内无因子时才拉取）",
    )
    p.add_argument(
        "--factor-source",
        choices=("auto", "sina", "baostock"),
        default="auto",
        help="因子源：auto=新浪优先 BaoStock 备用（北交所仅新浪）",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="最多处理 N 只（试跑用）",
    )
    p.add_argument(
        "--continue-on-error",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="单票失败是否继续（默认继续）",
    )
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    explicit = _parse_codes(args.codes)

    db = SessionLocal()
    try:
        missing = list_missing_codes(
            db,
            trade_date=args.trade_date,
            scope=args.scope,
            codes=explicit,
            limit=args.limit,
        )
    finally:
        db.close()

    return backfill(
        missing,
        dry_run=args.dry_run,
        force_refresh=args.force_refresh,
        factor_source=args.factor_source,
        continue_on_error=args.continue_on_error,
    )


if __name__ == "__main__":
    raise SystemExit(main())
