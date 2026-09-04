# -*- coding: utf-8 -*-
"""实时行情 → 日 K 末根合并，供个股「实时分析」叠加当日未收盘 bar。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import desc
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _f(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x


def _norm_code(code: str) -> str:
    s = str(code or "").strip()
    if s.isdigit() and len(s) <= 5:
        return s.zfill(5)
    if s.isdigit() and len(s) < 6:
        return s.zfill(6)
    return s


def _is_hk(code: str) -> bool:
    s = str(code or "").strip()
    return bool(s.isdigit() and len(s) <= 5)


def _volume_to_hist_unit(volume: Optional[float], *, is_hk: bool) -> Optional[float]:
    """实时成交量常为「股」；A 股 historical_quotes 多为「手」(÷100)。港股保持原值。"""
    if volume is None:
        return None
    try:
        v = float(volume)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return v
    if is_hk:
        return v
    # 与 kline_hist 一致：实时股 → 手
    if v >= 1000:
        return v / 100.0
    return v


def fetch_db_realtime_quote(db: Session, code: str) -> Optional[Dict[str, Any]]:
    """从本地实时行情表取该股最新一条。"""
    code_n = _norm_code(code)
    if not code_n:
        return None
    try:
        if _is_hk(code_n):
            from backend_api.models import StockRealtimeQuoteHK

            row = (
                db.query(StockRealtimeQuoteHK)
                .filter(StockRealtimeQuoteHK.code == code_n)
                .order_by(desc(StockRealtimeQuoteHK.trade_date))
                .first()
            )
            source = "realtime_db_hk"
        else:
            from backend_api.models import StockRealtimeQuote

            row = (
                db.query(StockRealtimeQuote)
                .filter(StockRealtimeQuote.code == code_n)
                .order_by(desc(StockRealtimeQuote.trade_date))
                .first()
            )
            source = "realtime_db"
        if not row:
            return None
        td = getattr(row, "trade_date", None)
        if hasattr(td, "strftime"):
            trade_date = td.strftime("%Y-%m-%d")
        else:
            trade_date = str(td or "")[:10] or datetime.now().strftime("%Y-%m-%d")
        ut = getattr(row, "update_time", None)
        if hasattr(ut, "strftime"):
            update_time = ut.strftime("%Y-%m-%d %H:%M:%S")
        elif ut is not None:
            update_time = str(ut)
        else:
            update_time = None
        px = _f(getattr(row, "current_price", None))
        if px is None or px <= 0:
            return None
        return {
            "code": code_n,
            "name": getattr(row, "name", None) or "",
            "current_price": px,
            "open": _f(getattr(row, "open", None)),
            "high": _f(getattr(row, "high", None)),
            "low": _f(getattr(row, "low", None)),
            "pre_close": _f(getattr(row, "pre_close", None)),
            "change_percent": _f(getattr(row, "change_percent", None)),
            "volume": _f(getattr(row, "volume", None)),
            "amount": _f(getattr(row, "amount", None)),
            "turnover_rate": _f(getattr(row, "turnover_rate", None)),
            "trade_date": trade_date,
            "update_time": update_time,
            "source": source,
        }
    except Exception as e:
        logger.warning("fetch_db_realtime_quote failed code=%s: %s", code_n, e)
        try:
            db.rollback()
        except Exception:
            pass
        return None


def fetch_live_realtime_quote(db: Session, code: str) -> Optional[Dict[str, Any]]:
    """优先外部快照：Fuyao → 东财 → 新浪 → BaoStock，失败回退本地实时表。"""
    code_n = _norm_code(code)
    if not code_n:
        return None
    if _is_hk(code_n):
        return fetch_db_realtime_quote(db, code_n)

    name = ""
    free_float = None
    try:
        from backend_api.models import StockBasicInfo

        info = db.query(StockBasicInfo).filter(StockBasicInfo.code == code_n).first()
        if info:
            name = getattr(info, "name", None) or ""
            free_float = getattr(info, "free_float_shares", None)
    except Exception:
        pass

    def _normalize_external(q: Dict[str, Any], *, default_source: str) -> Optional[Dict[str, Any]]:
        if not q or not _f(q.get("current_price")) or float(q["current_price"]) <= 0:
            return None
        td = str(q.get("trade_date") or "")[:10] or datetime.now().strftime("%Y-%m-%d")
        return {
            "code": code_n,
            "name": q.get("name") or name,
            "current_price": float(q["current_price"]),
            "open": _f(q.get("open")),
            "high": _f(q.get("high")),
            "low": _f(q.get("low")),
            "pre_close": _f(q.get("pre_close")),
            "change_percent": _f(q.get("change_percent")),
            "volume": _f(q.get("volume")),
            "amount": _f(q.get("turnover") if q.get("turnover") is not None else q.get("amount")),
            "turnover_rate": _f(q.get("turnover_rate")),
            "trade_date": td,
            "update_time": q.get("update_time") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": q.get("source") or default_source,
        }

    # 1. Fuyao
    try:
        from backend_api.utils.fuyao_client import fetch_realtime_quote_by_code as fetch_fuyao

        q = fetch_fuyao(code_n, name=name, free_float_shares=free_float)
        norm = _normalize_external(q or {}, default_source="fuyao")
        if norm:
            return norm
    except Exception as e:
        logger.debug("fuyao live quote skip code=%s: %s", code_n, e)

    # 2. AkShare 东财
    try:
        from backend_api.stock.stock_manage import _quote_from_akshare_em

        q = _quote_from_akshare_em(code_n, name=name)
        norm = _normalize_external(q or {}, default_source="akshare_em")
        if norm:
            return norm
    except Exception as e:
        logger.debug("akshare_em live quote skip code=%s: %s", code_n, e)

    # 3. 新浪财经
    try:
        from backend_api.stock.stock_manage import _quote_from_sina

        q = _quote_from_sina(code_n, name=name)
        norm = _normalize_external(q or {}, default_source="sina")
        if norm:
            return norm
    except Exception as e:
        logger.debug("sina live quote skip code=%s: %s", code_n, e)

    # 4. BaoStock
    try:
        from backend_api.stock.stock_manage import _quote_from_baostock

        q = _quote_from_baostock(code_n, name=name)
        norm = _normalize_external(q or {}, default_source="baostock")
        if norm:
            return norm
    except Exception as e:
        logger.debug("baostock live quote skip code=%s: %s", code_n, e)

    return fetch_db_realtime_quote(db, code_n)


def quote_to_ohlc_bar(quote: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """将实时快照转为与 batch_load_ohlc_asc 兼容的日 K 字典。"""
    if not quote:
        return None
    px = _f(quote.get("current_price") if quote.get("current_price") is not None else quote.get("close"))
    if px is None or px <= 0:
        return None
    code = _norm_code(str(quote.get("code") or ""))
    is_hk = _is_hk(code) if code else False
    high = _f(quote.get("high"))
    low = _f(quote.get("low"))
    open_px = _f(quote.get("open"))
    if high is None or high <= 0:
        high = px
    if low is None or low <= 0:
        low = px
    if open_px is None or open_px <= 0:
        open_px = px
    # 盘中 high/low 可能尚未刷新：至少包住现价
    high = max(high, px, open_px)
    low = min(low, px, open_px)
    td = str(quote.get("trade_date") or "")[:10] or datetime.now().strftime("%Y-%m-%d")
    vol = _volume_to_hist_unit(_f(quote.get("volume")), is_hk=is_hk)
    return {
        "date": td,
        "high": high,
        "low": low,
        "close": px,
        "open": open_px,
        "volume": vol,
        "name": quote.get("name") or "",
        "pct_chg": _f(quote.get("change_percent")),
        "_realtime": True,
    }


def merge_realtime_into_bars(
    bars: List[Dict[str, Any]],
    quote: Optional[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """将实时 bar 追加或覆盖同日末根；无有效报价则原样返回。"""
    bar = quote_to_ohlc_bar(quote) if quote else None
    if not bar:
        return list(bars or []), None
    out = list(bars or [])
    td = bar["date"]
    if out and str(out[-1].get("date") or "")[:10] == td:
        merged = dict(out[-1])
        merged.update({k: v for k, v in bar.items() if v is not None})
        out[-1] = merged
    else:
        out.append(bar)
    meta = {
        "trade_date": td,
        "current_price": bar["close"],
        "change_percent": quote.get("change_percent") if quote else None,
        "source": (quote or {}).get("source"),
        "update_time": (quote or {}).get("update_time"),
        "merged": True,
    }
    return out, meta


def load_bars_with_realtime(
    db: Session,
    code: str,
    *,
    lookback: int = 160,
    asof: Optional[str] = None,
    prefer_live: bool = True,
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]], str]:
    """加载日 K 并合并实时末根。

    返回 (bars, realtime_meta, effective_asof)。
    effective_asof：有实时则用实时 trade_date，否则为请求/表内对齐日。
    """
    from backend_core.strategies.double_bottom.data_loader import (
        batch_load_ohlc_asc,
        resolve_effective_trade_date,
    )

    code_n = _norm_code(code)
    try:
        from backend_api.utils.equity_code import infer_market_type
    except ImportError:
        from utils.equity_code import infer_market_type  # type: ignore

    market = infer_market_type(code_n) or ("HK" if _is_hk(code_n) else "CN")
    quote = fetch_live_realtime_quote(db, code_n) if prefer_live else fetch_db_realtime_quote(db, code_n)

    hist_asof = resolve_effective_trade_date(db, asof, market=market)
    rt_date = str((quote or {}).get("trade_date") or "")[:10]
    # 加载历史时用 max(hist_asof, rt_date) 无意义：hist 表可能无当日；先按 hist 对齐再 merge
    load_asof = hist_asof
    if rt_date and (not asof or str(asof).strip()[:10] == rt_date):
        # 实时模式且未强制历史基准日：加载到 hist 最新，再叠当日实时
        load_asof = hist_asof

    bars_map = batch_load_ohlc_asc(db, [code_n], lookback=lookback, asof=load_asof)
    bars = list(bars_map.get(code_n) or [])
    bars, meta = merge_realtime_into_bars(bars, quote)
    effective = (meta or {}).get("trade_date") or (bars[-1].get("date") if bars else load_asof)
    effective = str(effective)[:10]
    return bars, meta, effective


def apply_realtime_to_code_bars(
    db: Session,
    code: str,
    bars: List[Dict[str, Any]],
    *,
    prefer_live: bool = True,
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """对已加载的 bars 叠加入实时末根。"""
    quote = fetch_live_realtime_quote(db, code) if prefer_live else fetch_db_realtime_quote(db, code)
    return merge_realtime_into_bars(bars, quote)
