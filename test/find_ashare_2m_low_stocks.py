#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查找 A 股在最近 N 个月内区间最低价匹配给定「最低点」的股票。

数据源：PostgreSQL ``historical_quotes``（不复权日 K 的 low）。
默认窗口：近 3 个自然月（相对库内最新交易日）。

用法（项目根目录）::

    # 近 3 个月最低价精确等于 10 元
    python test/find_ashare_2m_low_stocks.py --low 10 --mode exact

    # 近 3 个月最低价约等于 10 元（默认容差 ±2%）
    python test/find_ashare_2m_low_stocks.py --low 10

    # 近 3 个月最低价 ≤ 5 元
    python test/find_ashare_2m_low_stocks.py --low 5 --mode below

    # 现价接近近 3 个月最低点（且该最低点约等于 8 元）
    python test/find_ashare_2m_low_stocks.py --low 8 --mode near_bottom

    # 自定义窗口与容差，导出 CSV
    python test/find_ashare_2m_low_stocks.py --low 12.5 --months 3 --tol 0.03 -o out.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _parse_date(val: Any) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, date):
        return val.isoformat()
    s = str(val).strip()
    return s[:10] if s else None


def _f(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def query_stocks(
    *,
    low: float,
    months: int,
    mode: str,
    tol: float,
    near_pct: float,
    include_st: bool,
    min_days: int,
    limit: int,
) -> Dict[str, Any]:
    from backend_api.database import SessionLocal

    db = SessionLocal()
    try:
        end_d = db.execute(text("SELECT MAX(date) FROM historical_quotes")).scalar()
        if end_d is None:
            return {"end_date": None, "start_date": None, "rows": []}

        end_s = _parse_date(end_d)
        # 相对最新交易日回推 N 个自然月
        start_row = db.execute(
            text(
                """
                SELECT (CAST(:end_d AS date) - make_interval(months => :months))::date
                """
            ),
            {"end_d": end_s, "months": int(months)},
        ).scalar()
        start_s = _parse_date(start_row)

        st_sql = ""
        if not include_st:
            st_sql = "AND COALESCE(a.name, '') NOT ILIKE '%ST%'"

        # A 股 6 位：沪/深主板、创业板、科创板等（0/3/6 开头）
        sql = f"""
            WITH win AS (
                SELECT CAST(:start_d AS date) AS start_d, CAST(:end_d AS date) AS end_d
            ),
            agg AS (
                SELECT
                    h.code,
                    MAX(h.name) AS name,
                    MIN(h.low) AS period_low,
                    MAX(h.high) AS period_high,
                    (array_agg(h.date ORDER BY h.low ASC NULLS LAST, h.date ASC))[1]
                        AS low_date,
                    (array_agg(h.close ORDER BY h.date DESC))[1] AS latest_close,
                    (array_agg(h.date ORDER BY h.date DESC))[1] AS latest_date,
                    COUNT(*)::int AS days
                FROM historical_quotes h, win
                WHERE CAST(h.date AS date) >= win.start_d
                  AND CAST(h.date AS date) <= win.end_d
                  AND h.low IS NOT NULL
                  AND h.code ~ '^[036][0-9]{{5}}$'
                GROUP BY h.code
                HAVING COUNT(*) >= :min_days
            )
            SELECT
                a.code,
                COALESCE(b.name, a.name) AS name,
                b.industry,
                a.period_low,
                a.period_high,
                a.low_date,
                a.latest_close,
                a.latest_date,
                a.days,
                CASE
                    WHEN a.period_low IS NULL OR a.period_low = 0 THEN NULL
                    ELSE ROUND(
                        ((a.latest_close - a.period_low) / a.period_low * 100)::numeric,
                        2
                    )
                END AS pct_above_low
            FROM agg a
            LEFT JOIN stock_basic_info b ON b.code = a.code
            WHERE 1 = 1
              {st_sql}
        """

        params: Dict[str, Any] = {
            "start_d": start_s,
            "end_d": end_s,
            "min_days": int(min_days),
            "low": float(low),
            "tol": float(tol),
            "near_pct": float(near_pct),
            "lim": int(limit),
        }

        if mode == "exact":
            # 精准：按分（2 位小数）相等，避免 float 噪声
            sql += """
              AND ROUND(a.period_low::numeric, 2) = ROUND(CAST(:low AS numeric), 2)
            """
        elif mode == "below":
            sql += " AND a.period_low <= :low"
        elif mode == "near_bottom":
            # 现价贴近区间最低点，且最低点落在参数价附近
            sql += """
              AND a.period_low BETWEEN :low * (1 - :tol) AND :low * (1 + :tol)
              AND a.latest_close IS NOT NULL
              AND a.period_low > 0
              AND (a.latest_close - a.period_low) / a.period_low <= :near_pct
            """
        else:
            # match：区间最低价接近参数价
            sql += """
              AND a.period_low BETWEEN :low * (1 - :tol) AND :low * (1 + :tol)
            """

        sql += """
            ORDER BY a.period_low ASC, a.code ASC
            LIMIT :lim
        """

        rows = db.execute(text(sql), params).mappings().all()
        out: List[Dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "code": r["code"],
                    "name": r["name"],
                    "industry": r["industry"],
                    "period_low": _f(r["period_low"]),
                    "period_high": _f(r["period_high"]),
                    "low_date": _parse_date(r["low_date"]),
                    "latest_close": _f(r["latest_close"]),
                    "latest_date": _parse_date(r["latest_date"]),
                    "days": int(r["days"] or 0),
                    "pct_above_low": _f(r["pct_above_low"]),
                }
            )
        return {"start_date": start_s, "end_date": end_s, "rows": out}
    finally:
        db.close()


