#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GMS 周线回填：近 N 年周 MF + 近 M 个已收盘周 GMS 预计算。

示例:
  python scripts/gms_weekly_backfill.py --mf-years 5 --trace-weeks 52
  python scripts/gms_weekly_backfill.py --mf-only --codes 000001 600000
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("gms_weekly_backfill")


def main():
    parser = argparse.ArgumentParser(description="GMS 周线 MF / trace 回填")
    parser.add_argument("--mf-years", type=int, default=5, help="周 MF 回填年数，默认 5")
    parser.add_argument("--trace-weeks", type=int, default=52, help="GMS 预计算周数，默认 52")
    parser.add_argument("--mf-only", action="store_true", help="只回填周 MF")
    parser.add_argument("--trace-only", action="store_true", help="只回填周 GMS trace")
    parser.add_argument("--codes", nargs="*", default=None, help="可选股票代码列表")
    args = parser.parse_args()

    from backend_core.database.db import SessionLocal
    from backend_core.data_collectors.batch_mean_frequency_weekly import (
        calculate_and_save_mean_frequency_weekly_for_date,
    )
    from backend_core.strategies.gms.config import GMSConfigManager
    from backend_core.strategies.gms.scheduled_precompute import run_gms_precompute_for_config
    from backend_core.strategies.gms.week_calendar import (
        is_week_closed,
        load_cn_trade_dates,
        load_weekly_friday_candidates,
        normalize_date_str,
        resolve_gms_trade_date_fallback,
    )

    db = SessionLocal()
    try:
        as_of = resolve_gms_trade_date_fallback(db)
        trade_dates = load_cn_trade_dates(db, end_date=as_of)
        fridays = load_weekly_friday_candidates(db, end_date=as_of, limit=400)
        closed = [f for f in fridays if is_week_closed(f, as_of, set(trade_dates))]
        if not closed:
            logger.error("无已收盘周可回填 as_of=%s", as_of)
            return 1

        start_mf = (
            dt.datetime.strptime(as_of, "%Y-%m-%d").date()
            - dt.timedelta(days=int(args.mf_years) * 365)
        ).isoformat()
        mf_weeks = [f for f in closed if f >= start_mf]
        trace_weeks = closed[-int(args.trace_weeks) :] if args.trace_weeks > 0 else []

        codes = args.codes
        if not args.trace_only:
            logger.info("回填周 MF weeks=%s codes=%s", len(mf_weeks), codes or "ALL")
            for i, f in enumerate(mf_weeks, 1):
                r = calculate_and_save_mean_frequency_weekly_for_date(
                    db, f, market_type="CN", stock_codes=codes, log=logger
                )
                logger.info("[%s/%s] MF %s written=%s", i, len(mf_weeks), f, r.get("written"))

        if not args.mf_only:
            cid = GMSConfigManager().ensure_canonical_weekly_config()
            logger.info(
                "回填周 GMS trace weeks=%s config_id=%s", len(trace_weeks), cid
            )
            for i, f in enumerate(trace_weeks, 1):
                out = run_gms_precompute_for_config(
                    cid,
                    "cn",
                    stock_pool=list(codes) if codes else None,
                    timeframe="weekly",
                    target_date=f,
                )
                logger.info("[%s/%s] GMS %s -> %s", i, len(trace_weeks), f, out)

        logger.info("完成 as_of=%s last_closed=%s", as_of, closed[-1] if closed else None)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
