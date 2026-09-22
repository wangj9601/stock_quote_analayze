# -*- coding: utf-8 -*-
"""ZHAB 扫描引擎。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from .config import ZhabConfigManager, get_default_zhab_config
from .data_loader import (
    load_bars_batch,
    load_recent_zt_codes,
    resolve_mainline_universe,
)
from .detector import evaluate_zhab_bars

logger = logging.getLogger(__name__)


class ZhabStrategyEngine:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or get_default_zhab_config()

    def screen(
        self,
        db: Session,
        *,
        trade_date: str,
        sector: Optional[Dict[str, Any]] = None,
        concept_board_codes: Optional[Sequence[str]] = None,
        season: Any = None,
        gates_passed: Any = None,
        gates_total: Any = None,
        stock_codes: Optional[Sequence[str]] = None,
        require_mainline: Optional[bool] = None,
    ) -> Dict[str, Any]:
        scfg = dict((self.config or {}).get("structure") or {})
        ecfg = dict((self.config or {}).get("env") or {})
        scan = dict((self.config or {}).get("scan") or {})
        lookback = int(scan.get("zt_lookback_calendar_days", 20))
        history_bars = int(scan.get("history_bars", 160))
        batch_size = int(scan.get("batch_size", 200))
        max_results = int(scan.get("max_results") or 0)
        req_ml = (
            bool(require_mainline)
            if require_mainline is not None
            else bool(ecfg.get("require_mainline", True))
        )

        zt_map = load_recent_zt_codes(db, trade_date, lookback_calendar_days=lookback)
        mainline = resolve_mainline_universe(
            db, sector=sector, concept_board_codes=concept_board_codes
        )

        if stock_codes:
            universe = {str(c).zfill(6) if str(c).isdigit() else str(c) for c in stock_codes}
            universe &= set(zt_map.keys()) or universe
        else:
            universe = set(zt_map.keys())
            if req_ml and mainline:
                universe &= mainline
            elif req_ml and not mainline:
                # 无主线时仍扫涨停池，但板块维度会在 detector 内否决（in_mainline=False）
                pass

        codes = sorted(universe)
        items: List[Dict[str, Any]] = []
        screened = 0
        for i in range(0, len(codes), max(1, batch_size)):
            chunk = codes[i : i + batch_size]
            bars_map = load_bars_batch(db, chunk, trade_date, history_bars=history_bars)
            for code in chunk:
                bars = bars_map.get(code) or []
                if not bars:
                    continue
                screened += 1
                name = bars[-1].get("name")
                in_ml = (code in mainline) if mainline else (not req_ml)
                try:
                    hit = evaluate_zhab_bars(
                        bars,
                        code=code,
                        asof_date=trade_date[:10],
                        zt_dates=zt_map.get(code) or [],
                        in_mainline=in_ml,
                        require_mainline=req_ml and bool(mainline),
                        season=season,
                        gates_passed=gates_passed,
                        gates_total=gates_total,
                        structure_cfg=scfg,
                        env_cfg=ecfg,
                        name=name,
                    )
                except Exception:
                    logger.debug("ZHAB evaluate failed code=%s", code, exc_info=True)
                    continue
                if hit is None:
                    continue
                if hit.get("signal_type") == "invalid":
                    items.append(hit)
                    continue
                items.append(hit)
                if max_results > 0 and len([x for x in items if x.get("setup_ok")]) >= max_results:
                    break

        setup_n = sum(1 for x in items if x.get("signal_type") == "setup")
        bo_n = sum(1 for x in items if x.get("signal_type") == "breakout")
        inv_n = sum(1 for x in items if x.get("signal_type") == "invalid")
        logger.info(
            "ZHAB screen date=%s universe=%s screened=%s setup=%s breakout=%s invalid=%s",
            trade_date[:10],
            len(codes),
            screened,
            setup_n,
            bo_n,
            inv_n,
        )
        return {
            "trade_date": trade_date[:10],
            "universe": len(codes),
            "screened": screened,
            "setup_count": setup_n,
            "breakout_count": bo_n,
            "invalid_count": inv_n,
            "items": items,
            "mainline_size": len(mainline),
        }


def ensure_zhab_signals(
    db: Session,
    trade_date: str,
    *,
    sector: Optional[Dict[str, Any]] = None,
    concept_board_codes: Optional[Sequence[str]] = None,
    season: Any = None,
    gates: Optional[Dict[str, Any]] = None,
    config_id: Optional[int] = None,
    persist: bool = True,
) -> Dict[str, Any]:
    """扫描并可选落库，供复盘 / 推荐复用。"""
    from .signal_storage import upsert_signal_traces

    cm = ZhabConfigManager()
    cid = int(config_id) if config_id is not None else cm.get_default_config_id()
    cfg = cm.get_config(cid)
    engine = ZhabStrategyEngine(config=cfg)
    season_name = season
    if isinstance(season, dict):
        season_name = season.get("season")
    gates = gates or {}
    result = engine.screen(
        db,
        trade_date=trade_date[:10],
        sector=sector,
        concept_board_codes=concept_board_codes,
        season=season_name,
        gates_passed=gates.get("passed"),
        gates_total=gates.get("total"),
    )
    saved = 0
    if persist:
        saved = upsert_signal_traces(
            db,
            list(result.get("items") or []),
            config_id=cid,
            trade_date=trade_date[:10],
        )
    result["config_id"] = cid
    result["saved"] = saved
    return result
