# -*- coding: utf-8 -*-
"""分析页 · 波段与趋势结构 API。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend_api.database import get_db
from backend_api.permissions import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis/market-structure", tags=["波段与趋势"])


@router.get("/{code}")
async def market_structure_for_stock(
    code: str,
    asof: Optional[str] = Query(None),
    lookback: int = Query(180, ge=60, le=400),
    adjust: str = Query("none", description="价格口径：none=不复权，qfq=前复权现算"),
    refresh_factor: bool = Query(False),
    factor_source: str = Query("auto"),
    max_points: int = Query(12, ge=4, le=24),
    pattern_short_bias: Optional[str] = Query(
        None,
        description="可选：形态 tactical.short_bias，用于生成对照句（不改写趋势）",
    ),
    use_realtime: bool = Query(
        False, description="叠加最新实时价为当日 K 线末根后再算波段结构"
    ),
    db: Session = Depends(get_db),
    _perm: None = Depends(require_permission("channel.analyze.tab.technical")),
):
    from backend_api.stock.stock_analysis_routes import resolve_levels_stock_identifier
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

    try:
        adjust_n = normalize_price_adjust(adjust)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    resolved = resolve_levels_stock_identifier(db, code)
    status = resolved.get("status")
    if status == "ambiguous":
        raise HTTPException(status_code=400, detail={"message": "代码不唯一", **resolved})
    if status == "not_found":
        raise HTTPException(status_code=404, detail=resolved.get("message") or "未找到股票")
    stock_code = normalize_equity_code(resolved.get("code") or code)
    if not stock_code or (
        stock_code.isdigit() and len(stock_code) not in (5, 6)
    ):
        raise HTTPException(status_code=400, detail="无效股票代码（A股6位，港股5位）")

    market = infer_market_type(stock_code) or "CN"
    realtime_meta: Optional[Dict[str, Any]] = None
    # 日线 lookback；周线需更多日线再聚合（约 5×）
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
    adj_meta: Optional[Dict[str, Any]] = None
    if adjust_n == "qfq":
        try:
            bars, adj_meta = apply_qfq_to_code_bars(
                db,
                stock_code,
                bars,
                refresh_factor=refresh_factor,
                factor_source=factor_source or "auto",
            )
        except AdjQuotesError as e:
            raise HTTPException(status_code=400, detail=e.message) from e
        except Exception as e:
            logger.exception("波段结构前复权失败 code=%s", stock_code)
            raise HTTPException(status_code=500, detail=f"前复权处理失败: {e}") from e

    daily_bars = bars[-int(lookback) :] if len(bars) > int(lookback) else bars
    names = load_names(db, [stock_code])
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
        "name": names.get(stock_code) or resolved.get("name") or "",
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
    return out
