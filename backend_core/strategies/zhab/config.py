# -*- coding: utf-8 -*-
"""ZHAB 策略可计算阈值（说明书六维 + 环境门控）。"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_CACHE: Dict[int, Dict] = {}


def get_default_zhab_config() -> Dict[str, Any]:
    return {
        "structure": {
            # 整理周期（涨停日后交易日数）
            "consol_days_min": 1,
            "consol_days_max": 6,
            "consol_days_best_lo": 2,
            "consol_days_best_hi": 4,
            # 量价收敛：横盘日量 / 涨停日量
            "consol_vol_vs_zt_max": 0.70,
            # 突破日量 / 横盘均量
            "breakout_vol_vs_consol_min": 1.5,
            # ATR 收敛：后半段 ATR 均值 / 前半段
            "atr_period": 3,
            "atr_converge_max_ratio": 1.0,
            # 空间真空软分：距近 lookback 日高点至少留 space_pct
            "space_lookback_days": 120,
            "space_vacuum_pct": 0.20,
            # 假突破：上影占比
            "false_break_upper_shadow_ratio": 0.50,
            "false_break_upper_vs_body": 2.0,
        },
        "env": {
            # 秋/冬或硬门槛未过半 → 突破仅观察、不可执行
            "cold_seasons": ["秋", "冬"],
            "gates_pass_ratio_min": 0.5,
            "require_mainline": True,
        },
        "scan": {
            "zt_lookback_calendar_days": 20,
            "history_bars": 160,
            "batch_size": 200,
            "max_results": 0,
        },
    }


class ZhabConfigManager:
    def get_default_config(self) -> Dict:
        return get_default_zhab_config()

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        result = copy.deepcopy(base)
        for k, v in (override or {}).items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = self._deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    def _session(self):
        from backend_api.database import SessionLocal

        return SessionLocal()

    def _invalidate_cache(self, config_id: Optional[int] = None) -> None:
        if config_id is None:
            _CACHE.clear()
        else:
            _CACHE.pop(config_id, None)

    def _ensure_default_row_exists(self, db) -> int:
        from backend_api.models import ZhabStrategyConfig

        row = (
            db.query(ZhabStrategyConfig)
            .filter(ZhabStrategyConfig.is_default.is_(True))
            .order_by(ZhabStrategyConfig.id.asc())
            .first()
        )
        if row:
            return int(row.id)

        row = ZhabStrategyConfig(
            name="default",
            description="涨停后高位蓄势再突破默认参数",
            config_params=self.get_default_config(),
            is_default=True,
            is_active=True,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return int(row.id)

    def get_default_config_id(self) -> int:
        db = self._session()
        try:
            return self._ensure_default_row_exists(db)
        finally:
            db.close()

    def get_config(self, config_id: Optional[int] = None) -> Dict[str, Any]:
        cid = int(config_id) if config_id is not None else None
        if cid is not None and cid in _CACHE:
            return copy.deepcopy(_CACHE[cid])
        db = self._session()
        try:
            from backend_api.models import ZhabStrategyConfig

            if cid is None:
                cid = self._ensure_default_row_exists(db)
            row = db.query(ZhabStrategyConfig).filter(ZhabStrategyConfig.id == cid).first()
            if not row:
                cfg = self.get_default_config()
            else:
                cfg = self._deep_merge(self.get_default_config(), row.config_params or {})
            _CACHE[cid] = copy.deepcopy(cfg)
            return copy.deepcopy(cfg)
        finally:
            db.close()
