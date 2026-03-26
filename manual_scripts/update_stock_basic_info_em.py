#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补丁：用 AKShare stock_individual_info_em 增量更新 A 股 stock_basic_info
（行业、上市日期、股本等）。每只股票请求后休眠，默认 5 秒，避免打爆源站。

运行（项目根目录）：
  python manual_scripts/update_stock_basic_info_em.py
  python manual_scripts/update_stock_basic_info_em.py --mode full --max 10
环境变量（可选）：STOCK_EM_PROFILE_STALE_DAYS、STOCK_EM_API_INTERVAL_SEC
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import akshare as ak
import pandas as pd
from sqlalchemy import text

current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

from backend_api.database import SessionLocal

# item 文案别名（东方财富/akshare 变更时可扩列）
_INDUSTRY_ITEMS = frozenset({"行业", "所属行业", "行业名称", "证监会行业"})
_LISTING_ITEMS = frozenset({"上市时间", "上市日期"})
_SHORT_NAME_ITEMS = frozenset({"股票简称", "证券简称", "简称"})
_TOTAL_SHARES_ITEMS = frozenset({"总股本", "总股本(股)"})
_FLOAT_SHARES_ITEMS = frozenset(
    {"流通股", "流通股(股)", "流通股本", "流通股本(股)"}
)


def _symbol_for_ak(code: Any) -> str:
    s = str(code).strip()
    if s.isdigit() and len(s) < 6:
        return s.zfill(6)
    return s


