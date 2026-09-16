# -*- coding: utf-8 -*-
"""补采：仅把同花顺「即时」快照中、指定交易日尚未入库的个股写入 stock_fund_flow_daily 并回写行情表。

用法:
  python test/backfill_missing_ths_fund_flow_daily.py --trade-date 2026-09-15
  python test/backfill_missing_ths_fund_flow_daily.py --trade-date 2026-09-15 --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from backend_core.database.db import SessionLocal
from backend_core.data_collectors.akshare.ths_fund_flow_daily import (
    ThsFundFlowDailyCollector,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="补齐 THS 个股资金流日表缺失代码")
    parser.add_argument("--trade-date", required=True, help="YYYY-MM-DD")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只统计缺失，不写库",
    )
    parser.add_argument(
        "--codes",
        default="",
        help="可选：逗号分隔代码，仅补这些（默认补当日全部缺失）",
    )
    args = parser.parse_args()
    trade_date = args.trade_date.strip()
    only_codes = {c.strip().zfill(6) for c in args.codes.split(",") if c.strip()}

    collector = ThsFundFlowDailyCollector(trade_date=trade_date)
    df = collector.fetch_dataframe()
    rows = collector.dataframe_to_rows(df)
    print(f"snapshot unique={len(rows)} trade_date={trade_date}")

    session = SessionLocal()
    try:
        existing = {
            r[0]
            for r in session.execute(
                text(
                    """
                    SELECT code FROM stock_fund_flow_daily
                    WHERE trade_date = :d
                    """
                ),
                {"d": trade_date},
            ).fetchall()
        }
    finally:
        session.close()

    missing_rows = [r for r in rows if r["code"] not in existing]
    if only_codes:
        missing_rows = [r for r in missing_rows if r["code"] in only_codes]

    print(f"already in db={len(existing)} missing_in_snapshot={len(missing_rows)}")
    sample = [r["code"] for r in missing_rows[:20]]
    print(f"missing sample={sample}")
    if "002709" in {r["code"] for r in missing_rows}:
        hit = next(r for r in missing_rows if r["code"] == "002709")
        print(
            "002709 will write:",
            hit.get("inflow_amount"),
            hit.get("outflow_amount"),
            hit.get("net_amount"),
        )

    if args.dry_run:
        print("dry-run: skip write")
        return 0

    if not missing_rows:
        print("nothing to write")
        return 0

    written = collector.upsert_rows(missing_rows)
    synced = collector.sync_to_quote_tables(missing_rows)
    print(
        f"done written={written} hist={synced['historical_updated']} "
        f"realtime={synced['realtime_updated']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
