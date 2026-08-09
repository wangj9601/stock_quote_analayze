# -*- coding: utf-8 -*-
"""DBLB 选股引擎：解析股票池 → 批量日线 → 双底识别。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from .config import DblbConfigManager, get_default_dblb_config
from .data_loader import batch_load_ohlc_asc, load_names, resolve_effective_trade_date
from .detector import detect_double_bottom
from .universe import resolve_stock_pool

logger = logging.getLogger(__name__)


class DblbStrategyEngine:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or get_default_dblb_config()

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
        max_results: Optional[int] = None,
    ) -> Dict[str, Any]:
        cm = DblbConfigManager()
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
        sf = (status_filter or scan.get("status_filter") or "both").strip().lower()
        if sf not in ("forming", "confirmed", "both"):
            sf = "both"

        date_s = resolve_effective_trade_date(db, trade_date)
        limit_default = int(scan.get("default_universe_limit") or 800)
        pool = resolve_stock_pool(
            db,
            stock_pool_mode=stock_pool_mode,
            industry_board_codes=industry_board_codes,
            concept_board_codes=concept_board_codes,
            stock_codes=stock_codes,
            universe_limit=universe_limit
            if universe_limit is not None
            else (limit_default if stock_pool_mode == "market" else None),
        )
        codes: List[str] = list(pool["codes"] or [])
        boards_by = pool.get("boards_by_code") or {}
        if not codes:
            return {
                "trade_date": date_s,
                "config_id": cid,
                "status_filter": sf,
                "scope_meta": pool.get("scope_meta") or {},
                "screened": 0,
                "hit_count": 0,
                "items": [],
            }

        lookback = max(
            int(pattern.get("lookback_days") or 120) + 20,
            int(scan.get("history_bars") or 160),
        )
        bars_by = batch_load_ohlc_asc(db, codes, lookback=lookback, asof=date_s)
        names = load_names(db, codes)

        items: List[Dict[str, Any]] = []
        for code in codes:
            bars = bars_by.get(code) or []
            if not bars:
                continue
            # 截断到 asof
            if date_s:
                bars = [b for b in bars if str(b.get("date") or "")[:10] <= date_s]
            hit = detect_double_bottom(bars, pattern_cfg=pattern)
            if not hit:
                continue
            st = hit.get("status")
            if sf != "both" and st != sf:
                continue
            name = names.get(code) or (bars[-1].get("name") if bars else "") or ""
            boards = list(boards_by.get(code) or [])
            row = {
                "code": code,
                "name": name,
                "date": date_s,
                "status": st,
                "l1_date": hit.get("l1_date"),
                "l2_date": hit.get("l2_date"),
                "l1_price": hit.get("l1_price"),
                "l2_price": hit.get("l2_price"),
                "neckline": hit.get("neckline"),
                "neck_date": hit.get("neck_date"),
                "last_close": hit.get("last_close"),
                "confirm_date": hit.get("confirm_date"),
                "trough_gap_bars": hit.get("trough_gap_bars"),
                "rise_to_neck_pct": hit.get("rise_to_neck_pct"),
                "boards": boards,
                "board_labels": "、".join(
                    str(b.get("board_name") or b.get("board_code") or "")
                    for b in boards
                    if b
                ),
                "detail": hit,
            }
            items.append(row)

        # confirmed 优先，再按突破日/代码
        def _sort_key(r: Dict[str, Any]):
            return (
                0 if r.get("status") == "confirmed" else 1,
                str(r.get("confirm_date") or r.get("l2_date") or ""),
                str(r.get("code") or ""),
            )

        items.sort(key=_sort_key)
        cap = int(max_results or scan.get("max_results") or 500)
        if cap > 0:
            items = items[:cap]

        return {
            "trade_date": date_s,
            "config_id": cid,
            "status_filter": sf,
            "scope_meta": pool.get("scope_meta") or {},
            "screened": len(codes),
            "hit_count": len(items),
            "items": items,
        }