def _parse_individual_info_em_df(df: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """从 stock_individual_info_em 返回的 DataFrame 解析字段。"""
    out: Dict[str, Any] = {
        "total_shares": None,
        "free_float_shares": None,
        "industry": None,
        "listing_date": None,
        "short_name": None,
    }
    if df is None or df.empty:
        return out

    for _, row in df.iterrows():
        item = str(row.get("item", "")).strip()
        value = row.get("value", None)
        if not item:
            continue

        if item in _TOTAL_SHARES_ITEMS:
            try:
                out["total_shares"] = float(value)
            except (TypeError, ValueError):
                pass
        elif item in _FLOAT_SHARES_ITEMS:
            try:
                out["free_float_shares"] = float(value)
            except (TypeError, ValueError):
                pass
        elif item in _INDUSTRY_ITEMS:
            if value is not None and str(value).strip():
                out["industry"] = str(value).strip()
        elif item in _LISTING_ITEMS:
            if value is not None and str(value).strip():
                out["listing_date"] = str(value).strip()
        elif item in _SHORT_NAME_ITEMS:
            if value is not None and str(value).strip():
                out["short_name"] = str(value).strip()

    return out


def _fetch_with_retry(
    symbol: str,
    max_retries: int,
    retry_delay: float,
    logger: logging.Logger,
) -> Optional[pd.DataFrame]:
    last_err: Optional[Exception] = None
    for i in range(max_retries):
        try:
            return ak.stock_individual_info_em(symbol=symbol)
        except Exception as e:
            last_err = e
            logger.warning("第 %s 次请求 %s 失败: %s", i + 1, symbol, e)
            if i < max_retries - 1:
                time.sleep(retry_delay)
    logger.error("股票 %s 拉取资料失败，已重试 %s 次: %s", symbol, max_retries, last_err)
    return None


def _ensure_columns(session, logger: logging.Logger) -> None:
    session.execute(
        text(
            """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='stock_basic_info'
                           AND column_name='total_shares') THEN
                ALTER TABLE stock_basic_info ADD COLUMN total_shares REAL;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='stock_basic_info'
                           AND column_name='free_float_shares') THEN
                ALTER TABLE stock_basic_info ADD COLUMN free_float_shares REAL;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='stock_basic_info'
                           AND column_name='shares_updated_at') THEN
                ALTER TABLE stock_basic_info ADD COLUMN shares_updated_at TIMESTAMP;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='stock_basic_info'
                           AND column_name='industry') THEN
                ALTER TABLE stock_basic_info ADD COLUMN industry TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='stock_basic_info'
                           AND column_name='listing_date') THEN
                ALTER TABLE stock_basic_info ADD COLUMN listing_date TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='stock_basic_info'
                           AND column_name='collect_enabled') THEN
                ALTER TABLE stock_basic_info ADD COLUMN collect_enabled BOOLEAN DEFAULT TRUE;
            END IF;
        END
        $$;
    """
        )
    )
    session.commit()
    logger.info("已确保 stock_basic_info 扩展列存在")


def _get_stocks_to_update(
    session,
    mode: str,
    max_stocks: Optional[int],
    stale_days: int,
) -> List[Tuple[Any, Optional[str]]]:
    if mode == "full":
        query = "SELECT code, name FROM stock_basic_info WHERE COALESCE(collect_enabled, TRUE) = TRUE ORDER BY code"
    elif mode == "missing":
        query = """
            SELECT code, name FROM stock_basic_info
            WHERE COALESCE(collect_enabled, TRUE) = TRUE
              AND (total_shares IS NULL OR free_float_shares IS NULL)
            ORDER BY code
        """
    else:
        # stale_days 由调用方保证为 int
        query = f"""
            SELECT code, name FROM stock_basic_info
            WHERE COALESCE(collect_enabled, TRUE) = TRUE
              AND (
                   shares_updated_at IS NULL
                   OR shares_updated_at < NOW() - INTERVAL '{stale_days} days'
              )
            ORDER BY shares_updated_at ASC NULLS FIRST, code
        """
    if max_stocks:
        query += f" LIMIT {int(max_stocks)}"
    r = session.execute(text(query))
    return list(r.fetchall())


def _has_any_profile_field(parsed: Dict[str, Any]) -> bool:
    return any(
        [
            parsed.get("total_shares") is not None,
            parsed.get("free_float_shares") is not None,
            parsed.get("industry"),
            parsed.get("listing_date"),
            parsed.get("short_name"),
        ]
    )


def run(
    mode: str = "incremental",
    max_stocks: Optional[int] = None,
    stale_days: int = 7,
    interval_seconds: float = 5.0,
    overwrite_name: bool = False,
    max_retries: int = 3,
    retry_delay: float = 5.0,
) -> Dict[str, int]:
    log_dir = project_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(
                log_dir / "update_stock_basic_info_em.log", encoding="utf-8"
            ),
            logging.StreamHandler(),
        ],
    )
    logger = logging.getLogger("update_stock_basic_info_em")

    stale_days = int(stale_days)
    interval_seconds = float(interval_seconds)

    session = SessionLocal()
    success_count = 0
    fail_count = 0
    skip_count = 0

    try:
        _ensure_columns(session, logger)
        stocks = _get_stocks_to_update(session, mode, max_stocks, stale_days)
        total = len(stocks)
        logger.info(
            "开始 EM 个股资料补丁，mode=%s，stale_days=%s，待处理=%s，间隔=%ss",
            mode,
            stale_days,
            total,
            interval_seconds,
        )

        for i, row in enumerate(stocks, 1):
            code = row[0]
            name = row[1] or ""
            sym = _symbol_for_ak(code)

            if "退" in str(name):
                skip_count += 1
                logger.debug("跳过退市: %s %s", sym, name)
                time.sleep(interval_seconds)
                continue

            try:
                df = _fetch_with_retry(sym, max_retries, retry_delay, logger)
                parsed = _parse_individual_info_em_df(df)

                if not _has_any_profile_field(parsed):
                    skip_count += 1
                    logger.debug("无有效字段，跳过: %s", sym)
                else:
                    apply_name = False
                    sn = parsed.get("short_name")
                    if sn:
                        if overwrite_name:
                            apply_name = True
                        elif not (name and str(name).strip()):
                            apply_name = True

                    session.execute(
                        text(
                            """
                            UPDATE stock_basic_info
                            SET
                                total_shares = COALESCE(:total_shares, total_shares),
                                free_float_shares = COALESCE(:free_float_shares, free_float_shares),
                                industry = COALESCE(:industry, industry),
                                listing_date = COALESCE(:listing_date, listing_date),
                                shares_updated_at = :updated_at,
                                name = CASE WHEN :apply_name THEN :short_name ELSE name END
                            WHERE code = :code
                            """
                        ),
                        {
                            "code": code,
                            "total_shares": parsed["total_shares"],
                            "free_float_shares": parsed["free_float_shares"],
                            "industry": parsed["industry"],
                            "listing_date": parsed["listing_date"],
                            "updated_at": datetime.now(),
                            "apply_name": apply_name,
                            "short_name": sn or "",
                        },
                    )
                    session.commit()
                    success_count += 1
                    logger.info(
                        "已更新 %s (%s/%s) industry=%s listing=%s",
                        sym,
                        i,
                        total,
                        parsed.get("industry"),
                        parsed.get("listing_date"),
                    )

            except Exception as e:
                session.rollback()
                fail_count += 1
                logger.exception("处理 %s 异常: %s", sym, e)

            time.sleep(interval_seconds)

        logger.info(
            "完成: 成功=%s 失败=%s 跳过=%s",
            success_count,
            fail_count,
            skip_count,
        )
        return {
            "total": total,
            "success": success_count,
            "failed": fail_count,
            "skipped": skip_count,
        }
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="用东方财富个股资料接口补丁更新 stock_basic_info"
    )
    parser.add_argument(
        "--mode",
        choices=["full", "incremental", "missing"],
        default="incremental",
        help="full=全表；incremental=仅未更新或超过 stale_days（默认）；missing=仅补缺股本",
    )
    parser.add_argument("--max", type=int, default=None, dest="max_stocks", help="最多处理条数")
    parser.add_argument(
        "--stale-days",
        type=int,
        default=None,
        help="增量模式下「过期」天数，默认环境变量 STOCK_EM_PROFILE_STALE_DAYS 或 7",
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=None,
        help="每只股票处理后的休眠秒数，默认环境变量 STOCK_EM_API_INTERVAL_SEC 或 5",
    )
    parser.add_argument(
        "--overwrite-name",
        action="store_true",
        help="用接口返回的股票简称覆盖已有 name（默认仅在 name 为空时写入）",
    )
    parser.add_argument("--max-retries", type=int, default=3, help="单只股票接口重试次数")
    parser.add_argument("--retry-delay", type=float, default=5.0, help="重试间隔秒数")
    args = parser.parse_args()

    stale = args.stale_days
    if stale is None:
        stale = int(os.getenv("STOCK_EM_PROFILE_STALE_DAYS", "7"))

    interval = args.interval_seconds
    if interval is None:
        interval = float(os.getenv("STOCK_EM_API_INTERVAL_SEC", "5"))

    run(
        mode=args.mode,
        max_stocks=args.max_stocks,
        stale_days=stale,
        interval_seconds=interval,
        overwrite_name=args.overwrite_name,
        max_retries=args.max_retries,
        retry_delay=args.retry_delay,
    )


if __name__ == "__main__":
    main()
