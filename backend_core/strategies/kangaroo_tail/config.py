# -*- coding: utf-8 -*-
"""KGT 袋鼠尾策略配置管理。"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_CACHE: Dict[int, Dict] = {}


def get_default_kgt_config() -> Dict[str, Any]:
    return {
        "pattern": {
            "min_range_pct": 0.02,
            "max_body_ratio": 0.3333,
            "shadow_body_mult": 2.0,
            "shadow_range_mult": 0.5,
            "opposite_shadow_body_mult": 0.3,
            "close_half_ratio": 0.5,
            "require_trend_filter": True,
            "ma_period": 20,
            "exclude_limit_board": True,
            "directions": "both",  # bullish | bearish | both
            "lookback_signal_bars": 1,
        },
        "scan": {
            "batch_size": 200,
            "max_results": 0,
            "history_bars": 60,
            "direction_filter": "both",  # bullish | bearish | both
        },
    }


class KgtConfigManager:
    def get_default_config(self) -> Dict:
        return get_default_kgt_config()

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
        from backend_api.models import KgtStrategyConfig

        row = (
            db.query(KgtStrategyConfig)
            .filter(KgtStrategyConfig.is_default.is_(True))
            .order_by(KgtStrategyConfig.id.asc())
            .first()
        )
        if row:
            return int(row.id)

        row = KgtStrategyConfig(
            name="default",
            description="袋鼠尾策略默认参数",
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
            cached = copy.deepcopy(_CACHE[config_id])
            cached["_config_id"] = int(config_id)
            return cached

        db = self._session()
        try:
            from backend_api.models import KgtStrategyConfig

            if config_id is None:
                cid = self._ensure_default_row_exists(db)
                row = db.query(KgtStrategyConfig).filter(KgtStrategyConfig.id == cid).first()
            else:
                row = (
                    db.query(KgtStrategyConfig)
                    .filter(KgtStrategyConfig.id == int(config_id))
                    .first()
                )
            if not row:
                return self.get_default_config()
            merged = self._deep_merge(self.get_default_config(), dict(row.config_params or {}))
            _CACHE[int(row.id)] = copy.deepcopy(merged)
            merged["_config_id"] = int(row.id)
            return merged
        except Exception as e:
            logger.warning("读取 KGT 配置失败，使用默认: %s", e)
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
            from backend_api.models import KgtStrategyConfig

            self._ensure_default_row_exists(db)
            q = db.query(KgtStrategyConfig)
            if active_only:
                q = q.filter(KgtStrategyConfig.is_active.is_(True))
            rows = q.order_by(
                KgtStrategyConfig.is_default.desc(), KgtStrategyConfig.id.asc()
            ).all()
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
            from backend_api.models import KgtStrategyConfig

            params = self._deep_merge(self.get_default_config(), config_params or {})
            if set_default:
                db.query(KgtStrategyConfig).update({"is_default": False})
            row = KgtStrategyConfig(
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
            from backend_api.models import KgtStrategyConfig

            row = (
                db.query(KgtStrategyConfig)
                .filter(KgtStrategyConfig.id == int(config_id))
                .first()
            )
            if not row:
                raise ValueError(f"config_id={config_id} not found")
            if "name" in patch and patch["name"]:
                row.name = str(patch["name"])
            if "description" in patch:
                row.description = str(patch.get("description") or "")
            if "config_params" in patch and isinstance(patch["config_params"], dict):
                row.config_params = self._deep_merge(
                    self.get_default_config(), patch["config_params"]
                )
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
            from backend_api.models import KgtStrategyConfig

            row = (
                db.query(KgtStrategyConfig)
                .filter(KgtStrategyConfig.id == int(config_id))
                .first()
            )
            if not row:
                raise ValueError(f"config_id={config_id} not found")
            db.query(KgtStrategyConfig).update({"is_default": False})
            row.is_default = True
            db.commit()
            self._invalidate_cache()
            return {"id": int(row.id), "is_default": True}
        finally:
            db.close()
