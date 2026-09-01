#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量补齐港股日线历史（historical_quotes_hk），抬高 RS 预计算覆盖率。

港股 RS 需要至少 ``max(RS_WINDOWS)+1 = 253`` 根有效 K 线；多数标的库内仅约
126–188 根，导致 coverage 偏低、无法 publish。本脚本对「K 线不足」的港股调用
``ak.stock_hk_hist`` 拉取长历史并 UPSERT（默认不删库内已有数据）。

用法（在项目根目录）::

    # 预览：K 线不足 253 的标的
    python scripts/backfill_hk_historical_quotes.py --dry-run

    # 实际补齐（建议先 limit 小批量试跑）
    python scripts/backfill_hk_historical_quotes.py --limit 20 --continue-on-error
    python scripts/backfill_hk_historical_quotes.py --codes 00700,09988
    python scripts/backfill_hk_historical_quotes.py --scope rs-pool --trade-date 2025-01-07
    python scripts/backfill_hk_historical_quotes.py --scope all --limit 50 --sleep 1.5

补齐行情后建议再跑::

    python migrations/backfill_missing_adj_factors.py --market HK --continue-on-error
    python scripts/batch_rs_rating_hk_precompute.py --days 30 --continue-on-error
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("backfill_hk_hist")

DEFAULT_MIN_BARS = 253  # max(RS_WINDOWS)=252 + 1
DEFAULT_START = "19950101"
DEFAULT_SLEEP = 1.5
FETCH_RETRIES = 3

SQL_SHORT = """
SELECT b.code,
       COALESCE(c.bars, 0) AS bars,
       c.min_d,
       c.max_d,
       b.name
FROM stock_basic_info_hk b
LEFT JOIN (
    SELECT code,
           COUNT(DISTINCT date)::int AS bars,
           MIN(date) AS min_d,
           MAX(date) AS max_d
    FROM historical_quotes_hk
    WHERE LENGTH(TRIM(code)) = 5
    GROUP BY code
) c ON c.code = b.code
WHERE LENGTH(TRIM(b.code)) = 5
  AND COALESCE(b.collect_enabled, TRUE) = TRUE
  AND COALESCE(c.bars, 0) < :min_bars
-- 优先补「已有部分历史且接近门槛」的标的，更快抬升 RS 覆盖率；bars=0 排最后
ORDER BY (COALESCE(c.bars, 0) = 0) ASC, COALESCE(c.bars, 0) DESC, b.code
"""

SQL_RS_POOL_SHORT = """
WITH cand AS (
    SELECT DISTINCT hq.code
    FROM historical_quotes_hk hq
    INNER JOIN stock_basic_info_hk b ON b.code = hq.code
    WHERE hq.date = :trade_date
      AND LENGTH(TRIM(hq.code)) = 5
      AND COALESCE(b.collect_enabled, TRUE) = TRUE
),
bars AS (
    SELECT code,
           COUNT(DISTINCT date)::int AS bars,
           MIN(date) AS min_d,
           MAX(date) AS max_d
    FROM historical_quotes_hk
    WHERE code IN (SELECT code FROM cand)
    GROUP BY code
)
SELECT c.code,
       COALESCE(b.bars, 0) AS bars,
       b.min_d,
       b.max_d,
       i.name
FROM cand c
LEFT JOIN bars b ON b.code = c.code
LEFT JOIN stock_basic_info_hk i ON i.code = c.code
WHERE COALESCE(b.bars, 0) < :min_bars
ORDER BY (COALESCE(b.bars, 0) = 0) ASC, COALESCE(b.bars, 0) DESC, c.code
"""

SQL_ALL = """
SELECT b.code,
       COALESCE(c.bars, 0) AS bars,
       c.min_d,
       c.max_d,
       b.name
FROM stock_basic_info_hk b
LEFT JOIN (
    SELECT code,
           COUNT(DISTINCT date)::int AS bars,
           MIN(date) AS min_d,
           MAX(date) AS max_d
    FROM historical_quotes_hk
    WHERE LENGTH(TRIM(code)) = 5
    GROUP BY code
) c ON c.code = b.code
WHERE LENGTH(TRIM(b.code)) = 5
  AND COALESCE(b.collect_enabled, TRUE) = TRUE
ORDER BY (COALESCE(c.bars, 0) = 0) ASC, COALESCE(c.bars, 0) ASC, b.code
"""

