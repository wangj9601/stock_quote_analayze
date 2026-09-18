# -*- coding: utf-8 -*-
"""个股分析统一编排：四策略 + 明细模块 + 综合交易计划。

供 GET /api/analysis/stock-analysis-bundle 调用；明细任务各自独立 Session，避免跨线程共用。
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_DETAIL_WORKERS = 5
# levels KDE 上限 750；pattern/swing/gann 取末段切片
_SHARED_BARS_LOOKBACK = 750


def _session_local():
    from backend_api.database import SessionLocal

    return SessionLocal()


def _err_section(message: str) -> Dict[str, Any]:
    return {"ok": False, "error": message or "失败", "payload": None}


def _strategy_snapshots_from_data(strategy_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """从 collect_stock_multi_strategy_check 结果提取 gms/rpe 摘要，供形态战术层复用。"""
    out: Dict[str, Any] = {}
    if not isinstance(strategy_data, dict):
        return out
    results = strategy_data.get("results")
    if isinstance(results, list):
        for r in results:
            if not isinstance(r, dict):
                continue
            key = str(r.get("strategy") or "").strip().lower()
            if key in ("gms", "rpe"):
                out[key] = r
    summaries = strategy_data.get("summaries")
    if isinstance(summaries, dict):
        for key in ("gms", "rpe"):
            if key not in out and isinstance(summaries.get(key), dict):
                out[key] = summaries[key]
    return out


def _prepare_shared_bars(
    db: Session,
    code: str,
    name: str = "",
    *,
    asof: Optional[str],
    use_realtime: bool,
    lookback: int = _SHARED_BARS_LOOKBACK,
) -> Dict[str, Any]:
    """一次加载 OHLC（+ 可选实时末根）并按需前复权，供 levels/pattern/swing/gann 复用。"""
    from backend_core.analysis.chart_patterns.scanner import (
        apply_qfq_to_code_bars,
        normalize_price_adjust,
    )
    from backend_core.strategies.double_bottom.data_loader import (
        batch_load_ohlc_asc,
        load_names,
        resolve_effective_trade_date,
    )

    try:
        from backend_api.utils.adj_quotes import AdjQuotesError
    except ImportError:
        from utils.adj_quotes import AdjQuotesError  # type: ignore
    try:
        from backend_api.utils.equity_code import (
            infer_market_type,
            normalize_equity_code,
        )
    except ImportError:
        from utils.equity_code import (  # type: ignore
            infer_market_type,
            normalize_equity_code,
        )

    adjust_n = normalize_price_adjust("none" if use_realtime else "qfq")
    stock_code = normalize_equity_code(code) or str(code).strip()
    market = infer_market_type(stock_code) or "CN"
    lb = max(60, int(lookback))
    realtime_meta: Optional[Dict[str, Any]] = None

    if use_realtime and not asof:
        from backend_core.analysis.realtime_bars import load_bars_with_realtime

        bars_raw, realtime_meta, asof_s = load_bars_with_realtime(
            db, stock_code, lookback=lb, asof=None, prefer_live=True
        )
    else:
        asof_s = resolve_effective_trade_date(db, asof, market=market)
        bars_map = batch_load_ohlc_asc(db, [stock_code], lookback=lb, asof=asof_s)
        bars_raw = list(bars_map.get(stock_code) or [])
        if use_realtime:
            from backend_core.analysis.realtime_bars import apply_realtime_to_code_bars

            bars_raw, realtime_meta = apply_realtime_to_code_bars(
                db, stock_code, bars_raw, prefer_live=True
            )
            if realtime_meta and realtime_meta.get("trade_date"):
                asof_s = str(realtime_meta["trade_date"])[:10]

    bars_raw = list(bars_raw or [])
    adj_meta: Optional[Dict[str, Any]] = None
    bars_adj = list(bars_raw)
    if adjust_n == "qfq" and bars_raw:
        try:
            bars_adj, adj_meta = apply_qfq_to_code_bars(
                db,
                stock_code,
                bars_raw,
                refresh_factor=False,
                factor_source="auto",
            )
        except AdjQuotesError:
            raise
        except Exception as e:
            logger.warning("shared bars qfq failed code=%s: %s", stock_code, e)
            bars_adj = list(bars_raw)
            adjust_n = "none"

    names = load_names(db, [stock_code])
    return {
        "code": stock_code,
        "name": names.get(stock_code) or name or "",
        "asof": asof_s,
        "market": market,
        "adjust": adjust_n,
        "bars_raw": bars_raw,
        "bars": bars_adj,
        "adj_meta": adj_meta,
        "realtime_meta": realtime_meta,
        "lookback": lb,
    }


def _compute_rs(db: Session, code: str, name: str, asof: Optional[str], market: str) -> Dict[str, Any]:
    from backend_core.indicators.rs_rating.service import get_rs_rating_for_stock

    code_n = str(code).strip()
    market_u = (market or "CN").upper()
    is_hk = market_u == "HK" or (len(code_n) == 5 and code_n.isdigit())
    is_cn = market_u != "HK" and len(code_n) == 6 and code_n.isdigit()
    if not is_hk and not is_cn:
        return {
            "ok": False,
            "data": None,
            "reason": "market_unsupported",
            "error": "相对强度 RS Rating 仅支持 A 股（6 位）或港股（5 位）",
            "payload": None,
        }
    result = get_rs_rating_for_stock(
        db,
        code_n,
        asof=asof,
        market_type="HK" if is_hk else "CN",
    )
    if not result.get("success") and result.get("reason") == "not_found":
        return {
            "ok": False,
            "data": None,
            "reason": result.get("reason"),
            "error": result.get("message") or "尚未预计算",
            "payload": {
                "success": False,
                "message": result.get("message") or "尚未预计算",
                "reason": result.get("reason"),
                "code": code_n,
                "name": name,
                "data": None,
            },
        }
    data = result.get("data") or {}
    if name and "name" not in data:
        data["name"] = name
    payload = {
        "success": True,
        "message": result.get("message") or "ok",
        "reason": result.get("reason"),
        "data": data,
    }
    return {
        "ok": True,
        "data": data,
        "reason": result.get("reason"),
        "error": None,
        "payload": payload,
    }


def _compute_fund_flow(db: Session, code: str) -> Dict[str, Any]:
    from backend_api.stock.stock_fund_flow import compute_daily_fund_flow

    body = compute_daily_fund_flow(db, code, days=20)
    if not body.get("success"):
        return {
            "ok": False,
            "data": None,
            "error": body.get("message") or "资金流向加载失败",
            "payload": body,
        }
    return {
        "ok": True,
        "data": body.get("data") or {},
        "error": None,
        "payload": body,
    }


def _compute_levels(
    db: Session,
    code: str,
    *,
    use_realtime: bool,
    shared_bars: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from backend_api.stock.stock_analysis_routes import _compute_levels_payload

    adjust = "none" if use_realtime else "qfq"
    hist = None
    adj_meta = None
    anchor = None
    skip_quote = False
    if isinstance(shared_bars, dict) and shared_bars.get("bars"):
        hist = list(shared_bars.get("bars") or [])
        adj_meta = shared_bars.get("adj_meta")
        adjust = str(shared_bars.get("adjust") or adjust)
        rt = shared_bars.get("realtime_meta") or {}
        if use_realtime and rt.get("current_price") is not None:
            try:
                anchor = float(rt["current_price"])
                skip_quote = True
            except (TypeError, ValueError):
                anchor = None
    status, body = _compute_levels_payload(
        code,
        8,
        db=db,
        adjust=adjust,
        factor_source="auto",
        use_realtime=bool(use_realtime),
        historical_data=hist,
        adj_meta=adj_meta,
        anchor_price=anchor,
        skip_external_quote=skip_quote,
    )
    ok = bool(body.get("success") is not False and body.get("data"))
    fetched = {
        "httpOk": int(status) < 400,
        "ok": ok,
        "data": body.get("data") or {},
        "message": body.get("message") or "",
        "candidates": body.get("candidates") or [],
        "payload": body,
    }
    return {
        "ok": ok,
        "data": body.get("data") if ok else (body.get("data") or None),
        "error": None if ok else (body.get("message") or "阻力支撑计算失败"),
        "payload": fetched,
    }


def _compute_pattern(
    db: Session,
    code: str,
    name: str,
    *,
    asof: Optional[str],
    use_realtime: bool,
    shared_bars: Optional[Dict[str, Any]] = None,
    strategy_snapshots: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from backend_api.stock.pattern_routes import _parse_types, _tactical_enrichment
    from backend_core.analysis.chart_patterns.engine import detect_all_counted
    from backend_core.analysis.chart_patterns.scanner import (
        apply_qfq_to_code_bars,
        normalize_price_adjust,
    )
    from backend_core.strategies.double_bottom.data_loader import (
        batch_load_ohlc_asc,
        load_names,
        resolve_effective_trade_date,
    )

    try:
        from backend_api.utils.adj_quotes import AdjQuotesError
    except ImportError:
        from utils.adj_quotes import AdjQuotesError  # type: ignore
    try:
        from backend_api.utils.equity_code import (
            infer_market_type,
            normalize_equity_code,
        )
    except ImportError:
        from utils.equity_code import (  # type: ignore
            infer_market_type,
            normalize_equity_code,
        )

    lookback = 160
    stock_code = normalize_equity_code(code) or str(code).strip()
    realtime_meta: Optional[Dict[str, Any]] = None
    adj_meta: Optional[Dict[str, Any]] = None
    bars_raw: List[Dict[str, Any]] = []
    bars: List[Dict[str, Any]] = []
    asof_s: Optional[str] = None
    adjust_n = normalize_price_adjust("none" if use_realtime else "qfq")
    resolved_name = name or ""

    if isinstance(shared_bars, dict) and (
        shared_bars.get("bars") or shared_bars.get("bars_raw")
    ):
        stock_code = str(shared_bars.get("code") or stock_code)
        resolved_name = shared_bars.get("name") or resolved_name
        asof_s = shared_bars.get("asof")
        adjust_n = normalize_price_adjust(
            shared_bars.get("adjust") or ("none" if use_realtime else "qfq")
        )
        bars_raw = list(shared_bars.get("bars_raw") or [])
        bars_full = list(shared_bars.get("bars") or bars_raw)
        bars = bars_full[-lookback:] if len(bars_full) > lookback else bars_full
        if bars_raw and len(bars_raw) > lookback:
            bars_raw = bars_raw[-lookback:]
        adj_meta = shared_bars.get("adj_meta")
        realtime_meta = shared_bars.get("realtime_meta")
    else:
        market = infer_market_type(stock_code) or "CN"
        if use_realtime and not asof:
            from backend_core.analysis.realtime_bars import load_bars_with_realtime

            bars, realtime_meta, asof_s = load_bars_with_realtime(
                db, stock_code, lookback=lookback, asof=None, prefer_live=True
            )
        else:
            asof_s = resolve_effective_trade_date(db, asof, market=market)
            bars_map = batch_load_ohlc_asc(db, [stock_code], lookback=lookback, asof=asof_s)
            bars = bars_map.get(stock_code) or []
            if use_realtime:
                from backend_core.analysis.realtime_bars import apply_realtime_to_code_bars

                bars, realtime_meta = apply_realtime_to_code_bars(
                    db, stock_code, bars, prefer_live=True
                )
                if realtime_meta and realtime_meta.get("trade_date"):
                    asof_s = str(realtime_meta["trade_date"])[:10]
        bars_raw = list(bars)
        if adjust_n == "qfq":
            try:
                bars, adj_meta = apply_qfq_to_code_bars(
                    db,
                    stock_code,
                    bars,
                    refresh_factor=False,
                    factor_source="auto",
                )
            except AdjQuotesError as e:
                raise ValueError(e.message) from e
        names = load_names(db, [stock_code])
        resolved_name = names.get(stock_code) or resolved_name

    type_list = _parse_types(None)
    cup_ref_bars = bars_raw if adjust_n == "qfq" else None
    if len(bars) >= 30:
        hits_all, invalidated_count = detect_all_counted(
            bars,
            types=type_list or None,
            include_invalidated=True,
            ref_bars=cup_ref_bars,
        )
    else:
        hits_all, invalidated_count = [], 0
    hits = [h for h in hits_all if str(h.get("status") or "") != "invalidated"]

    vp, confluence, rpe, gms, classic = _tactical_enrichment(
        db,
        bars,
        stock_code,
        asof_s,
        strategy_snapshots=strategy_snapshots,
    )
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

    tactical = build_pattern_tactical(
        hits_all,
        confluence=confluence,
        vp=vp,
        rpe=rpe,
        gms=gms,
        invalidated_count=invalidated_count,
        asof=asof_s,
        market=market_snapshot_from_bars(bars),
        classic=classic,
        bars=bars,
        weekly_trend=weekly_trend,
    )
    hits = annotate_hits_breakout_probe(hits, tactical)

    payload: Dict[str, Any] = {
        "success": True,
        "code": stock_code,
        "name": resolved_name or name or "",
        "asof": asof_s,
        "price_adjust": adjust_n,
        "bar_count": len(bars),
        "hit_count": len(hits),
        "invalidated_count": invalidated_count,
        "items": hits,
        "tactical": tactical,
        "use_realtime": bool(use_realtime),
    }
    if adj_meta:
        payload["adj_meta"] = adj_meta
    if realtime_meta:
        payload["realtime"] = realtime_meta
    return {
        "ok": True,
        "items": hits,
        "invalidated_count": invalidated_count,
        "code": stock_code,
        "name": payload["name"],
        "asof": asof_s or "",
        "price_adjust": adjust_n,
        "tactical": tactical,
        "error": None,
        "payload": payload,
    }


def _compute_swing(
    db: Session,
    code: str,
    name: str,
    *,
    asof: Optional[str],
    use_realtime: bool,
    pattern_short_bias: Optional[str] = None,
    shared_bars: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from backend_core.analysis.chart_patterns.scanner import (
        apply_qfq_to_code_bars,
        normalize_price_adjust,
    )
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
    from backend_core.strategies.double_bottom.data_loader import (
        batch_load_ohlc_asc,
        load_names,
        resolve_effective_trade_date,
    )

    try:
        from backend_api.utils.adj_quotes import AdjQuotesError
    except ImportError:
        from utils.adj_quotes import AdjQuotesError  # type: ignore
    try:
        from backend_api.utils.equity_code import (
            infer_market_type,
            normalize_equity_code,
        )
    except ImportError:
        from utils.equity_code import (  # type: ignore
            infer_market_type,
            normalize_equity_code,
        )

    lookback = 180
    max_points = 12
    stock_code = normalize_equity_code(code) or str(code).strip()
    adjust_n = normalize_price_adjust("none" if use_realtime else "qfq")
    realtime_meta: Optional[Dict[str, Any]] = None
    adj_meta: Optional[Dict[str, Any]] = None
    asof_s: Optional[str] = None
    resolved_name = name or ""
    bars: List[Dict[str, Any]] = []

    if isinstance(shared_bars, dict) and (
        shared_bars.get("bars") or shared_bars.get("bars_raw")
    ):
        stock_code = str(shared_bars.get("code") or stock_code)
        resolved_name = shared_bars.get("name") or resolved_name
        asof_s = shared_bars.get("asof")
        adjust_n = normalize_price_adjust(
            shared_bars.get("adjust") or ("none" if use_realtime else "qfq")
        )
        bars = list(shared_bars.get("bars") or shared_bars.get("bars_raw") or [])
        adj_meta = shared_bars.get("adj_meta")
        realtime_meta = shared_bars.get("realtime_meta")
    else:
        market = infer_market_type(stock_code) or "CN"
        daily_fetch = max(int(lookback), min(400, int(lookback) * 5))
        if use_realtime and not asof:
            from backend_core.analysis.realtime_bars import load_bars_with_realtime

            bars, realtime_meta, asof_s = load_bars_with_realtime(
                db, stock_code, lookback=daily_fetch, asof=None, prefer_live=True
            )
        else:
            asof_s = resolve_effective_trade_date(db, asof, market=market)
            bars_map = batch_load_ohlc_asc(db, [stock_code], lookback=daily_fetch, asof=asof_s)
            bars = bars_map.get(stock_code) or []
            if use_realtime:
                from backend_core.analysis.realtime_bars import apply_realtime_to_code_bars

                bars, realtime_meta = apply_realtime_to_code_bars(
                    db, stock_code, bars, prefer_live=True
                )
                if realtime_meta and realtime_meta.get("trade_date"):
                    asof_s = str(realtime_meta["trade_date"])[:10]
        if adjust_n == "qfq":
            try:
                bars, adj_meta = apply_qfq_to_code_bars(
                    db,
                    stock_code,
                    bars,
                    refresh_factor=False,
                    factor_source="auto",
                )
            except AdjQuotesError as e:
                raise ValueError(e.message) from e
        names = load_names(db, [stock_code])
        resolved_name = names.get(stock_code) or resolved_name

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
        str(ms.get("trend") or ""),
        pattern_short_bias,
        period_zh="日线",
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
        str(weekly_ms.get("trend") or ""),
        pattern_short_bias,
        period_zh="周线",
    )
    weekly_ms["pattern_contrast"] = weekly_contrast

    caution = weekly_counter_trend_caution(
        str(weekly_ms.get("trend") or ""),
        pattern_short_bias,
    )
    if caution:
        ms["counter_trend_caution"] = True
        ms["counter_trend_note"] = caution.get("text")
        weekly_ms["counter_trend_caution"] = True
        weekly_ms["counter_trend_note"] = caution.get("text")
    else:
        ms["counter_trend_caution"] = False
        ms["counter_trend_note"] = None
        weekly_ms["counter_trend_caution"] = False
        weekly_ms["counter_trend_note"] = None

    price_adjust = {
        "mode": adjust_n,
        "applied": bool(adjust_n == "qfq"),
    }
    if isinstance(adj_meta, dict):
        price_adjust.update(adj_meta)

    out: Dict[str, Any] = {
        "success": True,
        "code": stock_code,
        "name": resolved_name or name or "",
        "asof": ms.get("asof") or asof_s,
        "price_adjust": price_adjust,
        "market_structure": ms,
        "weekly": weekly_ms,
        "counter_trend_caution": bool(caution),
        "counter_trend_note": (caution or {}).get("text") if caution else None,
        "use_realtime": bool(use_realtime),
    }
    if realtime_meta:
        out["realtime"] = realtime_meta
    ok = bool(ms.get("ok") is not False)
    return {
        "ok": ok,
        "data": out,
        "code": stock_code,
        "name": out["name"],
        "asof": out.get("asof") or "",
        "error": None,
        "payload": out,
    }


def _compute_gann(
    db: Session,
    code: str,
    name: str,
    *,
    asof: Optional[str],
    use_realtime: bool,
    shared_bars: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from backend_core.analysis.chart_patterns.scanner import (
        apply_qfq_to_code_bars,
        normalize_price_adjust,
    )
    from backend_core.analysis.gann_trend import analyze_gann_trend
    from backend_core.analysis.swing_zigzag import (
        DEFAULT_FRACTAL,
        DEFAULT_MIN_SWING_BARS,
    )
    from backend_core.strategies.double_bottom.data_loader import (
        batch_load_ohlc_asc,
        load_names,
        resolve_effective_trade_date,
    )

    try:
        from backend_api.utils.adj_quotes import AdjQuotesError
    except ImportError:
        from utils.adj_quotes import AdjQuotesError  # type: ignore
    try:
        from backend_api.utils.equity_code import (
            infer_market_type,
            normalize_equity_code,
        )
    except ImportError:
        from utils.equity_code import (  # type: ignore
            infer_market_type,
            normalize_equity_code,
        )

    lookback = 180
    stock_code = normalize_equity_code(code) or str(code).strip()
    adjust_n = normalize_price_adjust("none" if use_realtime else "qfq")
    realtime_meta: Optional[Dict[str, Any]] = None
    adj_meta: Optional[Dict[str, Any]] = None
    asof_s: Optional[str] = None
    resolved_name = name or ""
    bars: List[Dict[str, Any]] = []

    if isinstance(shared_bars, dict) and (
        shared_bars.get("bars") or shared_bars.get("bars_raw")
    ):
        stock_code = str(shared_bars.get("code") or stock_code)
        resolved_name = shared_bars.get("name") or resolved_name
        asof_s = shared_bars.get("asof")
        adjust_n = normalize_price_adjust(
            shared_bars.get("adjust") or ("none" if use_realtime else "qfq")
        )
        bars = list(shared_bars.get("bars") or shared_bars.get("bars_raw") or [])
        adj_meta = shared_bars.get("adj_meta")
        realtime_meta = shared_bars.get("realtime_meta")
    else:
        market = infer_market_type(stock_code) or "CN"
        if use_realtime and not asof:
            from backend_core.analysis.realtime_bars import load_bars_with_realtime

            bars, realtime_meta, asof_s = load_bars_with_realtime(
                db, stock_code, lookback=int(lookback), asof=None, prefer_live=True
            )
        else:
            asof_s = resolve_effective_trade_date(db, asof, market=market)
            bars_map = batch_load_ohlc_asc(db, [stock_code], lookback=int(lookback), asof=asof_s)
            bars = bars_map.get(stock_code) or []
            if use_realtime:
                from backend_core.analysis.realtime_bars import apply_realtime_to_code_bars

                bars, realtime_meta = apply_realtime_to_code_bars(
                    db, stock_code, bars, prefer_live=True
                )
                if realtime_meta and realtime_meta.get("trade_date"):
                    asof_s = str(realtime_meta["trade_date"])[:10]
        if adjust_n == "qfq":
            try:
                bars, adj_meta = apply_qfq_to_code_bars(
                    db,
                    stock_code,
                    bars,
                    refresh_factor=False,
                    factor_source="auto",
                )
            except AdjQuotesError as e:
                raise ValueError(e.message) from e
        names = load_names(db, [stock_code])
        resolved_name = names.get(stock_code) or resolved_name

    daily_bars = bars[-int(lookback) :] if len(bars) > int(lookback) else bars
    gann = analyze_gann_trend(
        daily_bars,
        max_bars=lookback,
        fractal_left=DEFAULT_FRACTAL,
        fractal_right=DEFAULT_FRACTAL,
        min_swing_bars=DEFAULT_MIN_SWING_BARS,
        scale_override=None,
    )
    price_adjust = {
        "mode": adjust_n,
        "applied": bool(adjust_n == "qfq"),
    }
    if isinstance(adj_meta, dict):
        price_adjust.update(adj_meta)

    out: Dict[str, Any] = {
        "success": True,
        "code": stock_code,
        "name": resolved_name or name or "",
        "asof": gann.get("asof") or asof_s,
        "price_adjust": price_adjust,
        "gann_trend": gann,
        "use_realtime": bool(use_realtime),
    }
    if realtime_meta:
        out["realtime"] = realtime_meta
    g = gann or {}
    return {
        "ok": bool(g.get("ok")),
        "data": out,
        "code": stock_code,
        "name": out["name"],
        "asof": out.get("asof") or "",
        "error": None,
        "payload": out,
    }


def _run_with_own_session(fn: Callable[[Session], Dict[str, Any]], label: str) -> Dict[str, Any]:
    db = _session_local()
    try:
        return fn(db)
    except Exception as e:
        logger.exception("stock-analysis-bundle detail %s failed", label)
        try:
            db.rollback()
        except Exception:
            pass
        return _err_section(str(e) or f"{label}失败")
    finally:
        try:
            db.close()
        except Exception:
            pass


def _build_trade_plan(
    db: Session,
    *,
    code: str,
    name: str,
    trade_date: Optional[str],
    strategy_data: Optional[Dict[str, Any]],
    levels: Optional[Dict[str, Any]],
    pattern: Optional[Dict[str, Any]],
    swing: Optional[Dict[str, Any]],
    gann: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    from backend_core.analysis.integrated_trade_plan import build_integrated_trade_plan
    from backend_core.analysis.stock_multi_strategy import collect_strategy_raw_rows

    strategy_pack = None
    if isinstance(strategy_data, dict):
        # collect_stock_multi_strategy_check 返回 results 列表；trade plan 期望 summaries dict
        if strategy_data.get("summaries"):
            strategy_pack = {
                "summaries": strategy_data.get("summaries"),
                "trade_date": strategy_data.get("trade_date") or trade_date,
                "stock": strategy_data.get("stock"),
                "rows": strategy_data.get("rows"),
            }
        elif strategy_data.get("strategy_pack"):
            strategy_pack = strategy_data.get("strategy_pack")
        elif isinstance(strategy_data.get("results"), list):
            summaries: Dict[str, Any] = {}
            for r in strategy_data["results"]:
                if isinstance(r, dict) and r.get("strategy"):
                    summaries[str(r["strategy"]).strip().lower()] = r
            if summaries:
                strategy_pack = {
                    "summaries": summaries,
                    "trade_date": strategy_data.get("trade_date") or trade_date,
                    "stock": strategy_data.get("stock"),
                }
    if not isinstance(strategy_pack, dict) or not strategy_pack.get("summaries"):
        strategy_pack = collect_strategy_raw_rows(db, code=code, date=trade_date)

    snapshots_levels = None
    if levels and levels.get("data"):
        snapshots_levels = {"data": levels.get("data")}
    snapshots_pattern = None
    if pattern and (pattern.get("tactical") is not None or pattern.get("items")):
        snapshots_pattern = {
            "tactical": pattern.get("tactical"),
            "items": pattern.get("items") or [],
        }
    snapshots_swing = None
    if swing and swing.get("data"):
        snapshots_swing = {"data": swing.get("data")}
    snapshots_gann = None
    if gann and gann.get("data"):
        snapshots_gann = {"data": gann.get("data")}

    ctx = {
        "meta": {
            "code": code,
            "name": name or "",
            "trade_date": trade_date or (strategy_pack or {}).get("trade_date"),
        },
        "strategy_pack": strategy_pack,
        "levels": snapshots_levels,
        "pattern": snapshots_pattern,
        "swing": snapshots_swing,
        "gann": snapshots_gann,
    }
    plan = build_integrated_trade_plan(ctx)
    return {
        "ok": True,
        "plan": plan,
        "code": code,
        "name": name or "",
        "trade_date": ctx["meta"].get("trade_date") or trade_date or "",
        "error": None,
    }


def _resolve_stock(db: Session, raw: str) -> Dict[str, Any]:
    from backend_api.stock.stock_analysis_routes import resolve_levels_stock_identifier

    return resolve_levels_stock_identifier(db, raw)


def build_stock_analysis_bundle(
    db: Session,
    *,
    code: str,
    name: str = "",
    date: Optional[str] = None,
    strategies: Optional[List[str]] = None,
    use_realtime: bool = False,
) -> Dict[str, Any]:
    """
    编排个股分析全包。

    返回:
      - 成功: {"success": True, "data": {...}}
      - 歧义/未找到: {"success": False, "message": ..., "candidates": [...], "http_status": 400|404}
    """
    raw = (code or "").strip()
    if not raw:
        return {
            "success": False,
            "message": "请提供股票代码或名称",
            "candidates": [],
            "http_status": 400,
        }

    from backend_core.analysis.stock_multi_strategy import collect_stock_multi_strategy_check

    resolved = _resolve_stock(db, raw)
    status = resolved.get("status")
    if status == "ambiguous":
        return {
            "success": False,
            "message": resolved.get("message") or "匹配到多只股票，请选择",
            "candidates": resolved.get("candidates") or [],
            "http_status": 400,
        }
    if status == "not_found" or not resolved.get("code"):
        return {
            "success": False,
            "message": resolved.get("message") or "未找到匹配股票",
            "candidates": [],
            "http_status": 404,
        }

    code_n = str(resolved["code"])
    name_n = (resolved.get("name") or name or "").strip()
    market = (resolved.get("market") or resolved.get("market_type") or "CN").upper()
    strat_list = strategies or ["gms", "urt", "sbbr", "rpe"]

    strategy_data: Optional[Dict[str, Any]] = None
    strategy_error: Optional[str] = None
    try:
        strategy_data = collect_stock_multi_strategy_check(
            db,
            code=code_n,
            name=name_n,
            date=date,
            strategies=strat_list,
            use_realtime=bool(use_realtime),
        )
    except Exception as e:
        logger.exception("stock-analysis-bundle strategy failed code=%s", code_n)
        try:
            db.rollback()
        except Exception:
            pass
        strategy_error = f"个股多策略分析失败: {e}"

    trade_date = ""
    if use_realtime and isinstance(strategy_data, dict):
        trade_date = (
            strategy_data.get("realtime_trade_date")
            or ((strategy_data.get("realtime") or {}).get("trade_date"))
            or strategy_data.get("trade_date")
            or (date or "")
        )
    elif isinstance(strategy_data, dict):
        trade_date = strategy_data.get("trade_date") or (date or "")
    else:
        trade_date = date or ""
    trade_date = str(trade_date or "")[:10]
    asof_for_details = None if use_realtime else (trade_date or None)

    stock = (
        (strategy_data or {}).get("stock")
        if isinstance(strategy_data, dict)
        else None
    ) or {"code": code_n, "name": name_n}

    strategy_snapshots = _strategy_snapshots_from_data(strategy_data)
    shared_bars: Optional[Dict[str, Any]] = None
    try:
        shared_bars = _prepare_shared_bars(
            db,
            code_n,
            name_n,
            asof=asof_for_details,
            use_realtime=bool(use_realtime),
            lookback=_SHARED_BARS_LOOKBACK,
        )
        if shared_bars.get("name") and not name_n:
            name_n = str(shared_bars["name"])
            stock["name"] = name_n
    except Exception as e:
        logger.warning("shared bars prepare failed code=%s: %s", code_n, e)
        try:
            db.rollback()
        except Exception:
            pass
        shared_bars = None

    def job_rs(s: Session) -> Dict[str, Any]:
        return _compute_rs(s, code_n, name_n, asof_for_details, market)

    def job_ff(s: Session) -> Dict[str, Any]:
        return _compute_fund_flow(s, code_n)

    def job_levels(s: Session) -> Dict[str, Any]:
        return _compute_levels(
            s,
            code_n,
            use_realtime=bool(use_realtime),
            shared_bars=shared_bars,
        )

    def job_pattern(s: Session) -> Dict[str, Any]:
        return _compute_pattern(
            s,
            code_n,
            name_n,
            asof=asof_for_details,
            use_realtime=bool(use_realtime),
            shared_bars=shared_bars,
            strategy_snapshots=strategy_snapshots,
        )

    def job_gann(s: Session) -> Dict[str, Any]:
        return _compute_gann(
            s,
            code_n,
            name_n,
            asof=asof_for_details,
            use_realtime=bool(use_realtime),
            shared_bars=shared_bars,
        )

    # 先并行：RS / 资金 / levels / pattern / gann；swing 等 pattern 拿 bias 后再算
    parallel_specs: List[Tuple[str, Callable[[Session], Dict[str, Any]]]] = [
        ("rs", job_rs),
        ("fund_flow", job_ff),
        ("levels", job_levels),
        ("pattern", job_pattern),
        ("gann", job_gann),
    ]
    results: Dict[str, Dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=_DETAIL_WORKERS) as pool:
        futures = {
            pool.submit(_run_with_own_session, fn, label): label
            for label, fn in parallel_specs
        }
        for fut in as_completed(futures):
            label = futures[fut]
            try:
                results[label] = fut.result()
            except Exception as e:
                results[label] = _err_section(str(e) or f"{label}失败")

    rs = results.get("rs") or _err_section("相对强度加载失败")
    fund_flow = results.get("fund_flow") or _err_section("资金流向加载失败")
    levels = results.get("levels") or _err_section("阻力支撑计算失败")
    pattern = results.get("pattern") or _err_section("形态识别失败")
    gann = results.get("gann") or _err_section("江恩趋势分析失败")

    # 补齐 pattern 失败时的结构字段，供前端渲染
    if not pattern.get("ok"):
        pattern.setdefault("items", [])
        pattern.setdefault("code", code_n)
        pattern.setdefault("name", name_n)
        pattern.setdefault("asof", trade_date or "")
        pattern.setdefault("price_adjust", "none" if use_realtime else "qfq")
        pattern.setdefault("tactical", None)
        pattern.setdefault("invalidated_count", 0)

    bias = None
    if pattern.get("ok") and isinstance(pattern.get("tactical"), dict):
        bias = pattern["tactical"].get("short_bias")

    swing = _run_with_own_session(
        lambda s: _compute_swing(
            s,
            code_n,
            name_n,
            asof=asof_for_details,
            use_realtime=bool(use_realtime),
            pattern_short_bias=str(bias) if bias else None,
            shared_bars=shared_bars,
        ),
        "swing",
    )
    if not swing.get("ok"):
        swing.setdefault("data", None)
        swing.setdefault("code", code_n)
        swing.setdefault("name", name_n)
        swing.setdefault("asof", trade_date or "")

    trade_plan: Dict[str, Any]
    try:
        trade_plan = _build_trade_plan(
            db,
            code=code_n,
            name=name_n,
            trade_date=trade_date or None,
            strategy_data=strategy_data,
            levels=levels if levels.get("ok") else None,
            pattern=pattern if pattern.get("ok") else None,
            swing=swing if swing.get("ok") else None,
            gann=gann if gann.get("ok") else None,
        )
    except Exception as e:
        logger.exception("stock-analysis-bundle trade_plan failed code=%s", code_n)
        try:
            db.rollback()
        except Exception:
            pass
        trade_plan = {
            "ok": False,
            "plan": None,
            "code": code_n,
            "name": name_n,
            "trade_date": trade_date or "",
            "error": str(e) or "综合交易策略合成失败",
        }

    data = {
        "strategy": strategy_data,
        "strategy_error": strategy_error,
        "stock": stock,
        "trade_date": trade_date,
        "use_realtime": bool(use_realtime),
        "realtime": (strategy_data or {}).get("realtime") if strategy_data else None,
        "rs": rs,
        "fund_flow": fund_flow,
        "levels": levels,
        "pattern": pattern,
        "swing": swing,
        "gann": gann,
        "trade_plan": trade_plan,
    }
    return {"success": True, "data": data}
