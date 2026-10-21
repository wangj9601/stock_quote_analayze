# -*- coding: utf-8 -*-
"""BVF 选股引擎。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from backend_core.analysis.chart_patterns.scanner import (
    apply_qfq_to_code_bars,
    normalize_price_adjust,
)
from backend_core.strategies.double_bottom.data_loader import (
    batch_load_ohlc_asc,
    load_names,
    resolve_effective_trade_date,
)
from backend_core.strategies.double_bottom.universe import (
    enrich_items_with_ths_industry,
    resolve_stock_pool,
)

from .config import BvfConfigManager, get_default_bvf_config
from .detector import detect_bottom_volume_fractal

logger = logging.getLogger(__name__)


def _f(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def _limit_flag(prev_close: Optional[float], close: Optional[float]) -> str:
    if prev_close is None or prev_close <= 0 or close is None:
        return "unknown"
    pct = (close - prev_close) / prev_close
    if pct >= 0.095:
        return "limit_up"
    if pct <= -0.095:
        return "limit_down"
    return "normal"


def _is_st_name(name: str) -> bool:
    n = (name or "").upper().replace(" ", "")
    return "ST" in n


class BvfStrategyEngine:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or get_default_bvf_config()

    def screen(
        self,
        db: Session,
        *,
        trade_date: Optional[str] = None,
        config_id: Optional[int] = None,
        stock_pool_mode: str = "stocks",
        industry_board_codes: Optional[Sequence[Any]] = None,
        concept_board_codes: Optional[Sequence[Any]] = None,
        stock_codes: Optional[Sequence[Any]] = None,
        universe_limit: Optional[int] = None,
        max_results: Optional[int] = None,
        force_recompute: bool = False,
    ) -> Dict[str, Any]:
        cm = BvfConfigManager()
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
        try:
            adjust_n = normalize_price_adjust(pattern.get("price_adjust") or "qfq")
        except ValueError:
            adjust_n = "qfq"

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
        empty = {
            "trade_date": date_s,
            "config_id": cid,
            "scope_meta": pool.get("scope_meta") or {},
            "screened": 0,
            "hit_count": 0,
            "items": [],
            "force_recompute": bool(force_recompute),
            "reused": 0,
            "computed": 0,
            "scope_codes": codes,
            "price_adjust": adjust_n,
        }
        if not codes:
            return empty

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
                        reused_items.append(dict(row))
                        reused_codes.add(code)
                    codes_to_scan = [c for c in codes if c not in reused_codes]
            except Exception as e:
                logger.warning("BVF reuse load failed, fallback full scan: %s", e)
                reused_items = []
                codes_to_scan = list(codes)

        lookback_bottom = int(pattern.get("lookback_bottom") or 60)
        vol_ma = int(pattern.get("vol_ma") or 20)
        min_listing = int(scan.get("min_listing_bars") or 60)
        lookback = max(
            lookback_bottom + 5,
            vol_ma + lookback_bottom + 5,
            min_listing + 5,
            int(scan.get("history_bars") or 90),
        )
        bars_by = (
            batch_load_ohlc_asc(db, codes_to_scan, lookback=lookback, asof=date_s)
            if codes_to_scan
            else {}
        )
        names = load_names(db, codes_to_scan) if codes_to_scan else {}
        exclude_st = bool(scan.get("exclude_st", True))
        exclude_suspended = bool(scan.get("exclude_suspended", True))

        try:
            from backend_api.utils.adj_quotes import AdjQuotesError
        except ImportError:
            try:
                from utils.adj_quotes import AdjQuotesError  # type: ignore
            except ImportError:
                AdjQuotesError = Exception  # type: ignore

        new_items: List[Dict[str, Any]] = []
        for code in codes_to_scan:
            bars = bars_by.get(code) or []
            if not bars:
                continue
            if date_s:
                bars = [b for b in bars if str(b.get("date") or "")[:10] <= date_s]
            name = names.get(code) or (bars[-1].get("name") if bars else "") or ""
            if exclude_st and _is_st_name(str(name)):
                continue
            if len(bars) < min_listing:
                continue
            if date_s and str(bars[-1].get("date") or "")[:10] != date_s:
                if exclude_suspended:
                    continue
            last_vol = _f(bars[-1].get("volume"))
            if exclude_suspended and (last_vol is None or last_vol <= 0):
                continue

            if adjust_n == "qfq":
                try:
                    bars, _ = apply_qfq_to_code_bars(db, code, bars)
                except AdjQuotesError as e:
                    logger.debug("BVF skip %s no qfq: %s", code, e)
                    continue
                except Exception as e:
                    logger.warning("BVF qfq failed for %s: %s", code, e)
                    continue

            if date_s and bars and str(bars[-1].get("date") or "")[:10] != date_s:
                continue

            hit = detect_bottom_volume_fractal(bars, pattern_cfg=pattern)
            if not hit:
                continue
            if date_s and str(hit.get("right_date") or "")[:10] != date_s:
                continue

            prev_close = _f(bars[-2].get("close")) if len(bars) >= 2 else None
            right_close = _f(bars[-1].get("close"))
            limit_flag = _limit_flag(prev_close, right_close)
            boards = list(boards_by.get(code) or [])
            row = {
                "code": code,
                "name": name,
                "date": date_s,
                "status": hit.get("status") or "hit",
                "left_date": hit.get("left_date"),
                "mid_date": hit.get("mid_date"),
                "right_date": hit.get("right_date"),
                "mid_low": hit.get("mid_low"),
                "min_low": hit.get("min_low"),
                "bottom_dev_pct": hit.get("bottom_dev_pct"),
                "vol_ratio_actual": hit.get("vol_ratio_actual"),
                "mid_volume": hit.get("mid_volume"),
                "last_close": hit.get("last_close"),
                "limit_flag": limit_flag,
                "price_adjust": adjust_n,
                "boards": boards,
                "board_labels": "、".join(
                    str(b.get("board_name") or b.get("board_code") or "")
                    for b in boards
                    if b
                ),
                "detail": {**hit, "price_adjust": adjust_n, "limit_flag": limit_flag},
                "_from_cache": False,
            }
            new_items.append(row)

        items: List[Dict[str, Any]] = list(reused_items) + list(new_items)
        if items:
            enrich_items_with_ths_industry(db, items, force=(mode == "market"))

        items.sort(key=lambda r: str(r.get("code") or ""))
        items.sort(
            key=lambda r: float(r.get("vol_ratio_actual") or 0),
            reverse=True,
        )

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
            "scope_meta": pool.get("scope_meta") or {},
            "screened": len(codes),
            "hit_count": len(items),
            "items": items,
            "force_recompute": bool(force_recompute),
            "reused": len(reused_items),
            "computed": len(codes_to_scan),
            "scope_codes": codes,
            "price_adjust": adjust_n,
        }