SQL_LATEST_TRADE_DATE = """
SELECT MAX(hq.date)
FROM historical_quotes_hk hq
WHERE LENGTH(TRIM(hq.code)) = 5
"""

SQL_BARS_ONE = """
SELECT COUNT(DISTINCT date)::int
FROM historical_quotes_hk
WHERE code = :code
"""

SQL_NAME = """
SELECT name FROM stock_basic_info_hk WHERE code = :code LIMIT 1
"""


def _parse_ymd8(s: str) -> str:
    s = (s or "").strip()
    if len(s) == 8 and s.isdigit():
        return s
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10].replace("-", "")
    raise argparse.ArgumentTypeError(f"日期格式无效: {s!r}，请用 YYYYMMDD 或 YYYY-MM-DD")


def _parse_codes(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    out: List[str] = []
    for part in raw.replace(";", ",").split(","):
        c = part.strip().upper()
        if not c:
            continue
        if c.startswith("HK") and len(c) > 2:
            c = c[2:]
        if c.isdigit():
            c = c.zfill(5) if len(c) <= 5 else c
        out.append(c)
    return out


def _norm_date_cell(val: Any) -> Optional[str]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, date):
        return val.isoformat()
    s = str(val).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    if len(s) >= 10 and s[4] == "-":
        return s[:10]
    return s or None


def resolve_trade_date(db: Session, trade_date: Optional[str]) -> str:
    if trade_date:
        s = trade_date.strip()
        if len(s) == 8 and s.isdigit():
            return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
        return s[:10]
    row = db.execute(text(SQL_LATEST_TRADE_DATE)).scalar()
    if not row:
        raise SystemExit("historical_quotes_hk 无行情，无法推断 trade_date")
    return str(row)[:10]


def list_targets(
    db: Session,
    *,
    scope: str,
    min_bars: int,
    trade_date: Optional[str],
    codes: Sequence[str],
    limit: Optional[int],
) -> List[Dict[str, Any]]:
    """返回 [{code, bars, min_d, max_d, name}, ...]。"""
    if codes:
        rows: List[Dict[str, Any]] = []
        for code in codes:
            bars = db.execute(text(SQL_BARS_ONE), {"code": code}).scalar() or 0
            name = db.execute(text(SQL_NAME), {"code": code}).scalar()
            rows.append(
                {
                    "code": code,
                    "bars": int(bars),
                    "min_d": None,
                    "max_d": None,
                    "name": name,
                }
            )
        selected = rows
    elif scope == "all":
        result = db.execute(text(SQL_ALL)).mappings().fetchall()
        selected = [dict(r) for r in result]
    elif scope == "rs-pool":
        date_s = resolve_trade_date(db, trade_date)
        result = db.execute(
            text(SQL_RS_POOL_SHORT),
            {"trade_date": date_s, "min_bars": int(min_bars)},
        ).mappings().fetchall()
        selected = [dict(r) for r in result]
        logger.info(
            "RS 候选池 trade_date=%s 且 bars<%s：%s 只",
            date_s,
            min_bars,
            len(selected),
        )
    else:  # short
        result = db.execute(
            text(SQL_SHORT),
            {"min_bars": int(min_bars)},
        ).mappings().fetchall()
        selected = [dict(r) for r in result]
        logger.info("bars<%s 的港股：%s 只", min_bars, len(selected))

    if limit is not None and limit > 0:
        selected = selected[: int(limit)]
    return selected


def _lookup_name(db: Session, code: str, fallback: Optional[str] = None) -> Optional[str]:
    if fallback:
        return str(fallback)
    name = db.execute(text(SQL_NAME), {"code": code}).scalar()
    if name:
        return str(name)
    try:
        from backend_api.models import Watchlist

        row = db.query(Watchlist.stock_name).filter(Watchlist.stock_code == code).first()
        if row is not None and row[0]:
            return str(row[0])
    except Exception:
        pass
    return None


