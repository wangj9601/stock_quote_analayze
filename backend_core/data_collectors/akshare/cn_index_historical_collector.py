"""
A股指数历史行情归档采集器
每日休市后，将 index_realtime_quotes 当日快照转存到 index_historical_quotes
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import text

from backend_core.database.db import SessionLocal

logger = logging.getLogger("CNIndexHistoricalCollector")

# AkShare 新浪 symbol 前缀 -> ts_code 后缀
_AK_PREFIX_SUFFIX = {"sh": ".SH", "sz": ".SZ"}


def code_to_ts_code(code: str) -> str:
    """将实时表 code（如 sh000300 / 000300）映射为 ts_code（000300.SH）。"""
    raw = str(code or "").strip()
    lower = raw.lower()
    if lower.startswith("sh") and len(lower) > 2:
        return f"{lower[2:]}.SH"
    if lower.startswith("sz") and len(lower) > 2:
        return f"{lower[2:]}.SZ"
    digits = raw
    if len(digits) == 6 and digits.isdigit():
        if digits.startswith("399") or digits.startswith("1"):
            return f"{digits}.SZ"
        return f"{digits}.SH"
    return f"{digits}.SH"


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


class CNIndexHistoricalCollector:
    """A股指数实时 → 历史日 K 归档。"""

    def __init__(self) -> None:
        self.logger = logger

    def collect_daily_to_historical(self, trade_date: Optional[str] = None) -> Dict[str, Any]:
        if trade_date is None:
            trade_date = datetime.now().strftime("%Y-%m-%d")

        session = SessionLocal()
        try:
            self.logger.info("开始 A 股指数实时→历史归档，日期: %s", trade_date)

            query_sql = text(
                """
                SELECT DISTINCT ON (code)
                    code,
                    name,
                    price,
                    change,
                    pct_chg,
                    open,
                    pre_close,
                    high,
                    low,
                    volume,
                    amount,
                    update_time
                FROM index_realtime_quotes
                WHERE LEFT(update_time, 10) = :trade_date
                ORDER BY code, update_time DESC
                """
            )
            rows = session.execute(query_sql, {"trade_date": trade_date}).fetchall()

            if not rows:
                self.logger.warning("未找到日期 %s 的指数实时行情", trade_date)
                return {
                    "success": 0,
                    "failed": 0,
                    "skipped": 0,
                    "trade_date": trade_date,
                    "message": f"未找到日期 {trade_date} 的指数实时行情",
                }

            insert_sql = text(
                """
                INSERT INTO index_historical_quotes (
                    ts_code, trade_date, code, name,
                    open, high, low, close, pre_close, change, pct_chg, vol, amount,
                    collected_source, update_time
                ) VALUES (
                    :ts_code, CAST(:trade_date AS DATE), :code, :name,
                    :open, :high, :low, :close, :pre_close, :change, :pct_chg, :vol, :amount,
                    'realtime_archive', CURRENT_TIMESTAMP
                )
                ON CONFLICT (ts_code, trade_date) DO UPDATE SET
                    code = EXCLUDED.code,
                    name = EXCLUDED.name,
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    pre_close = EXCLUDED.pre_close,
                    change = EXCLUDED.change,
                    pct_chg = EXCLUDED.pct_chg,
                    vol = EXCLUDED.vol,
                    amount = EXCLUDED.amount,
                    collected_source = EXCLUDED.collected_source,
                    update_time = CURRENT_TIMESTAMP
                """
            )

            success = 0
            failed = 0
            for row in rows:
                try:
                    ts_code = code_to_ts_code(row.code)
                    code_digits = ts_code.split(".")[0]
                    session.execute(
                        insert_sql,
                        {
                            "ts_code": ts_code,
                            "trade_date": trade_date,
                            "code": code_digits,
                            "name": row.name,
                            "open": _safe_float(row.open),
                            "high": _safe_float(row.high),
                            "low": _safe_float(row.low),
                            "close": _safe_float(row.price),
                            "pre_close": _safe_float(row.pre_close),
                            "change": _safe_float(row.change),
                            "pct_chg": _safe_float(row.pct_chg),
                            "vol": _safe_float(row.volume),
                            "amount": _safe_float(row.amount),
                        },
                    )
                    success += 1
                except Exception as exc:
                    self.logger.error("归档指数 %s 失败: %s", row.code, exc)
                    failed += 1

            session.commit()
            msg = f"成功归档 {success} 条指数历史数据"
            self.logger.info("%s，失败 %d 条", msg, failed)
            return {
                "success": success,
                "failed": failed,
                "skipped": 0,
                "trade_date": trade_date,
                "message": msg,
            }
        except Exception as exc:
            session.rollback()
            self.logger.error("A 股指数归档异常: %s", exc, exc_info=True)
            return {
                "success": 0,
                "failed": 0,
                "skipped": 0,
                "error": str(exc),
                "message": f"归档失败: {exc}",
            }
        finally:
            session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = CNIndexHistoricalCollector().collect_daily_to_historical()
    print(result)
