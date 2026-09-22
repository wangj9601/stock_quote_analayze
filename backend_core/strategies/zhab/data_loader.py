# -*- coding: utf-8 -*-
"""ZHAB 数据加载：近窗涨停池、日线、主线成分。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from sqlalchemy import text
from sqlalchemy.orm import Session


def _norm_code(code: Any) -> str:
    s = str(code or "").strip()
    if s.isdigit() and len(s) < 6:
        return s.zfill(6)
    return s


def load_recent_zt_codes(
    db: Session,
    trade_date: str,
    *,
    lookback_calendar_days: int = 20,
) -> Dict[str, List[str]]:
    """返回 {code: [zt_date asc...]}，窗口内涨停日。"""
    d = str(trade_date)[:10]
    try:
        end = datetime.strptime(d, "%Y-%m-%d").date()
    except ValueError:
        return {}
    start = end - timedelta(days=int(lookback_calendar_days))
    rows = db.execute(
        text(
            """
            SELECT code, trade_date::text
            FROM stock_zt_pool_daily
            WHERE trade_date >= :s AND trade_date <= :e
            ORDER BY code, trade_date
            """
        ),
        {"s": start.isoformat(), "e": d},
    ).fetchall()
    out: Dict[str, List[str]] = {}
    for code, td in rows:
        c = _norm_code(code)
        if not c:
            continue
        out.setdefault(c, []).append(str(td)[:10])
    return out


def load_industry_constituents(db: Session, board_code: str) -> Set[str]:
    bc = str(board_code or "").strip()
    if not bc:
        return set()
    rows = db.execute(
        text(
            """
            SELECT stock_code FROM industry_board_constituents
            WHERE board_code = :bc
            """
        ),
        {"bc": bc},
    ).fetchall()
    return {_norm_code(r[0]) for r in rows if r and r[0]}


def load_concept_constituents(db: Session, board_codes: Sequence[str]) -> Set[str]:
    clean = [str(x).strip() for x in board_codes if str(x or "").strip()]
    if not clean:
        return set()
    rows = db.execute(
        text(
            """
            SELECT stock_code FROM concept_board_constituents
            WHERE board_code = ANY(:codes)
            """
        ),
        {"codes": clean},
    ).fetchall()
    return {_norm_code(r[0]) for r in rows if r and r[0]}


def load_bars_batch(
    db: Session,
    codes: Iterable[str],
    trade_date: str,
    *,
    history_bars: int = 160,
) -> Dict[str, List[Dict[str, Any]]]:
    """批量拉历史日线（升序）。用日历回看约 history_bars*2 天兜底。"""
    clean = [_norm_code(c) for c in codes if _norm_code(c)]
    if not clean:
        return {}
    d = str(trade_date)[:10]
    try:
        end = datetime.strptime(d, "%Y-%m-%d").date()
    except ValueError:
        return {}
    start = end - timedelta(days=max(40, int(history_bars) * 2))
    rows = db.execute(
        text(
            """
            SELECT code, date::text, name, open, high, low, close, volume, change_percent
            FROM historical_quotes
            WHERE date >= :s AND date <= :e AND code = ANY(:codes)
            ORDER BY code, date
            """
        ),
        {"s": start.isoformat(), "e": d, "codes": clean},
    ).fetchall()
    tmp: Dict[str, List[Dict[str, Any]]] = {}
    for code, date_s, name, o, h, lo, c, vol, chg in rows:
        key = _norm_code(code)
        tmp.setdefault(key, []).append(
            {
                "date": str(date_s)[:10],
                "name": name,
                "open": o,
                "high": h,
                "low": lo,
                "close": c,
                "volume": vol,
                "change_percent": chg,
            }
        )
    out: Dict[str, List[Dict[str, Any]]] = {}
    lim = max(20, int(history_bars))
    for code, bars in tmp.items():
        out[code] = bars[-lim:]
    return out


def resolve_mainline_universe(
    db: Session,
    *,
    sector: Optional[Dict[str, Any]] = None,
    concept_board_codes: Optional[Sequence[str]] = None,
) -> Set[str]:
    """主线行业成分 ∪ 概念成分。"""
    codes: Set[str] = set()
    main = (sector or {}).get("main") or {}
    board = str(main.get("board_code") or "").strip()
    if board:
        codes |= load_industry_constituents(db, board)
    if concept_board_codes:
        codes |= load_concept_constituents(db, concept_board_codes)
    return codes
