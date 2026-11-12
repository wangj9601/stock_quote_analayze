# -*- coding: utf-8 -*-
"""回补同花顺板块指数日 K（默认行业板 2 年，满足板 RS ≥253 根）。

用法:
  python test/backfill_board_historical_ths.py
  python test/backfill_board_historical_ths.py --years 2 --kinds industry
  python test/backfill_board_historical_ths.py --codes 881101,881102
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("backfill_board_hist")


def main() -> int:
    p = argparse.ArgumentParser(description="回补同花顺板块历史指数")
    p.add_argument("--years", type=int, default=2, help="回补年数（默认 2）")
    p.add_argument(
        "--kinds",
        default="industry",
        help="industry,concept 逗号分隔（板 RS 只需 industry）",
    )
    p.add_argument("--codes", default="", help="可选：限定 board_code 列表")
    p.add_argument(
        "--rerun-gates",
        action="store_true",
        help="回补成功后重跑 board_gates_daily",
    )
    args = p.parse_args()

    from backend_core.data_collectors.akshare.board_historical_ths import (
        BoardHistoricalThsCollector,
    )

    kinds = [k.strip() for k in str(args.kinds).split(",") if k.strip()]
    codes = [c.strip() for c in str(args.codes).split(",") if c.strip()] or None

    logger.info(
        "开始回补 kinds=%s years=%s codes=%s",
        kinds,
        args.years,
        codes or "ALL",
    )
    result = BoardHistoricalThsCollector().collect(
        mode="backfill",
        years_back=int(args.years),
        board_kinds=kinds,
        board_codes=codes,
    )
    summary = {
        k: result.get(k)
        for k in (
            "success",
            "mode",
            "start_date",
            "end_date",
            "boards_ok",
            "boards_failed",
            "rows",
        )
    }
    failed = [
        d
        for d in (result.get("details") or [])
        if not d.get("ok")
    ]
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if failed:
        print("failed_sample:", json.dumps(failed[:10], ensure_ascii=False, indent=2))

    if args.rerun_gates and result.get("success"):
        from backend_core.board_gates import run_board_gates_daily

        gate = run_board_gates_daily()
        print("gates:", json.dumps(gate, ensure_ascii=False, indent=2, default=str))

    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
