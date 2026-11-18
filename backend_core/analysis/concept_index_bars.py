# -*- coding: utf-8 -*-
"""概念板块指数日 K：只读 concept_board_historical_quotes。

不读行业指数表、大盘指数表，也不读个股 historical_quotes。
概念板块没有实时指数行情表，本模块不把现价合成当日 K。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_KDE_LOOKBACK_MAX = 750


def concept_bar_lookback() -> int:
    try:
        from backend_api.stock.stock_analysis import KeyLevels

        return max(int(KeyLevels.KDE_LOOKBACK_MAX), 220)
    except Exception:
        return _KDE_LOOKBACK_MAX


def resolve_concept_board_identity(db: Session, board_code: str) -> Dict[str, Any]:
    code = str(board_code or "").strip()
    if not code:
        return {"ok": False, "message": "请提供概念板块代码", "http_status": 400}

    name = ""
    has_basic = False
    try:
        row = db.execute(
            text(
                """
                SELECT board_name
                FROM concept_board_basic_info
                WHERE board_code = :c
                LIMIT 1
                """
            ),
            {"c": code},
        ).fetchone()
        if row and row[0]:
            name = str(row[0])
            has_basic = True
    except Exception:
        logger.debug("concept basic name fail %s", code, exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass

    has_hist = False
    try:
        row = db.execute(
            text(
                """
                SELECT board_name
                FROM concept_board_historical_quotes
                WHERE board_code = :c
                ORDER BY trade_date DESC
                LIMIT 1
                """
            ),
            {"c": code},
        ).fetchone()
        if row:
            has_hist = True
            if not name and row[0]:
                name = str(row[0])
    except Exception:
        logger.debug("concept hist identity fail %s", code, exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass

    if not has_hist and not has_basic:
        return {
            "ok": False,
            "message": f"未找到概念板块 {code}",
            "http_status": 404,
            "code": code,
            "name": name or code,
        }
    return {
        "ok": True,
        "code": code,
        "name": name or code,
        "has_hist": has_hist,
        "http_status": 200,
    }


def load_concept_board_ohlc_asc(
    db: Session,
    board_code: str,
    *,
    lookback: Optional[int] = None,
    asof: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """正序概念指数日 K。"""
    code = str(board_code or "").strip()
    if not code:
        return []
    lim = max(20, int(lookback or concept_bar_lookback()))
    params: Dict[str, Any] = {"bc": code, "lim": lim}
    date_clause = ""
    if asof:
        date_clause = "AND trade_date <= CAST(:d AS date)"
        params["d"] = str(asof).strip()[:10]
    sql = text(
        f"""
        SELECT trade_date, open, high, low, close, volume, amount
        FROM concept_board_historical_quotes
        WHERE board_code = :bc
          AND close IS NOT NULL
          {date_clause}
        ORDER BY trade_date DESC
        LIMIT :lim
        """
    )
    rows = db.execute(sql, params).fetchall()
    bars: List[Dict[str, Any]] = []
    for r in reversed(rows):
        d = r[0]
        ds = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
        bars.append(
            {
                "date": ds,
                "open": float(r[1] or 0),
                "high": float(r[2] or 0),
                "low": float(r[3] or 0),
                "close": float(r[4] or 0),
                "volume": float(r[5] or 0),
                "amount": float(r[6] or 0) if r[6] is not None else 0.0,
            }
        )
    return bars
