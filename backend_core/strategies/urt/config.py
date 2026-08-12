# -*- coding: utf-8 -*-
"""URT 上升趋势策略 — 配置（urt_config.json + 可选 DB 多版本）。"""

from __future__ import annotations

import json
import logging
import os
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_CACHE: Dict[int, Dict[str, Any]] = {}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        elif v is not None:
            out[k] = deepcopy(v)
    return out


class URTConfigManager:
    """默认参数 ← JSON；有 DB 时以 urt_strategy_configs 为主源。"""

    def __init__(self, config_file: str = "urt_config.json"):
        self.config_file = config_file
        self.default_config_path = os.path.join(os.path.dirname(__file__), self.config_file)

    def get_default_config(self) -> Dict[str, Any]:
        return {
            "ma_period": 20,
            "yang_rule_a": {"window": 4, "min_up_days": 3},
            "yang_rule_b": {"window": 5, "min_up_days": 4},
            # 中期阳线：use_yang_medium=true 时参与硬筛（须全部满足）
            "yang_medium_rules": [
                {"window": 10, "min_up_days": 6},
                {"window": 15, "min_up_days": 8},
                {"window": 20, "min_up_days": 10},
            ],
            "use_yang_medium": True,
            # 均线多头：require_ma_bull=true 时硬筛
            "require_ma_bull": True,
            "ma_bull_periods": [5, 10, 20],
            "volume_lookback": 20,
            "volume_multiple": 3.0,
            # 量能分项拉满阈值（≥ 此倍数得满分 34）
            "volume_score_full_multiple": 4.0,
            "min_score": 70,
            "use_turnover": True,
            "use_volume_ratio": False,
            "min_turnover": 3.0,
            "min_volume_ratio": 0.0,
            "history_calendar_days": 120,
            # KDE 支撑/阻力（与 RPE / 个股关键价位同口径）
            "kde_lookback_days": 250,
            "kde_lookback_step": 250,
            "kde_lookback_max": 750,
            "kde_base_factor": 1.0,
            "kde_grid_points": 200,
            # 结构盈亏比：RR 偏低仅软标签；破位/贴阻力/悬空可硬闸
            "structure_rr_warn_enabled": True,
            "structure_rr_min_rr": 2.0,
            "structure_rr_min_downside_pct": 0.015,
            # 相对现价上行空间低于该比例 → 视为贴阻力（硬闸）
            "structure_rr_min_upside_pct": 0.03,
            "structure_rr_hard_gate_enabled": True,
            "structure_hang_min_upside_pct": 0.08,
            "risk": {
                "stop_loss_pct_min": 5,
                "stop_loss_pct_max": 10,
                "time_stop_down_days": 3,
                "take_profit_alert_pct_min": 25,
                "take_profit_alert_pct_max": 30,
                "trailing_drawdown_pct": 5,
            },
        }

    def _load_from_json_file(self) -> Optional[Dict[str, Any]]:
        try:
            if os.path.exists(self.default_config_path):
                with open(self.default_config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning("读取 urt_config.json 失败: %s", e)
        return None

    def load_file_config(self) -> Dict[str, Any]:
        base = self.get_default_config()
        loaded = self._load_from_json_file()
        if loaded:
            return _deep_merge(base, loaded)
        return base

    def get_config(self, config_id: Optional[int] = None, db=None) -> Dict[str, Any]:
        """优先 DB 版本；否则 JSON 默认。"""
        if config_id is not None and db is not None:
            if config_id in _CACHE:
                return deepcopy(_CACHE[config_id])
            try:
                from backend_api.models import URTStrategyConfig

                row = (
                    db.query(URTStrategyConfig)
                    .filter(URTStrategyConfig.id == int(config_id), URTStrategyConfig.is_active.is_(True))
                    .first()
                )
                if row and isinstance(row.config_params, dict):
                    merged = _deep_merge(self.get_default_config(), dict(row.config_params))
                    _CACHE[config_id] = merged
                    return deepcopy(merged)
            except Exception as e:
                logger.warning("URT get_config from DB failed: %s", e)
        elif db is not None and config_id is None:
            try:
                from backend_api.models import URTStrategyConfig

                row = (
                    db.query(URTStrategyConfig)
                    .filter(URTStrategyConfig.is_default.is_(True), URTStrategyConfig.is_active.is_(True))
                    .order_by(URTStrategyConfig.id.asc())
                    .first()
                )
                if row:
                    return self.get_config(row.id, db=db)
            except Exception as e:
                logger.warning("URT default config lookup failed: %s", e)
        return self.load_file_config()

    def merge_overrides(self, base: Optional[Dict[str, Any]] = None, **overrides) -> Dict[str, Any]:
        cfg = deepcopy(base or self.load_file_config())
        for key in (
            "ma_period",
            "volume_lookback",
            "volume_multiple",
            "min_score",
            "use_turnover",
            "use_volume_ratio",
            "min_turnover",
            "min_volume_ratio",
            "history_calendar_days",
            "use_yang_medium",
            "require_ma_bull",
            "ma_bull_periods",
            "yang_medium_rules",
            "volume_score_full_multiple",
            "structure_rr_warn_enabled",
            "structure_rr_min_rr",
            "structure_rr_min_downside_pct",
            "structure_rr_min_upside_pct",
            "structure_rr_hard_gate_enabled",
            "structure_hang_min_upside_pct",
        ):
            if key in overrides and overrides[key] is not None:
                cfg[key] = overrides[key]
        if overrides.get("yang_rule_a") is not None:
            cfg["yang_rule_a"] = _deep_merge(cfg.get("yang_rule_a") or {}, overrides["yang_rule_a"])
        if overrides.get("yang_rule_b") is not None:
            cfg["yang_rule_b"] = _deep_merge(cfg.get("yang_rule_b") or {}, overrides["yang_rule_b"])
        if overrides.get("risk") is not None:
            cfg["risk"] = _deep_merge(cfg.get("risk") or {}, overrides["risk"])
        return cfg

    def invalidate_cache(self, config_id: Optional[int] = None) -> None:
        if config_id is None:
            _CACHE.clear()
        else:
            _CACHE.pop(int(config_id), None)

    def list_configs(self, db, *, active_only: bool = False) -> List[Dict[str, Any]]:
        from backend_api.models import URTStrategyConfig

        q = db.query(URTStrategyConfig).order_by(URTStrategyConfig.id.asc())
        if active_only:
            q = q.filter(URTStrategyConfig.is_active.is_(True))
        return [self._serialize_row(r) for r in q.all()]

    def get_config_row(self, db, config_id: int):
        from backend_api.models import URTStrategyConfig

        return db.query(URTStrategyConfig).filter(URTStrategyConfig.id == int(config_id)).first()

    def _serialize_row(self, row) -> Dict[str, Any]:
        return {
            "id": row.id,
            "name": row.name,
            "version_label": row.version_label,
            "description": row.description,
            "config_params": row.config_params,
            "is_active": bool(row.is_active),
            "is_default": bool(row.is_default),
            "precompute_enabled": bool(getattr(row, "precompute_enabled", False)),
            "created_by": row.created_by,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    def list_precompute_config_ids(self, db) -> List[int]:
        from backend_api.models import URTStrategyConfig

        rows = (
            db.query(URTStrategyConfig.id)
            .filter(
                URTStrategyConfig.is_active.is_(True),
                (
                    (URTStrategyConfig.is_default.is_(True))
                    | (URTStrategyConfig.precompute_enabled.is_(True))
                ),
            )
            .order_by(URTStrategyConfig.id.asc())
            .all()
        )
        return [int(r[0]) for r in rows]

    def update_config(
        self,
        db,
        config_id: int,
        *,
        name: Optional[str] = None,
        version_label: Optional[str] = None,
        description: Optional[str] = None,
        config_params: Optional[Dict[str, Any]] = None,
        is_active: Optional[bool] = None,
        is_default: Optional[bool] = None,
        precompute_enabled: Optional[bool] = None,
    ) -> bool:
        from backend_api.models import URTStrategyConfig

        row = self.get_config_row(db, config_id)
        if not row:
            return False
        if name is not None:
            row.name = name
        if version_label is not None:
            row.version_label = version_label
        if description is not None:
            row.description = description
        if config_params is not None:
            row.config_params = _deep_merge(self.get_default_config(), config_params)
        if is_active is not None:
            row.is_active = is_active
        if is_default is True:
            db.query(URTStrategyConfig).filter(URTStrategyConfig.is_default.is_(True)).update(
                {"is_default": False}
            )
            row.is_default = True
        elif is_default is False:
            row.is_default = False
        if precompute_enabled is not None:
            row.precompute_enabled = bool(precompute_enabled)
        row.updated_at = datetime.now()
        db.commit()
        self.invalidate_cache(config_id)
        return True

    def create_config(
        self,
        db,
        *,
        name: str,
        config_params: Optional[Dict[str, Any]] = None,
        version_label: Optional[str] = None,
        description: Optional[str] = None,
        is_active: bool = True,
        is_default: bool = False,
        precompute_enabled: bool = False,
        created_by: Optional[str] = None,
    ) -> int:
        from backend_api.models import URTStrategyConfig

        params = _deep_merge(self.get_default_config(), config_params or {})
        if is_default:
            db.query(URTStrategyConfig).filter(URTStrategyConfig.is_default.is_(True)).update(
                {"is_default": False}
            )
        row = URTStrategyConfig(
            name=name,
            version_label=version_label,
            description=description,
            config_params=params,
            is_active=is_active,
            is_default=is_default,
            precompute_enabled=bool(precompute_enabled),
            created_by=created_by,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        self.invalidate_cache()
        return int(row.id)

    def ensure_default_row(self, db) -> Optional[int]:
        """若表为空则写入 default 版本。

        不再在请求路径执行 CREATE/ALTER（易与 idle in transaction 互相锁死）。
        缺表/缺列请跑迁移：
          - python migrations/add_urt_core_tables.py
          - python migrations/add_urt_precompute_enabled_column.py
        """
        try:
            from backend_api.models import URTStrategyConfig

            existing = db.query(URTStrategyConfig).first()
            if existing:
                return int(existing.id)
            return self.create_config(
                db,
                name="default",
                version_label="v1",
                description="URT 上升趋势默认参数",
                config_params=self.load_file_config(),
                is_active=True,
                is_default=True,
                precompute_enabled=True,
                created_by="system",
            )
        except Exception as e:
            logger.warning("URT ensure_default_row failed: %s", e)
            try:
                db.rollback()
            except Exception:
                pass
            return None
