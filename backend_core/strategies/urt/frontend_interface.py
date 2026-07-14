# -*- coding: utf-8 -*-
"""URT 对外选股入口（优先读 urt_signal_trace）。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .config import URTConfigManager
from .data_loader import URTDataLoader, normalize_urt_board_keys
from .strategy_engine import URTStrategyEngine
from .trace_store import query_buy_signals_for_date

logger = logging.getLogger(__name__)


class URTFrontendInterface:
    @staticmethod
    def _resolve_config_id(db: Session, config_id: Optional[int], cm: URTConfigManager) -> Optional[int]:
        if config_id is not None:
            return int(config_id)
        try:
            from backend_api.models import URTStrategyConfig

            row = (
                db.query(URTStrategyConfig)
                .filter(URTStrategyConfig.is_default.is_(True), URTStrategyConfig.is_active.is_(True))
                .order_by(URTStrategyConfig.id.asc())
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
        boards: Optional[List[str]] = None,
        screening_date: Optional[str] = None,
        config_id: Optional[int] = None,
        volume_multiple: Optional[float] = None,
        min_score: Optional[float] = None,
        use_turnover: Optional[bool] = None,
        use_volume_ratio: Optional[bool] = None,
        min_turnover: Optional[float] = None,
        min_volume_ratio: Optional[float] = None,
        prefer_cache: bool = True,
        force_realtime: bool = False,
    ) -> Dict[str, Any]:
        cm = URTConfigManager()
        try:
            cm.ensure_default_row(db)
        except Exception:
            pass

        resolved_id = URTFrontendInterface._resolve_config_id(db, config_id, cm)
        base = cm.get_config(resolved_id, db=db)
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

        board_keys = normalize_urt_board_keys(boards)
        overrides_active = any(
            x is not None
            for x in (
                volume_multiple,
                min_score,
                use_turnover,
                use_volume_ratio,
                min_turnover,
                min_volume_ratio,
            )
        )

        data: List[Dict[str, Any]] = []
        data_source = "realtime"
        # 无 Query 覆盖时优先读预计算；限定股票池时再按代码过滤
        if prefer_cache and not force_realtime and not overrides_active and not board_keys and resolved_id is not None:
            try:
                cached = query_buy_signals_for_date(
                    db,
                    trade_date=effective,
                    config_id=resolved_id,
                    min_score=float(cfg.get("min_score") or 70),
                    limit=None if stock_codes else limit,
                )
                if cached:
                    if stock_codes:
                        allow = {
                            str(c).strip().zfill(6) if str(c).strip().isdigit() else str(c).strip()
                            for c in stock_codes
                        }
                        cached = [
                            r
                            for r in cached
                            if str(r.get("code") or "").zfill(6) in allow or str(r.get("code")) in allow
                        ]
                    if cached:
                        if limit and len(cached) > int(limit):
                            cached = cached[: int(limit)]
                        data = cached
                        data_source = "urt_signal_trace"
            except Exception as e:
                logger.debug("URT cache read failed: %s", e)

        if not data:
            pool_codes = stock_codes if stock_codes is not None else None
            stocks = loader.list_a_share_candidates(
                limit=limit if pool_codes is None else None,
                stock_codes=pool_codes,
                boards=board_keys or None,
            )
            if limit and pool_codes is not None and len(stocks) > int(limit):
                # 缩池很大时仍可用 limit 限制扫描量
                stocks = stocks[: int(limit)]
            engine = URTStrategyEngine(loader, cfg)
            data = engine.screen_universe(stocks, as_of_end_date=effective)
            data_source = "realtime"

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
            "config_id": resolved_id,
            "screening_date_requested": req_norm,
            "screening_date_effective": effective,
            "data_source": data_source,
        }
        out: Dict[str, Any] = {
            "success": True,
            "data": data,
            "total": len(data),
            "strategy_name": "上升趋势策略",
            "scope": scope,
            "parameters": parameters_out,
            "search_date": effective,
            "data_source": data_source,
        }
        if hint:
            out["message"] = hint
        return out
