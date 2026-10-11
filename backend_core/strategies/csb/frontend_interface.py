# -*- coding: utf-8 -*-
"""CSB 对外选股入口（优先读 csb_signal_trace，无缓存时可全市场现算并回写）。"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .config import CSBConfigManager
from .data_loader import CSBDataLoader
from .strategy_engine import CSBStrategyEngine
from .trace_store import (
    dates_ready_for_universe_backtest,
    mark_date_scanned,
    query_buy_signals_for_date,
    upsert_trace_rows,
)

logger = logging.getLogger(__name__)


def _env_allow_full_market_realtime() -> bool:
    """
    与 URT 对齐：默认允许全市场现算；设 CSB_ALLOW_FULL_MARKET_REALTIME=0 可快速失败，避免网关超时。
    """
    raw = (os.getenv("CSB_ALLOW_FULL_MARKET_REALTIME") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


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
        trace_only: bool = False,
        persist_realtime: bool = True,
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
        date_ready = False
        hint: Optional[str] = None

        if prefer_cache and not force_realtime and resolved_id is not None and require_entry:
            try:
                cached = query_buy_signals_for_date(
                    db,
                    trade_date=effective,
                    config_id=int(resolved_id),
                    min_score=float(cfg.get("min_score") or 0),
                    limit=limit,
                ) or []
                if stock_codes is not None:
                    allow = {
                        str(c).strip().zfill(6) if str(c).strip().isdigit() else str(c).strip()
                        for c in stock_codes
                    }
                    cached = [r for r in cached if str(r.get("code") or "").zfill(6) in allow]
                date_ready = effective in dates_ready_for_universe_backtest(
                    db, config_id=int(resolved_id), dates=[effective], stock_pool=stock_codes
                )
                if cached or date_ready:
                    data = cached
                    data_source = "csb_signal_trace"
                    if not cached and date_ready:
                        hint = f"基准日 {effective} 已有预计算，当日无符合条件的买点。"
            except Exception as e:
                logger.debug("CSB cache read failed: %s", e)

        # 仅读预计算：有覆盖（含 0 买点）即返回；无覆盖则提示需预计算/现算
        if trace_only and not force_realtime:
            if data_source == "csb_signal_trace":
                return {
                    "success": True,
                    "data": data,
                    "total": len(data),
                    "strategy_name": "CSB通道突破",
                    "scope": scope,
                    "message": hint,
                    "need_precompute": False,
                    "search_date": effective,
                    "config_id": resolved_id,
                    "source": data_source,
                    "data_source": data_source,
                    "parameters": {
                        "config_id": resolved_id,
                        "min_score": cfg.get("min_score"),
                        "screening_date_effective": effective,
                        "data_source": data_source,
                        "trace_only": True,
                    },
                }
            return {
                "success": True,
                "data": [],
                "total": 0,
                "strategy_name": "CSB通道突破",
                "scope": scope,
                "message": (
                    f"全市场暂无预计算（{effective}）。"
                    "将自动尝试现算；也可在管理端执行 CSB 信号预计算，或缩小为自选/板块/个股。"
                ),
                "need_precompute": True,
                "search_date": effective,
                "config_id": resolved_id,
                "source": "empty_trace",
                "data_source": "empty_trace",
                "parameters": {
                    "config_id": resolved_id,
                    "min_score": cfg.get("min_score"),
                    "screening_date_effective": effective,
                    "data_source": "empty_trace",
                    "trace_only": True,
                    "need_precompute": True,
                },
            }

        if data_source == "csb_signal_trace":
            return {
                "success": True,
                "data": data,
                "total": len(data),
                "strategy_name": "CSB通道突破",
                "scope": scope,
                "message": hint,
                "need_precompute": False,
                "search_date": effective,
                "config_id": resolved_id,
                "source": data_source,
                "data_source": data_source,
                "parameters": {
                    "config_id": resolved_id,
                    "min_score": cfg.get("min_score"),
                    "screening_date_effective": effective,
                    "data_source": data_source,
                },
            }

        full_market = stock_codes is None
        if full_market and not _env_allow_full_market_realtime():
            return {
                "success": True,
                "data": [],
                "total": 0,
                "strategy_name": "CSB通道突破",
                "scope": scope,
                "message": (
                    f"全市场暂无预计算（{effective}）。"
                    "请先在管理端/工作流执行 CSB 信号预计算，或将范围缩小为自选/板块/个股后再刷新。"
                    "（当前已关闭 CSB_ALLOW_FULL_MARKET_REALTIME）"
                ),
                "need_precompute": True,
                "search_date": effective,
                "config_id": resolved_id,
                "source": "empty_trace",
                "data_source": "empty_trace",
            }

        stocks = loader.list_a_share_candidates(stock_codes=stock_codes)
        engine = CSBStrategyEngine(loader, cfg)
        data = engine.screen(
            stocks,
            as_of_end_date=effective,
            config=cfg,
            require_entry=require_entry,
            max_results=limit,
        )
        data_source = "realtime"

        # 全市场现算结果回写 trace，便于下次「优先读预计算」命中（含 0 买点日）
        if (
            persist_realtime
            and full_market
            and resolved_id is not None
            and require_entry
        ):
            try:
                if data:
                    upsert_trace_rows(db, config_id=int(resolved_id), rows=data)
                mark_date_scanned(
                    db,
                    config_id=int(resolved_id),
                    trade_date=effective,
                    extra={
                        "hits": len(data),
                        "candidates": len(stocks),
                        "scope": "full_market",
                        "source": "frontend_screen",
                    },
                )
                data_source = "realtime+trace"
            except Exception as e:
                logger.warning("CSB 选股现算回写 trace 失败: %s", e)

        return {
            "success": True,
            "data": data,
            "total": len(data),
            "strategy_name": "CSB通道突破",
            "scope": scope,
            "message": (
                f"全市场现算完成（{effective}），命中 {len(data)} 只"
                + ("，已写入预计算缓存。" if data_source == "realtime+trace" else "。")
            )
            if full_market
            else None,
            "need_precompute": False,
            "search_date": effective,
            "config_id": resolved_id,
            "source": data_source,
            "data_source": data_source,
            "parameters": {
                "config_id": resolved_id,
                "min_score": cfg.get("min_score"),
                "screening_date_effective": effective,
                "data_source": data_source,
            },
        }
