# -*- coding: utf-8 -*-
"""回填个股两融日明细 stock_margin_daily。

用法：
  python test/backfill_margin_daily.py
  python test/backfill_margin_daily.py --days 120
  python test/backfill_margin_daily.py --start 2024-10-01 --end 2024-10-30
  python test/backfill_margin_daily.py --date 2024-10-25 --source auto
  python test/backfill_margin_daily.py --date 2024-10-25 --source akshare
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _log(msg: str) -> None:
    print(msg, flush=True)


def _weekday_dates(start: str, end: str) -> list:
    out = []
    d0 = datetime.strptime(start[:10], "%Y-%m-%d").date()
    d1 = datetime.strptime(end[:10], "%Y-%m-%d").date()
    cur = d0
    while cur <= d1:
        if cur.weekday() < 5:
            out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def main():
    parser = argparse.ArgumentParser(description="回填 stock_margin_daily")
    parser.add_argument("--days", type=int, default=120, help="回填最近 N 个自然日（默认 120）")
    parser.add_argument("--start", type=str, default=None, help="起始 YYYY-MM-DD")
    parser.add_argument("--end", type=str, default=None, help="结束 YYYY-MM-DD")
    parser.add_argument("--date", type=str, default=None, help="仅采单日")
    parser.add_argument(
        "--source",
        type=str,
        default="auto",
        choices=("auto", "tushare", "akshare"),
        help="数据源",
    )
    parser.add_argument("--sleep", type=float, default=0.4, help="日间休眠秒")
    args = parser.parse_args()

    _log("loading collectors...")
    from backend_core.data_collectors.tushare.margin import collect_margin_for_date
    from backend_core.data_collectors.tushare.moneyflow_daily import (
        list_open_trade_dates,
        resolve_tushare_pro,
    )

    if args.date:
        dates = [args.date[:10]]
    else:
        end = args.end or datetime.now().strftime("%Y-%m-%d")
        if args.start:
            start = args.start[:10]
        else:
            start = (
                datetime.strptime(end[:10], "%Y-%m-%d") - timedelta(days=int(args.days))
            ).strftime("%Y-%m-%d")
        _log(f"resolving trade calendar {start}..{end}")
        dates = []
        try:
            pro = resolve_tushare_pro()
            if pro is not None:
                dates = list_open_trade_dates(pro, start_date=start, end_date=end)
        except Exception as e:
            _log(f"WARN: trade_cal failed: {e}")
        if not dates:
            _log("WARN: 用工作日近似日历")
            dates = _weekday_dates(start, end)

    _log(
        f"回填两融 days={len(dates)} source={args.source} "
        f"first={dates[0] if dates else None} last={dates[-1] if dates else None}"
    )
    ok = fail = upserted = 0
    for i, d in enumerate(dates, 1):
        try:
            res = collect_margin_for_date(d, source=args.source)
        except Exception as e:
            fail += 1
            _log(f"[{i}/{len(dates)}] FAIL {d} err={e}")
            continue
        n = int((res or {}).get("upserted") or 0)
        if res and res.get("success"):
            ok += 1
            upserted += n
            _log(f"[{i}/{len(dates)}] OK {d} upserted={n} source={res.get('source')}")
        else:
            fail += 1
            _log(f"[{i}/{len(dates)}] FAIL {d} err={res.get('error') if res else 'none'}")
        if args.sleep > 0 and i < len(dates):
            time.sleep(args.sleep)
    _log(f"DONE ok={ok} fail={fail} upserted={upserted}")


if __name__ == "__main__":
    main()
