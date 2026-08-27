# -*- coding: utf-8 -*-
"""
全市场 MA / MAVOL 批量计算：预加载窗口行情、内存计算、批量 upsert。
供 Tushare 历史采集与港股历史采集共用。
"""

from __future__ import annotations

import datetime
import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from backend_core.utils.ma_calculator import MACalculator
from backend_core.utils.mavol_calculator import MAVOLCalculator

logger = logging.getLogger(__name__)

MA_PERIODS = [5, 10, 20, 30, 60, 120, 200]
MAVOL_PERIODS = [5, 10, 20, 30, 60, 120, 200]

DEFAULT_LOOKBACK_CALENDAR_DAYS = int(os.getenv("MA_MAVOL_LOOKBACK_DAYS") or "320")
DEFAULT_PRELOAD_BATCH_SIZE = int(os.getenv("MA_MAVOL_BATCH_SIZE") or "500")
DEFAULT_UPSERT_BATCH_SIZE = int(os.getenv("MA_MAVOL_UPSERT_BATCH_SIZE") or "1000")
DEFAULT_COMPUTE_WORKERS = int(os.getenv("MA_MAVOL_COMPUTE_WORKERS") or "0")


def _normalize_date_str(date_val: Any) -> str:
    if isinstance(date_val, datetime.datetime):
        return date_val.strftime("%Y-%m-%d")
    if isinstance(date_val, datetime.date):
        return date_val.isoformat()
    s = str(date_val).strip()
    if len(s) >= 10 and s[4] == "-":
        return s[:10]
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s


def _safe_float(val: Any) -> Optional[float]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        f = float(val)
        return None if pd.isna(f) else f
    except (TypeError, ValueError):
        return None


def _resolve_stock_codes(
    session: Session,
    target_date: str,
    quotes_table: str,
    stock_codes: Optional[Sequence[str]],
) -> List[str]:
    if stock_codes is not None:
        return [str(c) for c in stock_codes]
    rows = session.execute(
        text(
            f"""
            SELECT DISTINCT code
            FROM {quotes_table}
            WHERE date = :target_date
            ORDER BY code
            """
        ),
        {"target_date": target_date},
    ).fetchall()
    return [str(r[0]) for r in rows if r and r[0]]


def _preload_quote_series(
    session: Session,
    stock_codes: Sequence[str],
    target_date: str,
    quotes_table: str,
    *,
    lookback_calendar_days: int = DEFAULT_LOOKBACK_CALENDAR_DAYS,
    preload_batch_size: int = DEFAULT_PRELOAD_BATCH_SIZE,
    log: logging.Logger = logger,
) -> Dict[str, Dict[str, List[Any]]]:
    """批量预加载 close/volume 序列（按 code 分组、日期升序）。"""
    if not stock_codes:
        return {}

    min_date = (
        datetime.datetime.strptime(target_date, "%Y-%m-%d")
        - datetime.timedelta(days=lookback_calendar_days)
    ).strftime("%Y-%m-%d")

    out: Dict[str, Dict[str, List[Any]]] = {}
    codes = list(stock_codes)
    t0 = time.time()
    stmt = text(
        f"""
        SELECT code, date, close, volume
        FROM {quotes_table}
        WHERE code IN :codes
          AND date >= :min_date
          AND date <= :target_date
        ORDER BY code ASC, date ASC
        """
    ).bindparams(bindparam("codes", expanding=True))

    for i in range(0, len(codes), preload_batch_size):
        batch = codes[i : i + preload_batch_size]
        rows = session.execute(
            stmt,
            {"codes": batch, "min_date": min_date, "target_date": target_date},
        ).fetchall()
        for code, dt, close, volume in rows:
            key = str(code)
            bucket = out.setdefault(key, {"dates": [], "closes": [], "volumes": []})
            d = _normalize_date_str(dt)
            if bucket["dates"] and bucket["dates"][-1] == d:
                if close is not None:
                    bucket["closes"][-1] = float(close)
                if volume is not None:
                    bucket["volumes"][-1] = float(volume)
                continue
            bucket["dates"].append(d)
            bucket["closes"].append(float(close) if close is not None else None)
            bucket["volumes"].append(float(volume) if volume is not None else None)

    log.info(
        "MA/MAVOL 预加载完成 table=%s codes=%s rows=%s elapsed=%.2fs window=%s~%s",
        quotes_table,
        len(codes),
        sum(len(v["dates"]) for v in out.values()),
        time.time() - t0,
        min_date,
        target_date,
    )
    return out


