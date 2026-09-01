"""港股 RS Rating 全市场日终预计算（供采集流程节点调用）。

价格口径：前复权（库内 stock_adj_factor 港股源现算，不打外网）。
结果写入独立表 ``rs_ratings_hk``。
"""

from __future__ import annotations

import datetime as dt
import logging
import time
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from .calculator import compute_rs_raw, rank_cross_section
from .config import (
    LOOKBACK_CALENDAR_DAYS_HK,
    MARKET_TYPE_HK,
    PRICE_ADJUST,
    RS_WINDOWS,
    coverage_allows_publish,
    coverage_for_publish,
    coverage_threshold,
)
from .qfq_closes import build_qfq_close_map_hk
from .storage_hk import upsert_rs_ratings_hk
from .universe_hk import list_candidate_codes_hk

logger = logging.getLogger(__name__)

PRELOAD_BATCH = 500


def _normalize_date_str(date_val: Any) -> str:
    if isinstance(date_val, dt.datetime):
        return date_val.strftime("%Y-%m-%d")
    if isinstance(date_val, dt.date):
        return date_val.isoformat()
    s = str(date_val).strip()
    if len(s) >= 10 and s[4] == "-":
        return s[:10]
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s


def resolve_trade_date_hk(session: Session, trade_date: Optional[str] = None) -> str:
    if trade_date:
        return _normalize_date_str(trade_date)
    row = session.execute(
        text("SELECT MAX(date) FROM historical_quotes_hk")
    ).fetchone()
    if not row or not row[0]:
        raise ValueError("historical_quotes_hk 无数据，无法解析交易日")
    return _normalize_date_str(row[0])


def run_rs_rating_precompute_hk(
    *,
    trade_date: Optional[str] = None,
    codes: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    from backend_api.database import SessionLocal

    db = SessionLocal()
    t0 = time.time()
    try:
        date_s = resolve_trade_date_hk(db, trade_date)
        candidates = list_candidate_codes_hk(db, date_s, codes=codes)
        pool_size = len(candidates)
        logger.info(
            "RS Rating HK precompute start date=%s candidates=%s price_adjust=%s lookback=%s",
            date_s,
            pool_size,
            PRICE_ADJUST,
            LOOKBACK_CALENDAR_DAYS_HK,
        )
        if pool_size == 0:
            return {
                "ok": True,
                "market_type": MARKET_TYPE_HK,
                "trade_date": date_s,
                "price_adjust": PRICE_ADJUST,
                "candidate_count": 0,
                "universe_size": 0,
                "coverage_ratio": 0.0,
                "publish_ratings": False,
                "saved": 0,
                "elapsed_sec": round(time.time() - t0, 2),
            }

        closes_map, qfq_stats = build_qfq_close_map_hk(
            db,
            candidates,
            date_s,
            lookback_calendar_days=LOOKBACK_CALENDAR_DAYS_HK,
            batch_size=PRELOAD_BATCH,
        )
        need_bars = max(RS_WINDOWS) + 1
        raw_rows: List[Dict[str, Any]] = []
        for code in candidates:
            series = closes_map.get(code) or []
            if len(series) < need_bars:
                continue
            computed = compute_rs_raw(series)
            if not computed:
                continue
            raw_rows.append({"code": code, **computed})

        universe_size = len(raw_rows)
        # 港股覆盖率相对「已能前复权」的股票；无因子者不参与分母
        qfq_ready = int(qfq_stats.get("qfq_codes") or len(closes_map) or 0)
        coverage_base = qfq_ready if qfq_ready > 0 else pool_size
        coverage = (universe_size / coverage_base) if coverage_base else 0.0
        # 实际 coverage 入库；发布判定：>0.88 时按 0.90 计
        coverage_publish = coverage_for_publish(coverage, MARKET_TYPE_HK)
        thr = coverage_threshold(MARKET_TYPE_HK)
        publish = coverage_allows_publish(coverage, MARKET_TYPE_HK)
        ranked = rank_cross_section(raw_rows, publish_ratings=publish)
        for r in ranked:
            r["universe_size"] = universe_size
            r["coverage_ratio"] = coverage

        saved = upsert_rs_ratings_hk(db, ranked, trade_date=date_s)
        summary = {
            "ok": True,
            "market_type": MARKET_TYPE_HK,
            "trade_date": date_s,
            "price_adjust": PRICE_ADJUST,
            "candidate_count": pool_size,
            "qfq_ready_count": qfq_ready,
            "universe_size": universe_size,
            "coverage_ratio": round(coverage, 4),
            "coverage_for_publish": round(coverage_publish, 4),
            "coverage_base": "qfq_ready",
            "publish_ratings": publish,
            "saved": saved,
            "qfq_stats": qfq_stats,
            "lookback_calendar_days": LOOKBACK_CALENDAR_DAYS_HK,
            "elapsed_sec": round(time.time() - t0, 2),
        }
        if not publish:
            logger.warning(
                "RS Rating HK coverage %.2f%% (publish_as %.2f%%) < %.0f%% "
                "(base=qfq_ready=%s) — ratings not published",
                coverage * 100,
                coverage_publish * 100,
                thr * 100,
                qfq_ready,
            )
        logger.info("RS Rating HK precompute done: %s", summary)
        return summary
    except Exception as e:
        db.rollback()
        logger.exception("RS Rating HK precompute failed: %s", e)
        return {"ok": False, "market_type": MARKET_TYPE_HK, "error": str(e)}
    finally:
        db.close()


def scheduled_rs_rating_hk():
    try:
        return run_rs_rating_precompute_hk()
    except Exception as e:
        logger.exception("scheduled_rs_rating_hk failed: %s", e)
        return {"ok": False, "market_type": MARKET_TYPE_HK, "error": str(e)}
