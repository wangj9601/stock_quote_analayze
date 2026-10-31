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

import numpy as np
from sqlalchemy import text

from backend_core.analysis.sepa.bars import rs_rank, weighted_momentum

# 近 20 个交易日日均成交额下限（元）。采集端已把 Tushare 千元折成元。
DEFAULT_MIN_AVG_AMOUNT = 50_000_000.0
AMOUNT_DAYS = 20
MIN_AMOUNT_OBS = 10
# 流动性排序后的安全上限，避免一次请求扫完全市场里的壳股。
SAFETY_CAP = 4000


def is_excluded_name(name: Optional[str]) -> bool:
    """ST、*ST、退市整理。空名称不排除，交给行情侧自己决定是否展示。"""
    text_name = name or ""
    folded = text_name.upper()
    if "ST" in folded:
        return True
    return "退市" in text_name


def latest_trade_date(db) -> str:
    d = db.execute(text("SELECT MAX(date) FROM historical_quotes")).scalar()
    return str(d)[:10] if d else ""


def _amount_window_start(db, end_date: str, days: int = AMOUNT_DAYS) -> str:
    """end_date 往前第 days 个交易日（含端点）。日期在库里按文本比较。"""
    row = db.execute(
        text(
            """
            SELECT MIN(date) FROM (
                SELECT DISTINCT date FROM historical_quotes
                WHERE date <= :d
                ORDER BY date DESC
                LIMIT :n
            ) t
            """
        ),
        {"d": end_date, "n": int(days)},
    ).scalar()
    return str(row)[:10] if row else end_date


def load_universe(
    db,
    *,
    end_date: str,
    limit_codes: Optional[int] = None,
    min_bars: int = 260,
    min_avg_amount: float = DEFAULT_MIN_AVG_AMOUNT,
    exclude_st: bool = True,
) -> Dict[str, Any]:
    """全市场达标股票池：足够 K 线、排除 ST/退市、近 20 日均成交额达标。

    不再按代码序截取。名额用近 20 日均成交额从高到低排，上限 SAFETY_CAP，
    这样上证、创业板、科创板会按流动性一起进来，相对强度也在这只池子里算。
    limit_codes 为 0 或 None 时用安全上限。
    """
    cap = SAFETY_CAP if not limit_codes else min(int(limit_codes), SAFETY_CAP)
    start = _amount_window_start(db, end_date)
    params: Dict[str, Any] = {
        "d": end_date,
        "start": start,
        "mb": int(min_bars),
        "min_obs": MIN_AMOUNT_OBS,
        "min_amt": float(min_avg_amount or 0.0),
        "cap": cap,
    }
    amount_on = float(min_avg_amount or 0.0) > 0
    amount_clause = "AND l.avg_amount >= :min_amt" if amount_on else ""
    join_liq = "JOIN" if amount_on else "LEFT JOIN"
    st_clause = ""
    if exclude_st:
        st_clause = """
          AND COALESCE(s.name, '') NOT ILIKE '%ST%'
          AND COALESCE(s.name, '') NOT ILIKE '%退市%'
        """
    sql = f"""
        WITH bars AS (
            SELECT code, COUNT(*) AS n_bars
            FROM historical_quotes
            WHERE date <= :d AND code ~ '^[0-9]{{6}}$'
            GROUP BY code
            HAVING COUNT(*) >= :mb
        ),
        liq AS (
            SELECT code, AVG(amount) AS avg_amount, COUNT(amount) AS n_amt
            FROM historical_quotes
            WHERE date <= :d AND date >= :start
              AND code ~ '^[0-9]{{6}}$' AND amount IS NOT NULL
            GROUP BY code
            HAVING COUNT(amount) >= :min_obs
        )
        SELECT b.code, COALESCE(s.name, '') AS name, l.avg_amount
        FROM bars b
        {join_liq} liq l ON l.code = b.code
        LEFT JOIN stock_basic_info s ON s.code = b.code
        WHERE 1 = 1
          {amount_clause}
          {st_clause}
        ORDER BY l.avg_amount DESC NULLS LAST, b.code
        LIMIT :cap
    """
    rows = db.execute(text(sql), params).mappings().all()
    codes: List[str] = []
    names: Dict[str, str] = {}
    for r in rows:
        name = r["name"] or ""
        if exclude_st and is_excluded_name(name):
            continue
        codes.append(r["code"])
        names[r["code"]] = name
    return {
        "codes": codes,
        "names": names,
        "amount_start": start,
        "min_avg_amount": float(min_avg_amount or 0.0),
        "cap": cap,
        "exclude_st": bool(exclude_st),
    }


def resolve_codes(db, *, end_date: str, limit_codes: Optional[int] = None,
                  min_bars: int = 260, min_avg_amount: float = DEFAULT_MIN_AVG_AMOUNT,
                  exclude_st: bool = True) -> List[str]:
    """load_universe 的代码列表。保留旧函数名，排序已改为成交额。"""
    return load_universe(
        db,
        end_date=end_date,
        limit_codes=limit_codes,
        min_bars=min_bars,
        min_avg_amount=min_avg_amount,
        exclude_st=exclude_st,
    )["codes"]


def cross_section_rs(db, codes: Sequence[str], end_date: str, n_bars: int = 260) -> Dict[str, float]:
    """只用收盘价算横截面相对强度，供单票明细，避免为排名再拉整段 OHLC。"""
    if not codes:
        return {}
    rows = db.execute(
        text(
            """
            WITH ranked AS (
                SELECT code, close,
                       row_number() OVER (PARTITION BY code ORDER BY date DESC) AS rn
                FROM historical_quotes
                WHERE code = ANY(:codes) AND date <= :d AND close IS NOT NULL
            )
            SELECT code, rn, close FROM ranked WHERE rn <= :n
            """
        ),
        {"codes": list(codes), "d": end_date, "n": int(n_bars)},
    ).mappings().all()
    grouped: Dict[str, List[tuple]] = {}
    for r in rows:
        close = r["close"]
        if close is None:
            continue
        grouped.setdefault(r["code"], []).append((int(r["rn"]), float(close)))
    ordered = list(codes)
    moms = []
    for code in ordered:
        pairs = sorted(grouped.get(code) or [], key=lambda x: -x[0])
        closes = np.asarray([p[1] for p in pairs], dtype=float)
        moms.append(weighted_momentum(closes))
    return dict(zip(ordered, rs_rank(moms)))


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
    limit_codes: Optional[int] = None,
    min_avg_amount: float = DEFAULT_MIN_AVG_AMOUNT,
    n_bars: int = 340,
    margin_rows: int = 90,
    names: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """一次取齐 screen_universe 的入参。未指定 codes 时走全市场流动性池。"""
    d = end_date or latest_trade_date(db)
    pool: Dict[str, Any] = {}
    if codes is None:
        pool = load_universe(
            db, end_date=d, limit_codes=limit_codes, min_avg_amount=min_avg_amount,
        )
        code_list = pool["codes"]
        name_map = dict(pool["names"])
    else:
        code_list = list(codes)
        name_map = dict(names or {})
    bars = load_bars(db, code_list, d, n_bars=n_bars)
    used = [c for c in code_list if c in bars]
    return {
        "trade_date": d,
        "codes": used,
        "names": {c: name_map.get(c, "") for c in used},
        "bars": bars,
        "margin": load_margin(db, used, d, n_rows=margin_rows),
        "float_mv": load_float_mv(db, used, d),
        "pool": pool,
    }
