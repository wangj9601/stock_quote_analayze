# -*- coding: utf-8 -*-
"""CSB 策略配置：默认参数 + csb_strategy_configs 多版本。"""

from __future__ import annotations

import copy
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_CACHE: Dict[int, Dict[str, Any]] = {}

# 信号类型常量
CSB_SETUP = "CSB_SETUP"
CSB_PROBE = "CSB_PROBE"
CSB_BREAKOUT = "CSB_BREAKOUT"
CSB_FALSE_BREAK = "CSB_FALSE_BREAK"
CSB_STOP = "CSB_STOP"
CSB_TRAIL = "CSB_TRAIL"

BUY_SIGNAL_TYPES = frozenset({CSB_PROBE, CSB_BREAKOUT})

# 全市场扫描占位
CSB_TRACE_SCANNED_MARKER = "__CSB_SCANNED__"


def get_default_csb_config() -> Dict[str, Any]:
    return {
        "channel": {
            "ma_squeeze_pct": 0.04,
            "squeeze_days": 15,
            "touch_tol_pct": 0.015,
            "min_touches": 2,
        },
        "ma250": {
            "slope_min": -0.0005,
        },
        "turnover": {
            "min_avg_20": 1.0,
        },
        "dry_vol": {
            "dry_vol_ratio": 0.55,
            "lookback_short": 5,
            "lookback_long": 60,
        },
        "entry": {
            "vol_ratio_probe_max": 0.8,
            "vol_expand_mult": 2.0,
            "break_pct": 0.02,
            "body_min_pct": 0.03,
            "upper_shadow_max_ratio": 0.30,
        },
        "position": {
            "probe_pct": 0.12,
            "breakout_add_pct": 0.25,
        },
        "defense": {
            "false_break_days": 3,
            "trail_ma": 20,
        },
        "scan": {
            "history_bars": 280,
            "max_results": 200,
            "batch_size": 200,
        },
        "backtest": {
            "horizon_days": 10,
            "target_pct": 0.10,
            "commission_bps": 5,
            "slippage_bps": 5,
        },
        "premium": {
            "squeeze_days_min": 20,
            "min_touches": 3,
            "vol_expand_mult": 2.5,
        },
        "min_score": 60.0,
        "min_listing_bars": 250,
        "signal_quality_mode": "standard",
    }