def _print_table(rows: List[Dict[str, Any]]) -> None:
    if not rows:
        print("（无匹配结果）")
        return
    header = (
        f"{'代码':<8}{'名称':<12}{'行业':<10}"
        f"{'区间最低':>10}{'低点日':<12}{'最新收':>10}"
        f"{'距低%':>8}{'天数':>6}"
    )
    print(header)
    print("-" * 88)
    for r in rows:
        name = (r.get("name") or "")[:10]
        industry = (str(r.get("industry") or "")[:8]) or "--"
        pl = r.get("period_low")
        lc = r.get("latest_close")
        pct = r.get("pct_above_low")
        print(
            f"{r.get('code') or '':<8}"
            f"{name:<12}"
            f"{industry:<10}"
            f"{(pl if pl is not None else float('nan')):>10.3f}"
            f"{(r.get('low_date') or '--'):<12}"
            f"{(lc if lc is not None else float('nan')):>10.3f}"
            f"{(pct if pct is not None else float('nan')):>8.2f}"
            f"{int(r.get('days') or 0):>6}"
        )


def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    fields = [
        "code",
        "name",
        "industry",
        "period_low",
        "period_high",
        "low_date",
        "latest_close",
        "latest_date",
        "days",
        "pct_above_low",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fields})


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="查找 A 股最近 N 个月区间最低价接近给定最低点的股票"
    )
    p.add_argument(
        "--low",
        type=float,
        required=True,
        help="最低点价格参数（元），例如 10 表示关注区间最低价约 10 元的股票",
    )
    p.add_argument(
        "--months",
        type=int,
        default=3,
        help="回看自然月数，默认 3",
    )
    p.add_argument(
        "--mode",
        choices=("exact", "match", "below", "near_bottom"),
        default="match",
        help=(
            "exact=区间最低价精确等于参数价（按分）；"
            "match=区间最低价≈参数价；"
            "below=区间最低价≤参数价；"
            "near_bottom=现价贴近区间最低且最低≈参数价"
        ),
    )
    p.add_argument(
        "--tol",
        type=float,
        default=0.02,
        help="match/near_bottom 时相对容差，默认 0.02（±2%%）",
    )
    p.add_argument(
        "--near-pct",
        type=float,
        default=0.05,
        dest="near_pct",
        help="near_bottom 模式：现价相对区间最低的最大涨幅，默认 0.05（5%%）",
    )
    p.add_argument(
        "--min-days",
        type=int,
        default=10,
        dest="min_days",
        help="窗口内最少交易日数，默认 10",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=200,
        help="最多返回条数，默认 200",
    )
    p.add_argument(
        "--include-st",
        action="store_true",
        help="包含名称含 ST 的股票（默认排除）",
    )
    p.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="导出 CSV 路径（可选）",
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.low <= 0:
        print("错误：--low 必须 > 0", file=sys.stderr)
        return 2
    if args.months < 1:
        print("错误：--months 必须 >= 1", file=sys.stderr)
        return 2
    if args.tol < 0:
        print("错误：--tol 不能为负", file=sys.stderr)
        return 2

    result = query_stocks(
        low=args.low,
        months=args.months,
        mode=args.mode,
        tol=args.tol,
        near_pct=args.near_pct,
        include_st=bool(args.include_st),
        min_days=args.min_days,
        limit=args.limit,
    )
    rows = result["rows"]
    print(
        f"窗口: {result['start_date']} ~ {result['end_date']}  "
        f"mode={args.mode}  low={args.low}  "
        f"匹配 {len(rows)} 只"
    )
    _print_table(rows)

    if args.output:
        out = Path(args.output)
        if not out.is_absolute():
            out = PROJECT_ROOT / out
        _write_csv(out, rows)
        print(f"已导出: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
