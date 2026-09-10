# -*- coding: utf-8 -*-
"""CSB 对外选股入口（优先读 csb_signal_trace）。"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .config import CSBConfigManager
from .data_loader import CSBDataLoader
from .strategy_engine import CSBStrategyEngine
from .trace_store import dates_ready_for_universe_backtest, query_buy_signals_for_date

logger = logging.getLogger(__name__)


class CSBFrontendInterface:
    @staticmethod
    def _resolve_config_id(db: Session, config_id: Optional[int], cm: CSBConfigManager) -> Optional[int]:
        if config_id is not None:
            return int(config_id)
        try:
            from backend_api.models import CSBStrategyConfig

            row = (
                db.query(CSBStrategyConfig)
                .filter(CSBStrategyConfig.is_default.is_(True), CSBStrategyConfig.is_active.is_(True))
                .order_by(CSBStrategyConfig.id.asc())
                .first()
            )
            return int(row.id) if row else None
        except Exception:
            return None

    @staticmethod
    def screen(
        db: Session,
        *,
        scope: str = "all",
        limit: Optional[int] = None,
        stock_codes: Optional[List[str]] = None,
        screening_date: Optional[str] = None,
        config_id: Optional[int] = None,
        min_score: Optional[float] = None,
        prefer_cache: bool = True,
        force_realtime: bool = False,
        require_entry: bool = True,
    ) -> Dict[str, Any]:
        cm = CSBConfigManager()
        try:
            cm.ensure_default_row(db)
        except Exception:
            pass

        resolved_id = CSBFrontendInterface._resolve_config_id(db, config_id, cm)
        base = cm.get_config(resolved_id, db=db)
        cfg = cm.merge_overrides(base, min_score=min_score) if min_score is not None else base

        loader = CSBDataLoader(db)
        effective = loader.resolve_effective_trade_date(screening_date)
        data: List[Dict[str, Any]] = []
        data_source = "realtime"

        if prefer_cache and not force_realtime and resolved_id is not None and require_entry:
            try:
                cached = query_buy_signals_for_date(
                    db,
                    trade_date=effective,
                    config_id=resolved_id,
                    min_score=float(cfg.get("min_score") or 0),
                    limit=limit,
                ) or []
                if stock_codes is not None:
                    allow = {str(c).strip().zfill(6) if str(c).strip().isdigit() else str(c).strip() for c in stock_codes}
                    cached = [r for r in cached if str(r.get("code") or "").zfill(6) in allow]
                date_ready = effective in dates_ready_for_universe_backtest(
                    db, config_id=int(resolved_id), dates=[effective], stock_pool=stock_codes
                )
                if cached or date_ready:
                    data = cached
                    data_source = "csb_signal_trace"
            except Exception as e:
                logger.debug("CSB cache read failed: %s", e)

        if not data:
            allow_full_rt = (os.getenv("CSB_ALLOW_FULL_MARKET_REALTIME") or "").strip().lower() in (
                "1", "true", "yes", "on",
            )
            if stock_codes is None and not limit and not allow_full_rt:
                return {
                    "success": False,
                    "data": [],
                    "total": 0,
                    "strategy_name": "CSB通道突破",
                    "message": f"全市场暂无预计算（{effective}），请先执行 CSB 预计算或缩小范围。",
                    "need_precompute": True,
                    "search_date": effective,
                }
            stocks = loader.list_a_share_candidates(
                limit=limit if stock_codes is None else None,
                stock_codes=stock_codes,
            )
            engine = CSBStrategyEngine(loader, cfg)
            data = engine.screen(
                stocks,
                as_of_end_date=effective,
                config=cfg,
                require_entry=require_entry,
                max_results=limit,
            )

        return {
            "success": True,
            "data": data,
            "total": len(data),
            "strategy_name": "CSB通道突破",
            "scope": scope,
            "parameters": {
                "config_id": resolved_id,
                "min_score": cfg.get("min_score"),
                "screening_date_effective": effective,
                "data_source": data_source,
            },
            "search_date": effective,
            "data_source": data_source,
        }
