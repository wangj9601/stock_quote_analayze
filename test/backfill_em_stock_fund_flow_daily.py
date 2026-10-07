#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""回填东财个股主力/分档资金流到 stock_fund_flow_em_daily。

用法:
  python test/backfill_em_stock_fund_flow_daily.py --codes 600519,300750
  python test/backfill_em_stock_fund_flow_daily.py --all --sleep 0.4 --max-codes 100
  python test/backfill_em_stock_fund_flow_daily.py --all --resume-from 000001
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend_core.data_collectors.akshare.em_stock_fund_flow_daily import (
    collect_em_stock_fund_flow_for_code,
    list_active_codes,
)
from backend_core.database.db import SessionLocal


def main() -> int:
    parser = argparse.ArgumentParser(description="回填东财个股资金流分档日表")
    parser.add_argument("--codes", type=str, default="", help="逗号分隔代码；与 --all 互斥优先")
    parser.add_argument("--all", action="store_true", help="活跃池全量回填（保留接口返回的全部历史）")
    parser.add_argument("--sleep", type=float, default=0.4, help="每票间隔秒")
    parser.add_argument("--max-codes", type=int, default=0, help="最多处理票数，0=不限制")
    parser.add_argument("--resume-from", type=str, default="", help="从该代码起（含）继续")
    parser.add_argument("--dry-run", action="store_true", help="只列出代码不请求")
    args = parser.parse_args()

    codes: list[str] = []
    if args.codes.strip():
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    elif args.all:
        session = SessionLocal()
        try:
            lim = args.max_codes if args.max_codes > 0 else None
            codes = list_active_codes(session, limit=lim)
        finally:
            session.close()
    else:
        parser.error("请指定 --codes 或 --all")

    if args.resume_from:
        rf = args.resume_from.strip().zfill(6)
        codes = [c for c in codes if c >= rf]

    if args.max_codes > 0:
        codes = codes[: args.max_codes]

    print(f"codes={len(codes)} sleep={args.sleep} dry_run={args.dry_run}")
    if args.dry_run:
        for c in codes[:20]:
            print(" ", c)
        if len(codes) > 20:
            print(f"  ... +{len(codes) - 20}")
        return 0

    # 回填保留全历史：recent_days=None，keep_last_n 不截断
    ok = fail = upserted = 0
    for i, code in enumerate(codes, 1):
        res = collect_em_stock_fund_flow_for_code(
            code,
            keep_last_n=None,
            sleep_sec=args.sleep,
        )
        if res.get("success"):
            ok += 1
            upserted += int(res.get("upserted") or 0)
            print(
                f"[{i}/{len(codes)}] OK {code} "
                f"{res.get('first_date')}~{res.get('last_date')} n={res.get('upserted')}"
            )
        else:
            fail += 1
            print(f"[{i}/{len(codes)}] FAIL {code} {res.get('error')}")

    print(f"done ok={ok} fail={fail} upserted={upserted}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
