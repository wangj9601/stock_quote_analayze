# -*- coding: utf-8 -*-
"""CUPB 预计算：管理端手动触发 + 收盘流程日终节点。"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


def _env_bool(key: str, default: bool = True) -> bool:
    raw = (os.getenv(key) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "y", "on")


def run_cupb_precompute(
    *,
    config_id: Optional[int] = None,
    trade_date: Optional[str] = None,
    status_filter: Optional[str] = None,
    stock_pool_mode: str = "stocks",
    industry_board_codes: Optional[Sequence[Any]] = None,
    concept_board_codes: Optional[Sequence[Any]] = None,
    stock_codes: Optional[Sequence[Any]] = None,
    universe_limit: Optional[int] = None,
    max_results: Optional[int] = None,
    market_scopes: Optional[Sequence[Any]] = None,
    cn_board_segments: Optional[Sequence[Any]] = None,
    force_recompute: bool = True,
    price_adjust: str = "none",
) -> Dict[str, Any]:
    from backend_api.database import SessionLocal

    from .config import CupbConfigManager
    from .signal_storage import delete_traces_not_in_codes, upsert_signal_traces
    from .strategy_engine import CupbStrategyEngine

    cm = CupbConfigManager()
    cid = int(config_id) if config_id is not None else cm.get_default_config_id()
    cfg = cm.get_config(cid)
    engine = CupbStrategyEngine(config=cfg)

    db = SessionLocal()
    try:
        result = engine.screen(
            db,
            trade_date=trade_date,
            config_id=cid,
            status_filter=status_filter,
            stock_pool_mode=stock_pool_mode,
            industry_board_codes=industry_board_codes,
            concept_board_codes=concept_board_codes,
            stock_codes=stock_codes,
            universe_limit=universe_limit,
            max_results=max_results,
            market_scopes=market_scopes,
            cn_board_segments=cn_board_segments,
            force_recompute=force_recompute,
            price_adjust=price_adjust,
        )
        items: List[Dict[str, Any]] = list(result.get("items") or [])
        date_s = str(result.get("trade_date") or trade_date or "")
        saved = upsert_signal_traces(
            db,
            items,
            config_id=cid,
            trade_date=date_s,
        )
        deleted = 0
        if force_recompute:
            deleted = delete_traces_not_in_codes(
                db,
                trade_date=date_s,
                config_id=cid,
                scope_codes=list(result.get("scope_codes") or []),
                keep_codes=[str(r.get("code") or "") for r in items],
            )
        return {
            "ok": True,
            "trade_date": result.get("trade_date"),
            "config_id": cid,
            "status_filter": result.get("status_filter"),
            "scope_meta": result.get("scope_meta") or {},
            "screened": result.get("screened"),
            "hit_count": result.get("hit_count"),
            "saved": saved,
            "deleted_stale": deleted,
            "force_recompute": bool(force_recompute),
            "reused": result.get("reused"),
            "computed": result.get("computed"),
        }
    except Exception as e:
        logger.exception("CUPB precompute failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        raise
    finally:
        db.close()


def scheduled_cupb_signals_cn() -> None:
    """A股收盘流程入口：全市场 CN、不复权、forming+confirmed 入库。

    失败向上抛，便于 `_wrap_plain` 将节点标红。周末直接返回。
    """
    if datetime.now().weekday() >= 5:
        return
    if not _env_bool("ENABLE_CUPB_PRECOMPUTE", True):
        logger.info("CUPB 信号预计算已禁用（ENABLE_CUPB_PRECOMPUTE=false）")
        return
    started = datetime.now()
    out = run_cupb_precompute(
        stock_pool_mode="market",
        market_scopes=["CN"],
        status_filter="both",
        force_recompute=True,
        price_adjust="none",
        universe_limit=0,
        max_results=0,
    )
    elapsed = (datetime.now() - started).total_seconds()
    logger.info(
        "CUPB 日终预计算完成 date=%s config_id=%s hit=%s saved=%s deleted=%s elapsed=%.1fs",
        out.get("trade_date"),
        out.get("config_id"),
        out.get("hit_count"),
        out.get("saved"),
        out.get("deleted_stale"),
        elapsed,
    )
