#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量补齐缺失的前复权因子（stock_adj_factor）。

默认：在指定交易日 RS 候选池内，找出库内无对应市场因子源的股票，
调用 ``ensure_adj_factors`` 外网拉取并 UPSERT。

用法（在项目根目录）::

    # A 股
    python migrations/backfill_missing_adj_factors.py --dry-run
    python migrations/backfill_missing_adj_factors.py --trade-date 2025-11-26
    python migrations/backfill_missing_adj_factors.py --codes 920000,920001
    python migrations/backfill_missing_adj_factors.py --scope all --limit 50

    # 港股（RS HK 预计算前必须先补齐，否则 coverage≈0）
    python migrations/backfill_missing_adj_factors.py --market HK --dry-run
    python migrations/backfill_missing_adj_factors.py --market HK --trade-date 2025-01-07
    python migrations/backfill_missing_adj_factors.py --market HK --scope all --limit 20
    python migrations/backfill_missing_adj_factors.py --market HK --codes 00700,09988

限速：遵循 ``ADJ_FACTOR_FETCH_THROTTLE_ENABLED`` / ``ADJ_FACTOR_FETCH_INTERVAL_SEC``（默认约 3 秒/票）。
港股全市场约 1900 只时，按默认限速大约需要数小时。
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from typing import List, Optional, Sequence, Tuple

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

CN_SOURCES: Tuple[str, ...] = ("akshare_sina_qfq", "baostock_qfq")
HK_SOURCES: Tuple[str, ...] = ("akshare_sina_hk_qfq", "akshare_em_hk_qfq")

SQL_MISSING_IN_RS_POOL_CN = """
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

SQL_MISSING_IN_RS_POOL_HK = """
WITH cand AS (
    SELECT DISTINCT hq.code
    FROM historical_quotes_hk hq
    INNER JOIN stock_basic_info_hk b ON b.code = hq.code
    WHERE hq.date = :trade_date
      AND LENGTH(TRIM(hq.code)) = 5
      AND COALESCE(b.collect_enabled, TRUE) = TRUE
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

SQL_MISSING_ALL_HK = """
SELECT b.code
FROM stock_basic_info_hk b
WHERE LENGTH(TRIM(b.code)) = 5
  AND COALESCE(b.collect_enabled, TRUE) = TRUE
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

SQL_LATEST_TRADE_DATE_CN = """
SELECT MAX(hq.date)
FROM historical_quotes hq
WHERE LENGTH(TRIM(hq.code)) = 6
"""

SQL_LATEST_TRADE_DATE_HK = """
SELECT MAX(hq.date)
FROM historical_quotes_hk hq
WHERE LENGTH(TRIM(hq.code)) = 5
"""


def _norm_market(raw: str) -> str:
    m = str(raw or "CN").strip().upper()
    if m not in ("CN", "HK"):
        raise SystemExit(f"--market 仅支持 CN|HK，当前：{raw}")
    return m


def _sources_for(market: str) -> Tuple[str, ...]:
    return HK_SOURCES if market == "HK" else CN_SOURCES


def _parse_codes(raw: Optional[str], *, market: str) -> List[str]:
    if not raw:
        return []
    width = 5 if market == "HK" else 6
    out: List[str] = []
    for part in raw.replace(";", ",").split(","):
        c = part.strip().upper()
        if not c:
            continue
        if c.startswith("HK") and len(c) > 2:
            c = c[2:]
        if c.isdigit():
            c = c.zfill(width) if len(c) <= width else c
        out.append(c)
    return out


def resolve_trade_date(db: Session, trade_date: Optional[str], *, market: str) -> str:
    if trade_date:
        return trade_date[:10]
    sql = SQL_LATEST_TRADE_DATE_HK if market == "HK" else SQL_LATEST_TRADE_DATE_CN
    row = db.execute(text(sql)).scalar()
    if not row:
        table = "historical_quotes_hk" if market == "HK" else "historical_quotes"
        raise SystemExit(f"{table} 无行情，无法推断 trade_date")
    return str(row)[:10]


def list_missing_codes(
    db: Session,
    *,
    market: str,
    trade_date: Optional[str],
    scope: str,
    codes: Sequence[str],
    limit: Optional[int],
) -> List[str]:
    sources = list(_sources_for(market))
    if codes:
        selected = list(codes)
    elif scope == "all":
        sql = SQL_MISSING_ALL_HK if market == "HK" else SQL_MISSING_ALL_CN
        stmt = text(sql).bindparams(bindparam("sources", expanding=True))
        rows = db.execute(stmt, {"sources": sources}).fetchall()
        selected = [str(r[0]).strip() for r in rows if r and r[0]]
    else:
        date_s = resolve_trade_date(db, trade_date, market=market)
        sql = (
            SQL_MISSING_IN_RS_POOL_HK if market == "HK" else SQL_MISSING_IN_RS_POOL_CN
        )
        stmt = text(sql).bindparams(bindparam("sources", expanding=True))
        rows = db.execute(
            stmt,
            {"trade_date": date_s, "sources": sources},
        ).fetchall()
        selected = [str(r[0]).strip() for r in rows if r and r[0]]
        logger.info(
            "%s RS 候选池 trade_date=%s 缺因子 %s 只（sources=%s）",
            market,
            date_s,
            len(selected),
            sources,
        )

    if limit is not None and limit > 0:
        selected = selected[: int(limit)]
    return selected


def backfill(
    codes: Sequence[str],
    *,
    market: str,
    dry_run: bool,
    force_refresh: bool,
    factor_source: str,
    continue_on_error: bool,
) -> int:
    if not codes:
        logger.info("无待补齐股票，退出")
        return 0

    if market == "HK" and factor_source == "baostock":
        raise SystemExit("港股不支持 baostock 因子源，请用 auto 或 sina")

    logger.info(
        "待处理 %s 只 market=%s dry_run=%s force_refresh=%s factor_source=%s",
        len(codes),
        market,
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
    p = argparse.ArgumentParser(description="批量补齐缺失前复权因子（A股/港股）")
    p.add_argument(
        "--market",
        choices=("CN", "HK"),
        default="CN",
        help="市场：CN=A股（默认）；HK=港股",
    )
    p.add_argument(
        "--trade-date",
        help="RS 候选池基准交易日 YYYY-MM-DD；scope=rs_pool 时默认取对应行情表最新日",
    )
    p.add_argument(
        "--scope",
        choices=("rs_pool", "all"),
        default="rs_pool",
        help="rs_pool=当日有行情的 RS 候选池（默认）；all=全部 collect_enabled 股票",
    )
    p.add_argument(
        "--codes",
        help="指定代码，逗号/分号分隔；指定后忽略 scope/trade-date 筛选",
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
        help="因子源：A股 auto=新浪优先 BaoStock 备用；港股 auto=新浪优先东财备用（勿用 baostock）",
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
    market = _norm_market(args.market)
    explicit = _parse_codes(args.codes, market=market)

    db = SessionLocal()
    try:
        missing = list_missing_codes(
            db,
            market=market,
            trade_date=args.trade_date,
            scope=args.scope,
            codes=explicit,
            limit=args.limit,
        )
    finally:
        db.close()

    return backfill(
        missing,
        market=market,
        dry_run=args.dry_run,
        force_refresh=args.force_refresh,
        factor_source=args.factor_source,
        continue_on_error=args.continue_on_error,
    )


if __name__ == "__main__":
    raise SystemExit(main())