def _compute_single_stock(
    code: str,
    series: Dict[str, List[Any]],
    target_date: str,
    market_type: str,
    compute_ma: bool,
    compute_mavol: bool,
    created_at: datetime.datetime,
) -> Tuple[Optional[dict], Optional[dict], str]:
    """返回 (ma_row, mavol_row, status)；status: ok|skip|fail。"""
    try:
        dates = series.get("dates") or []
        if target_date not in dates:
            return None, None, "skip"
        idx = dates.index(target_date)
        closes = [c for c in (series.get("closes") or [])[: idx + 1] if c is not None]
        volumes = [v for v in (series.get("volumes") or [])[: idx + 1] if v is not None]

        ma_row = None
        mavol_row = None

        if compute_ma:
            if len(closes) < 5:
                return None, None, "skip"
            ma_vals = MACalculator.calculate_ma_for_list(closes, periods=MA_PERIODS)
            ma_row = {
                "code": code,
                "date": target_date,
                "market_type": market_type,
                "ma5": ma_vals.get("ma5"),
                "ma10": ma_vals.get("ma10"),
                "ma20": ma_vals.get("ma20"),
                "ma30": ma_vals.get("ma30"),
                "ma60": ma_vals.get("ma60"),
                "ma120": ma_vals.get("ma120"),
                "ma200": ma_vals.get("ma200"),
                "created_at": created_at,
            }

        if compute_mavol:
            if len(volumes) < 5:
                if compute_ma and ma_row:
                    return ma_row, None, "ok"
                return None, None, "skip"
            mavol_vals = MAVOLCalculator.calculate_mavol_for_list(volumes, periods=MAVOL_PERIODS)
            mavol_row = {
                "code": code,
                "date": target_date,
                "market_type": market_type,
                "m5": mavol_vals.get("mavol5"),
                "m10": mavol_vals.get("mavol10"),
                "m20": mavol_vals.get("mavol20"),
                "m30": mavol_vals.get("mavol30"),
                "m60": mavol_vals.get("mavol60"),
                "m120": mavol_vals.get("mavol120"),
                "m200": mavol_vals.get("mavol200"),
                "created_at": created_at,
            }

        if not ma_row and not mavol_row:
            return None, None, "skip"
        return ma_row, mavol_row, "ok"
    except Exception:
        return None, None, "fail"


def _compute_worker_payload(payload: Tuple[str, Dict[str, List[Any]], str, str, bool, bool, datetime.datetime]):
    code, series, target_date, market_type, compute_ma, compute_mavol, created_at = payload
    ma_row, mavol_row, status = _compute_single_stock(
        code, series, target_date, market_type, compute_ma, compute_mavol, created_at
    )
    return code, ma_row, mavol_row, status


def _compute_all_rows(
    preloaded: Dict[str, Dict[str, List[Any]]],
    target_date: str,
    market_type: str,
    *,
    compute_ma: bool,
    compute_mavol: bool,
    workers: int = DEFAULT_COMPUTE_WORKERS,
    log: logging.Logger = logger,
) -> Tuple[List[dict], List[dict], dict]:
    created_at = datetime.datetime.now()
    ma_rows: List[dict] = []
    mavol_rows: List[dict] = []
    stats = {"success": 0, "skipped": 0, "failed": 0, "details": []}

    items = list(preloaded.items())
    if not items:
        return ma_rows, mavol_rows, stats

    worker_count = workers if workers > 0 else min(8, max(1, (os.cpu_count() or 4)))
    use_pool = worker_count > 1 and len(items) >= 200

    if use_pool:
        payloads = [
            (code, series, target_date, market_type, compute_ma, compute_mavol, created_at)
            for code, series in items
        ]
        t0 = time.time()
        with ProcessPoolExecutor(max_workers=worker_count) as pool:
            futures = [pool.submit(_compute_worker_payload, p) for p in payloads]
            for fut in as_completed(futures):
                code, ma_row, mavol_row, status = fut.result()
                if status == "ok":
                    stats["success"] += 1
                    if ma_row:
                        ma_rows.append(ma_row)
                    if mavol_row:
                        mavol_rows.append(mavol_row)
                elif status == "skip":
                    stats["skipped"] += 1
                else:
                    stats["failed"] += 1
                    stats["details"].append(f"{code}: compute failed")
        log.info(
            "MA/MAVOL 并行计算完成 workers=%s codes=%s elapsed=%.2fs",
            worker_count,
            len(items),
            time.time() - t0,
        )
        return ma_rows, mavol_rows, stats

    for code, series in items:
        ma_row, mavol_row, status = _compute_single_stock(
            code, series, target_date, market_type, compute_ma, compute_mavol, created_at
        )
        if status == "ok":
            stats["success"] += 1
            if ma_row:
                ma_rows.append(ma_row)
            if mavol_row:
                mavol_rows.append(mavol_row)
        elif status == "skip":
            stats["skipped"] += 1
        else:
            stats["failed"] += 1
            stats["details"].append(f"{code}: compute failed")
    return ma_rows, mavol_rows, stats


