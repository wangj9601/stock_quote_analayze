"""RS 预计算用：不复权日 K + 库内因子 → 前复权收盘序列。"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# 与 adj_quotes 一致：auto = 新浪优先，其次 BaoStock
SOURCE_SINA = "akshare_sina_qfq"
SOURCE_BAOSTOCK = "baostock_qfq"
PREFERRED_SOURCES = (SOURCE_SINA, SOURCE_BAOSTOCK)


def _parse_date(v: Any) -> Optional[dt.date]:
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    s = str(v).strip()
    if len(s) >= 10 and s[4] == "-":
        try:
            return dt.date.fromisoformat(s[:10])
        except ValueError:
            return None
    if len(s) == 8 and s.isdigit():
        try:
            return dt.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        except ValueError:
            return None
    return None


def preload_raw_bars(
    session: Session,
    codes: Sequence[str],
    trade_date: str,
    *,
    lookback_calendar_days: int,
    batch_size: int = 500,
) -> Dict[str, List[Dict[str, Any]]]:
    """批量预加载不复权 bars：[{date, close}, ...] 升序。"""
    if not codes:
        return {}
    min_date = (
        dt.datetime.strptime(trade_date[:10], "%Y-%m-%d")
        - dt.timedelta(days=lookback_calendar_days)
    ).strftime("%Y-%m-%d")
    out: Dict[str, List[Dict[str, Any]]] = {}
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
    for i in range(0, len(codes), batch_size):
        batch = list(codes[i : i + batch_size])
        rows = session.execute(
            stmt,
            {"codes": batch, "min_date": min_date, "trade_date": trade_date[:10]},
        ).fetchall()
        for code, d, close in rows:
            c = str(code).strip()
            bd = _parse_date(d)
            try:
                px = float(close)
            except (TypeError, ValueError):
                continue
            if bd is None or px <= 0:
                continue
            out.setdefault(c, []).append({"date": bd, "close": px})
    return out


def preload_adj_factors(
    session: Session,
    codes: Sequence[str],
    *,
    batch_size: int = 500,
) -> Dict[str, List[Tuple[dt.date, float]]]:
    """
    批量加载库内因子；每只股票优先新浪，否则 BaoStock（不混源）。
    日终批算只读库，不打外网。
    """
    if not codes:
        return {}
    by_code_src: Dict[str, Dict[str, List[Tuple[dt.date, float]]]] = {}
    stmt = text(
        """
        SELECT code, source, trade_date, adj_factor
        FROM stock_adj_factor
        WHERE code IN :codes
          AND source IN :sources
          AND trade_date > DATE '1900-01-01'
          AND adj_factor > 0
        ORDER BY code, source, trade_date
        """
    ).bindparams(
        bindparam("codes", expanding=True),
        bindparam("sources", expanding=True),
    )
    for i in range(0, len(codes), batch_size):
        batch = list(codes[i : i + batch_size])
        rows = session.execute(
            stmt,
            {"codes": batch, "sources": list(PREFERRED_SOURCES)},
        ).fetchall()
        for code, source, td, fac in rows:
            c = str(code).strip()
            src = str(source or "").strip()
            d = _parse_date(td)
            try:
                f = float(fac)
            except (TypeError, ValueError):
                continue
            if d is None or f <= 0 or not src:
                continue
            by_code_src.setdefault(c, {}).setdefault(src, []).append((d, f))

    out: Dict[str, List[Tuple[dt.date, float]]] = {}
    for code, src_map in by_code_src.items():
        chosen: Optional[List[Tuple[dt.date, float]]] = None
        for pref in PREFERRED_SOURCES:
            seq = src_map.get(pref)
            if seq:
                chosen = seq
                break
        if chosen:
            out[code] = chosen
    return out


def apply_qfq_closes(
    bars: Sequence[Dict[str, Any]],
    factors: Sequence[Tuple[dt.date, float]],
) -> Optional[List[float]]:
    """
    P_qfq = P_raw × f_t / f_T（与 adj_quotes.apply_qfq_to_bars 一致）。
    返回升序前复权收盘价；失败返回 None。
    """
    if not bars or not factors:
        return None
    factors_sorted = sorted(factors, key=lambda x: x[0])
    f_T = float(factors_sorted[-1][1])
    if f_T <= 0:
        return None
    fi = 0
    last_f: Optional[float] = None
    first_f = float(factors_sorted[0][1])
    out: List[float] = []
    for bar in bars:
        bd = bar.get("date")
        if not isinstance(bd, dt.date):
            bd = _parse_date(bd)
        if bd is None:
            return None
        while fi < len(factors_sorted) and factors_sorted[fi][0] <= bd:
            last_f = float(factors_sorted[fi][1])
            fi += 1
        f_t = last_f if last_f is not None else first_f
        if f_t <= 0:
            return None
        try:
            raw = float(bar["close"])
        except (TypeError, ValueError, KeyError):
            return None
        if raw <= 0:
            return None
        out.append(raw * (f_t / f_T))
    return out


def build_qfq_close_map(
    session: Session,
    codes: Sequence[str],
    trade_date: str,
    *,
    lookback_calendar_days: int,
    batch_size: int = 500,
) -> Tuple[Dict[str, List[float]], Dict[str, int]]:
    """
    返回 (code -> 前复权收盘升序, 统计)。
    无行情或无因子的代码不会出现在结果中。
    """
    raw = preload_raw_bars(
        session,
        codes,
        trade_date,
        lookback_calendar_days=lookback_calendar_days,
        batch_size=batch_size,
    )
    factors = preload_adj_factors(session, list(raw.keys()), batch_size=batch_size)
    qfq_map: Dict[str, List[float]] = {}
    skipped_no_factor = 0
    skipped_qfq_fail = 0
    for code, bars in raw.items():
        fac = factors.get(code)
        if not fac:
            skipped_no_factor += 1
            continue
        series = apply_qfq_closes(bars, fac)
        if not series:
            skipped_qfq_fail += 1
            continue
        qfq_map[code] = series
    stats = {
        "raw_codes": len(raw),
        "factor_codes": len(factors),
        "qfq_codes": len(qfq_map),
        "skipped_no_factor": skipped_no_factor,
        "skipped_qfq_fail": skipped_qfq_fail,
    }
    logger.info(
        "RS qfq preload trade_date=%s raw=%s factors=%s qfq=%s no_factor=%s fail=%s",
        trade_date,
        stats["raw_codes"],
        stats["factor_codes"],
        stats["qfq_codes"],
        skipped_no_factor,
        skipped_qfq_fail,
    )
    return qfq_map, stats
