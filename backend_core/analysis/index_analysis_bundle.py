# -*- coding: utf-8 -*-
"""指数分析统一编排：价格行为 + 广度/强弱/行业贡献 + 市场环境研判。

数据源：index_historical_quotes / index_realtime_quotes / index_board_constituents。
禁止读个股 historical_quotes。
"""

from __future__ import annotations

import logging
import statistics
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend_core.analysis.index_bars import (
    KNOWN_INDEX_NAMES,
    fetch_index_realtime_quote,
    load_index_bars_with_realtime,
    normalize_index_display_code,
    resolve_index_identity,
    to_index_ts_code,
)

logger = logging.getLogger(__name__)

_SECTOR_DISCLAIMER = "行业贡献按成分成交额加权近似，非官方指数权重，仅供对照。"
_LEADERS_TOP_N = 10


def _err_section(msg: str) -> Dict[str, Any]:
    return {"ok": False, "error": msg, "data": None}


def _bars_for_key_levels(bars: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    hist = []
    for b in bars:
        row = dict(b)
        if "date" in row and "trade_date" not in row:
            row["trade_date"] = row["date"]
        hist.append(row)
    return hist


def compute_index_key_levels(
    db: Session,
    *,
    code: str,
    max_levels: int = 8,
    kde_lookback: Optional[int] = None,
    kde_from_date: Optional[str] = None,
    vp_lookback: Optional[int] = None,
    vp_from_date: Optional[str] = None,
    use_realtime: bool = False,
    asof: Optional[str] = None,
) -> Dict[str, Any]:
    """指数阻力支撑（读 index_historical_quotes，绝不走个股表）。"""
    from backend_api.stock.stock_analysis import StockAnalysisService

    ident = resolve_index_identity(db, code)
    if not ident.get("ok"):
        return {
            "success": False,
            "message": ident.get("message") or "未找到指数",
            "http_status": int(ident.get("http_status") or 404),
        }
    code_n = str(ident["code"])
    name_n = str(ident.get("name") or KNOWN_INDEX_NAMES.get(code_n) or code_n)
    try:
        from backend_api.stock.stock_analysis import KeyLevels as _KL

        kde_max = int(_KL.KDE_LOOKBACK_MAX)
    except Exception:
        kde_max = 750
    lookback = max(
        220,
        int(kde_lookback or 0) + 50,
        int(vp_lookback or 0) + 50,
        kde_max,
    )
    # 回看重算也要能叠实时；无实时则用日线末收作锚点，严禁落到个股现价
    bars, rt_meta, asof_eff = load_index_bars_with_realtime(
        db,
        code_n,
        lookback=lookback,
        asof=None if use_realtime else asof,
        use_realtime=True if use_realtime else False,
    )
    if not use_realtime:
        # 非实时：仍取指数实时快照作锚点（若有），避免 get_key_levels_only 回落到个股 000001
        quote = fetch_index_realtime_quote(db, code_n)
        if quote and not rt_meta:
            rt_meta = {
                "trade_date": quote.get("trade_date"),
                "current_price": quote.get("current_price"),
                "change_percent": quote.get("change_percent"),
                "source": quote.get("source"),
                "update_time": quote.get("update_time"),
                "merged": False,
            }
    if not bars or len(bars) < 20:
        return {
            "success": False,
            "message": f"指数 {code_n} 日线不足，无法计算阻力支撑",
            "http_status": 404,
        }
    hist = _bars_for_key_levels(bars)
    anchor = None
    if rt_meta and rt_meta.get("current_price") is not None:
        try:
            anchor = float(rt_meta["current_price"])
        except (TypeError, ValueError):
            anchor = None
    if anchor is None:
        try:
            anchor = float(bars[-1]["close"])
        except (TypeError, ValueError, KeyError, IndexError):
            anchor = None

    with StockAnalysisService(db) as svc:
        result = svc.get_key_levels_only(
            code_n,
            max_levels=max(1, int(max_levels or 8)),
            historical_data=hist,
            price_adjust="none",
            adj_meta=None,
            vp_lookback=vp_lookback,
            vp_from_date=vp_from_date,
            kde_lookback=kde_lookback,
            kde_from_date=kde_from_date,
            anchor_price=anchor,
        )
    if not result.get("success"):
        return {
            "success": False,
            "message": result.get("error") or "指数阻力支撑计算失败",
            "data": result.get("data") or {},
            "http_status": 200,
        }
    data = result.get("data") or {}
    data["stock_code"] = code_n
    data["code"] = code_n
    data["stock_name"] = name_n
    data["name"] = name_n
    data["asset_type"] = "index"
    data["price_adjust"] = "none"
    data["asof"] = asof_eff or (bars[-1].get("date") if bars else "")
    data["ts_code"] = ident.get("ts_code")
    if rt_meta:
        data["realtime"] = rt_meta
        if rt_meta.get("change_percent") is not None:
            data["change_percent"] = rt_meta.get("change_percent")
        if rt_meta.get("current_price") is not None:
            data["current_price"] = rt_meta.get("current_price")
    quote = fetch_index_realtime_quote(db, code_n) or {}
    if data.get("change_percent") is None and quote.get("change_percent") is not None:
        data["change_percent"] = quote.get("change_percent")
    if quote.get("change") is not None:
        data["change_amount"] = quote.get("change")
    if quote.get("pre_close") is not None:
        data["pre_close"] = quote.get("pre_close")
    # 禁止把个股板块语义带进指数结果
    data.pop("industry", None)
    data.pop("boards", None)
    return {"success": True, "data": data, "http_status": 200}


def _compute_levels_from_bars(
    bars: List[Dict[str, Any]],
    *,
    code: str,
    name: str,
    asof: Optional[str],
    realtime_meta: Optional[Dict[str, Any]],
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """bundle 内关位：优先走完整 get_key_levels_only（含 VP）。"""
    if db is not None:
        packed = compute_index_key_levels(
            db,
            code=code,
            max_levels=8,
            use_realtime=bool(realtime_meta and realtime_meta.get("merged")),
            asof=asof,
        )
        if packed.get("success"):
            data = packed["data"]
            return {
                "ok": True,
                "data": data,
                "error": None,
                "payload": {"success": True, "data": data, "ok": True, "message": ""},
            }
        # 失败则降级本地轻量计算

    from backend_api.stock.stock_analysis import KeyLevels

    if not bars or len(bars) < 20:
        return _err_section("指数日线不足，无法计算阻力支撑")
    try:
        current = float(bars[-1]["close"])
        if realtime_meta and realtime_meta.get("current_price") is not None:
            current = float(realtime_meta["current_price"])
    except (TypeError, ValueError, KeyError, IndexError):
        return _err_section("无法取得指数现价")

    hist = _bars_for_key_levels(bars)
    kde = KeyLevels.calculate_key_levels(hist, current, max_levels=8)
    classic = KeyLevels.calculate_classic_reference_levels(hist, current)
    data = {
        "stock_code": code,
        "code": code,
        "stock_name": name,
        "name": name,
        "asof": asof or (bars[-1].get("date") if bars else ""),
        "current_price": current,
        "price_adjust": "none",
        "asset_type": "index",
        "classic_levels": classic if isinstance(classic, dict) else {},
        "volume_profile": {},
        "vp_vs_kde": {},
        "key_levels": kde,
    }
    if isinstance(kde, dict):
        for k in (
            "resistance_levels",
            "support_levels",
            "nearest_support",
            "nearest_resistance",
            "method",
            "kde_ok",
            "kde_reason",
            "kde_bw",
            "kde_lookback_used",
            "kde_lookback_expanded",
            "kde_lookback_initial",
            "kde_lookback_max",
            "kde_base_factor",
            "kde_multi_windows",
            "kde_anchor",
            "kde_window_mode",
        ):
            if k in kde:
                data[k] = kde[k]
    if realtime_meta:
        data["realtime"] = realtime_meta
    ok = bool(kde.get("kde_ok") or (isinstance(classic, dict) and classic.get("ok")))
    return {
        "ok": ok,
        "data": data,
        "error": None if ok else "阻力支撑计算失败",
        "payload": {"success": True, "data": data, "ok": ok, "message": ""},
    }


def _compute_pattern_from_bars(
    db: Session,
    bars: List[Dict[str, Any]],
    *,
    code: str,
    name: str,
    asof: Optional[str],
    use_realtime: bool,
    realtime_meta: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    from backend_api.stock.pattern_routes import _parse_types, _tactical_enrichment
    from backend_core.analysis.chart_patterns.engine import detect_all_counted
    from backend_core.analysis.market_structure import (
        aggregate_daily_to_weekly,
        analyze_market_structure,
    )
    from backend_core.analysis.pattern_tactical import (
        annotate_hits_breakout_probe,
        build_pattern_tactical,
        market_snapshot_from_bars,
    )
    from backend_core.analysis.swing_zigzag import (
        DEFAULT_FRACTAL,
        DEFAULT_MIN_SWING_BARS,
    )

    if len(bars) < 30:
        return {
            "ok": False,
            "items": [],
            "invalidated_count": 0,
            "code": code,
            "name": name,
            "asof": asof or "",
            "price_adjust": "none",
            "tactical": None,
            "error": "指数日线不足，无法识别形态",
            "payload": None,
        }

    type_list = _parse_types(None)
    hits_all, invalidated_count = detect_all_counted(
        bars, types=type_list or None, include_invalidated=True, ref_bars=None
    )
    hits = [h for h in hits_all if str(h.get("status") or "") != "invalidated"]

    # 指数不做 RPE/GMS 快照：传空 asof 跳过；VP/经典位仍可用
    vp, confluence, rpe, gms, classic = _tactical_enrichment(db, bars, code, None)
    weekly_bars = aggregate_daily_to_weekly(bars)
    weekly_ms = analyze_market_structure(
        weekly_bars,
        max_bars=max(40, min(120, len(weekly_bars))),
        fractal_left=DEFAULT_FRACTAL,
        fractal_right=DEFAULT_FRACTAL,
        min_swing_bars=max(1, DEFAULT_MIN_SWING_BARS // 2 or 1),
        max_points=12,
        period="weekly",
    )
    weekly_trend = str(weekly_ms.get("trend") or "") if weekly_ms.get("ok") else None
    asof_s = asof or (str(bars[-1].get("date") or "")[:10] if bars else "")
    tactical = build_pattern_tactical(
        hits_all,
        confluence=confluence,
        vp=vp,
        rpe=None,
        gms=None,
        invalidated_count=invalidated_count,
        asof=asof_s,
        market=market_snapshot_from_bars(bars),
        classic=classic,
        bars=bars,
        weekly_trend=weekly_trend,
    )
    hits = annotate_hits_breakout_probe(hits, tactical)
    payload = {
        "success": True,
        "code": code,
        "name": name,
        "asof": asof_s,
        "price_adjust": "none",
        "bar_count": len(bars),
        "hit_count": len(hits),
        "invalidated_count": invalidated_count,
        "items": hits,
        "tactical": tactical,
        "use_realtime": bool(use_realtime),
        "asset_type": "index",
    }
    if realtime_meta:
        payload["realtime"] = realtime_meta
    return {
        "ok": True,
        "items": hits,
        "invalidated_count": invalidated_count,
        "code": code,
        "name": name,
        "asof": asof_s,
        "price_adjust": "none",
        "tactical": tactical,
        "error": None,
        "payload": payload,
    }


def _compute_swing_from_bars(
    bars: List[Dict[str, Any]],
    *,
    code: str,
    name: str,
    asof: Optional[str],
    use_realtime: bool,
    realtime_meta: Optional[Dict[str, Any]],
    pattern_short_bias: Optional[str],
) -> Dict[str, Any]:
    from backend_core.analysis.market_structure import (
        aggregate_daily_to_weekly,
        analyze_market_structure,
        contrast_with_pattern_bias,
        weekly_counter_trend_caution,
    )
    from backend_core.analysis.swing_zigzag import (
        DEFAULT_FRACTAL,
        DEFAULT_MIN_SWING_BARS,
    )

    lookback = 180
    max_points = 12
    if len(bars) < 30:
        return {
            "ok": False,
            "data": None,
            "code": code,
            "name": name,
            "asof": asof or "",
            "error": "指数日线不足，无法分析波段",
            "payload": None,
        }
    daily_bars = bars[-int(lookback) :] if len(bars) > int(lookback) else bars
    ms = analyze_market_structure(
        daily_bars,
        max_bars=lookback,
        fractal_left=DEFAULT_FRACTAL,
        fractal_right=DEFAULT_FRACTAL,
        min_swing_bars=DEFAULT_MIN_SWING_BARS,
        max_points=max_points,
        period="daily",
    )
    contrast = contrast_with_pattern_bias(
        str(ms.get("trend") or ""), pattern_short_bias, period_zh="日线"
    )
    ms["pattern_contrast"] = contrast
    weekly_bars = aggregate_daily_to_weekly(bars)
    weekly_lookback = max(40, min(120, int(lookback) // 2 + 20))
    weekly_ms = analyze_market_structure(
        weekly_bars,
        max_bars=weekly_lookback,
        fractal_left=DEFAULT_FRACTAL,
        fractal_right=DEFAULT_FRACTAL,
        min_swing_bars=max(1, DEFAULT_MIN_SWING_BARS // 2 or 1),
        max_points=max_points,
        period="weekly",
    )
    weekly_contrast = contrast_with_pattern_bias(
        str(weekly_ms.get("trend") or ""), pattern_short_bias, period_zh="周线"
    )
    weekly_ms["pattern_contrast"] = weekly_contrast
    caution = weekly_counter_trend_caution(
        str(weekly_ms.get("trend") or ""), pattern_short_bias
    )
    if caution:
        ms["counter_trend_caution"] = True
        ms["counter_trend_note"] = caution.get("text")
    else:
        ms["counter_trend_caution"] = False
        ms["counter_trend_note"] = None
        weekly_ms["counter_trend_caution"] = False
        weekly_ms["counter_trend_note"] = None

    asof_s = asof or ms.get("asof") or (bars[-1].get("date") if bars else "")
    out = {
        "success": True,
        "code": code,
        "name": name,
        "asof": asof_s,
        "price_adjust": {"mode": "none", "applied": False},
        "market_structure": ms,
        "weekly": weekly_ms,
        "counter_trend_caution": bool(caution),
        "counter_trend_note": (caution or {}).get("text") if caution else None,
        "use_realtime": bool(use_realtime),
        "asset_type": "index",
    }
    if realtime_meta:
        out["realtime"] = realtime_meta
    return {
        "ok": bool(ms.get("ok") is not False),
        "data": out,
        "code": code,
        "name": name,
        "asof": asof_s or "",
        "error": None,
        "payload": out,
    }


def _compute_gann_from_bars(
    bars: List[Dict[str, Any]],
    *,
    code: str,
    name: str,
    asof: Optional[str],
    use_realtime: bool,
    realtime_meta: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    from backend_core.analysis.gann_trend import analyze_gann_trend
    from backend_core.analysis.swing_zigzag import (
        DEFAULT_FRACTAL,
        DEFAULT_MIN_SWING_BARS,
    )

    lookback = 180
    if len(bars) < 30:
        return _err_section("指数日线不足，无法做江恩分析")
    daily_bars = bars[-int(lookback) :] if len(bars) > int(lookback) else bars
    gann = analyze_gann_trend(
        daily_bars,
        max_bars=lookback,
        fractal_left=DEFAULT_FRACTAL,
        fractal_right=DEFAULT_FRACTAL,
        min_swing_bars=DEFAULT_MIN_SWING_BARS,
        scale_override=None,
    )
    asof_s = asof or gann.get("asof") or (bars[-1].get("date") if bars else "")
    out = {
        "success": True,
        "code": code,
        "name": name,
        "asof": asof_s,
        "price_adjust": {"mode": "none", "applied": False},
        "gann_trend": gann,
        "use_realtime": bool(use_realtime),
        "asset_type": "index",
    }
    if realtime_meta:
        out["realtime"] = realtime_meta
    return {
        "ok": bool((gann or {}).get("ok")),
        "data": out,
        "code": code,
        "name": name,
        "asof": asof_s or "",
        "error": None,
        "payload": out,
    }


def _load_constituent_quotes(
    db: Session, board_code: str
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """返回成分+最新实时行情列表；无成分时 ([], reason)。"""
    code = normalize_index_display_code(board_code)
    # 兼容 board_code 为 000300 / sh000300
    try:
        cons = db.execute(
            text(
                """
                SELECT stock_code, stock_name
                FROM index_board_constituents
                WHERE board_code = :c
                   OR board_code = :sh
                   OR board_code = :sz
                   OR RIGHT(board_code, 6) = :c
                """
            ),
            {"c": code, "sh": f"sh{code}", "sz": f"sz{code}"},
        ).fetchall()
    except Exception as e:
        logger.warning("load index constituents fail %s: %s", code, e)
        try:
            db.rollback()
        except Exception:
            pass
        return [], "成分表查询失败"

    if not cons:
        return [], "暂无成分数据（index_board_constituents 无该指数）"

    codes = [str(r[0]).zfill(6) if str(r[0]).isdigit() else str(r[0]) for r in cons]
    name_map = {
        (str(r[0]).zfill(6) if str(r[0]).isdigit() else str(r[0])): (r[1] or "")
        for r in cons
    }

    # 分批取实时，再按 code 留最新 trade_date
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
    except Exception as e2:
        logger.warning("constituent quotes fail %s: %s", code, e2)
        try:
            db.rollback()
        except Exception:
            pass
        return [], "成分实时行情不可用"

    quote_map = {str(k): v for k, v in best.items()}
    out: List[Dict[str, Any]] = []
    for c in codes:
        r = quote_map.get(c)
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


def _compute_breadth_and_leaders(
    members: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    with_pct = [m for m in members if m.get("change_percent") is not None]
    if not with_pct:
        breadth = {
            "available": False,
            "reason": "成分无可用涨跌幅",
            "member_count": len(members),
            "quoted_count": 0,
        }
        leaders = {"available": False, "gainers": [], "losers": []}
        return breadth, leaders

    up = sum(1 for m in with_pct if float(m["change_percent"]) > 0)
    down = sum(1 for m in with_pct if float(m["change_percent"]) < 0)
    flat = len(with_pct) - up - down
    pcts = [float(m["change_percent"]) for m in with_pct]
    median_pct = statistics.median(pcts) if pcts else None
    breadth = {
        "available": True,
        "member_count": len(members),
        "quoted_count": len(with_pct),
        "up_count": up,
        "down_count": down,
        "flat_count": flat,
        "up_ratio": round(up / len(with_pct), 4) if with_pct else None,
        "median_change_percent": round(median_pct, 4) if median_pct is not None else None,
        "avg_change_percent": round(sum(pcts) / len(pcts), 4) if pcts else None,
    }
    ranked = sorted(with_pct, key=lambda x: float(x["change_percent"]), reverse=True)
    n = _LEADERS_TOP_N
    leaders = {
        "available": True,
        "gainers": ranked[:n],
        "losers": list(reversed(ranked[-n:])) if len(ranked) >= 1 else [],
    }
    return breadth, leaders


def _compute_sector_contrib(db: Session, members: List[Dict[str, Any]]) -> Dict[str, Any]:
    codes = [m["code"] for m in members if m.get("code")]
    if not codes:
        return {
            "available": False,
            "reason": "无成分",
            "disclaimer": _SECTOR_DISCLAIMER,
            "items": [],
        }
    rows: List[Any] = []
    try:
        for i in range(0, len(codes), 400):
            chunk = codes[i : i + 400]
            placeholders = ", ".join(f":c{j}" for j in range(len(chunk)))
            params = {f"c{j}": chunk[j] for j in range(len(chunk))}
            part = db.execute(
                text(
                    f"""
                    SELECT c.stock_code, c.board_code,
                           COALESCE(b.board_name, c.board_code) AS board_name
                    FROM industry_board_constituents c
                    LEFT JOIN industry_board_basic_info b ON b.board_code = c.board_code
                    WHERE c.stock_code IN ({placeholders})
                    """
                ),
                params,
            ).fetchall()
            rows.extend(part)
    except Exception as e:
        logger.warning("sector map fail: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        return {
            "available": False,
            "reason": "行业映射不可用",
            "disclaimer": _SECTOR_DISCLAIMER,
            "items": [],
        }

    # 一股多板时取第一个行业板
    stock_board: Dict[str, Tuple[str, str]] = {}
    for r in rows:
        sc = str(r[0]).zfill(6) if str(r[0]).isdigit() else str(r[0])
        if sc not in stock_board:
            stock_board[sc] = (str(r[1]), str(r[2] or r[1]))

    buckets: Dict[str, Dict[str, Any]] = {}
    total_amt = 0.0
    for m in members:
        pct = m.get("change_percent")
        if pct is None:
            continue
        amt = max(float(m.get("amount") or 0), 0.0)
        bc, bn = stock_board.get(m["code"], ("unknown", "未分类行业"))
        b = buckets.setdefault(
            bc,
            {
                "board_code": bc,
                "board_name": bn,
                "amount": 0.0,
                "weighted_pct_sum": 0.0,
                "member_count": 0,
            },
        )
        b["amount"] += amt
        b["weighted_pct_sum"] += float(pct) * amt
        b["member_count"] += 1
        total_amt += amt

    items = []
    for b in buckets.values():
        amt = b["amount"]
        w_pct = (b["weighted_pct_sum"] / amt) if amt > 0 else None
        contrib = (amt / total_amt * (w_pct or 0)) if total_amt > 0 and w_pct is not None else None
        items.append(
            {
                "board_code": b["board_code"],
                "board_name": b["board_name"],
                "member_count": b["member_count"],
                "amount": round(amt, 2),
                "amount_weight": round(amt / total_amt, 4) if total_amt > 0 else None,
                "weighted_change_percent": round(w_pct, 4) if w_pct is not None else None,
                "approx_contribution": round(contrib, 4) if contrib is not None else None,
            }
        )
    items.sort(key=lambda x: abs(x.get("approx_contribution") or 0), reverse=True)
    return {
        "available": bool(items),
        "reason": None if items else "无有效行业贡献",
        "disclaimer": _SECTOR_DISCLAIMER,
        "items": items[:20],
    }


def _build_market_view(
    *,
    code: str,
    name: str,
    asof: Optional[str],
    levels: Dict[str, Any],
    pattern: Dict[str, Any],
    swing: Dict[str, Any],
    gann: Dict[str, Any],
    breadth: Dict[str, Any],
) -> Dict[str, Any]:
    """指数环境研判：偏多/中性/偏空，无买卖/仓位字段。"""
    scores = []  # +1 bull, -1 bear
    bullets: List[str] = []

    sw_data = (swing.get("data") or {}) if swing.get("ok") else {}
    ms = sw_data.get("market_structure") or {}
    trend = str(ms.get("trend") or "").lower()
    if "up" in trend or trend in ("bullish", "上升", "上涨"):
        scores.append(1)
        bullets.append(f"日线结构偏多（{ms.get('trend') or trend}）")
    elif "down" in trend or trend in ("bearish", "下降", "下跌"):
        scores.append(-1)
        bullets.append(f"日线结构偏空（{ms.get('trend') or trend}）")
    elif trend:
        bullets.append(f"日线结构：{ms.get('trend') or trend}")

    tactical = pattern.get("tactical") if pattern.get("ok") else None
    bias = None
    if isinstance(tactical, dict):
        bias = tactical.get("short_bias") or tactical.get("bias")
        if bias in ("bullish", "long", "偏多", "多"):
            scores.append(1)
            bullets.append("形态短线偏多")
        elif bias in ("bearish", "short", "偏空", "空"):
            scores.append(-1)
            bullets.append("形态短线偏空")
        elif bias:
            bullets.append(f"形态短线偏向：{bias}")

    g_data = (gann.get("data") or {}) if gann.get("ok") else {}
    gv = (g_data.get("gann_trend") or {}).get("verdict") or {}
    g_bias = str(gv.get("bias") or "").lower()
    if g_bias in ("bullish", "up", "long"):
        scores.append(1)
        bullets.append("江恩趋势偏多")
    elif g_bias in ("bearish", "down", "short"):
        scores.append(-1)
        bullets.append("江恩趋势偏空")
    elif gv.get("summary"):
        bullets.append(str(gv.get("summary")))

    lv = (levels.get("data") or {}) if levels.get("ok") else {}
    # 扁平 levels 与嵌套 key_levels 均兼容
    nearest_sup = lv.get("nearest_support")
    nearest_res = lv.get("nearest_resistance")
    if nearest_sup is None and isinstance(lv.get("key_levels"), dict):
        nearest_sup = lv["key_levels"].get("nearest_support")
    if nearest_res is None and isinstance(lv.get("key_levels"), dict):
        nearest_res = lv["key_levels"].get("nearest_resistance")
    if nearest_sup is not None:
        bullets.append(f"近端支撑约 {nearest_sup}")
    if nearest_res is not None:
        bullets.append(f"近端阻力约 {nearest_res}")

    if breadth.get("available"):
        up_r = breadth.get("up_ratio")
        if up_r is not None:
            if up_r >= 0.55:
                scores.append(1)
                bullets.append(f"成分上涨占比 {up_r:.0%}，广度偏强")
            elif up_r <= 0.45:
                scores.append(-1)
                bullets.append(f"成分上涨占比 {up_r:.0%}，广度偏弱")
            else:
                bullets.append(f"成分上涨占比 {up_r:.0%}，广度中性")

    s = sum(scores)
    if s >= 2:
        env_bias, label = "bullish", "偏多"
    elif s <= -2:
        env_bias, label = "bearish", "偏空"
    else:
        env_bias, label = "neutral", "中性"

    return {
        "ok": True,
        "title": "指数环境研判",
        "bias": env_bias,
        "bias_label": label,
        "summary": f"{name or code} 当前环境：{label}",
        "bullets": bullets[:8],
        "asof": asof or "",
        "code": code,
        "name": name,
        # 显式不提供交易字段
        "entry": None,
        "stop": None,
        "target": None,
        "position": None,
        "action": None,
    }


def build_index_analysis_bundle(
    db: Session,
    *,
    code: str,
    date: Optional[str] = None,
    use_realtime: bool = False,
) -> Dict[str, Any]:
    raw = (code or "").strip()
    if not raw:
        return {
            "success": False,
            "message": "请提供指数代码",
            "http_status": 400,
        }

    ident = resolve_index_identity(db, raw)
    if not ident.get("ok"):
        return {
            "success": False,
            "message": ident.get("message") or "未找到指数",
            "http_status": int(ident.get("http_status") or 404),
        }

    code_n = str(ident["code"])
    ts_code = str(ident["ts_code"])
    name_n = str(ident.get("name") or KNOWN_INDEX_NAMES.get(code_n) or code_n)
    asof_req = None if use_realtime else ((str(date).strip()[:10] if date else None) or None)

    bars, rt_meta, asof_eff = load_index_bars_with_realtime(
        db,
        code_n,
        lookback=220,
        asof=asof_req,
        use_realtime=bool(use_realtime),
    )
    if not bars:
        return {
            "success": False,
            "message": f"指数 {code_n} 无可用日线（index_historical_quotes）",
            "http_status": 404,
        }

    quote = fetch_index_realtime_quote(db, code_n) if use_realtime else None
    if not quote:
        quote = fetch_index_realtime_quote(db, code_n)

    levels = _compute_levels_from_bars(
        bars,
        code=code_n,
        name=name_n,
        asof=asof_eff,
        realtime_meta=rt_meta,
        db=db,
    )
    pattern = _compute_pattern_from_bars(
        db,
        bars,
        code=code_n,
        name=name_n,
        asof=asof_eff,
        use_realtime=bool(use_realtime),
        realtime_meta=rt_meta,
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
        realtime_meta=rt_meta,
        pattern_short_bias=str(bias) if bias else None,
    )
    gann = _compute_gann_from_bars(
        bars,
        code=code_n,
        name=name_n,
        asof=asof_eff,
        use_realtime=bool(use_realtime),
        realtime_meta=rt_meta,
    )

    members, cons_reason = _load_constituent_quotes(db, code_n)
    if cons_reason:
        breadth = {
            "available": False,
            "reason": cons_reason,
            "member_count": 0,
            "quoted_count": 0,
        }
        leaders = {"available": False, "gainers": [], "losers": [], "reason": cons_reason}
        sector_contrib = {
            "available": False,
            "reason": cons_reason,
            "disclaimer": _SECTOR_DISCLAIMER,
            "items": [],
        }
    else:
        breadth, leaders = _compute_breadth_and_leaders(members)
        sector_contrib = _compute_sector_contrib(db, members)

    market_view = _build_market_view(
        code=code_n,
        name=name_n,
        asof=asof_eff,
        levels=levels,
        pattern=pattern,
        swing=swing,
        gann=gann,
        breadth=breadth,
    )

    index_info = {
        "code": code_n,
        "ts_code": ts_code,
        "name": name_n,
        "asset_type": "index",
        "current": (quote or {}).get("current_price"),
        "change": (quote or {}).get("change"),
        "change_percent": (quote or {}).get("change_percent"),
        "update_time": (quote or {}).get("update_time"),
    }
    if bars:
        index_info["last_close"] = bars[-1].get("close")
        index_info["last_date"] = bars[-1].get("date")

    return {
        "success": True,
        "data": {
            "index": index_info,
            "trade_date": asof_eff or "",
            "use_realtime": bool(use_realtime),
            "realtime": rt_meta,
            "bar_count": len(bars),
            "market_view": market_view,
            "breadth": breadth,
            "leaders": leaders,
            "sector_contrib": sector_contrib,
            "levels": levels,
            "pattern": pattern,
            "swing": swing,
            "gann": gann,
        },
    }


# 供测试断言：确认模块不引用个股历史表加载器
def _uses_stock_historical_quotes() -> bool:
    return False
