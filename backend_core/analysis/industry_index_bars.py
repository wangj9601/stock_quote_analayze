# -*- coding: utf-8 -*-
"""行业板块指数日 K：只读 industry_board_historical_quotes。

不读 index_historical_quotes，不读个股 historical_quotes。
行业实时表没有开高低，本模块不把实时价合成当日 K。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_KDE_LOOKBACK_MAX = 750


def industry_bar_lookback() -> int:
    try:
        from backend_api.stock.stock_analysis import KeyLevels

        return max(int(KeyLevels.KDE_LOOKBACK_MAX), 220)
    except Exception:
        return _KDE_LOOKBACK_MAX


def resolve_industry_board_identity(db: Session, board_code: str) -> Dict[str, Any]:
    code = str(board_code or "").strip()
    if not code:
        return {"ok": False, "message": "请提供行业板块代码", "http_status": 400}

    name = ""
    has_basic = False
    try:
        row = db.execute(
            text(
                """
                SELECT board_name
                FROM industry_board_basic_info
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
        logger.debug("industry basic name fail %s", code, exc_info=True)
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
                FROM industry_board_historical_quotes
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
        logger.debug("industry hist identity fail %s", code, exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass

    has_rt = False
    try:
        row = db.execute(
            text(
                """
                SELECT board_name
                FROM industry_board_realtime_quotes
                WHERE board_code = :c
                LIMIT 1
                """
            ),
            {"c": code},
        ).fetchone()
        if row:
            has_rt = True
            if not name and row[0]:
                name = str(row[0])
    except Exception:
        logger.debug("industry rt identity fail %s", code, exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass

    if not has_hist and not has_rt and not has_basic:
        return {
            "ok": False,
            "message": f"未找到行业板块 {code}",
            "http_status": 404,
            "code": code,
            "name": name or code,
        }
    return {
        "ok": True,
        "code": code,
        "name": name or code,
        "has_hist": has_hist,
        "has_rt": has_rt,
        "http_status": 200,
    }


def load_industry_board_ohlc_asc(
    db: Session,
    board_code: str,
    *,
    lookback: Optional[int] = None,
    asof: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """正序行业指数日 K。"""
    code = str(board_code or "").strip()
    if not code:
        return []
    lim = max(20, int(lookback or industry_bar_lookback()))
    params: Dict[str, Any] = {"bc": code, "lim": lim}
    date_clause = ""
    if asof:
        date_clause = "AND trade_date <= CAST(:d AS date)"
        params["d"] = str(asof).strip()[:10]
    sql = text(
        f"""
        SELECT trade_date, open, high, low, close, volume, amount
        FROM industry_board_historical_quotes
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


def fetch_industry_board_realtime(db: Session, board_code: str) -> Optional[Dict[str, Any]]:
    """行业实时快照。没有开高低，调用方不得据此改写日 K。"""
    code = str(board_code or "").strip()
    if not code:
        return None
    try:
        row = db.execute(
            text(
                """
                SELECT board_code, board_name, latest_price, change_amount, change_percent,
                       volume, amount, up_count, down_count, update_time
                FROM industry_board_realtime_quotes
                WHERE board_code = :c
                LIMIT 1
                """
            ),
            {"c": code},
        ).fetchone()
    except Exception:
        logger.debug("fetch industry realtime fail %s", code, exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
        return None
    if not row:
        return None
    update_time = str(row[9] or "")
    trade_date = update_time[:10] if len(update_time) >= 10 else ""
    return {
        "code": str(row[0] or code),
        "name": str(row[1] or ""),
        "current_price": float(row[2]) if row[2] is not None else None,
        "change": float(row[3]) if row[3] is not None else None,
        "change_percent": float(row[4]) if row[4] is not None else None,
        "volume": float(row[5]) if row[5] is not None else None,
        "amount": float(row[6]) if row[6] is not None else None,
        "up_count": int(row[7]) if row[7] is not None else None,
        "down_count": int(row[8]) if row[8] is not None else None,
        "update_time": update_time,
        "trade_date": trade_date,
        "source": "industry_board_realtime_quotes",
    }
