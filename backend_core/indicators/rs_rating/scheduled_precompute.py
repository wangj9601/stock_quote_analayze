"""RS Rating 全市场日终预计算（供采集流程节点调用）。"""

from __future__ import annotations

import datetime as dt
import logging
import time
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from .calculator import compute_rs_raw, rank_cross_section
from .config import LOOKBACK_CALENDAR_DAYS, MARKET_TYPE, RS_WINDOWS, coverage_threshold
from .storage import upsert_rs_ratings
from .universe import list_candidate_codes

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


def resolve_trade_date(session: Session, trade_date: Optional[str] = None) -> str:
    if trade_date:
        return _normalize_date_str(trade_date)
    row = session.execute(
        text("SELECT MAX(date) FROM historical_quotes")
    ).fetchone()
    if not row or not row[0]:
        raise ValueError("historical_quotes 无数据，无法解析交易日")
    return _normalize_date_str(row[0])


def _preload_closes(
    session: Session,
    codes: Sequence[str],
    trade_date: str,
    *,
    lookback_calendar_days: int = LOOKBACK_CALENDAR_DAYS,
) -> Dict[str, List[float]]:
    """批量预加载升序 close 序列（截至 trade_date）。"""
    if not codes:
        return {}
    min_date = (
        dt.datetime.strptime(trade_date[:10], "%Y-%m-%d")
        - dt.timedelta(days=lookback_calendar_days)
    ).strftime("%Y-%m-%d")
    out: Dict[str, List[float]] = {}
    for i in range(0, len(codes), PRELOAD_BATCH):
        batch = list(codes[i : i + PRELOAD_BATCH])
        stmt = text(
            """
            SELECT code, date, close
            FROM historical_quotes
            WHERE code IN :codes
              AND date >= :min_date
              AND date <= :trade_date
              AND close IS NOT NULL
              AND close > 0
            ORDER BY code, date
            """
        ).bindparams(bindparam("codes", expanding=True))
        rows = session.execute(
            stmt,
            {"codes": batch, "min_date": min_date, "trade_date": trade_date[:10]},
        ).fetchall()
        for code, _date, close in rows:
            c = str(code).strip()
            try:
                px = float(close)
            except (TypeError, ValueError):
                continue
            if px <= 0:
                continue
            out.setdefault(c, []).append(px)
    return out


def run_rs_rating_precompute(
    *,
    trade_date: Optional[str] = None,
    codes: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    from backend_api.database import SessionLocal

    db = SessionLocal()
    t0 = time.time()
    try:
        date_s = resolve_trade_date(db, trade_date)
        candidates = list_candidate_codes(db, date_s, codes=codes)
        pool_size = len(candidates)
        logger.info(
            "RS Rating precompute start date=%s candidates=%s",
            date_s,
            pool_size,
        )
        if pool_size == 0:
            return {
                "ok": True,
                "trade_date": date_s,
                "candidate_count": 0,
                "universe_size": 0,
                "coverage_ratio": 0.0,
                "publish_ratings": False,
                "saved": 0,
                "elapsed_sec": round(time.time() - t0, 2),
            }

        closes_map = _preload_closes(db, candidates, date_s)
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
        coverage = (universe_size / pool_size) if pool_size else 0.0
        publish = coverage >= coverage_threshold()
        ranked = rank_cross_section(raw_rows, publish_ratings=publish)
        for r in ranked:
            r["universe_size"] = universe_size
            r["coverage_ratio"] = coverage

        saved = upsert_rs_ratings(db, ranked, trade_date=date_s, market_type=MARKET_TYPE)
        summary = {
            "ok": True,
            "trade_date": date_s,
            "candidate_count": pool_size,
            "universe_size": universe_size,
            "coverage_ratio": round(coverage, 4),
            "publish_ratings": publish,
            "saved": saved,
            "elapsed_sec": round(time.time() - t0, 2),
        }
        if not publish:
            logger.warning(
                "RS Rating coverage %.2f%% < %.0f%% — ratings not published",
                coverage * 100,
                coverage_threshold() * 100,
            )
        logger.info("RS Rating precompute done: %s", summary)
        return summary
    except Exception as e:
        db.rollback()
        logger.exception("RS Rating precompute failed: %s", e)
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


def scheduled_rs_rating_cn():
    try:
        return run_rs_rating_precompute()
    except Exception as e:
        logger.exception("scheduled_rs_rating_cn failed: %s", e)
        return {"ok": False, "error": str(e)}
