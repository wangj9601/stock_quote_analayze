# -*- coding: utf-8 -*-
"""取数层：把库里三张表读成 SEPA 需要的入参（只读 SELECT，不写库）。

已在本地库验证过的三个口径坑：
1. historical_quotes.date 是 TEXT 类型，比较时必须用字符串（不要写 DATE 'xxx'）。
2. 股票代码在库里是裸 6 位（'600000'），不带 .SH/.SZ 后缀。
3. stock_realtime_quote.circulating_market_value 当前全为 NULL，
   流通市值必须走 stock_basic_info.free_float_shares × 最新收盘（<1e6 视为万股）。

用法::

    from backend_core.analysis.sepa.loaders import fetch_inputs
    from backend_core.analysis.sepa import screen_universe, to_table_rows

    inputs = fetch_inputs(db, limit_codes=800)
    picks = screen_universe(inputs["bars"], margin_by_code=inputs["margin"],
                            circ_mv_by_code=inputs["float_mv"], top=30)
    rows = to_table_rows(picks)
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence

from sqlalchemy import text


def latest_trade_date(db) -> str:
    d = db.execute(text("SELECT MAX(date) FROM historical_quotes")).scalar()
    return str(d)[:10] if d else ""


def resolve_codes(db, *, end_date: str, limit_codes: Optional[int] = None,
                  min_bars: int = 260) -> List[str]:
    """取 K 线足够的历史标的；limit 用固定顺序，保证回放可复现。"""
    sql = (
        "SELECT code FROM historical_quotes "
        "WHERE date <= :d GROUP BY code HAVING COUNT(*) >= :mb ORDER BY code"
    )
    params: Dict[str, Any] = {"d": end_date, "mb": int(min_bars)}
    if limit_codes:
        sql += " LIMIT :n"
        params["n"] = int(limit_codes)
    return [r[0] for r in db.execute(text(sql), params)]


def load_bars(db, codes: Sequence[str], end_date: str, n_bars: int = 340) -> Dict[str, List[Dict[str, Any]]]:
    """一次取回多只票的最近 n_bars 根日线（前复权口径由采集端保证）。"""
    if not codes:
        return {}
    rows = db.execute(
        text(
            """
            WITH ranked AS (
                SELECT code, date, open, high, low, close, volume,
                       row_number() OVER (PARTITION BY code ORDER BY date DESC) AS rn
                FROM historical_quotes
                WHERE code = ANY(:codes) AND date <= :d
            )
            SELECT code, date, open, high, low, close, volume
            FROM ranked WHERE rn <= :n
            ORDER BY code, date
            """
        ),
        {"codes": list(codes), "d": end_date, "n": int(n_bars)},
    ).mappings().all()

    out: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        out.setdefault(r["code"], []).append(dict(r))
    return out


def load_margin(db, codes: Sequence[str], end_date: str, n_rows: int = 90) -> Dict[str, List[Dict[str, Any]]]:
    """两融明细；非两融标的不会出现在结果里（下游按无数据处理）。"""
    if not codes:
        return {}
    rows = db.execute(
        text(
            """
            WITH ranked AS (
                SELECT code, trade_date, rzye, rzmre, rzche,
                       row_number() OVER (PARTITION BY code ORDER BY trade_date DESC) AS rn
                FROM stock_margin_daily
                WHERE code = ANY(:codes) AND trade_date <= :d
            )
            SELECT code, trade_date, rzye, rzmre, rzche FROM ranked WHERE rn <= :n
            ORDER BY code, trade_date
            """
        ),
        {"codes": list(codes), "d": end_date, "n": int(n_rows)},
    ).mappings().all()

    out: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        out.setdefault(r["code"], []).append(dict(r))
    return out


def load_float_mv(db, codes: Sequence[str], end_date: str) -> Dict[str, float]:
    """流通市值（元）：free_float_shares × 最近收盘；小于 1e6 的股本按万股处理。"""
    if not codes:
        return {}
    rows = db.execute(
        text(
            """
            SELECT b.code, b.free_float_shares,
                   (SELECT q.close FROM historical_quotes q
                     WHERE q.code = b.code AND q.date <= :d
                     ORDER BY q.date DESC LIMIT 1) AS close
            FROM stock_basic_info b
            WHERE b.code = ANY(:codes)
            """
        ),
        {"codes": list(codes), "d": end_date},
    ).mappings().all()

    out: Dict[str, float] = {}
    for r in rows:
        shares, close = r["free_float_shares"], r["close"]
        if not shares or not close:
            continue
        shares = float(shares)
        if shares < 1e6:
            shares *= 1e4
        out[r["code"]] = shares * float(close)
    return out


def fetch_inputs(
    db,
    *,
    codes: Optional[Iterable[str]] = None,
    end_date: Optional[str] = None,
    limit_codes: Optional[int] = 800,
    n_bars: int = 340,
    margin_rows: int = 90,
) -> Dict[str, Any]:
    """一次取齐 screen_universe 的三个入参。"""
    d = end_date or latest_trade_date(db)
    code_list = list(codes) if codes else resolve_codes(db, end_date=d, limit_codes=limit_codes)
    bars = load_bars(db, code_list, d, n_bars=n_bars)
    used = list(bars.keys())
    return {
        "trade_date": d,
        "codes": used,
        "bars": bars,
        "margin": load_margin(db, used, d, n_rows=margin_rows),
        "float_mv": load_float_mv(db, used, d),
    }
