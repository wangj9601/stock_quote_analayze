"""
批量查询股票最新收盘价：优先实时行情表，缺失时回退历史行情表。
使用 ROW_NUMBER 窗口函数，避免对大表做 GROUP BY + JOIN。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import bindparam, inspect, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from backend_api.models import (
    HistoricalQuotes,
    HistoricalQuotesHK,
    StockRealtimeQuote,
    StockRealtimeQuoteHK,
)

ClosePair = Tuple[Optional[float], Optional[str]]


def _format_quote_date(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    if hasattr(raw, "strftime"):
        return raw.strftime("%Y-%m-%d")
    s = str(raw).strip()
    return s[:10] if s else None


def _chunked(items: List[str], size: int = 200) -> List[List[str]]:
    if not items:
        return []
    return [items[i : i + size] for i in range(0, len(items), size)]


def _table_exists(db: Session, table_name: str) -> bool:
    try:
        return inspect(db.get_bind()).has_table(table_name)
    except Exception:
        return False


def _batch_latest_from_table(
    db: Session,
    *,
    table: str,
    code_column: str,
    date_column: str,
    price_column: str,
    codes: List[str],
) -> Dict[str, ClosePair]:
    """从指定表批量取每只股票最新一条记录的收盘价。"""
    out: Dict[str, ClosePair] = {}
    if not codes or not _table_exists(db, table):
        return out

    sql = text(
        f"""
        SELECT code, price, quote_date
        FROM (
            SELECT
                {code_column} AS code,
                {price_column} AS price,
                {date_column} AS quote_date,
                ROW_NUMBER() OVER (
                    PARTITION BY {code_column}
                    ORDER BY {date_column} DESC
                ) AS rn
            FROM {table}
            WHERE {code_column} IN :codes
        ) ranked
        WHERE rn = 1
        """
    ).bindparams(bindparam("codes", expanding=True))

    for chunk in _chunked(codes):
        try:
            rows = db.execute(sql, {"codes": chunk}).fetchall()
        except (OperationalError, ProgrammingError):
            return out
        for code, price, quote_date in rows:
            c = str(code or "").strip()
            if not c:
                continue
            out[c] = (
                float(price) if price is not None else None,
                _format_quote_date(quote_date),
            )
    return out


def batch_lookup_latest_closes(
    db: Session,
    pairs: List[Tuple[str, str]],
) -> Dict[Tuple[str, str], ClosePair]:
    """
    批量查询最新收盘价：(market, code) -> (close, date)。

    1. 先查 stock_realtime_quote / stock_realtime_quote_hk（数据量小）
    2. 未命中的再查 historical_quotes / historical_quotes_hk
    """
    out: Dict[Tuple[str, str], ClosePair] = {}
    cn_codes: List[str] = []
    hk_codes: List[str] = []
    seen_cn: set[str] = set()
    seen_hk: set[str] = set()

    for market, code in pairs:
        m = (market or "CN").upper()
        c = str(code or "").strip()
        if not c:
            continue
        key = (m, c)
        if key in out:
            continue
        out[key] = (None, None)
        if m == "HK":
            if c not in seen_hk:
                seen_hk.add(c)
                hk_codes.append(c)
        else:
            if c not in seen_cn:
                seen_cn.add(c)
                cn_codes.append(c)

    if cn_codes:
        rt = _batch_latest_from_table(
            db,
            table=StockRealtimeQuote.__tablename__,
            code_column="code",
            date_column="trade_date",
            price_column="current_price",
            codes=cn_codes,
        )
        for code, pair in rt.items():
            if pair[0] is not None:
                out[("CN", code)] = pair

        missing_cn = [c for c in cn_codes if out.get(("CN", c), (None, None))[0] is None]
        if missing_cn:
            hist = _batch_latest_from_table(
                db,
                table=HistoricalQuotes.__tablename__,
                code_column="code",
                date_column="date",
                price_column="close",
                codes=missing_cn,
            )
            for code, pair in hist.items():
                out[("CN", code)] = pair

    if hk_codes:
        rt = _batch_latest_from_table(
            db,
            table=StockRealtimeQuoteHK.__tablename__,
            code_column="code",
            date_column="trade_date",
            price_column="current_price",
            codes=hk_codes,
        )
        for code, pair in rt.items():
            if pair[0] is not None:
                out[("HK", code)] = pair

        missing_hk = [c for c in hk_codes if out.get(("HK", c), (None, None))[0] is None]
        if missing_hk:
            hist = _batch_latest_from_table(
                db,
                table=HistoricalQuotesHK.__tablename__,
                code_column="code",
                date_column="date",
                price_column="close",
                codes=missing_hk,
            )
            for code, pair in hist.items():
                out[("HK", code)] = pair

    return out
