# -*- coding: utf-8 -*-
"""
周频 PVFRS：从 weekly_quotes 计算并写入 mean_frequency_resonance_indicators_weekly。

- MF 窗口：20 根周 K（与日线公式一致）
- ma60_d：12 根周收盘均线（GMS 周线策略语义位）
"""

from __future__ import annotations

import datetime
import logging
import os
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from backend_core.data_collectors.batch_ma_mavol import _normalize_date_str, _resolve_stock_codes
from backend_core.utils.mean_frequency_calculator import MeanFrequencyResonanceCalculator

logger = logging.getLogger(__name__)

DEFAULT_LOOKBACK_CALENDAR_DAYS = int(os.getenv("PVFRS_WEEKLY_LOOKBACK_DAYS") or "1600")
DEFAULT_PRELOAD_BATCH_SIZE = int(os.getenv("PVFRS_WEEKLY_BATCH_SIZE") or "500")
DEFAULT_UPSERT_BATCH_SIZE = int(os.getenv("PVFRS_WEEKLY_UPSERT_BATCH_SIZE") or "1000")
MA60_WEEKLY_BARS = int(os.getenv("GMS_WEEKLY_MA60_BARS") or "12")

_calculator = MeanFrequencyResonanceCalculator()


def _preload_weekly_series(
    session: Session,
    stock_codes: Sequence[str],
    target_date: str,
    *,
    lookback_calendar_days: int = DEFAULT_LOOKBACK_CALENDAR_DAYS,
    preload_batch_size: int = DEFAULT_PRELOAD_BATCH_SIZE,
    log: logging.Logger = logger,
) -> Dict[str, Dict[str, List[Any]]]:
    if not stock_codes:
        return {}
    min_date = (
        datetime.datetime.strptime(target_date, "%Y-%m-%d")
        - datetime.timedelta(days=lookback_calendar_days)
    ).strftime("%Y-%m-%d")
    out: Dict[str, Dict[str, List[Any]]] = {}
    codes = list(stock_codes)
    t0 = time.time()
    for i in range(0, len(codes), preload_batch_size):
        batch = codes[i : i + preload_batch_size]
        stmt = text(
            """
            SELECT code, date, close, volume
            FROM weekly_quotes
            WHERE code IN :codes
              AND date >= :min_date
              AND date <= :target_date
            ORDER BY code ASC, date ASC
            """
        ).bindparams(bindparam("codes", expanding=True))
        rows = session.execute(
            stmt,
            {"codes": batch, "min_date": min_date, "target_date": target_date},
        ).fetchall()
        for code, date_val, close, volume in rows:
            key = str(code)
            bucket = out.setdefault(key, {"dates": [], "closes": [], "volumes": []})
            ds = _normalize_date_str(date_val)
            if not ds:
                continue
            try:
                c = float(close) if close is not None else None
                v = float(volume) if volume is not None else 0.0
            except (TypeError, ValueError):
                continue
            if c is None:
                continue
            bucket["dates"].append(ds)
            bucket["closes"].append(c)
            bucket["volumes"].append(v if v is not None else 0.0)
    log.info(
        "周频 PVFRS 预加载 codes=%s hit=%s elapsed=%.2fs",
        len(codes),
        len(out),
        time.time() - t0,
    )
    return out


def _ma_n(closes: Sequence[float], n: int) -> Optional[float]:
    if n <= 0 or len(closes) < n:
        return None
    window = closes[-n:]
    return float(sum(window) / n)


def _compute_single_stock(
    code: str,
    series: Dict[str, List[Any]],
    target_date: str,
    market_type: str,
    created_at: datetime.datetime,
) -> Tuple[Optional[dict], str]:
    try:
        dates = series.get("dates") or []
        if target_date not in dates:
            return None, "skip"
        idx = dates.index(target_date)
        closes = series.get("closes") or []
        volumes = series.get("volumes") or []
        closes_upto = closes[: idx + 1]
        volumes_upto = volumes[: idx + 1]
        dates_upto = dates[: idx + 1]
        res = _calculator.calculate_for_target_day(
            closes_upto,
            volumes_upto,
            dates_upto,
            target_date,
        )
        if not res:
            return None, "skip"
        ma60 = _ma_n(closes_upto, MA60_WEEKLY_BARS)
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
            "ma60_d": ma60,
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


def _bulk_upsert(session: Session, rows: List[dict], batch_size: int = DEFAULT_UPSERT_BATCH_SIZE) -> None:
    if not rows:
        return
    sql = text(
        """
        INSERT INTO mean_frequency_resonance_indicators_weekly
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


def calculate_and_save_mean_frequency_weekly_for_date(
    session: Session,
    target_date: str,
    *,
    market_type: str = "CN",
    stock_codes: Optional[Sequence[str]] = None,
    log: Optional[logging.Logger] = None,
) -> dict:
    """批量计算并写入指定周五标签的周频 PVFRS。"""
    log = log or logger
    target_date = _normalize_date_str(target_date)
    codes = _resolve_stock_codes(session, target_date, "weekly_quotes", stock_codes)
    total = len(codes)
    empty = {"total": total, "success": 0, "skipped": 0, "failed": 0, "written": 0}
    if not codes:
        log.warning("周 %s 无股票可计算周频 PVFRS", target_date)
        return empty

    preloaded = _preload_weekly_series(session, codes, target_date, log=log)
    created_at = datetime.datetime.now()
    rows: List[dict] = []
    stats = {"success": 0, "skipped": 0, "failed": 0}
    for code, series in preloaded.items():
        row, status = _compute_single_stock(code, series, target_date, market_type, created_at)
        if status == "ok" and row:
            stats["success"] += 1
            rows.append(row)
        elif status == "skip":
            stats["skipped"] += 1
        else:
            stats["failed"] += 1

    _bulk_upsert(session, rows)
    session.commit()
    log.info(
        "周频 PVFRS 完成 date=%s ok=%s skip=%s fail=%s written=%s",
        target_date,
        stats["success"],
        stats["skipped"],
        stats["failed"],
        len(rows),
    )
    return {
        "total": total,
        "success": stats["success"],
        "skipped": stats["skipped"],
        "failed": stats["failed"],
        "written": len(rows),
        "date": target_date,
    }


def run_weekly_mf_cn_for_as_of(
    session: Session,
    as_of: Optional[str] = None,
    *,
    stock_codes: Optional[Sequence[str]] = None,
    log: Optional[logging.Logger] = None,
) -> dict:
    """解析已收盘周后计算该周五的周频 MF。"""
    from backend_core.strategies.gms.week_calendar import (
        normalize_date_str,
        resolve_gms_trade_date_fallback,
        resolve_gms_week_end,
    )

    log = log or logger
    if not as_of:
        try:
            as_of = resolve_gms_trade_date_fallback(session)
        except Exception:
            as_of = datetime.date.today().isoformat()
    as_of = normalize_date_str(as_of)
    week_end = resolve_gms_week_end(session, as_of)
    if not week_end:
        log.warning("无法解析已收盘周 as_of=%s", as_of)
        return {"success": False, "error": "no_closed_week", "as_of": as_of}
    result = calculate_and_save_mean_frequency_weekly_for_date(
        session, week_end, market_type="CN", stock_codes=stock_codes, log=log
    )
    result["as_of"] = as_of
    result["week_end"] = week_end
    result["success"] = True
    return result
