# -*- coding: utf-8 -*-
"""DBLB 日线加载（升序 bars）。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def resolve_effective_trade_date(db: Session, requested: Optional[str] = None) -> str:
    from sqlalchemy import func

    from backend_api.models import HistoricalQuotes

    today_s = datetime.now().strftime("%Y-%m-%d")
    raw = (requested or "").strip()[:10]
    target_s = raw if raw else today_s
    try:
        target = datetime.strptime(target_s, "%Y-%m-%d").date()
    except ValueError:
        target = datetime.now().date()
        target_s = today_s

    row_max = db.query(func.max(HistoricalQuotes.date)).scalar()
    if row_max is None:
        return target_s
    if hasattr(row_max, "strftime"):
        max_s = row_max.strftime("%Y-%m-%d")
        max_d = row_max
    else:
        max_s = str(row_max).strip()[:10]
        try:
            max_d = datetime.strptime(max_s, "%Y-%m-%d").date()
        except ValueError:
            return target_s
    if target > max_d:
        return max_s
    return target_s


def load_names(db: Session, codes: Sequence[str]) -> Dict[str, str]:
    from backend_api.models import StockBasicInfo

    from .universe import normalize_a_code

    uniq = [normalize_a_code(c) for c in codes if normalize_a_code(c)]
    if not uniq:
        return {}
    rows = (
        db.query(StockBasicInfo.code, StockBasicInfo.name)
        .filter(StockBasicInfo.code.in_(uniq))
        .all()
    )
    return {str(r[0]): str(r[1] or "") for r in rows}


def batch_load_ohlc_asc(
    db: Session,
    codes: Sequence[str],
    *,
    lookback: int = 160,
    asof: Optional[str] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """批量取日线 OHLC，按 code 升序截断末 lookback 根。"""
    from .universe import normalize_a_code

    uniq = sorted({normalize_a_code(c) for c in codes if normalize_a_code(c)})
    if not uniq:
        return {}
    lb = max(30, int(lookback))
    fetch_n = max(lb * 2, lb + 20)
    asof_s = (asof or "").strip()[:10] or None
    try:
        sql = text(
            """
            SELECT code, trade_date, high, low, close, volume, name
            FROM (
                SELECT code,
                       date AS trade_date,
                       high, low, close, volume, name,
                       ROW_NUMBER() OVER (PARTITION BY code ORDER BY date DESC) AS rn
                FROM historical_quotes
                WHERE code IN :codes
                  AND high IS NOT NULL AND low IS NOT NULL AND close IS NOT NULL
                  AND (:asof IS NULL OR date <= :asof)
            ) t
            WHERE rn <= :lim
            ORDER BY code, trade_date
            """
        ).bindparams(bindparam("codes", expanding=True))
        rows = db.execute(
            sql, {"codes": uniq, "lim": fetch_n, "asof": asof_s}
        ).fetchall()
    except Exception as e:
        logger.warning("dblb batch_load_ohlc_asc failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        return {}

    by: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        code = normalize_a_code(r[0])
        d = r[1]
        if hasattr(d, "strftime"):
            ds = d.strftime("%Y-%m-%d")
        else:
            ds = str(d)[:10]
        by.setdefault(code, []).append(
            {
                "date": ds,
                "high": r[2],
                "low": r[3],
                "close": r[4],
                "volume": r[5] if len(r) > 5 else None,
                "name": r[6] if len(r) > 6 else "",
            }
        )
    out: Dict[str, List[Dict[str, Any]]] = {}
    for code, bars in by.items():
        out[code] = bars[-lb:] if len(bars) > lb else bars
    return out