def upsert_hk_hist(db: Session, stock_code: str, df: pd.DataFrame, stock_name: Optional[str]) -> int:
    """UPSERT 港股日线；name 用 COALESCE，避免空名覆盖库内已有名称。"""
    rows = []
    for _, row in df.iterrows():
        date_formatted = _norm_date_cell(row.get("日期"))
        if not date_formatted:
            continue
        vol_raw = row.get("成交量") if "成交量" in row.index else None
        vol_val = None
        if vol_raw is not None and not (isinstance(vol_raw, float) and pd.isna(vol_raw)):
            try:
                vol_val = float(vol_raw) / 100  # 股 → 手
            except (TypeError, ValueError):
                vol_val = None
        rows.append(
            {
                "code": stock_code,
                "name": stock_name,
                "date": date_formatted,
                "open": row.get("开盘") if "开盘" in row.index else None,
                "close": row.get("收盘") if "收盘" in row.index else None,
                "high": row.get("最高") if "最高" in row.index else None,
                "low": row.get("最低") if "最低" in row.index else None,
                "pre_close": row.get("昨收") if "昨收" in row.index else None,
                "volume": vol_val,
                "amount": row.get("成交额") if "成交额" in row.index else None,
                "amplitude": row.get("振幅") if "振幅" in row.index else None,
                "change_percent": row.get("涨跌幅") if "涨跌幅" in row.index else None,
                "change_amount": row.get("涨跌额") if "涨跌额" in row.index else None,
                "turnover_rate": row.get("换手率") if "换手率" in row.index else None,
            }
        )

    if not rows:
        return 0

    stmt = text(
        """
        INSERT INTO historical_quotes_hk (
            code, name, date, open, close, high, low, pre_close,
            volume, amount, amplitude, change_percent, change_amount, turnover_rate
        ) VALUES (
            :code, :name, :date, :open, :close, :high, :low, :pre_close,
            :volume, :amount, :amplitude, :change_percent, :change_amount, :turnover_rate
        )
        ON CONFLICT (code, date) DO UPDATE SET
            name = COALESCE(EXCLUDED.name, historical_quotes_hk.name),
            open = EXCLUDED.open,
            close = EXCLUDED.close,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            pre_close = EXCLUDED.pre_close,
            volume = EXCLUDED.volume,
            amount = EXCLUDED.amount,
            amplitude = EXCLUDED.amplitude,
            change_percent = EXCLUDED.change_percent,
            change_amount = EXCLUDED.change_amount,
            turnover_rate = EXCLUDED.turnover_rate
        """
    )
    for row_data in rows:
        db.execute(stmt, row_data)
    db.commit()
    return len(rows)


