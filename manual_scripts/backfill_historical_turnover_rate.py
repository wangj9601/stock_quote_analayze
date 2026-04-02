#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补丁脚本：回填 A 股历史行情换手率（调用 HistoricalTurnoverRateCollector）。

说明：
- 计算逻辑使用系统内 HistoricalTurnoverRateCollector（已按 A 股 1手=100股 修正）。
- 默认仅补缺失换手率（turnover_rate IS NULL OR turnover_rate = 0）。
- 加 --force 时对该日期/区间内每日的全部历史行情记录重新计算并强制 UPDATE。

示例：
  python manual_scripts/backfill_historical_turnover_rate.py --days 30
  python manual_scripts/backfill_historical_turnover_rate.py --date 2026-03-31 --force
  python manual_scripts/backfill_historical_turnover_rate.py --start-date 2026-01-01 --end-date 2026-03-31 --force
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

from backend_core.data_collectors.akshare.historical_turnover_rate import HistoricalTurnoverRateCollector


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="回填A股历史换手率（仅补缺失）")
    parser.add_argument("--days", type=int, default=None, help="回填最近N天（默认 30）")
    parser.add_argument("--date", type=str, default=None, help="回填单日，格式 YYYY-MM-DD")
    parser.add_argument("--start-date", type=str, default=None, help="区间开始日期 YYYY-MM-DD")
    parser.add_argument("--end-date", type=str, default=None, help="区间结束日期 YYYY-MM-DD")
    parser.add_argument("--progress-every", type=int, default=200, help="每成功更新N条打印一次进度日志（默认 200）")
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重算并覆盖：处理该日/区间内所有 historical_quotes 记录（不限于缺省换手率）",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    if args.progress_every <= 0:
        parser.error("--progress-every 必须为正整数")

    collector = HistoricalTurnoverRateCollector()

    # 优先级：date > start/end > days
    if args.date:
        ok = collector.collect_turnover_rate_for_date(
            args.date,
            progress_every=args.progress_every,
            force_update=args.force,
        )
        print(
            json.dumps(
                {"mode": "date", "date": args.date, "force": args.force, "success": bool(ok)},
                ensure_ascii=False,
            )
        )
        sys.exit(0 if ok else 2)

    if args.start_date or args.end_date:
        if not (args.start_date and args.end_date):
            parser.error("--start-date 与 --end-date 必须同时提供")
        ok = collector.collect_turnover_rate_for_period(
            args.start_date,
            args.end_date,
            progress_every=args.progress_every,
            force_update=args.force,
        )
        print(
            json.dumps(
                {
                    "mode": "period",
                    "start_date": args.start_date,
                    "end_date": args.end_date,
                    "force": args.force,
                    "success": bool(ok),
                },
                ensure_ascii=False,
            )
        )
        sys.exit(0 if ok else 2)

    days = args.days if args.days is not None else 30
    if days <= 0:
        parser.error("--days 必须为正整数")
    ok = collector.collect_missing_turnover_rate(
        days, progress_every=args.progress_every, force_update=args.force
    )
    print(
        json.dumps(
            {"mode": "days", "days": days, "force": args.force, "success": bool(ok)},
            ensure_ascii=False,
        )
    )
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()

