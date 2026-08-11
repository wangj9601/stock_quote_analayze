# -*- coding: utf-8 -*-
"""分析页 · 形态识别 API。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.database import get_db
from backend_api.permissions import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis/patterns", tags=["形态识别"])


class PatternScanRequest(BaseModel):
    scope: str = Field("market", description="market | industry | concept")
    board_codes: List[str] = Field(default_factory=list)
    board_kind: str = Field("industry", description="industry | concept")
    types: List[str] = Field(default_factory=list, description="形态族，空=全部")
    asof: Optional[str] = None
    lookback: int = Field(160, ge=60, le=400)
    limit: int = Field(100, ge=1, le=200)
    timeout_sec: float = Field(45.0, ge=5.0, le=120.0)
    adjust: str = Field("none", description="价格口径：none=不复权，qfq=前复权现算")
    refresh_factor: bool = False
    factor_source: str = Field(
        "auto",
        description="因子源：auto / sina / baostock（仅 adjust=qfq 生效）",
    )


def _parse_types(raw: Optional[str], lst: Optional[List[str]] = None) -> List[str]:
    if lst:
        return [str(x).strip() for x in lst if str(x).strip()]
    if not raw:
        return []
    return [p.strip() for p in str(raw).replace(";", ",").split(",") if p.strip()]


@router.get("/meta")
async def patterns_meta(
    _perm: None = Depends(require_permission("channel.analyze.tab.technical")),
):
    from backend_core.analysis.chart_patterns.engine import PATTERN_FAMILIES

    return {
        "success": True,
        "families": list(PATTERN_FAMILIES),
        "labels": {
            "double_extremes": "双顶双底",
            "head_shoulders": "头肩顶底",
            "triangle": "三角形",
            "wedge_flag": "楔形旗形",
        },
        "types": {
            "double_bottom": "双底",
            "double_top": "双顶",
            "head_shoulders_top": "头肩顶",
            "head_shoulders_bottom": "头肩底",
            "ascending_triangle": "上升三角",
            "descending_triangle": "下降三角",
            "symmetrical_triangle": "对称三角",
            "rising_wedge": "上升楔形",
            "falling_wedge": "下降楔形",
            "bull_flag": "上升旗形",
            "bear_flag": "下降旗形",
        },
    }


@router.get("/{code}")
async def patterns_for_stock(
    code: str,
    types: Optional[str] = Query(None, description="逗号分隔形态族"),
    asof: Optional[str] = Query(None),
    lookback: int = Query(160, ge=60, le=400),
    adjust: str = Query("none", description="价格口径：none=不复权，qfq=前复权现算"),
    refresh_factor: bool = Query(False, description="强制重新拉取复权因子"),
    factor_source: str = Query(
        "auto",
        description="因子源：auto=归一化新浪优先BaoStock备用，sina=仅归一化新浪，baostock=仅BaoStock",
    ),
    db: Session = Depends(get_db),
    _perm: None = Depends(require_permission("channel.analyze.tab.technical.btn.pattern")),
):
    from backend_api.stock.stock_analysis_routes import resolve_levels_stock_identifier
    from backend_core.analysis.chart_patterns.engine import detect_all
    from backend_core.analysis.chart_patterns.scanner import (
        apply_qfq_to_code_bars,
        normalize_price_adjust,
    )
    from backend_core.strategies.double_bottom.data_loader import (
        batch_load_ohlc_asc,
        load_names,
        resolve_effective_trade_date,
    )
    from backend_core.strategies.double_bottom.universe import normalize_a_code

    try:
        from backend_api.utils.adj_quotes import AdjQuotesError
    except ImportError:
        from utils.adj_quotes import AdjQuotesError  # type: ignore

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
    stock_code = normalize_a_code(resolved.get("code") or code)
    if not stock_code:
        raise HTTPException(status_code=400, detail="无效股票代码")

    asof_s = resolve_effective_trade_date(db, asof)
    bars_map = batch_load_ohlc_asc(db, [stock_code], lookback=lookback, asof=asof_s)
    bars = bars_map.get(stock_code) or []
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
            logger.exception("形态识别前复权失败 code=%s", stock_code)
            raise HTTPException(status_code=500, detail=f"前复权处理失败: {e}") from e

    names = load_names(db, [stock_code])
    type_list = _parse_types(types)
    hits = detect_all(bars, types=type_list or None) if len(bars) >= 30 else []
    payload: Dict[str, Any] = {
        "success": True,
        "code": stock_code,
        "name": names.get(stock_code) or resolved.get("name") or "",
        "asof": asof_s,
        "price_adjust": adjust_n,
        "bar_count": len(bars),
        "hit_count": len(hits),
        "items": hits,
    }
    if adj_meta:
        payload["adj_meta"] = adj_meta
    return payload


@router.post("/scan")
async def patterns_scan(
    body: PatternScanRequest,
    db: Session = Depends(get_db),
    _perm: None = Depends(require_permission("channel.analyze.tab.technical.btn.pattern_scan")),
):
    from backend_core.analysis.chart_patterns.scanner import (
        normalize_price_adjust,
        scan_patterns,
    )

    try:
        adjust_n = normalize_price_adjust(body.adjust)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        result = scan_patterns(
            db,
            scope=body.scope,
            board_codes=body.board_codes,
            board_kind=body.board_kind,
            types=body.types or None,
            asof=body.asof,
            lookback=body.lookback,
            limit=body.limit,
            timeout_sec=body.timeout_sec,
            adjust=adjust_n,
            refresh_factor=bool(body.refresh_factor),
            factor_source=body.factor_source or "auto",
        )
    except Exception as e:
        logger.exception("patterns scan failed")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"success": True, **result}
