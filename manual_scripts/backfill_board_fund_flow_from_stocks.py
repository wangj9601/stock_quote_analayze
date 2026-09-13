#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
根据个股资金流向（stock_fund_flow_daily）上卷回填板块资金流向。

目标表：board_fund_flow_daily（行业 + 概念），source=aggregate。
成分：优先同花顺 board_code 下成分；若无则经 industry_board_code_map 用东财码。

默认仅补缺（无行或 main_net_inflow 为空），不覆盖同花顺/东财主路径。
--force：覆盖已有 aggregate（及非保护来源）行。
--force-all：覆盖任意来源（慎用）。

示例：
  python manual_scripts/backfill_board_fund_flow_from_stocks.py --days 30
  python manual_scripts/backfill_board_fund_flow_from_stocks.py --date 2026-03-20
  python manual_scripts/backfill_board_fund_flow_from_stocks.py --start-date 2026-01-01 --end-date 2026-03-20
  python manual_scripts/backfill_board_fund_flow_from_stocks.py --days 7 --kind industry --force
  python manual_scripts/backfill_board_fund_flow_from_stocks.py --days 7 --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

from backend_core.data_collectors.akshare.board_fund_flow_aggregate_backfill import (
    backfill_board_fund_flow_from_stocks,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="按个股资金流上卷回填行业/概念板块资金流向"
    )
    parser.add_argument("--days", type=int, default=None, help="回填最近 N 天（默认 30）")
    parser.add_argument("--date", type=str, default=None, help="回填单日 YYYY-MM-DD")
    parser.add_argument("--start-date", type=str, default=None, help="区间开始 YYYY-MM-DD")
    parser.add_argument("--end-date", type=str, default=None, help="区间结束 YYYY-MM-DD")
    parser.add_argument(
        "--kind",
        action="append",
        dest="kinds",
        choices=["industry", "concept"],
        help="仅处理指定类型，可重复；默认 industry+concept",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="覆盖已有 aggregate 行（及非 ths/em 保护来源）",
    )
    parser.add_argument(
        "--force-all",
        action="store_true",
        help="覆盖任意来源（含 ths_fund_flow），慎用",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只统计将写入条数，不落库",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="DEBUG 日志",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        result = backfill_board_fund_flow_from_stocks(
            trade_date=args.date,
            start_date=args.start_date,
            end_date=args.end_date,
            days=args.days,
            board_kinds=args.kinds,
            force=args.force,
            force_all=args.force_all,
            dry_run=args.dry_run,
        )
    except ValueError as e:
        parser.error(str(e))
        return

    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result.get("success") else 2)


if __name__ == "__main__":
    main()