def fetch_hk_hist(
    code: str,
    *,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    import akshare as ak

    last_err: Optional[Exception] = None
    for attempt in range(1, FETCH_RETRIES + 1):
        try:
            df = ak.stock_hk_hist(
                symbol=code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="",
            )
            if df is not None and not df.empty:
                return df
            last_err = RuntimeError("返回空 DataFrame")
        except Exception as e:
            last_err = e
            logger.warning("拉取 %s 失败 (%s/%s): %s", code, attempt, FETCH_RETRIES, e)
        time.sleep(min(2.0 * attempt, 6.0))
    raise RuntimeError(f"{code} 拉取失败: {last_err}")


def _date_range_from_df(df: pd.DataFrame) -> Tuple[Optional[str], Optional[str]]:
    if df is None or df.empty or "日期" not in df.columns:
        return None, None
    s = df["日期"]
    return _norm_date_cell(s.min()), _norm_date_cell(s.max())


def process_one(
    db: Session,
    item: Dict[str, Any],
    *,
    start_date: str,
    end_date: str,
    replace: bool,
    with_indicators: bool,
) -> Dict[str, Any]:
    code = str(item["code"]).strip().zfill(5) if str(item["code"]).strip().isdigit() else str(item["code"]).strip()
    bars_before = int(item.get("bars") or 0)
    name = _lookup_name(db, code, item.get("name"))

    df = fetch_hk_hist(code, start_date=start_date, end_date=end_date)
    if replace:
        db.execute(text("DELETE FROM historical_quotes_hk WHERE code = :code"), {"code": code})
        db.commit()

    written = upsert_hk_hist(db, code, df, name)
    bars_after = int(db.execute(text(SQL_BARS_ONE), {"code": code}).scalar() or 0)

    if with_indicators:
        start_d, end_d = _date_range_from_df(df)
        if start_d and end_d:
            from backend_core.data_collectors.akshare.watchlist_history_collector import (
                _calculate_indicators_after_collect,
            )

            _calculate_indicators_after_collect(db, code, "HK", start_d, end_d)

    return {
        "code": code,
        "bars_before": bars_before,
        "bars_after": bars_after,
        "fetched": len(df),
        "written": written,
        "name": name,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="补齐港股日线历史，使 RS 预计算能达到 253 根 K 线门槛",
    )
    parser.add_argument(
        "--scope",
        choices=("short", "rs-pool", "all"),
        default="short",
        help="选股范围：short=bars<min_bars（默认）；rs-pool=某交易日 RS 池内不足；all=全部可采集港股",
    )
    parser.add_argument("--min-bars", type=int, default=DEFAULT_MIN_BARS, help="K 线门槛（默认 253）")
    parser.add_argument("--trade-date", default=None, help="rs-pool 用交易日 YYYY-MM-DD；缺省取库内最新")
    parser.add_argument("--codes", default=None, help="显式代码列表，逗号分隔（忽略 scope）")
    parser.add_argument("--limit", type=int, default=None, help="最多处理只数")
    parser.add_argument(
        "--start-date",
        type=_parse_ymd8,
        default=DEFAULT_START,
        help="akshare 起始日 YYYYMMDD（默认 19950101）",
    )
    parser.add_argument(
        "--end-date",
        type=_parse_ymd8,
        default=None,
        help="akshare 结束日 YYYYMMDD（默认今天）",
    )
    parser.add_argument("--sleep", type=float, default=DEFAULT_SLEEP, help="每只间隔秒数（限速）")
    parser.add_argument("--dry-run", action="store_true", help="只列出待补标的，不拉外网")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="写入前 DELETE 该 code 全部历史（默认仅 UPSERT）",
    )
    parser.add_argument(
        "--with-indicators",
        action="store_true",
        help="写入后计算 MA/MACD 等（默认跳过以加速批量补齐）",
    )
    parser.add_argument("--continue-on-error", action="store_true", help="单只失败继续")
    args = parser.parse_args(list(argv) if argv is not None else None)

    end_date = args.end_date or datetime.now().strftime("%Y%m%d")
    codes = _parse_codes(args.codes)

    from backend_api.database import SessionLocal

    db = SessionLocal()
    try:
        targets = list_targets(
            db,
            scope=args.scope,
            min_bars=args.min_bars,
            trade_date=args.trade_date,
            codes=codes,
            limit=args.limit,
        )
    finally:
        db.close()

    if not targets:
        logger.info("无待补齐标的，退出")
        return 0

    logger.info(
        "待处理 %s 只 scope=%s min_bars=%s start=%s end=%s dry_run=%s replace=%s",
        len(targets),
        "codes" if codes else args.scope,
        args.min_bars,
        args.start_date,
        end_date,
        args.dry_run,
        args.replace,
    )

    if args.dry_run:
        for i, item in enumerate(targets, 1):
            print(
                f"  [{i}/{len(targets)}] {item['code']}"
                f"  bars={item.get('bars')}"
                f"  range={item.get('min_d')}~{item.get('max_d')}"
                f"  {item.get('name') or ''}"
            )
        print(f"dry-run 合计 {len(targets)} 只（未拉取外网）")
        return 0

    ok = empty = failed = 0
    t0 = time.time()
    db = SessionLocal()
    try:
        for i, item in enumerate(targets, 1):
            code = item["code"]
            try:
                result = process_one(
                    db,
                    item,
                    start_date=args.start_date,
                    end_date=end_date,
                    replace=args.replace,
                    with_indicators=args.with_indicators,
                )
                if result["fetched"] <= 0:
                    empty += 1
                    logger.warning("[%s/%s] %s 外网空数据", i, len(targets), code)
                else:
                    ok += 1
                    logger.info(
                        "[%s/%s] %s bars %s→%s fetched=%s written=%s %s",
                        i,
                        len(targets),
                        result["code"],
                        result["bars_before"],
                        result["bars_after"],
                        result["fetched"],
                        result["written"],
                        result.get("name") or "",
                    )
            except Exception as e:
                try:
                    db.rollback()
                except Exception:
                    pass
                failed += 1
                logger.exception("[%s/%s] %s 失败: %s", i, len(targets), code, e)
                if not args.continue_on_error:
                    return 1
            if args.sleep and args.sleep > 0 and i < len(targets):
                time.sleep(float(args.sleep))
    finally:
        db.close()

    elapsed = time.time() - t0
    logger.info(
        "完成 ok=%s empty=%s failed=%s elapsed=%.1fs",
        ok,
        empty,
        failed,
        elapsed,
    )
    if failed and not args.continue_on_error:
        return 1
    logger.info(
        "下一步建议: "
        "python migrations/backfill_missing_adj_factors.py --market HK --continue-on-error ; "
        "python scripts/batch_rs_rating_hk_precompute.py --days 30 --continue-on-error"
    )
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
