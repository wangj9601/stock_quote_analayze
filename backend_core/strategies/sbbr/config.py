"""SBBR 策略配置管理（代码默认 + PostgreSQL sbbr_strategy_configs 多版本）。"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_CACHE: Dict[int, Dict] = {}


def get_default_sbbr_config() -> Dict[str, Any]:
    return {
        "size": {
            "total_mv_min_yi": 20.0,
            "total_mv_max_yi": 200.0,
            "circ_mv_min_yi": 5.0,
            "circ_mv_max_yi": 10.0,
            "require_shares": True,
            "exclude_unknown_size": True,
        },
        "bottom": {
            "lookback_days": 60,
            "max_range_pct": 0.60,
            "touch_tol_pct": 0.02,
            "min_touches": 3,
            "max_touches": 4,
            "up_volume_gt_down": True,
            "panic_market_drop_pct": -0.02,
            "panic_stock_drop_pct": -0.05,
            "panic_reclaim_ma20": True,
        },
        "entry": {
            "ma_period": 20,
            "shrink_volume_ratio_max": 0.7,
            "expand_volume_ratio_min": 1.05,
            "expand_volume_ratio_max": 1.8,
            "require_market_sync_down": True,
            "market_lookback_days": 5,
            "market_drop_pct": -0.01,
        },
        "defense": {
            "buffer_min_pct": 0.02,
            "buffer_max_pct": 0.05,
            "default_buffer_pct": 0.03,
        },
        "exit": {
            "space_pcts": [0.50, 0.70, 1.00],
            "high_consolidate_days": 15,
            "high_consolidate_range_pct": 0.15,
            "turnover_sum_days": 5,
            "turnover_sum_pct": 100.0,
        },
        "position": {
            "probe_pct": 50.0,
            "add_pct": 30.0,
            "reserve_cash_pct": 20.0,
            "max_open_positions": 3,
            "small_capital_max_positions": 2,
            "small_capital_threshold": 1_000_000.0,
        },
        "scan": {
            "batch_size": 200,
            "max_results": 200,
            "history_bars": 120,
        },
        "alert": {
            "enable_entry": True,
            "enable_defense_breach": True,
            "enable_exit": True,
        },
        "backtest": {
            "horizon_days": 60,
            "target_pct": 0.50,
            "commission_bps": 5.0,
            "slippage_bps": 5.0,
        },
    }


class SBBRConfigManager:
    """SBBR 配置管理器。"""

    def get_default_config(self) -> Dict:
        return get_default_sbbr_config()

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
        from backend_api.models import SBBRStrategyConfig

        row = (
            db.query(SBBRStrategyConfig)
            .filter(SBBRStrategyConfig.is_default.is_(True))
            .order_by(SBBRStrategyConfig.id.asc())
            .first()
        )
        if row:
            return int(row.id)

        row = SBBRStrategyConfig(
            name="default",
            description="SBBR 默认参数",
            config_params=self.get_default_config(),
            is_default=True,
            is_active=True,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return int(row.id)

    def get_config(self, config_id: Optional[int] = None) -> Dict:
        if config_id is not None and config_id in _CACHE:
            return copy.deepcopy(_CACHE[config_id])

        db = self._session()
        try:
            from backend_api.models import SBBRStrategyConfig

            if config_id is None:
                cid = self._ensure_default_row_exists(db)
                row = db.query(SBBRStrategyConfig).filter(SBBRStrategyConfig.id == cid).first()
            else:
                row = (
                    db.query(SBBRStrategyConfig)
                    .filter(SBBRStrategyConfig.id == int(config_id))
                    .first()
                )
            if not row:
                return self.get_default_config()
            merged = self._deep_merge(self.get_default_config(), dict(row.config_params or {}))
            _CACHE[int(row.id)] = copy.deepcopy(merged)
            merged["_config_id"] = int(row.id)
            return merged
        except Exception as e:
            logger.warning("读取 SBBR 配置失败，使用默认: %s", e)
            return self.get_default_config()
        finally:
            db.close()

    def get_default_config_id(self) -> int:
        db = self._session()
        try:
            return self._ensure_default_row_exists(db)
        finally:
            db.close()

    def list_configs(self, active_only: bool = True) -> List[Dict]:
        db = self._session()
        try:
            from backend_api.models import SBBRStrategyConfig

            self._ensure_default_row_exists(db)
            q = db.query(SBBRStrategyConfig)
            if active_only:
                q = q.filter(SBBRStrategyConfig.is_active.is_(True))
            rows = q.order_by(SBBRStrategyConfig.is_default.desc(), SBBRStrategyConfig.id.asc()).all()
            return [
                {
                    "id": int(r.id),
                    "name": r.name,
                    "description": r.description,
                    "is_default": bool(r.is_default),
                    "is_active": bool(r.is_active),
                    "config_params": dict(r.config_params or {}),
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                }
                for r in rows
            ]
        finally:
            db.close()

    def create_config(
        self,
        name: str,
        config_params: Optional[Dict] = None,
        description: str = "",
        set_default: bool = False,
    ) -> Dict:
        db = self._session()
        try:
            from backend_api.models import SBBRStrategyConfig

            params = self._deep_merge(self.get_default_config(), config_params or {})
            if set_default:
                db.query(SBBRStrategyConfig).update({"is_default": False})
            row = SBBRStrategyConfig(
                name=name,
                description=description or "",
                config_params=params,
                is_default=bool(set_default),
                is_active=True,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            self._invalidate_cache()
            return {"id": int(row.id), "name": row.name, "is_default": bool(row.is_default)}
        finally:
            db.close()

    def update_config(self, config_id: int, patch: Dict) -> Dict:
        db = self._session()
        try:
            from backend_api.models import SBBRStrategyConfig

            row = db.query(SBBRStrategyConfig).filter(SBBRStrategyConfig.id == int(config_id)).first()
            if not row:
                raise ValueError(f"config_id={config_id} not found")
            if "name" in patch and patch["name"]:
                row.name = str(patch["name"])
            if "description" in patch:
                row.description = str(patch.get("description") or "")
            if "config_params" in patch and isinstance(patch["config_params"], dict):
                row.config_params = self._deep_merge(self.get_default_config(), patch["config_params"])
            if "is_active" in patch:
                row.is_active = bool(patch["is_active"])
            db.commit()
            self._invalidate_cache(int(config_id))
            return {"id": int(row.id), "ok": True}
        finally:
            db.close()

    def set_default(self, config_id: int) -> Dict:
        db = self._session()
        try:
            from backend_api.models import SBBRStrategyConfig

            row = db.query(SBBRStrategyConfig).filter(SBBRStrategyConfig.id == int(config_id)).first()
            if not row:
                raise ValueError(f"config_id={config_id} not found")
            db.query(SBBRStrategyConfig).update({"is_default": False})
            row.is_default = True
            db.commit()
            self._invalidate_cache()
            return {"id": int(row.id), "is_default": True}
        finally:
            db.close()

    def list_precompute_config_ids(self) -> List[int]:
        try:
            configs = self.list_configs(active_only=True)
            ids = [int(c["id"]) for c in configs if c.get("is_default") or c.get("is_active")]
            return list(dict.fromkeys(ids)) or [self.get_default_config_id()]
        except Exception:
            return [self.get_default_config_id()]
