#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量全市场港股 RS Rating（股价相对强度）预计算。

按交易日逐日重算港股截面排名并写入 ``rs_ratings_hk``（前复权口径）。
缺省：以 ``historical_quotes_hk`` 最新交易日为终点，向前约一年（日历 365 天）。

用法（在项目根目录）::

    python scripts/batch_rs_rating_hk_precompute.py
    python scripts/batch_rs_rating_hk_precompute.py --start 2025-01-01 --end 2025-06-30
    python scripts/batch_rs_rating_hk_precompute.py --days 90
    python scripts/batch_rs_rating_hk_precompute.py --dry-run
    python scripts/batch_rs_rating_hk_precompute.py --continue-on-error
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("batch_rs_rating_hk")


def _parse_ymd(s: str) -> str:
    s = (s or "").strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    raise argparse.ArgumentTypeError(f"日期格式无效: {s!r}，请用 YYYY-MM-DD 或 YYYYMMDD")


def _normalize_date_str(val) -> str:
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, date):
        return val.isoformat()
    s = str(val).strip()
    if len(s) >= 10 and s[4] == "-":
        return s[:10]
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s


def resolve_range(
    *,
    start: Optional[str],
    end: Optional[str],
    days: int,
) -> Tuple[str, str]:
    from backend_api.database import SessionLocal
    from backend_core.indicators.rs_rating.scheduled_precompute_hk import (
        resolve_trade_date_hk,
    )

    db = SessionLocal()
    try:
        end_s = end or resolve_trade_date_hk(db, None)
        if start:
            start_s = start
        else:
            end_d = date.fromisoformat(end_s)
            start_s = (end_d - timedelta(days=max(1, int(days)))).isoformat()
        if start_s > end_s:
            raise ValueError(f"起始日 {start_s} 晚于结束日 {end_s}")
        return start_s, end_s
    finally:
        db.close()


def list_trade_dates(start: str, end: str) -> List[str]:
    from backend_api.database import SessionLocal

    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT DISTINCT date::text AS d
                FROM historical_quotes_hk
                WHERE date >= :sd AND date <= :ed
                ORDER BY d ASC
                """
            ),
            {"sd": start, "ed": end},
        ).fetchall()
        return [_normalize_date_str(r[0]) for r in rows if r and r[0]]
    finally:
        db.close()


def run_batch(
    trade_dates: Sequence[str],
    *,
    dry_run: bool = False,
    continue_on_error: bool = False,
) -> int:
    if dry_run:
        logger.info("dry-run：将处理 %d 个交易日", len(trade_dates))
        for i, d in enumerate(trade_dates, 1):
            logger.info("  [%d/%d] %s", i, len(trade_dates), d)
        return 0

    from backend_core.indicators.rs_rating.scheduled_precompute_hk import (
        run_rs_rating_precompute_hk,
    )

    total = len(trade_dates)
    ok_n = 0
    fail_n = 0
    t_all = time.time()
    for i, d in enumerate(trade_dates, 1):
        logger.info("==== [%d/%d] 港股全市场 RS 预计算 %s ====", i, total, d)
        t0 = time.time()
        try:
            summary = run_rs_rating_precompute_hk(trade_date=d)
            if not summary.get("ok"):
                raise RuntimeError(summary.get("error") or "预计算返回 ok=False")
            ok_n += 1
            logger.info(
                "完成 %s: saved=%s universe=%s coverage=%s publish=%s elapsed=%.1fs",
                d,
                summary.get("saved"),
                summary.get("universe_size"),
                summary.get("coverage_ratio"),
                summary.get("publish_ratings"),
                time.time() - t0,
            )
        except Exception as e:
            fail_n += 1
            logger.exception("失败 %s: %s", d, e)
            if not continue_on_error:
                logger.error("已中止（可用 --continue-on-error 跳过失败日继续）")
                break
    logger.info(
        "批量结束: ok=%d fail=%d total=%d wall=%.1fs",
        ok_n,
        fail_n,
        total,
        time.time() - t_all,
    )
    return 0 if fail_n == 0 else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="批量港股全市场 RS Rating 预计算（写入 rs_ratings_hk）",
    )
    parser.add_argument("--start", type=_parse_ymd, default=None)
    parser.add_argument("--end", type=_parse_ymd, default=None)
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        start_s, end_s = resolve_range(start=args.start, end=args.end, days=args.days)
    except Exception as e:
        logger.error("解析日期区间失败: %s", e)
        return 2

    dates = list_trade_dates(start_s, end_s)
    if not dates:
        logger.error("区间 %s ~ %s 在 historical_quotes_hk 中无交易日", start_s, end_s)
        return 2

    logger.info(
        "区间 %s ~ %s，共 %d 个交易日（港股全市场截面；写入 rs_ratings_hk）",
        start_s,
        end_s,
        len(dates),
    )
    return run_batch(
        dates,
        dry_run=bool(args.dry_run),
        continue_on_error=bool(args.continue_on_error),
    )


if __name__ == "__main__":
    raise SystemExit(main())
