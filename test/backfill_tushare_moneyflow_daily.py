#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从 Tushare 回填个股主力/分档资金流到 stock_fund_flow_em_daily。

默认接口 moneyflow（L2 主动买卖分档，约 2000 积分，source=tushare_l2）：
  主力净额 = 特大单净额 + 大单净额（买卖差，万元→元）。
也可用 --api dc 走 moneyflow_dc（东财口径，约 5000 积分，source=tushare_dc）。

金额单位：接口为万元，入库换算为元。UPSERT 会覆盖同 code+trade_date 的旧行（含 akshare 写入）。

用法:
  # 单票 / 多票（按代码拉区间，默认 L2）
  python test/backfill_tushare_moneyflow_daily.py --codes 600519 --start 2026-07-01 --end 2026-09-30

  # 活跃池：按交易日全市场拉取（推荐，更快）
  python test/backfill_tushare_moneyflow_daily.py --all --start 2026-09-01 --end 2026-09-30 --sleep 0.35

  # 东财口径（需 moneyflow_dc 权限）
  python test/backfill_tushare_moneyflow_daily.py --codes 600519 --api dc --days 60

  # 只看将处理的交易日/代码
  python test/backfill_tushare_moneyflow_daily.py --all --days 30 --dry-run

环境变量: TUSHARE_TOKEN（或 backend_core.config.TUSHARE_CONFIG.token）
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend_core.data_collectors.akshare.em_stock_fund_flow_daily import (
    list_active_codes,
    normalize_code,
)
from backend_core.data_collectors.tushare.moneyflow_daily import (
    backfill_by_code,
    backfill_by_date,
    default_date_range,
    list_open_trade_dates,
    resolve_tushare_pro,
)
from backend_core.database.db import SessionLocal


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Tushare 主力资金流回填 → stock_fund_flow_em_daily"
    )
    parser.add_argument(
        "--codes",
        type=str,
        default="",
        help="逗号分隔代码；指定后按代码拉区间（优先于 --all）",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="活跃池；默认按交易日全市场拉取后再按活跃池过滤",
    )
    parser.add_argument(
        "--api",
        choices=("l2", "dc"),
        default="l2",
        help="l2=moneyflow（默认，约2000积分）；dc=moneyflow_dc（约5000积分）",
    )
    parser.add_argument(
        "--mode",
        choices=("auto", "by-date", "by-code"),
        default="auto",
        help="auto: 有 --codes 则 by-code，否则 by-date",
    )
    parser.add_argument("--start", type=str, default="", help="开始日期 YYYY-MM-DD 或 YYYYMMDD")
    parser.add_argument("--end", type=str, default="", help="结束日期 YYYY-MM-DD 或 YYYYMMDD")
    parser.add_argument(
        "--days",
        type=int,
        default=120,
        help="未指定 start/end 时，回看自然日天数（默认 120）",
    )
    parser.add_argument("--sleep", type=float, default=0.35, help="每次请求间隔秒")
    parser.add_argument("--max-codes", type=int, default=0, help="活跃池最多票数，0=不限")
    parser.add_argument(
        "--resume-from",
        type=str,
        default="",
        help="by-code 时从该代码起（含）；by-date 时从该交易日起（含）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只打印计划，不请求")
    args = parser.parse_args()

    if not args.codes.strip() and not args.all:
        parser.error("请指定 --codes 或 --all")

    start, end = args.start.strip(), args.end.strip()
    if not start or not end:
        ds, de = default_date_range(args.days)
        start = start or ds
        end = end or de
    # 统一成 YYYY-MM-DD
    if len(start.replace("-", "")) == 8 and "-" not in start:
        start = f"{start[:4]}-{start[4:6]}-{start[6:8]}"
    if len(end.replace("-", "")) == 8 and "-" not in end:
        end = f"{end[:4]}-{end[4:6]}-{end[6:8]}"

    mode = args.mode
    if mode == "auto":
        mode = "by-code" if args.codes.strip() else "by-date"

    codes: list[str] = []
    if args.codes.strip():
        codes = [normalize_code(c) for c in args.codes.split(",") if c.strip()]
        codes = [c for c in codes if c]
    else:
        session = SessionLocal()
        try:
            lim = args.max_codes if args.max_codes > 0 else None
            codes = list_active_codes(session, limit=lim)
        finally:
            session.close()

    if args.max_codes > 0 and codes:
        codes = codes[: args.max_codes]

    code_filter = set(codes) if (args.all or mode == "by-date") else None

    print(
        f"api={args.api} mode={mode} start={start} end={end} "
        f"codes={len(codes)} sleep={args.sleep} dry_run={args.dry_run}"
    )
    print(
        "注意: UPSERT 覆盖同 code+trade_date；source="
        + ("tushare_dc" if args.api == "dc" else "tushare_l2")
    )

    if args.dry_run:
        if mode == "by-date":
            pro = resolve_tushare_pro()
            if pro is None:
                print("ERROR: 无法初始化 Tushare（检查 TUSHARE_TOKEN）")
                return 2
            dates = list_open_trade_dates(pro, start_date=start, end_date=end)
            if args.resume_from:
                rf = args.resume_from.strip().replace("-", "")
                if len(rf) == 8:
                    rf = f"{rf[:4]}-{rf[4:6]}-{rf[6:8]}"
                dates = [d for d in dates if d >= rf]
            print(f"trade_dates={len(dates)} (show first 15)")
            for d in dates[:15]:
                print(" ", d)
            if len(dates) > 15:
                print(f"  ... +{len(dates) - 15}")
            print(f"active_code_filter={len(codes)}")
        else:
            if args.resume_from:
                rf = args.resume_from.strip().zfill(6)
                codes = [c for c in codes if c >= rf]
            for c in codes[:20]:
                print(" ", c)
            if len(codes) > 20:
                print(f"  ... +{len(codes) - 20}")
        return 0

    pro = resolve_tushare_pro()
    if pro is None:
        print("ERROR: 无法初始化 Tushare（请设置环境变量 TUSHARE_TOKEN）")
        return 2

    if mode == "by-date":
        dates = list_open_trade_dates(pro, start_date=start, end_date=end)
        if args.resume_from:
            rf = args.resume_from.strip().replace("-", "")
            if len(rf) == 8:
                rf = f"{rf[:4]}-{rf[4:6]}-{rf[6:8]}"
            dates = [d for d in dates if d >= rf]
        if not dates:
            print("ERROR: 区间内无开市日")
            return 1
        print(f"trade_dates={len(dates)}")
        result = backfill_by_date(
            pro,
            dates,
            api=args.api,
            sleep_sec=args.sleep,
            code_filter=code_filter,
        )
    else:
        if args.resume_from:
            rf = args.resume_from.strip().zfill(6)
            codes = [c for c in codes if c >= rf]
        if not codes:
            print("ERROR: 无有效代码")
            return 1
        result = backfill_by_code(
            pro,
            codes,
            api=args.api,
            start_date=start,
            end_date=end,
            sleep_sec=args.sleep,
            code_filter=None,
        )

    print(
        f"done mode={result.get('mode')} api={result.get('api')} "
        f"ok={result.get('ok')} fail={result.get('fail')} "
        f"upserted={result.get('upserted')}"
    )
    if result.get("errors_sample"):
        print("errors_sample:", result["errors_sample"][:10])
    return 0 if int(result.get("fail") or 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