class CSBConfigManager:
    """CSB 配置管理器（对齐 SBBR/RPE）。"""

    def get_default_config(self) -> Dict[str, Any]:
        return get_default_csb_config()

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        result = copy.deepcopy(base)
        for k, v in (override or {}).items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = self._deep_merge(result[k], v)
            else:
                result[k] = copy.deepcopy(v)
        return result

    def _session(self):
        from backend_api.database import SessionLocal

        return SessionLocal()

    def _invalidate_cache(self, config_id: Optional[int] = None) -> None:
        if config_id is None:
            _CACHE.clear()
        else:
            _CACHE.pop(int(config_id), None)

    def _ensure_default_row_exists(self, db) -> int:
        from backend_api.models import CSBStrategyConfig

        row = (
            db.query(CSBStrategyConfig)
            .filter(CSBStrategyConfig.is_default.is_(True))
            .order_by(CSBStrategyConfig.id.asc())
            .first()
        )
        if row:
            return int(row.id)
        row = CSBStrategyConfig(
            name="default",
            description="CSB 默认参数",
            config_params=self.get_default_config(),
            is_default=True,
            is_active=True,
            precompute_enabled=True,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return int(row.id)

    def ensure_default_row(self, db) -> Optional[int]:
        try:
            return self._ensure_default_row_exists(db)
        except Exception as e:
            logger.warning("CSB ensure_default_row failed: %s", e)
            try:
                db.rollback()
            except Exception:
                pass
            return None

    def get_config(self, config_id: Optional[int] = None, db=None) -> Dict[str, Any]:
        if config_id is not None and config_id in _CACHE:
            return copy.deepcopy(_CACHE[int(config_id)])

        own_db = db is None
        if own_db:
            db = self._session()
        try:
            from backend_api.models import CSBStrategyConfig

            if config_id is None:
                cid = self._ensure_default_row_exists(db)
                row = db.query(CSBStrategyConfig).filter(CSBStrategyConfig.id == cid).first()
            else:
                row = (
                    db.query(CSBStrategyConfig)
                    .filter(CSBStrategyConfig.id == int(config_id), CSBStrategyConfig.is_active.is_(True))
                    .first()
                )
            if not row:
                return self.get_default_config()
            merged = self._deep_merge(self.get_default_config(), dict(row.config_params or {}))
            _CACHE[int(row.id)] = copy.deepcopy(merged)
            merged["_config_id"] = int(row.id)
            return merged
        except Exception as e:
            logger.warning("CSB get_config failed: %s", e)
            return self.get_default_config()
        finally:
            if own_db and db is not None:
                db.close()

    def merge_overrides(self, base: Optional[Dict[str, Any]] = None, **overrides) -> Dict[str, Any]:
        cfg = copy.deepcopy(base or self.get_default_config())
        for key in ("min_score", "min_listing_bars", "signal_quality_mode"):
            if key in overrides and overrides[key] is not None:
                cfg[key] = overrides[key]
        for sect in (
            "channel", "ma250", "turnover", "dry_vol", "entry",
            "position", "defense", "scan", "backtest", "premium",
        ):
            if overrides.get(sect) is not None:
                cfg[sect] = self._deep_merge(cfg.get(sect) or {}, overrides[sect])
        return cfg

    def list_configs(self, db, *, active_only: bool = False) -> List[Dict[str, Any]]:
        from backend_api.models import CSBStrategyConfig

        q = db.query(CSBStrategyConfig).order_by(CSBStrategyConfig.id.asc())
        if active_only:
            q = q.filter(CSBStrategyConfig.is_active.is_(True))
        return [self._serialize_row(r) for r in q.all()]

    def get_config_row(self, db, config_id: int):
        from backend_api.models import CSBStrategyConfig

        return db.query(CSBStrategyConfig).filter(CSBStrategyConfig.id == int(config_id)).first()

    def _serialize_row(self, row) -> Dict[str, Any]:
        return {
            "id": row.id,
            "name": row.name,
            "description": row.description,
            "config_params": row.config_params,
            "is_active": bool(row.is_active),
            "is_default": bool(row.is_default),
            "precompute_enabled": bool(getattr(row, "precompute_enabled", False)),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    def list_precompute_config_ids(self, db) -> List[int]:
        from backend_api.models import CSBStrategyConfig

        rows = (
            db.query(CSBStrategyConfig.id)
            .filter(
                CSBStrategyConfig.is_active.is_(True),
                (
                    (CSBStrategyConfig.is_default.is_(True))
                    | (CSBStrategyConfig.precompute_enabled.is_(True))
                ),
            )
            .order_by(CSBStrategyConfig.id.asc())
            .all()
        )
        return [int(r[0]) for r in rows]

    def create_config(
        self,
        db,
        *,
        name: str,
        config_params: Optional[Dict[str, Any]] = None,
        description: str = "",
        is_active: bool = True,
        is_default: bool = False,
        precompute_enabled: bool = False,
    ) -> int:
        from backend_api.models import CSBStrategyConfig

        params = self._deep_merge(self.get_default_config(), config_params or {})
        if is_default:
            db.query(CSBStrategyConfig).filter(CSBStrategyConfig.is_default.is_(True)).update(
                {"is_default": False}
            )
        row = CSBStrategyConfig(
            name=name,
            description=description,
            config_params=params,
            is_active=is_active,
            is_default=is_default,
            precompute_enabled=bool(precompute_enabled),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        self._invalidate_cache()
        return int(row.id)

    def update_config(
        self,
        db,
        config_id: int,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        config_params: Optional[Dict[str, Any]] = None,
        is_active: Optional[bool] = None,
        is_default: Optional[bool] = None,
        precompute_enabled: Optional[bool] = None,
    ) -> bool:
        from backend_api.models import CSBStrategyConfig

        row = self.get_config_row(db, config_id)
        if not row:
            return False
        if name is not None:
            row.name = name
        if description is not None:
            row.description = description
        if config_params is not None:
            row.config_params = self._deep_merge(self.get_default_config(), config_params)
        if is_active is not None:
            row.is_active = is_active
        if is_default is True:
            db.query(CSBStrategyConfig).filter(CSBStrategyConfig.is_default.is_(True)).update(
                {"is_default": False}
            )
            row.is_default = True
        elif is_default is False:
            row.is_default = False
        if precompute_enabled is not None:
            row.precompute_enabled = bool(precompute_enabled)
        row.updated_at = datetime.now()
        db.commit()
        self._invalidate_cache(config_id)
        return True
