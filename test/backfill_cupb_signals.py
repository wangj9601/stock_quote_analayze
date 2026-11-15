# -*- coding: utf-8 -*-
"""批量回补 CUPB（杯底）历史信号到 cupb_signal_trace。

默认口径与日终节点一致：全市场 A 股（CN）、不复权、forming+confirmed、
默认配置、force 重算并清理范围内未命中行。

用法：
  python test/backfill_cupb_signals.py --days 30
  python test/backfill_cupb_signals.py --start 2026-10-01 --end 2026-11-13
  python test/backfill_cupb_signals.py --date 2026-11-13
  python test/backfill_cupb_signals.py --start 2026-10-01 --end 2026-11-13 --config-id 1
  python test/backfill_cupb_signals.py --days 10 --dry-run
  python test/backfill_cupb_signals.py --days 5 --universe-limit 200
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import traceback
from datetime import datetime, timedelta
from typing import List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def _list_cn_trade_dates(db, start: str, end: str) -> List[str]:
    """优先用 historical_quotes 中实际有行情的交易日；否则退回工作日。"""
    from backend_api.models import HistoricalQuotes

    s = str(start)[:10]
    e = str(end)[:10]
    rows = (
        db.query(HistoricalQuotes.date)
        .filter(HistoricalQuotes.date >= s, HistoricalQuotes.date <= e)
        .distinct()
        .order_by(HistoricalQuotes.date)
        .all()
    )
    out = [str(r[0])[:10] for r in rows if r[0]]
    if out:
        return out

    # 无行情表时退回周一到周五
    d0 = datetime.strptime(s, "%Y-%m-%d").date()
    d1 = datetime.strptime(e, "%Y-%m-%d").date()
    cur = d0
    while cur <= d1:
        if cur.weekday() < 5:
            out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def _resolve_dates(args: argparse.Namespace) -> List[str]:
    from backend_api.database import SessionLocal

    if args.date:
        return [args.date[:10]]

    end = (args.end or datetime.now().strftime("%Y-%m-%d"))[:10]
    if args.start:
        start = args.start[:10]
    else:
        start = (
            datetime.strptime(end, "%Y-%m-%d") - timedelta(days=int(args.days))
        ).strftime("%Y-%m-%d")

    db = SessionLocal()
    try:
        dates = _list_cn_trade_dates(db, start, end)
    finally:
        db.close()
    return dates


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="批量回补 CUPB 历史信号")
    parser.add_argument("--days", type=int, default=30, help="回补最近 N 个自然日（默认 30）")
    parser.add_argument("--start", type=str, default=None, help="起始 YYYY-MM-DD")
    parser.add_argument("--end", type=str, default=None, help="结束 YYYY-MM-DD")
    parser.add_argument("--date", type=str, default=None, help="仅跑单日")
    parser.add_argument("--config-id", type=int, default=None, help="配置版本 id；默认 is_default")
    parser.add_argument(
        "--price-adjust",
        type=str,
        default="none",
        choices=("none", "qfq"),
        help="价格口径（默认 none 不复权）",
    )
    parser.add_argument(
        "--status-filter",
        type=str,
        default="both",
        choices=("both", "forming", "confirmed"),
        help="入库状态过滤（默认 both）",
    )
    parser.add_argument(
        "--universe-limit",
        type=int,
        default=0,
        help="股票池上限，0=不截断（默认 0）",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=0,
        help="结果条数上限，0=不截断（默认 0）",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help="日与日之间休眠秒数（默认 0）",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="单日失败继续后续日期（默认遇错即停）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印将要跑的交易日，不计算",
    )
    args = parser.parse_args(argv)

    _log("resolving trade dates…")
    dates = _resolve_dates(args)
    if not dates:
        _log("ERROR: 区间内无交易日")
        return 2

    _log(
        f"plan: {len(dates)} days  {dates[0]} .. {dates[-1]}  "
        f"config_id={args.config_id or 'default'}  "
        f"price_adjust={args.price_adjust}  status={args.status_filter}"
    )
    if args.dry_run:
        for d in dates:
            print(d)
        _log("dry-run done")
        return 0

    from backend_core.strategies.cup_bottom.scheduled_precompute import run_cupb_precompute

    ok_n = 0
    fail_n = 0
    total_hits = 0
    total_saved = 0
    t0 = time.time()

    for i, day in enumerate(dates, 1):
        _log(f"[{i}/{len(dates)}] CUPB precompute {day} …")
        day_t0 = time.time()
        try:
            out = run_cupb_precompute(
                config_id=args.config_id,
                trade_date=day,
                stock_pool_mode="market",
                market_scopes=["CN"],
                status_filter=args.status_filter,
                force_recompute=True,
                price_adjust=args.price_adjust,
                universe_limit=args.universe_limit or 0,
                max_results=args.max_results or 0,
            )
            elapsed = time.time() - day_t0
            hits = int(out.get("hit_count") or 0)
            saved = int(out.get("saved") or 0)
            deleted = int(out.get("deleted_stale") or 0)
            screened = out.get("screened")
            total_hits += hits
            total_saved += saved
            ok_n += 1
            _log(
                f"  OK date={out.get('trade_date') or day} "
                f"config={out.get('config_id')} screened={screened} "
                f"hit={hits} saved={saved} deleted={deleted} "
                f"elapsed={elapsed:.1f}s"
            )
        except Exception as e:
            fail_n += 1
            _log(f"  FAIL {day}: {e}")
            traceback.print_exc()
            if not args.continue_on_error:
                _log("abort (use --continue-on-error to skip failures)")
                return 1
        if args.sleep and i < len(dates):
            time.sleep(float(args.sleep))

    _log(
        f"done ok={ok_n} fail={fail_n} days={len(dates)} "
        f"hits={total_hits} saved={total_saved} "
        f"elapsed={time.time() - t0:.1f}s"
    )
    return 0 if fail_n == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
