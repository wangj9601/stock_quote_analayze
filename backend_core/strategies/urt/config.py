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
            # 均线多头：require_ma_bull=true 时硬筛（仅 ma_bull_periods）
            "require_ma_bull": True,
            "ma_bull_periods": [5, 10, 20],
            # 积分用加长链；硬筛不抬门槛
            "ma_bull_score_periods": [5, 10, 20, 30, 60, 120, 250],
            "ma_bull_score_max": 8.0,
            # 深度 d=0..6 → 分（满分 8）
            "ma_bull_score_table": [0, 1.5, 3, 4.5, 6, 7, 8],
            "volume_lookback": 20,
            "volume_multiple": 3.0,
            # 量能分项拉满阈值（≥ 此倍数得满分档，再缩放到 volume_score_max）
            "volume_score_full_multiple": 4.0,
            # 打分校准（225a）：降量能/连阳权重，抬结构位权重，加强过热扣分
            "volume_score_max": 20.0,
            "yang_score_max": 16.0,
            "yang_quality_score_max": 10.0,
            "yang_quality_window": 5,
            "yang_medium_score_max": 5.0,
            "ma20_score_mode": "slope_bias",
            "ma20_score_max": 10.0,
            "ma20_slope_days": 5,
            "structure_proximity_score_max": 10.0,
            "structure_rr_score_max": 9.0,
            "structure_proximity_full_pct": 0.02,
            "structure_proximity_zero_pct": 0.08,
            "structure_rr_score_full": 3.0,
            "structure_rr_score_mid": 2.0,
            "structure_rr_score_low": 1.5,
            "structure_rr_score_missing": 2.0,
            "overheat_penalty_max": 12.0,
            "min_score": 70,
            "use_turnover": True,
            "use_volume_ratio": False,
            "min_turnover": 3.0,
            "min_volume_ratio": 0.0,
            # 换手：门槛与积分解耦（use_turnover=总开关；未显式写新键时与之对齐）
            "turnover_hard_filter": True,
            "turnover_score_enabled": True,
            "turnover_score_max": 8.0,
            "turnover_score_min": -8.0,
            "turnover_lookback": 20,
            "turnover_rel_sweet_low": 1.0,
            "turnover_rel_sweet_high": 2.0,
            "turnover_rel_soft_cap": 3.5,
            "turnover_rel_penalty_full": 5.0,
            "turnover_abs_penalty_above": 25.0,
            "turnover_abs_penalty_full": 40.0,
            # 绝对回退甜区（中位样本不足时）
            "turnover_abs_sweet_low": 3.0,
            "turnover_abs_sweet_high": 7.0,
            "history_calendar_days": 120,
            # KDE 支撑/阻力（与个股关键价位：结构锚窗 + confluence）
            "kde_lookback_days": 60,
            "kde_lookback_step": 250,
            "kde_lookback_max": 750,
            "kde_base_factor": 1.0,
            "kde_grid_points": 200,
            "structure_use_structural_window": True,
            "structure_use_confluence": True,
            "structure_prefer_confluence": True,
            "structure_prefer_strong_confluence": True,
            # 结构盈亏比：RR 偏低仅软标签；破位/贴阻力/悬空可硬闸
            "structure_rr_warn_enabled": True,
            "structure_rr_min_rr": 2.0,
            "structure_rr_min_downside_pct": 0.015,
            # 相对现价上行空间低于该比例 → 视为贴阻力（硬闸，选股）
            "structure_rr_min_upside_pct": 0.03,
            "structure_rr_hard_gate_enabled": True,
            "structure_hang_min_upside_pct": 0.08,
            # RR 分母额外下限 k×ATR（0.5～1.0，默认 0.75）；0=关闭
            "structure_rr_atr_k": 0.75,
            # True：打分/提示用第二档支撑阻力；最近档仍只做硬闸
            "structure_rr_use_second_level": True,
            # 结构出场：阻力止盈最小上行空间（默认 5%，过近则改百分比/移动）
            "structure_exit_min_upside_pct": 0.05,
            # 结构出场回测：止损 = 支撑 × (1 - buffer)
            "structure_stop_buffer_pct": 0.02,
            # P0：缓存缺位时重算 KDE；P2：仍缺则弱结构兜底
            "structure_recompute_on_missing": True,
            "structure_weak_fallback_enabled": True,
            "structure_weak_lookback": 20,
            # 全路径浮盈保护（保本 / 峰值回撤）；兼容旧键 structure_fallback_*
            "structure_protect_enabled": True,
            "structure_protect_arm_pct": 0.065,
            "structure_protect_trail_drawdown_pct": 0.04,
            "structure_fallback_protect_enabled": True,
            "structure_fallback_arm_pct": 0.065,
            "structure_fallback_trail_drawdown_pct": 0.04,
            # 阻力分批：触及首阻力平部分仓，余仓移动止盈
            "structure_partial_exit_enabled": True,
            "structure_partial_exit_frac": 0.5,
            # 百分比目标改为跟踪：触及后不全仓硬平，改武装移动止盈
            "structure_pct_target_trail_enabled": True,
            # P3：回退止损百分比（可小于 risk.stop_loss_pct_max）
            "structure_fallback_stop_loss_pct": 8.0,
            # 近期涨幅过大：近窗相对最低价涨幅 + MA20 乖离
            "overheat_warn_enabled": True,
            "overheat_hard_gate_enabled": True,
            "overheat_lookback_days": 10,
            "overheat_soft_pct": 0.12,
            "overheat_hard_pct": 0.25,
            "overheat_bias_soft_pct": 0.15,
            "overheat_bias_hard_pct": 0.20,
            "risk": {
                "stop_loss_pct_min": 5,
                "stop_loss_pct_max": 10,
                "time_stop_down_days": 3,
                # 连跌须同时浮亏达到该比例才离场（避免放量后普通回调被洗出）
                "time_stop_min_loss_pct": 4.0,
                # 短线：约 +8% 起武装回撤止盈（原 25%–30% 几乎触发不到）
                "take_profit_alert_pct_min": 8,
                "take_profit_alert_pct_max": 10,
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

    def resolve_effective_config_id(self, db) -> Optional[int]:
        """当前生效策略版本 id（is_default && is_active）；无则 None（调用方回退文件默认）。"""
        if db is None:
            return None
        try:
            from backend_api.models import URTStrategyConfig

            row = (
                db.query(URTStrategyConfig)
                .filter(URTStrategyConfig.is_default.is_(True), URTStrategyConfig.is_active.is_(True))
                .order_by(URTStrategyConfig.id.asc())
                .first()
            )
            return int(row.id) if row else None
        except Exception as e:
            logger.warning("URT resolve_effective_config_id failed: %s", e)
            return None

    def get_config_meta(self, db, config_id: Optional[int] = None) -> Dict[str, Any]:
        """返回版本元信息 + 合并后的关键阈值（供前后端对齐展示）。"""
        self.ensure_default_row(db)
        effective_id = self.resolve_effective_config_id(db)
        resolved_id = int(config_id) if config_id is not None else effective_id
        row = self.get_config_row(db, resolved_id) if resolved_id is not None else None
        cfg = self.get_config(resolved_id, db=db)
        return {
            "config_id": resolved_id,
            "effective_config_id": effective_id,
            "is_effective": bool(
                resolved_id is not None and effective_id is not None and int(resolved_id) == int(effective_id)
            ),
            "name": (row.name if row else None) or "文件默认",
            "version_label": row.version_label if row else None,
            "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
            "min_score": cfg.get("min_score"),
            "volume_multiple": cfg.get("volume_multiple"),
            "config_params": cfg,
        }

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
            "ma_bull_score_periods",
            "ma_bull_score_max",
            "ma_bull_score_table",
            "yang_medium_rules",
            "volume_score_full_multiple",
            "volume_score_max",
            "yang_score_max",
            "yang_quality_score_max",
            "yang_quality_window",
            "yang_medium_score_max",
            "ma20_score_mode",
            "ma20_score_max",
            "ma20_slope_days",
            "structure_proximity_score_max",
            "structure_rr_score_max",
            "structure_proximity_full_pct",
            "structure_proximity_zero_pct",
            "structure_rr_score_full",
            "structure_rr_score_mid",
            "structure_rr_score_low",
            "structure_rr_score_missing",
            "overheat_penalty_max",
            "turnover_hard_filter",            "turnover_score_enabled",
            "turnover_score_max",
            "turnover_score_min",
            "turnover_lookback",
            "turnover_rel_sweet_low",
            "turnover_rel_sweet_high",
            "turnover_rel_soft_cap",
            "turnover_rel_penalty_full",
            "turnover_abs_penalty_above",
            "turnover_abs_penalty_full",
            "turnover_abs_sweet_low",
            "turnover_abs_sweet_high",
            "structure_rr_warn_enabled",
            "structure_rr_min_rr",
            "structure_rr_min_downside_pct",
            "structure_rr_min_upside_pct",
            "structure_exit_min_upside_pct",
            "structure_rr_hard_gate_enabled",
            "structure_hang_min_upside_pct",
            "structure_rr_atr_k",
            "structure_rr_use_second_level",
            "structure_stop_buffer_pct",
            "structure_use_structural_window",
            "structure_use_confluence",
            "structure_prefer_confluence",
            "structure_prefer_strong_confluence",
            "structure_recompute_on_missing",
            "structure_weak_fallback_enabled",
            "structure_weak_lookback",
            "structure_protect_enabled",
            "structure_protect_arm_pct",
            "structure_protect_trail_drawdown_pct",
            "structure_fallback_protect_enabled",
            "structure_fallback_arm_pct",
            "structure_fallback_trail_drawdown_pct",
            "structure_partial_exit_enabled",
            "structure_partial_exit_frac",
            "structure_pct_target_trail_enabled",
            "structure_fallback_stop_loss_pct",
            "overheat_warn_enabled",
            "overheat_hard_gate_enabled",
            "overheat_lookback_days",
            "overheat_soft_pct",
            "overheat_hard_pct",
            "overheat_bias_soft_pct",
            "overheat_bias_hard_pct",
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
