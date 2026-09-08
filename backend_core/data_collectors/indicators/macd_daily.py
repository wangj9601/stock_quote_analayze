# -*- coding: utf-8 -*-
"""A股/港股 MACD 日指标独立计算（采集后按日 UPSERT 到 macd_indicators）。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from backend_core.database.db import SessionLocal
from backend_core.utils.macd_calculator import MACDCalculator

logger = logging.getLogger(__name__)

_LOOKBACK_DAYS = 90  # 覆盖足够交易日以计算 MACD(26)


def _fmt_date(d: Any) -> str:
    if isinstance(d, datetime):
        return d.strftime("%Y-%m-%d")
    if hasattr(d, "strftime"):
        return d.strftime("%Y-%m-%d")
    return str(d)[:10]


def resolve_trade_date(market_type: str, trade_date: Optional[str] = None) -> str:
    """优先使用传入日期；否则取对应历史表最新交易日；再否则今天。"""
    if trade_date:
        datetime.strptime(trade_date, "%Y-%m-%d")
        return trade_date
    table = "historical_quotes" if market_type == "CN" else "historical_quotes_hk"
    session = SessionLocal()
    try:
        row = session.execute(text(f"SELECT MAX(date) FROM {table}")).fetchone()
        if row and row[0]:
            return _fmt_date(row[0])
    finally:
        session.close()
    return datetime.now().strftime("%Y-%m-%d")


def _codes_for_date(session, market_type: str, trade_date: str) -> List[str]:
    table = "historical_quotes" if market_type == "CN" else "historical_quotes_hk"
    rows = session.execute(
        text(
            f"""
            SELECT DISTINCT code
            FROM {table}
            WHERE date = :d
            ORDER BY code
            """
        ),
        {"d": trade_date},
    ).fetchall()
    return [str(r[0]) for r in rows if r and r[0]]


def _closes_for_code(
    session, market_type: str, code: str, trade_date: str
) -> List[tuple]:
    table = "historical_quotes" if market_type == "CN" else "historical_quotes_hk"
    start = (
        datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=_LOOKBACK_DAYS)
    ).strftime("%Y-%m-%d")
    return session.execute(
        text(
            f"""
            SELECT date, close
            FROM {table}
            WHERE code = :code
              AND date >= :start
              AND date <= :end
              AND close IS NOT NULL
            ORDER BY date ASC
            """
        ),
        {"code": code, "start": start, "end": trade_date},
    ).fetchall()


def run_macd_daily(
    market_type: str,
    trade_date: Optional[str] = None,
    stock_codes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    对指定市场、交易日批量计算 MACD，仅 UPSERT 该日指标。

    Args:
        market_type: 'CN' | 'HK'
        trade_date: YYYY-MM-DD，缺省取历史表最新日
        stock_codes: 可选，限定股票；默认取该日有行情的全部代码
    """
    if market_type not in ("CN", "HK"):
        raise ValueError("market_type 须为 CN 或 HK")

    target = resolve_trade_date(market_type, trade_date)
    calculator = MACDCalculator()
    session = SessionLocal()
    success = 0
    skipped = 0
    failed = 0
    failed_details: List[str] = []

    try:
        codes = stock_codes or _codes_for_date(session, market_type, target)
        logger.info(
            "MACD日算开始 market=%s trade_date=%s codes=%s",
            market_type,
            target,
            len(codes),
        )
        if not codes:
            return {
                "success": True,
                "market_type": market_type,
                "trade_date": target,
                "total": 0,
                "ok": 0,
                "skipped": 0,
                "failed": 0,
                "details": [],
            }

        for code in codes:
            try:
                rows = _closes_for_code(session, market_type, code, target)
                if len(rows) < 26:
                    skipped += 1
                    continue
                dates = [_fmt_date(r[0]) for r in rows]
                closes = [float(r[1]) for r in rows]
                macd_results = calculator.calculate_macd_batch(closes)
                if not macd_results:
                    failed += 1
                    failed_details.append(f"{code}: 计算为空")
                    continue

                saved = False
                for i, macd_data in enumerate(macd_results):
                    if not macd_data or macd_data.get("dif") is None:
                        continue
                    date_str = dates[i]
                    if date_str != target:
                        continue
                    session.execute(
                        text(
                            """
                            INSERT INTO macd_indicators
                            (code, date, market_type, dif, dea, macd, ema12, ema26, created_at)
                            VALUES
                            (:code, :date, :market_type, :dif, :dea, :macd, :ema12, :ema26, :created_at)
                            ON CONFLICT (code, date, market_type) DO UPDATE SET
                                dif = EXCLUDED.dif,
                                dea = EXCLUDED.dea,
                                macd = EXCLUDED.macd,
                                ema12 = EXCLUDED.ema12,
                                ema26 = EXCLUDED.ema26,
                                created_at = EXCLUDED.created_at
                            """
                        ),
                        {
                            "code": code,
                            "date": date_str,
                            "market_type": market_type,
                            "dif": macd_data.get("dif"),
                            "dea": macd_data.get("dea"),
                            "macd": macd_data.get("macd"),
                            "ema12": macd_data.get("ema12"),
                            "ema26": macd_data.get("ema26"),
                            "created_at": datetime.now(),
                        },
                    )
                    saved = True
                if saved:
                    session.commit()
                    success += 1
                else:
                    skipped += 1
            except Exception as e:
                session.rollback()
                failed += 1
                failed_details.append(f"{code}: {e}")
                logger.warning("MACD日算失败 code=%s: %s", code, e)

        result = {
            "success": failed == 0,
            "market_type": market_type,
            "trade_date": target,
            "total": len(codes),
            "ok": success,
            "skipped": skipped,
            "failed": failed,
            "details": failed_details[:50],
        }
        logger.info(
            "MACD日算完成 market=%s date=%s ok=%s skipped=%s failed=%s",
            market_type,
            target,
            success,
            skipped,
            failed,
        )
        return result
    finally:
        session.close()


def run_macd_cn(trade_date: Optional[str] = None) -> Dict[str, Any]:
    return run_macd_daily("CN", trade_date=trade_date)


def run_macd_hk(trade_date: Optional[str] = None) -> Dict[str, Any]:
    return run_macd_daily("HK", trade_date=trade_date)
