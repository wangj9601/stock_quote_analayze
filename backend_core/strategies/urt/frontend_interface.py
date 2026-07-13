# -*- coding: utf-8 -*-
"""URT 对外选股入口。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .config import URTConfigManager
from .data_loader import URTDataLoader, normalize_urt_board_keys
from .strategy_engine import URTStrategyEngine

logger = logging.getLogger(__name__)


class URTFrontendInterface:
    @staticmethod
    def screen(
        db: Session,
        *,
        scope: str = "all",
        limit: Optional[int] = None,
        stock_codes: Optional[List[str]] = None,
        boards: Optional[List[str]] = None,
        screening_date: Optional[str] = None,
        config_id: Optional[int] = None,
        volume_multiple: Optional[float] = None,
        min_score: Optional[float] = None,
        use_turnover: Optional[bool] = None,
        use_volume_ratio: Optional[bool] = None,
        min_turnover: Optional[float] = None,
        min_volume_ratio: Optional[float] = None,
    ) -> Dict[str, Any]:
        cm = URTConfigManager()
        try:
            cm.ensure_default_row(db)
        except Exception:
            pass

        base = cm.get_config(config_id, db=db)
        cfg = cm.merge_overrides(
            base,
            volume_multiple=volume_multiple,
            min_score=min_score,
            use_turnover=use_turnover,
            use_volume_ratio=use_volume_ratio,
            min_turnover=min_turnover,
            min_volume_ratio=min_volume_ratio,
        )

        loader = URTDataLoader(db)
        effective = URTDataLoader.resolve_effective_history_end_date(db, screening_date)
        today_s = datetime.now().strftime("%Y-%m-%d")
        req_norm = (screening_date or "").strip()[:10] or None
        hint: Optional[str] = None
        if effective != (req_norm or today_s):
            if req_norm:
                hint = (
                    f"基准日 {req_norm} 在历史行情表中无数据或尚未入库，"
                    f"已改用表内最新交易日 {effective}。"
                )
            else:
                hint = f"当前自然日 {today_s} 无行情数据，已改用表内最新交易日 {effective}。"

        pool_codes = stock_codes if scope == "watchlist" else None
        board_keys = normalize_urt_board_keys(boards)
        stocks = loader.list_a_share_candidates(
            limit=limit,
            stock_codes=pool_codes,
            boards=board_keys or None,
        )
        engine = URTStrategyEngine(loader, cfg)
        data = engine.screen_universe(stocks, as_of_end_date=effective)

        parameters_out = {
            "ma_period": cfg.get("ma_period"),
            "volume_lookback": cfg.get("volume_lookback"),
            "volume_multiple": cfg.get("volume_multiple"),
            "min_score": cfg.get("min_score"),
            "yang_rule_a": cfg.get("yang_rule_a"),
            "yang_rule_b": cfg.get("yang_rule_b"),
            "use_turnover": cfg.get("use_turnover"),
            "use_volume_ratio": cfg.get("use_volume_ratio"),
            "min_turnover": cfg.get("min_turnover"),
            "min_volume_ratio": cfg.get("min_volume_ratio"),
            "limit": limit,
            "boards": board_keys,
            "config_id": config_id,
            "screening_date_requested": req_norm,
            "screening_date_effective": effective,
        }
        out: Dict[str, Any] = {
            "success": True,
            "data": data,
            "total": len(data),
            "strategy_name": "上升趋势策略",
            "scope": scope,
            "parameters": parameters_out,
            "search_date": effective,
        }
        if hint:
            out["message"] = hint
        return out
