# -*- coding: utf-8 -*-
"""DBLB / 形态识别 日线加载（升序 bars）。

支持 A 股 ``historical_quotes`` 与港股 ``historical_quotes_hk``：
纯数字 5 位码缺省走港股表，6 位走 A 股表。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_OHLC_SQL_TMPL = """
SELECT code, trade_date, high, low, close, volume, name
FROM (
    SELECT code,
           date AS trade_date,
           high, low, close, volume, name,
           ROW_NUMBER() OVER (PARTITION BY code ORDER BY date DESC) AS rn
    FROM {table}
    WHERE code IN :codes
      AND high IS NOT NULL AND low IS NOT NULL AND close IS NOT NULL
      AND (:asof IS NULL OR date <= :asof)
) t
WHERE rn <= :lim
ORDER BY code, trade_date
"""


def resolve_effective_trade_date(
    db: Session,
    requested: Optional[str] = None,
    *,
    market: Optional[str] = None,
) -> str:
    """将请求日钳到行情表可用最新日。

    market=HK 仅看港股表；market=CN 仅看 A 股表；其它取两表 MAX 的较大者。
    """
    from sqlalchemy import func

    today_s = datetime.now().strftime("%Y-%m-%d")
    raw = (requested or "").strip()[:10]
    target_s = raw if raw else today_s
    try:
        target = datetime.strptime(target_s, "%Y-%m-%d").date()
    except ValueError:
        target = datetime.now().date()
        target_s = today_s

    mt = str(market or "").strip().upper()

    def _max_date(model) -> Optional[Any]:
        try:
            return db.query(func.max(model.date)).scalar()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            return None

    def _to_date(row_max) -> Optional[Any]:
        if row_max is None:
            return None
        if hasattr(row_max, "strftime"):
            return row_max
        try:
            return datetime.strptime(str(row_max).strip()[:10], "%Y-%m-%d").date()
        except ValueError:
            return None

    max_candidates = []
    try:
        from backend_api.models import HistoricalQuotes, HistoricalQuotesHK
    except Exception:
        from models import HistoricalQuotes, HistoricalQuotesHK  # type: ignore

    if mt == "HK":
        max_candidates.append(_to_date(_max_date(HistoricalQuotesHK)))
    elif mt == "CN":
        max_candidates.append(_to_date(_max_date(HistoricalQuotes)))
    else:
        max_candidates.append(_to_date(_max_date(HistoricalQuotes)))
        max_candidates.append(_to_date(_max_date(HistoricalQuotesHK)))

    max_candidates = [d for d in max_candidates if d is not None]
    if not max_candidates:
        return target_s
    max_d = max(max_candidates)
    max_s = max_d.strftime("%Y-%m-%d") if hasattr(max_d, "strftime") else str(max_d)[:10]
    if target > max_d:
        return max_s
    return target_s


def load_names(db: Session, codes: Sequence[str]) -> Dict[str, str]:
    """查名称：A 股 stock_basic_info + 港股 stock_basic_info_hk。"""
    try:
        from backend_api.utils.equity_code import (
            normalize_equity_code,
            partition_codes_by_market,
        )
    except ImportError:
        from utils.equity_code import (  # type: ignore
            normalize_equity_code,
            partition_codes_by_market,
        )

    try:
        from backend_api.models import StockBasicInfo, StockBasicInfoHK
    except Exception:
        from models import StockBasicInfo, StockBasicInfoHK  # type: ignore

    cn_codes, hk_codes = partition_codes_by_market(codes)
    # 兼容非纯数字代码（极少）
    other = [
        normalize_equity_code(c)
        for c in codes
        if normalize_equity_code(c)
        and not str(normalize_equity_code(c)).isdigit()
    ]
    out: Dict[str, str] = {}
    if cn_codes or other:
        rows = (
            db.query(StockBasicInfo.code, StockBasicInfo.name)
            .filter(StockBasicInfo.code.in_(cn_codes + other))
            .all()
        )
        for r in rows:
            out[str(r[0])] = str(r[1] or "")
    if hk_codes:
        rows = (
            db.query(StockBasicInfoHK.code, StockBasicInfoHK.name)
            .filter(StockBasicInfoHK.code.in_(hk_codes))
            .all()
        )
        for r in rows:
            out[str(r[0])] = str(r[1] or "")
    return out


def _fetch_ohlc_from_table(
    db: Session,
    table: str,
    codes: Sequence[str],
    *,
    lim: int,
    asof_s: Optional[str],
) -> List[Any]:
    if not codes:
        return []
    sql = text(_OHLC_SQL_TMPL.format(table=table)).bindparams(
        bindparam("codes", expanding=True)
    )
    return db.execute(
        sql, {"codes": list(codes), "lim": lim, "asof": asof_s}
    ).fetchall()


def batch_load_ohlc_asc(
    db: Session,
    codes: Sequence[str],
    *,
    lookback: int = 160,
    asof: Optional[str] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """批量取日线 OHLC，按 code 升序截断末 lookback 根。

    5 位码从 ``historical_quotes_hk`` 取；6 位码从 ``historical_quotes`` 取。
    """
    try:
        from backend_api.utils.equity_code import (
            normalize_equity_code,
            partition_codes_by_market,
        )
    except ImportError:
        from utils.equity_code import (  # type: ignore
            normalize_equity_code,
            partition_codes_by_market,
        )

    cn_codes, hk_codes = partition_codes_by_market(codes)
    if not cn_codes and not hk_codes:
        return {}
    lb = max(30, int(lookback))
    fetch_n = max(lb * 2, lb + 20)
    asof_s = (asof or "").strip()[:10] or None

    rows: List[Any] = []
    try:
        rows.extend(
            _fetch_ohlc_from_table(
                db, "historical_quotes", cn_codes, lim=fetch_n, asof_s=asof_s
            )
        )
        rows.extend(
            _fetch_ohlc_from_table(
                db,
                "historical_quotes_hk",
                hk_codes,
                lim=fetch_n,
                asof_s=asof_s,
            )
        )
    except Exception as e:
        logger.warning("dblb batch_load_ohlc_asc failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        return {}

    by: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        code = normalize_equity_code(r[0])
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
