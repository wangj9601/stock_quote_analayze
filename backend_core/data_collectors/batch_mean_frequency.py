# -*- coding: utf-8 -*-
"""
全市场 PVFRS（均值频率共振）批量计算：预加载窗口行情、内存计算、批量 upsert。
供 Tushare / 港股历史采集共用。
"""

from __future__ import annotations

import datetime
import logging
import os
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend_core.data_collectors.batch_ma_mavol import (
    _normalize_date_str,
    _preload_quote_series,
    _resolve_stock_codes,
)
from backend_core.utils.mean_frequency_calculator import MeanFrequencyResonanceCalculator

logger = logging.getLogger(__name__)

DEFAULT_LOOKBACK_CALENDAR_DAYS = int(os.getenv("PVFRS_LOOKBACK_DAYS") or "90")
DEFAULT_PRELOAD_BATCH_SIZE = int(os.getenv("PVFRS_BATCH_SIZE") or os.getenv("MA_MAVOL_BATCH_SIZE") or "500")
DEFAULT_UPSERT_BATCH_SIZE = int(os.getenv("PVFRS_UPSERT_BATCH_SIZE") or os.getenv("MA_MAVOL_UPSERT_BATCH_SIZE") or "1000")

_calculator = MeanFrequencyResonanceCalculator()


def _compute_single_stock(
    code: str,
    series: Dict[str, List[Any]],
    target_date: str,
    market_type: str,
    created_at: datetime.datetime,
) -> Tuple[Optional[dict], str]:
    """返回 (row, status)；status: ok|skip|fail。"""
    try:
        dates = series.get("dates") or []
        if target_date not in dates:
            return None, "skip"
        idx = dates.index(target_date)
        closes = series.get("closes") or []
        volumes = series.get("volumes") or []
        res = _calculator.calculate_for_target_day(
            closes[: idx + 1],
            volumes[: idx + 1],
            dates[: idx + 1],
            target_date,
        )
        if not res:
            return None, "skip"
        return {
            "code": code,
            "date": target_date,
            "market_type": market_type,
            "delta": res["macro_displacement_delta"],
            "amplitude": res.get("amplitude"),
            "ratio_d20": res.get("ratio_d20"),
            "ratio_d1": res.get("ratio_d1"),
            "instant_deviation": res["instant_deviation"],
            "z": res["rising_days_z"],
            "f": res["falling_days_f"],
            "efficiency": res["efficiency_m20_minus_m"],
            "ma20": res["ma20_d"],
            "mavol20": res["mavol20_m"],
            "bias": res["bias"],
            "d1": res.get("d1"),
            "d1_date": res.get("d1_date"),
            "d20": res.get("d20"),
            "d20_date": res.get("d20_date"),
            "created_at": created_at,
        }, "ok"
    except Exception:
        return None, "fail"


def _attach_ma60_d(session: Session, rows: List[dict]) -> None:
    if not rows:
        return
    from backend_core.strategies.gms.ma60_source import batch_lookup_ma60_d, ma60_key

    keys = [ma60_key(r["code"], r["date"], r["market_type"]) for r in rows]
    cache = batch_lookup_ma60_d(session, keys)
    for r in rows:
        k = ma60_key(r["code"], r["date"], r["market_type"])
        if k in cache:
            r["ma60_d"] = cache[k]


