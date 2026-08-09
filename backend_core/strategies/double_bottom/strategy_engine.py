# -*- coding: utf-8 -*-
"""DBLB 选股引擎：解析股票池 → 利旧/检测 → 双底识别。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from .config import DblbConfigManager, get_default_dblb_config
from .data_loader import batch_load_ohlc_asc, load_names, resolve_effective_trade_date
from .detector import detect_double_bottom
from .universe import enrich_items_with_ths_industry, resolve_stock_pool

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
        force_recompute: bool = False,
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
                "status_filter": sf,
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
                        st = row.get("status")
                        if sf != "both" and st != sf:
                            # 已有记录但不符过滤：仍视为已算过，跳过重算
                            reused_codes.add(code)
                            continue
                        reused_items.append(dict(row))
                        reused_codes.add(code)
                    codes_to_scan = [c for c in codes if c not in reused_codes]
            except Exception as e:
                logger.warning("DBLB reuse load failed, fallback full scan: %s", e)
                reused_items = []
                codes_to_scan = list(codes)

        lookback = max(
            int(pattern.get("lookback_days") or 120) + 20,
            int(scan.get("history_bars") or 160),
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
                "_from_cache": False,
            }
            new_items.append(row)

        items: List[Dict[str, Any]] = list(reused_items) + list(new_items)
        if items:
            enrich_items_with_ths_industry(db, items, force=(mode == "market"))

        items.sort(key=lambda r: str(r.get("code") or ""))
        items.sort(
            key=lambda r: str(r.get("confirm_date") or r.get("l2_date") or "")
            or "0000-00-00",
            reverse=True,
        )
        items.sort(key=lambda r: 0 if r.get("status") == "confirmed" else 1)

        # 命中条数默认不截断；仅当调用方显式传入 max_results>0 时才截断
        # （忽略配置 JSON 里历史遗留的 scan.max_results=500）
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
            "scope_meta": pool.get("scope_meta") or {},
            "screened": len(codes),
            "hit_count": len(items),
            "items": items,
            "force_recompute": bool(force_recompute),
            "reused": len(reused_items),
            "computed": len(codes_to_scan),
            "scope_codes": codes,
        }
