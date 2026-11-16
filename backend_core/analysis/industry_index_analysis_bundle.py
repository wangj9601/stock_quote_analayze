# -*- coding: utf-8 -*-
"""行业指数分析：价格行为 + 成分广度。日 K 只来自行业板块指数表。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend_core.analysis.index_analysis_bundle import (
    _build_market_view,
    _compute_breadth_and_leaders,
    _compute_gann_from_bars,
    _compute_pattern_from_bars,
    _compute_swing_from_bars,
)
from backend_core.analysis.industry_index_bars import (
    fetch_industry_board_realtime,
    industry_bar_lookback,
    load_industry_board_ohlc_asc,
    resolve_industry_board_identity,
)

logger = logging.getLogger(__name__)

_REALTIME_REASON = "行业实时行情无开高低，未改写当日K"
_ASSET = "industry_index"


def _norm_stock_code(raw: Any) -> str:
    s = str(raw or "").strip()
    if s.isdigit() and len(s) <= 6:
        return s.zfill(6)
    return s


def _load_industry_constituent_quotes(
    db: Session, board_code: str
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    code = str(board_code or "").strip()
    try:
        cons = db.execute(
            text(
                """
                SELECT stock_code, stock_name
                FROM industry_board_constituents
                WHERE board_code = :c
                """
            ),
            {"c": code},
        ).fetchall()
    except Exception as e:
        logger.warning("industry constituents fail %s: %s", code, e)
        try:
            db.rollback()
        except Exception:
            pass
        return [], "成分表查询失败"

    if not cons:
        return [], "库内暂无该行业成分"

    name_map: Dict[str, str] = {}
    codes: List[str] = []
    for r in cons:
        c = _norm_stock_code(r[0])
        if not c or c in name_map:
            continue
        name_map[c] = str(r[1] or "")
        codes.append(c)
    if not codes:
        return [], "库内暂无该行业成分"

    best: Dict[str, Any] = {}
    try:
        for i in range(0, len(codes), 400):
            chunk = codes[i : i + 400]
            placeholders = ", ".join(f":c{j}" for j in range(len(chunk)))
            params = {f"c{j}": chunk[j] for j in range(len(chunk))}
            rows = db.execute(
                text(
                    f"""
                    SELECT code, name, current_price, change_percent, amount, trade_date
                    FROM stock_realtime_quote
                    WHERE code IN ({placeholders})
                    """
                ),
                params,
            ).fetchall()
            for r in rows:
                c = str(r[0])
                prev = best.get(c)
                if prev is None or str(r[5] or "") > str(prev[5] or ""):
                    best[c] = r
    except Exception as e:
        logger.warning("industry constituent quotes fail %s: %s", code, e)
        try:
            db.rollback()
        except Exception:
            pass
        return [], "成分实时行情不可用"

    out: List[Dict[str, Any]] = []
    for c in codes:
        r = best.get(c)
        pct = None
        amt = 0.0
        price = None
        nm = name_map.get(c) or ""
        if r:
            try:
                pct = float(r[3]) if r[3] is not None else None
            except (TypeError, ValueError):
                pct = None
            try:
                amt = float(r[4] or 0)
            except (TypeError, ValueError):
                amt = 0.0
            try:
                price = float(r[2]) if r[2] is not None else None
            except (TypeError, ValueError):
                price = None
            if r[1]:
                nm = str(r[1])
        out.append(
            {
                "code": c,
                "name": nm,
                "change_percent": pct,
                "amount": amt,
                "current_price": price,
            }
        )
    return out, None


def _attach_official_breadth(
    breadth: Dict[str, Any], quote: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    out = dict(breadth or {})
    out["official_up_count"] = (quote or {}).get("up_count")
    out["official_down_count"] = (quote or {}).get("down_count")
    return out


def _compute_industry_levels(
    db: Session,
    bars: List[Dict[str, Any]],
    *,
    code: str,
    name: str,
    asof: Optional[str],
    anchor: Optional[float],
    realtime_meta: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    from backend_core.analysis.index_analysis_bundle import _bars_for_key_levels

    if not bars or len(bars) < 20:
        return {
            "ok": False,
            "data": None,
            "error": "行业指数日线不足，无法计算阻力支撑",
            "payload": None,
        }
    hist = _bars_for_key_levels(bars)
    try:
        from backend_api.stock.stock_analysis import StockAnalysisService

        with StockAnalysisService(db) as svc:
            result = svc.get_key_levels_only(
                code,
                max_levels=8,
                historical_data=hist,
                price_adjust="none",
                adj_meta=None,
                anchor_price=anchor,
            )
        if result.get("success"):
            data = dict(result.get("data") or {})
            data["code"] = code
            data["name"] = name
            data["stock_code"] = code
            data["stock_name"] = name
            data["asset_type"] = _ASSET
            data["price_adjust"] = "none"
            data["asof"] = asof or (bars[-1].get("date") if bars else "")
            if anchor is not None:
                data["current_price"] = anchor
            if realtime_meta:
                data["realtime"] = realtime_meta
            return {
                "ok": True,
                "data": data,
                "error": None,
                "payload": {"success": True, "data": data, "ok": True, "message": ""},
            }
    except Exception:
        logger.exception("industry key levels fail %s", code)
    return {
        "ok": False,
        "data": None,
        "error": "行业指数阻力支撑计算失败",
        "payload": None,
    }


def build_industry_index_analysis_bundle(
    db: Session,
    *,
    board_code: str,
    date: Optional[str] = None,
    use_realtime: bool = False,
) -> Dict[str, Any]:
    raw = (board_code or "").strip()
    if not raw:
        return {
            "success": False,
            "message": "请提供行业板块代码",
            "http_status": 400,
        }

    ident = resolve_industry_board_identity(db, raw)
    if not ident.get("ok"):
        return {
            "success": False,
            "message": ident.get("message") or "未找到行业板块",
            "http_status": int(ident.get("http_status") or 404),
        }

    code_n = str(ident["code"])
    name_n = str(ident.get("name") or code_n)
    asof_req = None if use_realtime else ((str(date).strip()[:10] if date else None) or None)
    bars = load_industry_board_ohlc_asc(
        db,
        code_n,
        lookback=industry_bar_lookback(),
        asof=asof_req,
    )
    if not bars:
        return {
            "success": False,
            "message": f"行业板块 {code_n} 无可用日线（industry_board_historical_quotes）",
            "http_status": 404,
        }

    quote = fetch_industry_board_realtime(db, code_n)
    asof_eff = asof_req or (bars[-1].get("date") if bars else "")
    anchor = None
    if use_realtime and quote and quote.get("current_price") is not None:
        try:
            anchor = float(quote["current_price"])
        except (TypeError, ValueError):
            anchor = None
    if anchor is None:
        try:
            anchor = float(bars[-1]["close"])
        except (TypeError, ValueError, KeyError, IndexError):
            anchor = None

    realtime_meta = None
    if use_realtime:
        realtime_meta = {
            "merged": False,
            "reason": _REALTIME_REASON,
            "current_price": (quote or {}).get("current_price"),
            "change_percent": (quote or {}).get("change_percent"),
            "source": "industry_board_realtime_quotes",
            "update_time": (quote or {}).get("update_time"),
            "trade_date": (quote or {}).get("trade_date"),
        }

    levels = _compute_industry_levels(
        db,
        bars,
        code=code_n,
        name=name_n,
        asof=asof_eff,
        anchor=anchor,
        realtime_meta=realtime_meta,
    )
    pattern = _compute_pattern_from_bars(
        db,
        bars,
        code=code_n,
        name=name_n,
        asof=asof_eff,
        use_realtime=bool(use_realtime),
        realtime_meta=realtime_meta,
        asset_type=_ASSET,
    )
    bias = None
    if pattern.get("ok") and isinstance(pattern.get("tactical"), dict):
        bias = pattern["tactical"].get("short_bias")
    swing = _compute_swing_from_bars(
        bars,
        code=code_n,
        name=name_n,
        asof=asof_eff,
        use_realtime=bool(use_realtime),
        realtime_meta=realtime_meta,
        pattern_short_bias=str(bias) if bias else None,
        asset_type=_ASSET,
    )
    gann = _compute_gann_from_bars(
        bars,
        code=code_n,
        name=name_n,
        asof=asof_eff,
        use_realtime=bool(use_realtime),
        realtime_meta=realtime_meta,
        asset_type=_ASSET,
    )

    members, cons_reason = _load_industry_constituent_quotes(db, code_n)
    if cons_reason:
        breadth = {
            "available": False,
            "reason": cons_reason,
            "member_count": 0,
            "quoted_count": 0,
        }
        leaders = {"available": False, "gainers": [], "losers": [], "reason": cons_reason}
    else:
        breadth, leaders = _compute_breadth_and_leaders(members)
    breadth = _attach_official_breadth(breadth, quote)

    market_view = _build_market_view(
        code=code_n,
        name=name_n,
        asof=asof_eff,
        levels=levels,
        pattern=pattern,
        swing=swing,
        gann=gann,
        breadth=breadth,
        title="行业环境研判",
    )

    index_info = {
        "code": code_n,
        "name": name_n,
        "asset_type": _ASSET,
        "current": (quote or {}).get("current_price"),
        "change": (quote or {}).get("change"),
        "change_percent": (quote or {}).get("change_percent"),
        "update_time": (quote or {}).get("update_time"),
        "last_close": bars[-1].get("close"),
        "last_date": bars[-1].get("date"),
    }
    return {
        "success": True,
        "data": {
            "index": index_info,
            "trade_date": asof_eff or "",
            "use_realtime": bool(use_realtime),
            "realtime": realtime_meta,
            "bar_count": len(bars),
            "market_view": market_view,
            "breadth": breadth,
            "leaders": leaders,
            "sector_contrib": None,
            "levels": levels,
            "pattern": pattern,
            "swing": swing,
            "gann": gann,
        },
    }
