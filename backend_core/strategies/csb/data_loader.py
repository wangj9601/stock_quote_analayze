# -*- coding: utf-8 -*-
"""CSB 数据加载：A 股日 K（含 turnover）。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, not_, or_, text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _norm_code(code: str) -> str:
    s = str(code or "").strip()
    if s.isdigit() and len(s) <= 6:
        return s.zfill(6)
    return s


class CSBDataLoader:
    def __init__(self, db_session=None):
        self._db = db_session

    def _session(self):
        if self._db is not None:
            return self._db
        from backend_api.database import SessionLocal

        return SessionLocal()

    def list_a_share_candidates(
        self,
        *,
        limit: Optional[int] = None,
        stock_codes: Optional[List[str]] = None,
    ) -> List[Tuple[str, str]]:
        from backend_api.models import StockBasicInfo

        db = self._session()
        own = self._db is None
        try:
            qry = (
                db.query(StockBasicInfo.code, StockBasicInfo.name)
                .filter(func.length(StockBasicInfo.code) == 6)
                .filter(not_(StockBasicInfo.name.like("%ST%")))
                .filter(or_(StockBasicInfo.collect_enabled.is_(True), StockBasicInfo.collect_enabled.is_(None)))
                .order_by(StockBasicInfo.code)
            )
            if stock_codes is not None:
                cleaned = [_norm_code(c) for c in stock_codes if _norm_code(c)]
                if not cleaned:
                    return []
                qry = qry.filter(StockBasicInfo.code.in_(cleaned))
            rows = qry.all()
            out = [(str(r[0]), str(r[1] or "")) for r in rows]
            if limit is not None and limit > 0:
                out = out[: int(limit)]
            return out
        finally:
            if own:
                db.close()

    def load_bars(
        self,
        code: str,
        *,
        end_date: Optional[str] = None,
        limit: int = 280,
    ) -> List[Dict[str, Any]]:
        """返回时间正序 bars。"""
        db = self._session()
        own = self._db is None
        try:
            code_n = _norm_code(code)
            params: Dict[str, Any] = {"code": code_n, "lim": int(limit)}
            if end_date:
                sql = text(
                    """
                    SELECT date, open, high, low, close, volume, amount, turnover_rate
                    FROM historical_quotes
                    WHERE code = :code AND date <= :d
                    ORDER BY date DESC
                    LIMIT :lim
                    """
                )
                params["d"] = end_date
            else:
                sql = text(
                    """
                    SELECT date, open, high, low, close, volume, amount, turnover_rate
                    FROM historical_quotes
                    WHERE code = :code
                    ORDER BY date DESC
                    LIMIT :lim
                    """
                )
            rows = db.execute(sql, params).fetchall()
            bars = []
            for r in reversed(rows):
                d = r[0]
                ds = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
                vol = float(r[5] or 0)
                if vol <= 0:
                    continue
                bars.append(
                    {
                        "date": ds,
                        "open": float(r[1] or 0),
                        "high": float(r[2] or 0),
                        "low": float(r[3] or 0),
                        "close": float(r[4] or 0),
                        "volume": vol,
                        "amount": float(r[6] or 0),
                        "turnover_rate": float(r[7]) if r[7] is not None else None,
                    }
                )
            return bars
        except Exception as e:
            logger.warning("CSB load_bars %s failed: %s", code, e)
            return []
        finally:
            if own:
                db.close()

    def resolve_effective_trade_date(self, requested: Optional[str] = None) -> str:
        db = self._session()
        own = self._db is None
        today_s = datetime.now().strftime("%Y-%m-%d")
        try:
            from backend_api.models import HistoricalQuotes

            raw = (requested or "").strip()[:10]
            target_s: Optional[str] = None
            if raw:
                try:
                    datetime.strptime(raw, "%Y-%m-%d")
                    target_s = raw
                except ValueError:
                    target_s = None

            latest = db.query(func.max(HistoricalQuotes.date)).scalar()
            if latest is None:
                return target_s or today_s
            max_s = latest.strftime("%Y-%m-%d") if hasattr(latest, "strftime") else str(latest)[:10]
            if not target_s:
                return max_s
            asof = (
                db.query(func.max(HistoricalQuotes.date))
                .filter(HistoricalQuotes.date <= target_s)
                .scalar()
            )
            if asof is None:
                return max_s
            return asof.strftime("%Y-%m-%d") if hasattr(asof, "strftime") else str(asof)[:10]
        except Exception as e:
            logger.warning("CSB resolve_effective_trade_date failed: %s", e)
            return (requested or "").strip()[:10] or today_s
        finally:
            if own:
                db.close()

    @staticmethod
    def truncate_bars_asof(bars: List[Dict[str, Any]], asof: Optional[str]) -> List[Dict[str, Any]]:
        if not bars or not asof:
            return list(bars or [])
        d = str(asof)[:10]
        return [b for b in bars if str(b.get("date") or "")[:10] <= d]

    @staticmethod
    def resolve_effective_history_end_date(db: Session, requested: Optional[str] = None) -> str:
        loader = CSBDataLoader(db)
        return loader.resolve_effective_trade_date(requested)