def _bulk_upsert_pvfrs(session: Session, rows: List[dict], batch_size: int = DEFAULT_UPSERT_BATCH_SIZE) -> None:
    if not rows:
        return
    sql = text(
        """
        INSERT INTO mean_frequency_resonance_indicators
        (code, date, market_type, macro_displacement_delta, amplitude, ratio_d20, ratio_d1,
         instant_deviation, rising_days_z, falling_days_f, efficiency_m20_minus_m,
         ma20_d, ma60_d, mavol20_m, bias, d1, d1_date, d20, d20_date, created_at)
        VALUES (:code, :date, :market_type, :delta, :amplitude, :ratio_d20, :ratio_d1,
                :instant_deviation, :z, :f, :efficiency, :ma20, :ma60_d, :mavol20, :bias,
                :d1, :d1_date, :d20, :d20_date, :created_at)
        ON CONFLICT (code, date, market_type) DO UPDATE SET
            macro_displacement_delta = EXCLUDED.macro_displacement_delta,
            amplitude = EXCLUDED.amplitude,
            ratio_d20 = EXCLUDED.ratio_d20,
            ratio_d1 = EXCLUDED.ratio_d1,
            instant_deviation = EXCLUDED.instant_deviation,
            rising_days_z = EXCLUDED.rising_days_z,
            falling_days_f = EXCLUDED.falling_days_f,
            efficiency_m20_minus_m = EXCLUDED.efficiency_m20_minus_m,
            ma20_d = EXCLUDED.ma20_d,
            ma60_d = EXCLUDED.ma60_d,
            mavol20_m = EXCLUDED.mavol20_m,
            bias = EXCLUDED.bias,
            d1 = EXCLUDED.d1,
            d1_date = EXCLUDED.d1_date,
            d20 = EXCLUDED.d20,
            d20_date = EXCLUDED.d20_date,
            created_at = EXCLUDED.created_at
        """
    )
    for i in range(0, len(rows), batch_size):
        session.execute(sql, rows[i : i + batch_size])


def calculate_and_save_mean_frequency_for_date(
    session: Session,
    target_date: str,
    *,
    quotes_table: str = "historical_quotes",
    market_type: str = "CN",
    stock_codes: Optional[Sequence[str]] = None,
    include_ma60: bool = True,
    log: Optional[logging.Logger] = None,
) -> dict:
    """
    批量计算并写入指定日期的 PVFRS（mean_frequency_resonance_indicators）。
    """
    log = log or logger
    codes = _resolve_stock_codes(session, target_date, quotes_table, stock_codes)
    total = len(codes)
    empty = {"total": total, "success": 0, "skipped": 0, "failed": 0, "written": 0, "details": []}
    if not codes:
        log.warning("日期 %s 无股票可计算 PVFRS", target_date)
        return empty

    try:
        preloaded = _preload_quote_series(
            session,
            codes,
            target_date,
            quotes_table,
            lookback_calendar_days=DEFAULT_LOOKBACK_CALENDAR_DAYS,
            preload_batch_size=DEFAULT_PRELOAD_BATCH_SIZE,
            log=log,
        )
        created_at = datetime.datetime.now()
        rows: List[dict] = []
        stats = {"success": 0, "skipped": 0, "failed": 0, "details": []}
        t0 = time.time()
        for code, series in preloaded.items():
            row, status = _compute_single_stock(code, series, target_date, market_type, created_at)
            if status == "ok" and row:
                stats["success"] += 1
                rows.append(row)
            elif status == "skip":
                stats["skipped"] += 1
            else:
                stats["failed"] += 1
                stats["details"].append(f"{code}: compute failed")

        log.info(
            "PVFRS 内存计算完成 codes=%s ok=%s skip=%s fail=%s elapsed=%.2fs",
            len(preloaded),
            stats["success"],
            stats["skipped"],
            stats["failed"],
            time.time() - t0,
        )

        if include_ma60 and rows:
            _attach_ma60_d(session, rows)
        for r in rows:
            r.setdefault("ma60_d", None)

        t1 = time.time()
        _bulk_upsert_pvfrs(session, rows)
        session.commit()
        log.info("PVFRS 批量写入完成 rows=%s elapsed=%.2fs", len(rows), time.time() - t1)

        return {
            "total": total,
            "success": stats["success"],
            "skipped": stats["skipped"],
            "failed": stats["failed"],
            "written": len(rows),
            "details": stats["details"],
        }
    except Exception as e:
        log.exception("批量 PVFRS 计算失败: %s", e)
        session.rollback()
        return {
            "total": total,
            "success": 0,
            "skipped": 0,
            "failed": total,
            "written": 0,
            "details": [str(e)],
        }
