# -*- coding: utf-8 -*-
"""KGT 选股引擎。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from backend_core.strategies.double_bottom.data_loader import (
    batch_load_ohlc_asc,
    load_names,
    resolve_effective_trade_date,
)
from backend_core.strategies.double_bottom.universe import (
    enrich_items_with_ths_industry,
    resolve_stock_pool,
)

from .config import KgtConfigManager, get_default_kgt_config
from .detector import detect_kangaroo_tail

logger = logging.getLogger(__name__)


class KgtStrategyEngine:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or get_default_kgt_config()

    def screen(
        self,
        db: Session,
        *,
        trade_date: Optional[str] = None,
        config_id: Optional[int] = None,
        direction_filter: Optional[str] = None,
        stock_pool_mode: str = "stocks",
        industry_board_codes: Optional[Sequence[Any]] = None,
        concept_board_codes: Optional[Sequence[Any]] = None,
        stock_codes: Optional[Sequence[Any]] = None,
        universe_limit: Optional[int] = None,
        max_results: Optional[int] = None,
        force_recompute: bool = False,
    ) -> Dict[str, Any]:
        cm = KgtConfigManager()
        cid = int(config_id) if config_id is not None else None
        cfg = cm.get_config(cid) if cid is not None else (
            self.config if self.config else cm.get_config(None)
        )
        if cid is None:
            try:
                cid = int(cfg.get("_config_id") or cm.get_default_config_id())
            except Exception:
                cid = cm.get_default_config_id()

        pattern = dict(cfg.get("pattern") or {})
        scan = dict(cfg.get("scan") or {})
        df = (direction_filter or scan.get("direction_filter") or "both").strip().lower()
        if df not in ("bullish", "bearish", "both"):
            df = "both"
        # 检测侧也按方向过滤
        pattern = dict(pattern)
        if df in ("bullish", "bearish"):
            pattern["directions"] = df

        date_s = resolve_effective_trade_date(db, trade_date)
        pool = resolve_stock_pool(
            db,
            stock_pool_mode=stock_pool_mode,
            industry_board_codes=industry_board_codes,
            concept_board_codes=concept_board_codes,
            stock_codes=stock_codes,
            universe_limit=universe_limit if (universe_limit or 0) > 0 else None,
        )
        codes: List[str] = list(pool["codes"] or [])
        boards_by = pool.get("boards_by_code") or {}
        mode = str(pool.get("mode") or stock_pool_mode or "").strip().lower()
        if not codes:
            return {
                "trade_date": date_s,
                "config_id": cid,
                "direction_filter": df,
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
                    direction_filter=None,
                )
                if cached:
                    reused_codes = set()
                    for code, row in cached.items():
                        direction = str(row.get("direction") or "").lower()
                        if df != "both" and direction != df:
                            reused_codes.add(code)
                            continue
                        reused_items.append(dict(row))
                        reused_codes.add(code)
                    codes_to_scan = [c for c in codes if c not in reused_codes]
            except Exception as e:
                logger.warning("KGT reuse load failed, fallback full scan: %s", e)
                reused_items = []
                codes_to_scan = list(codes)

        lookback = max(
            int(pattern.get("ma_period") or 20) + 5,
            int(scan.get("history_bars") or 60),
        )
        bars_by = (
            batch_load_ohlc_asc(db, codes_to_scan, lookback=lookback, asof=date_s)
            if codes_to_scan
            else {}
        )
        names = load_names(db, codes_to_scan) if codes_to_scan else {}

        new_items: List[Dict[str, Any]] = []
        for code in codes_to_scan:
            bars = bars_by.get(code) or []
            if not bars:
                continue
            if date_s:
                bars = [b for b in bars if str(b.get("date") or "")[:10] <= date_s]
            hit = detect_kangaroo_tail(bars, pattern_cfg=pattern)
            if not hit:
                continue
            direction = str(hit.get("direction") or "").lower()
            if df != "both" and direction != df:
                continue
            name = names.get(code) or (bars[-1].get("name") if bars else "") or ""
            boards = list(boards_by.get(code) or [])
            row = {
                "code": code,
                "name": name,
                "date": date_s,
                "direction": direction,
                "status": hit.get("status") or "hit",
                "score": hit.get("score"),
                "signal_date": hit.get("signal_date"),
                "open": hit.get("open"),
                "high": hit.get("high"),
                "low": hit.get("low"),
                "close": hit.get("close"),
                "last_close": hit.get("last_close"),
                "range_pct": hit.get("range_pct"),
                "body_ratio": hit.get("body_ratio"),
                "shadow_ratio": hit.get("shadow_ratio"),
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
        items.sort(key=lambda r: float(r.get("score") or 0), reverse=True)

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
            "direction_filter": df,
            "scope_meta": pool.get("scope_meta") or {},
            "screened": len(codes),
            "hit_count": len(items),
            "items": items,
            "force_recompute": bool(force_recompute),
            "reused": len(reused_items),
            "computed": len(codes_to_scan),
            "scope_codes": codes,
        }
