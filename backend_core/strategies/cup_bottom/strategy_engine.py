# -*- coding: utf-8 -*-
"""CUPB 选股引擎：解析股票池 → 利旧/检测 → 杯底形态识别。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from backend_core.analysis.chart_patterns.scanner import apply_qfq_to_code_bars, normalize_price_adjust
from backend_core.strategies.double_bottom.data_loader import (
    batch_load_ohlc_asc,
    load_names,
    resolve_effective_trade_date,
)
from backend_core.strategies.cup_bottom.universe import enrich_items_with_ths_industry, resolve_stock_pool

from .config import CupbConfigManager, get_default_cupb_config, merge_pattern_cfg
from .detector import detect_cup_bottom

logger = logging.getLogger(__name__)


class CupbStrategyEngine:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or get_default_cupb_config()

    def screen(
        self,
        db: Session,
        *,
        trade_date: Optional[str] = None,
        config_id: Optional[int] = None,
        status_filter: Optional[str] = None,
        stock_pool_mode: str = "stocks",
        industry_board_codes: Optional[Sequence[Any]] = None,
        concept_board_codes: Optional[Sequence[Any]] = None,
        stock_codes: Optional[Sequence[Any]] = None,
        universe_limit: Optional[int] = None,
        market_scopes: Optional[Sequence[Any]] = None,
        cn_board_segments: Optional[Sequence[Any]] = None,
        max_results: Optional[int] = None,
        force_recompute: bool = False,
        price_adjust: str = "none",
    ) -> Dict[str, Any]:
        cm = CupbConfigManager()
        cid = int(config_id) if config_id is not None else None
        cfg = cm.get_config(cid) if cid is not None else (
            self.config if self.config else cm.get_config(None)
        )
        if cid is None:
            try:
                cid = int(cfg.get("_config_id") or cm.get_default_config_id())
            except Exception:
                cid = cm.get_default_config_id()

        pattern = merge_pattern_cfg(cfg)
        scan = dict(cfg.get("scan") or {})
        sf = (status_filter or scan.get("status_filter") or "both").strip().lower()
        if sf not in ("forming", "confirmed", "both"):
            sf = "both"

        adjust_n = normalize_price_adjust(price_adjust)

        date_s = resolve_effective_trade_date(db, trade_date)
        pool = resolve_stock_pool(
            db,
            stock_pool_mode=stock_pool_mode,
            industry_board_codes=industry_board_codes,
            concept_board_codes=concept_board_codes,
            stock_codes=stock_codes,
            universe_limit=universe_limit if (universe_limit or 0) > 0 else None,
            market_scopes=market_scopes,
            cn_board_segments=cn_board_segments,
        )
        codes: List[str] = list(pool["codes"] or [])
        boards_by = pool.get("boards_by_code") or {}
        mode = str(pool.get("mode") or stock_pool_mode or "").strip().lower()
        if not codes:
            return {
                "trade_date": date_s,
                "config_id": cid,
                "status_filter": sf,
                "price_adjust": adjust_n,
                "scope_meta": pool.get("scope_meta") or {},
                "screened": 0,
                "hit_count": 0,
                "items": [],
                "force_recompute": bool(force_recompute),
                "reused": 0,
                "computed": 0,
            }

        reused_items: List[Dict[str, Any]] = []
        codes_to_scan = list(codes)
        if not force_recompute and cid is not None and date_s:
            try:
                from .signal_storage import load_traces_by_codes

                cached = load_traces_by_codes(
                    db,
                    trade_date=date_s,
                    config_id=int(cid),
                    codes=codes,
                    status_filter=None,
                )
                if cached:
                    reused_codes = set()
                    for code, row in cached.items():
                        row_adjust = str(
                            (row.get("detail") or {}).get("price_adjust")
                            or row.get("price_adjust")
                            or "none"
                        ).strip().lower()
                        if row_adjust != adjust_n:
                            continue
                        st = row.get("status")
                        if sf != "both" and st != sf:
                            reused_codes.add(code)
                            continue
                        reused_items.append(dict(row))
                        reused_codes.add(code)
                    codes_to_scan = [c for c in codes if c not in reused_codes]
            except Exception as e:
                logger.warning("CUPB reuse load failed, fallback full scan: %s", e)
                reused_items = []
                codes_to_scan = list(codes)

        lookback = max(
            int(pattern.get("lookback_days") or 160) + 20,
            int(scan.get("history_bars") or 180),
        )
        bars_by = (
            batch_load_ohlc_asc(db, codes_to_scan, lookback=lookback, asof=date_s)
            if codes_to_scan
            else {}
        )
        names = load_names(db, codes_to_scan) if codes_to_scan else {}

        new_items: List[Dict[str, Any]] = []
        grade_filter = str(scan.get("grade_filter") or "all").strip().lower()
        for code in codes_to_scan:
            bars = bars_by.get(code) or []
            if not bars:
                continue
            if date_s:
                bars = [b for b in bars if str(b.get("date") or "")[:10] <= date_s]
            if adjust_n == "qfq" and bars:
                try:
                    bars, _ = apply_qfq_to_code_bars(db, code, bars)
                except Exception as e:
                    logger.warning("CUPB qfq failed for %s: %s", code, e)
                    continue
            hit = detect_cup_bottom(bars, pattern_cfg=pattern)
            if not hit:
                continue
            st = hit.get("status")
            if sf != "both" and st != sf:
                continue
            g = str(hit.get("grade") or "").upper()
            if grade_filter not in ("all", "", "both") and g != grade_filter.upper():
                continue
            name = names.get(code) or (bars[-1].get("name") if bars else "") or ""
            boards = list(boards_by.get(code) or [])
            row = {
                "code": code,
                "name": name,
                "date": date_s,
                "status": st,
                "left_rim_date": hit.get("left_rim_date"),
                "cup_bottom_date": hit.get("cup_bottom_date"),
                "right_rim_date": hit.get("right_rim_date"),
                "handle_low_date": hit.get("handle_low_date"),
                "left_rim_price": hit.get("left_rim_price"),
                "cup_bottom_price": hit.get("cup_bottom_price"),
                "right_rim_price": hit.get("right_rim_price"),
                "handle_low_price": hit.get("handle_low_price"),
                "rim": hit.get("rim"),
                "last_close": hit.get("last_close"),
                "confirm_date": hit.get("confirm_date"),
                "first_confirm_date": hit.get("first_confirm_date"),
                "ever_confirmed": bool(hit.get("ever_confirmed")),
                "price_adjust": adjust_n,
                "cup_depth_pct": hit.get("cup_depth_pct"),
                "handle_retrace_pct": hit.get("handle_retrace_pct"),
                "grade": hit.get("grade"),
                "volume_score": hit.get("volume_score"),
                "boards": boards,
                "board_labels": "、".join(
                    str(b.get("board_name") or b.get("board_code") or "")
                    for b in boards
                    if b
                ),
                "detail": hit,
                "_from_cache": False,
            }
            new_items.append(row)

        items: List[Dict[str, Any]] = list(reused_items) + list(new_items)
        if items:
            enrich_items_with_ths_industry(db, items, force=(mode == "market"))

        items.sort(key=lambda r: str(r.get("code") or ""))
        items.sort(
            key=lambda r: str(r.get("confirm_date") or r.get("right_rim_date") or "")
            or "0000-00-00",
            reverse=True,
        )
        items.sort(key=lambda r: 0 if r.get("status") == "confirmed" else 1)

        cap = 0
        if max_results is not None:
            try:
                cap = int(max_results)
            except (TypeError, ValueError):
                cap = 0
        if cap > 0:
            items = items[:cap]

        return {
            "trade_date": date_s,
            "config_id": cid,
            "status_filter": sf,
            "price_adjust": adjust_n,
            "scope_meta": pool.get("scope_meta") or {},
            "screened": len(codes),
            "hit_count": len(items),
            "items": items,
            "force_recompute": bool(force_recompute),
            "reused": len(reused_items),
            "computed": len(codes_to_scan),
            "scope_codes": codes,
        }
