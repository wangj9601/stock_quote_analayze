# -*- coding: utf-8 -*-
"""CUPB 杯底形态策略配置管理（代码默认 + PostgreSQL cupb_strategy_configs 多版本）。"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_CACHE: Dict[int, Dict] = {}


def get_default_cupb_config() -> Dict[str, Any]:
    return {
        "pattern": {
            "lookback_days": 160,
            "min_bars": 50,
            "min_cup_bars": 20,
            "min_handle_bars": 5,
            "max_handle_bars": 20,
            "rim_rel_tol": 0.12,
            "cup_depth_min": 0.12,
            "cup_depth_max": 0.45,
            "handle_depth_min": 0.05,
            "handle_depth_max": 0.35,
            "handle_floor_frac": 0.50,
            "handle_retrace_of_rim_min": 0.08,
            "handle_retrace_of_rim_max": 0.18,
            "confirm_close_above": True,
            "confirm_buffer_pct": 0.005,
            "exclude_invalidated": True,
            "use_low_for_bottom": True,
            "use_high_for_rim": True,
            "invalidate_on_lower_low": True,
            "lower_low_tol_pct": 0.005,
            "prior_trend_min_pct": 0.30,
            "prior_trend_lookback": 120,
            "prior_trend_required": True,
            "cup_bottom_flat_bars": 3,
            "cup_bottom_flat_pct": 0.03,
            "cup_symmetry_max_ratio": 0.40,
            "cup_u_shape_required": True,
            "reject_upward_handle": True,
            "extended_cup_bars": 60,
            "grade_filter": "all",
        },
        "volume": {
            "enabled": True,
            "ma_window": 50,
            "bottom_shrink_ratio": 0.70,
            "handle_shrink_ratio": 0.65,
            "breakout_expand_ratio": 1.40,
            "right_expand_min_days": 3,
            "require_volume_confirm": False,
            "require_all": False,
        },
        "scan": {
            "batch_size": 200,
            "max_results": 0,
            "history_bars": 180,
            "status_filter": "both",
            "grade_filter": "all",
        },
    }


def merge_pattern_cfg(full_cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """合并 pattern + volume 供 detector 使用。"""
    cfg = dict(full_cfg or get_default_cupb_config())
    pattern = dict(cfg.get("pattern") or {})
    vol = cfg.get("volume")
    if isinstance(vol, dict):
        pattern["volume"] = dict(vol)
    gf = (cfg.get("scan") or {}).get("grade_filter")
    if gf and str(gf).strip().lower() not in ("", "all", "both"):
        pattern["grade_filter"] = str(gf).strip().lower()
    return pattern


class CupbConfigManager:
    """CUPB 配置管理器。"""

    def get_default_config(self) -> Dict:
        return get_default_cupb_config()

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
        from backend_api.models import CupbStrategyConfig

        row = (
            db.query(CupbStrategyConfig)
            .filter(CupbStrategyConfig.is_default.is_(True))
            .order_by(CupbStrategyConfig.id.asc())
            .first()
        )
        if row:
            return int(row.id)

        row = CupbStrategyConfig(
            name="default",
            description="杯底形态策略默认参数",
            config_params=self.get_default_config(),
            is_default=True,
            is_active=True,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return int(row.id)

    @staticmethod
    def _strip_hit_cap(cfg: Dict) -> Dict:
        out = copy.deepcopy(cfg) if cfg else get_default_cupb_config()
        scan = out.setdefault("scan", {})
        if isinstance(scan, dict):
            scan["max_results"] = 0
        return out

    def get_config(self, config_id: Optional[int] = None) -> Dict:
        if config_id is not None and config_id in _CACHE:
            cached = self._strip_hit_cap(_CACHE[config_id])
            cached["_config_id"] = int(config_id)
            return cached

        db = self._session()
        try:
            from backend_api.models import CupbStrategyConfig

            if config_id is None:
                cid = self._ensure_default_row_exists(db)
                row = db.query(CupbStrategyConfig).filter(CupbStrategyConfig.id == cid).first()
            else:
                row = (
                    db.query(CupbStrategyConfig)
                    .filter(CupbStrategyConfig.id == int(config_id))
                    .first()
                )
            if not row:
                return self._strip_hit_cap(self.get_default_config())
            merged = self._deep_merge(self.get_default_config(), dict(row.config_params or {}))
            merged = self._strip_hit_cap(merged)
            params = dict(row.config_params or {})
            scan_p = params.get("scan") if isinstance(params.get("scan"), dict) else None
            if scan_p is not None and int(scan_p.get("max_results") or 0) != 0:
                scan_p = dict(scan_p)
                scan_p["max_results"] = 0
                params["scan"] = scan_p
                row.config_params = params
                try:
                    db.commit()
                except Exception:
                    db.rollback()
            _CACHE[int(row.id)] = copy.deepcopy(merged)
            merged["_config_id"] = int(row.id)
            return merged
        except Exception as e:
            logger.warning("读取 CUPB 配置失败，使用默认: %s", e)
            return self._strip_hit_cap(self.get_default_config())
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
            from backend_api.models import CupbStrategyConfig

            self._ensure_default_row_exists(db)
            q = db.query(CupbStrategyConfig)
            if active_only:
                q = q.filter(CupbStrategyConfig.is_active.is_(True))
            rows = q.order_by(
                CupbStrategyConfig.is_default.desc(), CupbStrategyConfig.id.asc()
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
            from backend_api.models import CupbStrategyConfig

            params = self._deep_merge(self.get_default_config(), config_params or {})
            if set_default:
                db.query(CupbStrategyConfig).update({"is_default": False})
            row = CupbStrategyConfig(
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
            from backend_api.models import CupbStrategyConfig

            row = (
                db.query(CupbStrategyConfig)
                .filter(CupbStrategyConfig.id == int(config_id))
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
            from backend_api.models import CupbStrategyConfig

            row = (
                db.query(CupbStrategyConfig)
                .filter(CupbStrategyConfig.id == int(config_id))
                .first()
            )
            if not row:
                raise ValueError(f"config_id={config_id} not found")
            db.query(CupbStrategyConfig).update({"is_default": False})
            row.is_default = True
            db.commit()
            self._invalidate_cache()
            return {"id": int(row.id), "is_default": True}
        finally:
            db.close()
