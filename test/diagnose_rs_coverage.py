#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断指定交易日 RS Rating 覆盖率及排除原因。"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text

from backend_api.database import SessionLocal
from backend_core.indicators.rs_rating.calculator import compute_rs_raw
from backend_core.indicators.rs_rating.config import (
    COVERAGE_THRESHOLD,
    LOOKBACK_CALENDAR_DAYS,
    RS_WINDOWS,
)
from backend_core.indicators.rs_rating.qfq_closes import build_qfq_close_map
from backend_core.indicators.rs_rating.universe import list_candidate_codes


def diagnose(trade_date: str) -> None:
    db = SessionLocal()
    try:
        candidates = list_candidate_codes(db, trade_date)
        pool_size = len(candidates)
        need_bars = max(RS_WINDOWS) + 1

        closes_map, qfq_stats = build_qfq_close_map(
            db,
            candidates,
            trade_date,
            lookback_calendar_days=LOOKBACK_CALENDAR_DAYS,
            batch_size=500,
        )

        reasons: Counter[str] = Counter()
        universe_codes: list[str] = []
        for code in candidates:
            series = closes_map.get(code)
            if not series:
                reasons["无前复权序列(缺行情/缺因子/复权失败)"] += 1
                continue
            if len(series) < need_bars:
                reasons[f"前复权K线不足{need_bars}根(实际{len(series)}根)"] += 1
                continue
            computed = compute_rs_raw(series)
            if not computed:
                reasons["compute_rs_raw失败"] += 1
                continue
            universe_codes.append(code)

        universe_size = len(universe_codes)
        coverage = (universe_size / pool_size) if pool_size else 0.0
        publish = coverage >= COVERAGE_THRESHOLD

        row = db.execute(
            text(
                """
                SELECT COUNT(*) AS cnt,
                       COUNT(rs_rating) AS rated,
                       MAX(universe_size) AS uni,
                       MAX(coverage_ratio) AS cov
                FROM rs_ratings
                WHERE date = :d AND market_type = 'CN'
                """
            ),
            {"d": trade_date},
        ).mappings().first()

        sample = db.execute(
            text(
                """
                SELECT code, rs_rating, rs_raw, universe_size, coverage_ratio
                FROM rs_ratings
                WHERE date = :d AND market_type = 'CN'
                ORDER BY rs_raw DESC NULLS LAST
                LIMIT 3
                """
            ),
            {"d": trade_date},
        ).mappings().all()

        print("=" * 60)
        print(f"交易日: {trade_date}")
        print(f"候选池 pool_size: {pool_size}")
        print(f"有效宇宙 universe_size: {universe_size}")
        print(f"覆盖率 coverage: {coverage:.4f} ({coverage*100:.2f}%)")
        print(f"阈值: {COVERAGE_THRESHOLD*100:.0f}%  ->  是否发布评级: {publish}")
        print("-" * 60)
        print("前复权预处理统计:", qfq_stats)
        print("-" * 60)
        print("排除原因明细:")
        excluded = pool_size - universe_size
        for reason, cnt in reasons.most_common():
            print(f"  {reason}: {cnt}")
        print(f"  合计排除: {excluded}")
        print("-" * 60)
        print("rs_ratings 表快照:")
        print(f"  行数: {row['cnt']}, 有 rs_rating 的行: {row['rated']}")
        print(f"  表内 universe_size/coverage_ratio: {row['uni']} / {row['cov']}")
        if sample:
            print("  样例(按 rs_raw 降序):")
            for s in sample:
                print(
                    f"    {s['code']} rs_rating={s['rs_rating']} rs_raw={s['rs_raw']:.4f} "
                    f"uni={s['universe_size']} cov={s['coverage_ratio']}"
                )

        # 近 10 个交易日覆盖率趋势
        trend = db.execute(
            text(
                """
                SELECT date,
                       MAX(universe_size) AS uni,
                       MAX(coverage_ratio) AS cov,
                       COUNT(rs_rating) AS rated_cnt,
                       COUNT(*) AS total
                FROM rs_ratings
                WHERE market_type = 'CN'
                  AND date >= CAST(:d AS date) - INTERVAL '15 day'
                  AND date <= CAST(:d AS date)
                GROUP BY date
                ORDER BY date DESC
                LIMIT 12
                """
            ),
            {"d": trade_date},
        ).mappings().all()
        print("-" * 60)
        print("近 12 个交易日覆盖率趋势:")
        for t in trend:
            d = str(t["date"])[:10]
            cov = t["cov"]
            cov_s = f"{cov*100:.1f}%" if cov is not None else "N/A"
            pub = "发布" if cov is not None and cov >= COVERAGE_THRESHOLD else "未发布"
            print(
                f"  {d}  universe={t['uni']}  coverage={cov_s}  "
                f"rated={t['rated_cnt']}/{t['total']}  [{pub}]"
            )
        print("=" * 60)
    finally:
        db.close()


if __name__ == "__main__":
    dates = sys.argv[1:] or ["2025-11-26"]
    for d in dates:
        diagnose(d[:10])
        print()