def _bulk_upsert_ma(session: Session, rows: List[dict], batch_size: int = DEFAULT_UPSERT_BATCH_SIZE) -> None:
    if not rows:
        return
    sql = text(
        """
        INSERT INTO ma_indicators
        (code, date, market_type, ma5, ma10, ma20, ma30, ma60, ma120, ma200, created_at)
        VALUES (:code, :date, :market_type, :ma5, :ma10, :ma20, :ma30, :ma60, :ma120, :ma200, :created_at)
        ON CONFLICT (code, date, market_type) DO UPDATE SET
            ma5 = EXCLUDED.ma5,
            ma10 = EXCLUDED.ma10,
            ma20 = EXCLUDED.ma20,
            ma30 = EXCLUDED.ma30,
            ma60 = EXCLUDED.ma60,
            ma120 = EXCLUDED.ma120,
            ma200 = EXCLUDED.ma200,
            created_at = EXCLUDED.created_at
        """
    )
    for i in range(0, len(rows), batch_size):
        session.execute(sql, rows[i : i + batch_size])


def _bulk_upsert_mavol(session: Session, rows: List[dict], batch_size: int = DEFAULT_UPSERT_BATCH_SIZE) -> None:
    if not rows:
        return
    sql = text(
        """
        INSERT INTO mavol_indicators
        (code, date, market_type, mavol5, mavol10, mavol20, mavol30, mavol60, mavol120, mavol200, created_at)
        VALUES (:code, :date, :market_type, :m5, :m10, :m20, :m30, :m60, :m120, :m200, :created_at)
        ON CONFLICT (code, date, market_type) DO UPDATE SET
            mavol5 = EXCLUDED.mavol5,
            mavol10 = EXCLUDED.mavol10,
            mavol20 = EXCLUDED.mavol20,
            mavol30 = EXCLUDED.mavol30,
            mavol60 = EXCLUDED.mavol60,
            mavol120 = EXCLUDED.mavol120,
            mavol200 = EXCLUDED.mavol200,
            created_at = EXCLUDED.created_at
        """
    )
    for i in range(0, len(rows), batch_size):
        session.execute(sql, rows[i : i + batch_size])


def calculate_and_save_ma_mavol_for_date(
    session: Session,
    target_date: str,
    *,
    quotes_table: str = "historical_quotes",
    market_type: str = "CN",
    stock_codes: Optional[Sequence[str]] = None,
    compute_ma: bool = True,
    compute_mavol: bool = True,
    log: Optional[logging.Logger] = None,
) -> dict:
    """
    批量计算并写入指定日期的 MA / MAVOL。
    一次预加载 close+volume，内存计算后批量 upsert。
    """
    log = log or logger
    codes = _resolve_stock_codes(session, target_date, quotes_table, stock_codes)
    total = len(codes)
    empty = {
        "total": total,
        "success": 0,
        "skipped": 0,
        "failed": 0,
        "ma_written": 0,
        "mavol_written": 0,
        "details": [],
    }
    if not codes:
        log.warning("日期 %s 无股票可计算 MA/MAVOL", target_date)
        return empty

    if not compute_ma and not compute_mavol:
        return empty

    try:
        preloaded = _preload_quote_series(session, codes, target_date, quotes_table, log=log)
        ma_rows, mavol_rows, stats = _compute_all_rows(
            preloaded,
            target_date,
            market_type,
            compute_ma=compute_ma,
            compute_mavol=compute_mavol,
            log=log,
        )
        t0 = time.time()
        if compute_ma:
            _bulk_upsert_ma(session, ma_rows)
        if compute_mavol:
            _bulk_upsert_mavol(session, mavol_rows)
        session.commit()
        log.info(
            "MA/MAVOL 批量写入完成 ma=%s mavol=%s elapsed=%.2fs",
            len(ma_rows),
            len(mavol_rows),
            time.time() - t0,
        )
        return {
            "total": total,
            "success": stats["success"],
            "skipped": stats["skipped"],
            "failed": stats["failed"],
            "ma_written": len(ma_rows),
            "mavol_written": len(mavol_rows),
            "details": stats["details"],
        }
    except Exception as e:
        log.exception("批量 MA/MAVOL 计算失败: %s", e)
        session.rollback()
        return {
            "total": total,
            "success": 0,
            "skipped": 0,
            "failed": total,
            "ma_written": 0,
            "mavol_written": 0,
            "details": [str(e)],
        }
