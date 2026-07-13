# -*- coding: utf-8 -*-
"""URT 数据加载：候选池 + historical_quotes（日期倒序，最新在前）。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, not_, or_, text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

URT_BOARD_PREFIX_GROUPS: Dict[str, Tuple[str, ...]] = {
    "CYB": ("300",),
    "KCB": ("688",),
    "SH_MAIN": ("600", "601", "602", "603", "605"),
    "SZ_MAIN": ("000", "001"),
    "SZ_SME": ("002",),
    "BJ": ("43", "83", "87", "88", "92"),
}


def normalize_urt_board_keys(boards: Optional[List[str]]) -> List[str]:
    if not boards:
        return []
    seen: set[str] = set()
    out: List[str] = []
    for b in boards:
        if b is None:
            continue
        for piece in str(b).split(","):
            k = piece.strip().upper()
            if not k or k not in URT_BOARD_PREFIX_GROUPS or k in seen:
                continue
            seen.add(k)
            out.append(k)
    return out


class URTDataLoader:
    def __init__(self, db: Session):
        self.db = db

    def list_a_share_candidates(
        self,
        *,
        limit: Optional[int] = None,
        stock_codes: Optional[List[str]] = None,
        boards: Optional[List[str]] = None,
    ) -> List[Tuple[str, str]]:
        from backend_api.models import StockBasicInfo

        def _normalize(c: str) -> Optional[str]:
            s = str(c).strip()
            if len(s) == 5 and s.isdigit():
                s = s.zfill(6)
            if len(s) == 6 and s.isdigit():
                return s
            return None

        qry = (
            self.db.query(StockBasicInfo.code, StockBasicInfo.name)
            .filter(func.length(StockBasicInfo.code) == 6)
            .filter(not_(StockBasicInfo.name.like("%ST%")))
            .filter(or_(StockBasicInfo.collect_enabled.is_(True), StockBasicInfo.collect_enabled.is_(None)))
            .order_by(StockBasicInfo.code)
        )
        board_keys = normalize_urt_board_keys(boards)
        if board_keys:
            like_clauses = [
                StockBasicInfo.code.like(f"{p}%")
                for key in board_keys
                for p in URT_BOARD_PREFIX_GROUPS[key]
            ]
            qry = qry.filter(or_(*like_clauses))
        if stock_codes:
            cleaned = [_normalize(c) for c in stock_codes]
            cleaned = [c for c in cleaned if c]
            if not cleaned:
                return []
            qry = qry.filter(StockBasicInfo.code.in_(cleaned))
        rows = qry.all()
        out = [(str(r[0]), str(r[1] or "")) for r in rows]
        if limit is not None and limit > 0:
            out = out[: int(limit)]
        return out

    def fetch_historical_desc(
        self,
        code: str,
        *,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT code, name, date, open, close, high, low,
                       change_percent, volume, amount, turnover_rate
                FROM historical_quotes
                WHERE code = :code
                  AND date >= :start_date
                  AND date <= :end_date
                ORDER BY date DESC
                """
            ),
            {"code": str(code), "start_date": start_date, "end_date": end_date},
        ).fetchall()
        out: List[Dict[str, Any]] = []
        for row in rows:
            date_val = row[2]
            if hasattr(date_val, "strftime"):
                date_str = date_val.strftime("%Y-%m-%d")
            else:
                date_str = str(date_val)[:10]
            out.append(
                {
                    "code": row[0],
                    "name": row[1],
                    "date": date_str,
                    "open": float(row[3]) if row[3] is not None else 0.0,
                    "close": float(row[4]) if row[4] is not None else 0.0,
                    "high": float(row[5]) if row[5] is not None else 0.0,
                    "low": float(row[6]) if row[6] is not None else 0.0,
                    "change_percent": float(row[7]) if row[7] is not None else 0.0,
                    "volume": float(row[8]) if row[8] is not None else 0.0,
                    "amount": float(row[9]) if row[9] is not None else 0.0,
                    "turnover_rate": float(row[10]) if row[10] is not None else None,
                }
            )
        return out

    @staticmethod
    def resolve_effective_history_end_date(db: Session, requested: Optional[str]) -> str:
        from backend_api.models import HistoricalQuotes

        today = datetime.now().date()
        today_s = today.strftime("%Y-%m-%d")
        raw = (requested or "").strip()[:10]
        if not raw:
            target = today
            target_s = today_s
        else:
            try:
                target = datetime.strptime(raw, "%Y-%m-%d").date()
                target_s = raw
            except ValueError:
                target = today
                target_s = today_s

        row_max = db.query(func.max(HistoricalQuotes.date)).scalar()
        if row_max is None:
            return target_s
        if hasattr(row_max, "strftime"):
            max_d = row_max
            max_s = max_d.strftime("%Y-%m-%d")
        else:
            max_s = str(row_max).strip()[:10]
            try:
                max_d = datetime.strptime(max_s, "%Y-%m-%d").date()
            except ValueError:
                return target_s

        if target > max_d:
            return max_s

        exists = (
            db.query(HistoricalQuotes.code)
            .filter(HistoricalQuotes.date == target_s)
            .limit(1)
            .first()
        )
        if exists is not None:
            return target_s
        return max_s

    @staticmethod
    def default_date_window(calendar_days: int, end_anchor: Optional[str] = None) -> Tuple[str, str]:
        if end_anchor:
            try:
                end = datetime.strptime(str(end_anchor)[:10], "%Y-%m-%d").date()
            except ValueError:
                end = datetime.now().date()
        else:
            end = datetime.now().date()
        start = end - timedelta(days=max(30, int(calendar_days)))
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
