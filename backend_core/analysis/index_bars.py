# -*- coding: utf-8 -*-
"""指数日线加载：读 index_historical_quotes，可选叠 index_realtime_quotes。

严禁走个股 historical_quotes（000001 上证 ≠ 平安银行）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

KNOWN_INDEX_NAMES: Dict[str, str] = {
    "000001": "上证指数",
    "399001": "深证成指",
    "399006": "创业板指",
    "000300": "沪深300",
}


def normalize_index_display_code(raw: str) -> str:
    """规范为 6 位展示码（000001），去掉 sh/sz / .SH 等。"""
    s = str(raw or "").strip()
    if not s:
        return ""
    upper = s.upper()
    if upper.endswith(".SH") or upper.endswith(".SZ"):
        digits = "".join(ch for ch in upper.rsplit(".", 1)[0] if ch.isdigit())
        return digits.zfill(6) if digits else ""
    lower = s.lower()
    if lower.startswith("sh") and len(lower) > 2:
        digits = "".join(ch for ch in lower[2:] if ch.isdigit())
        return digits.zfill(6) if digits else ""
    if lower.startswith("sz") and len(lower) > 2:
        digits = "".join(ch for ch in lower[2:] if ch.isdigit())
        return digits.zfill(6) if digits else ""
    digits = "".join(ch for ch in s if ch.isdigit())
    if digits:
        return digits.zfill(6) if len(digits) <= 6 else digits[-6:]
    return s


def to_index_ts_code(raw: str) -> str:
    from backend_core.strategies.sbbr.data_loader import normalize_index_ts_code

    return normalize_index_ts_code(raw)


def resolve_index_identity(db: Session, raw: str) -> Dict[str, Any]:
    """解析指数身份；优先已知四大指数，其次实时/历史表名称。"""
    display = normalize_index_display_code(raw)
    if not display and not (raw or "").strip():
        return {"ok": False, "message": "请提供指数代码", "http_status": 400}
    ts_code = to_index_ts_code(display or raw)
    code = display or normalize_index_display_code(ts_code) or str(raw).strip()
    name = KNOWN_INDEX_NAMES.get(code) or ""

    if not name:
        try:
            row = db.execute(
                text(
                    """
                    SELECT name FROM index_realtime_quotes
                    WHERE code = :c
                       OR code = :sh
                       OR code = :sz
                       OR RIGHT(code, 6) = :c
                    ORDER BY update_time DESC NULLS LAST
                    LIMIT 1
                    """
                ),
                {"c": code, "sh": f"sh{code}", "sz": f"sz{code}"},
            ).fetchone()
            if row and row[0]:
                name = str(row[0])
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass

    if not name:
        try:
            row = db.execute(
                text(
                    """
                    SELECT name FROM index_historical_quotes
                    WHERE ts_code = :ts OR code = :c
                    ORDER BY trade_date DESC
                    LIMIT 1
                    """
                ),
                {"ts": ts_code, "c": code},
            ).fetchone()
            if row and row[0]:
                name = str(row[0])
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass

    if not name:
        name = code

    # 至少历史或实时有一条才算找到
    has_hist = False
    try:
        n = db.execute(
            text(
                "SELECT 1 FROM index_historical_quotes WHERE ts_code = :ts LIMIT 1"
            ),
            {"ts": ts_code},
        ).fetchone()
        has_hist = bool(n)
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    if not has_hist and code not in KNOWN_INDEX_NAMES:
        return {
            "ok": False,
            "message": f"未找到指数 {code}",
            "http_status": 404,
            "code": code,
            "ts_code": ts_code,
            "name": name,
        }

    return {
        "ok": True,
        "code": code,
        "ts_code": ts_code,
        "name": name,
        "http_status": 200,
    }


def load_index_ohlc_asc(
    db: Session,
    code: str,
    *,
    lookback: int = 180,
    asof: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """正序指数日 K。"""
    ts = to_index_ts_code(code)
    lim = max(20, int(lookback or 180))
    params: Dict[str, Any] = {"ts": ts, "lim": lim}
    if asof:
        sql = text(
            """
            SELECT trade_date, open, high, low, close, vol, amount
            FROM index_historical_quotes
            WHERE ts_code = :ts AND trade_date <= CAST(:d AS date)
            ORDER BY trade_date DESC
            LIMIT :lim
            """
        )
        params["d"] = str(asof).strip()[:10]
    else:
        sql = text(
            """
            SELECT trade_date, open, high, low, close, vol, amount
            FROM index_historical_quotes
            WHERE ts_code = :ts
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


def fetch_index_realtime_quote(db: Session, code: str) -> Optional[Dict[str, Any]]:
    """读取指数实时快照，标准化为 display code。"""
    display = normalize_index_display_code(code)
    try:
        row = db.execute(
            text(
                """
                SELECT code, name, price, change, pct_chg, open, high, low,
                       pre_close, volume, amount, update_time
                FROM index_realtime_quotes
                WHERE code = :c OR code = :sh OR code = :sz OR RIGHT(code, 6) = :c
                ORDER BY update_time DESC NULLS LAST
                LIMIT 1
                """
            ),
            {
                "c": display,
                "sh": f"sh{display}",
                "sz": f"sz{display}",
            },
        ).fetchone()
    except Exception as e:
        logger.debug("fetch_index_realtime_quote fail %s: %s", code, e)
        try:
            db.rollback()
        except Exception:
            pass
        return None
    if not row:
        return None
    update_time = str(row[11] or "")
    trade_date = update_time[:10] if len(update_time) >= 10 else ""
    price = float(row[2]) if row[2] is not None else None
    return {
        "code": display,
        "name": str(row[1] or KNOWN_INDEX_NAMES.get(display) or display),
        "current_price": price,
        "change": float(row[3]) if row[3] is not None else None,
        "change_percent": float(row[4]) if row[4] is not None else None,
        "open": float(row[5]) if row[5] is not None else None,
        "high": float(row[6]) if row[6] is not None else None,
        "low": float(row[7]) if row[7] is not None else None,
        "pre_close": float(row[8]) if row[8] is not None else None,
        "volume": float(row[9]) if row[9] is not None else None,
        "amount": float(row[10]) if row[10] is not None else None,
        "update_time": update_time,
        "trade_date": trade_date,
        "source": "index_realtime_quotes",
    }


def merge_index_realtime_bar(
    bars: List[Dict[str, Any]],
    quote: Optional[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """将实时价叠到当日未收盘 bar（无报价则原样返回）。"""
    if not quote or quote.get("current_price") is None:
        return list(bars or []), None
    out = list(bars or [])
    td = str(quote.get("trade_date") or "")[:10]
    if not td:
        return out, {
            "trade_date": None,
            "current_price": quote.get("current_price"),
            "change_percent": quote.get("change_percent"),
            "source": quote.get("source"),
            "update_time": quote.get("update_time"),
            "merged": False,
        }
    price = float(quote["current_price"])
    o = float(quote["open"]) if quote.get("open") is not None else price
    h = float(quote["high"]) if quote.get("high") is not None else price
    low = float(quote["low"]) if quote.get("low") is not None else price
    vol = float(quote["volume"]) if quote.get("volume") is not None else 0.0
    amt = float(quote["amount"]) if quote.get("amount") is not None else 0.0
    bar = {
        "date": td,
        "open": o,
        "high": max(h, price, o),
        "low": min(low, price, o) if low else min(price, o),
        "close": price,
        "volume": vol,
        "amount": amt,
    }
    meta = {
        "trade_date": td,
        "current_price": price,
        "change_percent": quote.get("change_percent"),
        "source": quote.get("source"),
        "update_time": quote.get("update_time"),
        "merged": True,
    }
    if out and str(out[-1].get("date") or "")[:10] == td:
        out[-1] = bar
    else:
        out.append(bar)
    return out, meta


def load_index_bars_with_realtime(
    db: Session,
    code: str,
    *,
    lookback: int = 180,
    asof: Optional[str] = None,
    use_realtime: bool = False,
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]], Optional[str]]:
    """
    返回 (bars, realtime_meta, effective_asof)。
    use_realtime 时忽略 asof 叠加实时；否则按 asof 截断历史。
    """
    hist_asof = None if use_realtime else (str(asof).strip()[:10] if asof else None)
    bars = load_index_ohlc_asc(db, code, lookback=lookback, asof=hist_asof)
    rt_meta = None
    if use_realtime:
        quote = fetch_index_realtime_quote(db, code)
        bars, rt_meta = merge_index_realtime_bar(bars, quote)
        if rt_meta and rt_meta.get("trade_date"):
            return bars, rt_meta, str(rt_meta["trade_date"])[:10]
    effective = hist_asof
    if not effective and bars:
        effective = str(bars[-1].get("date") or "")[:10]
    return bars, rt_meta, effective
