"""
GMS 策略配置管理（PostgreSQL gms_strategy_configs 多版本 + gms_runtime_config 兼容层）
"""

from __future__ import annotations

import copy
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_ROW_NAME = "default"
GMS_CANONICAL_STANDARD_NAME = "default"
GMS_CANONICAL_PENALTY_NAME = "gms_penalty"
CANONICAL_CONFIG_NAMES = frozenset({GMS_CANONICAL_STANDARD_NAME, GMS_CANONICAL_PENALTY_NAME})
_CACHE: Dict[int, Dict] = {}


class GMSConfigManager:
    """GMS 配置管理器：支持多版本参数快照。"""

    def __init__(self, config_file: str = "gms_config.json"):
        self.config_file = config_file
        self.default_config_path = os.path.join(
            os.path.dirname(__file__),
            self.config_file,
        )

    def get_default_config(self) -> Dict:
        """获取代码内置默认策略参数。"""
        return {
            "observation_period": 20,
            "ratio_indicators": {
                "use_ratio_d": True,
                "use_ratio_d_for_exit": False,
            },
            "left_buy": {
                "ratio_d20_abs_max": 0.015,
                "volume_ratio_max": 0.8,
                "min_accumulation_score": 0,
            },
            "right_buy": {
                "volume_ratio_min": 1.5,
            },
            "scoring": {
                "mechanism": "tiered_dual_max",
                "penalty_rules": [],
                "ma60_flat_lookback_days": 20,
                "ma60_flat_tol": 0.015,
                "accumulation_fz_min": 1.5,
                "balance_ratio_max": 0.01,
                "momentum_volume_ratio_min": 1.5,
                "watch_threshold": 60,
                "alert_threshold": 90,
            },
            "exit": {
                "trend_break_days": 3,
                "overbought_ratio": 0.15,
            },
            # 成交量加权 KDE 支撑/阻力（与 URT/RPE 同口径；亦可写在 structure/kde 子节）
            "kde_lookback_days": 250,
            "kde_lookback_initial": 250,
            "kde_lookback_step": 250,
            "kde_lookback_max": 750,
            "kde_base_factor": 1.0,
            "kde_grid_points": 200,
        }

    def _load_from_json_file(self) -> Optional[Dict]:
        try:
            if os.path.exists(self.default_config_path):
                with open(self.default_config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                default = self.get_default_config()
                return self._deep_merge(default, loaded)
        except Exception as e:
            logger.warning("读取本地 gms_config.json 失败: %s", e)
        return None

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        result = base.copy()
        for k, v in override.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = self._deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    def _invalidate_cache(self, config_id: Optional[int] = None) -> None:
        if config_id is None:
            _CACHE.clear()
        else:
            _CACHE.pop(config_id, None)

    def _session(self):
        from backend_api.database import SessionLocal

        return SessionLocal()

    def _ensure_default_row_exists(self, db) -> int:
        from backend_api.models import GMSStrategyConfig, GMSRuntimeConfig

        row = (
            db.query(GMSStrategyConfig)
            .filter(GMSStrategyConfig.is_default == True)  # noqa: E712
            .order_by(GMSStrategyConfig.id.asc())
            .first()
        )
        if row:
            return int(row.id)

        params = None
        runtime = (
            db.query(GMSRuntimeConfig)
            .filter(GMSRuntimeConfig.name == _DEFAULT_ROW_NAME)
            .first()
        )
        if runtime and runtime.config_params:
            params = dict(runtime.config_params)
        if params is None:
            file_merged = self._load_from_json_file()
            params = file_merged if file_merged is not None else self.get_default_config()
        else:
            params = self._deep_merge(self.get_default_config(), params)

        row = GMSStrategyConfig(
            name="default",
            version_label="1.0.0",
            description="系统默认 GMS 策略参数",
            config_params=params,
            is_active=True,
            is_default=True,
            precompute_enabled=True,
            created_by="system",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db.add(row)
        db.flush()
        self._sync_runtime_config_mirror(db, params)
        db.commit()
        return int(row.id)

    def _sync_runtime_config_mirror(self, db, config: Dict) -> None:
        """保持 gms_runtime_config.default 与默认版本镜像同步（兼容旧接口）。"""
        from backend_api.models import GMSRuntimeConfig

        row = (
            db.query(GMSRuntimeConfig)
            .filter(GMSRuntimeConfig.name == _DEFAULT_ROW_NAME)
            .first()
        )
        if row is None:
            db.add(
                GMSRuntimeConfig(
                    name=_DEFAULT_ROW_NAME,
                    config_params=config,
                    updated_at=datetime.now(),
                )
            )
        else:
            row.config_params = config
            row.updated_at = datetime.now()

    def resolve_config_id(self, config_id: Optional[int] = None) -> int:
        if config_id is not None:
            return int(config_id)
        db = self._session()
        try:
            return self._ensure_default_row_exists(db)
        finally:
            db.close()

    def should_use_trace(self, config_id: Optional[int] = None) -> bool:
        cid = self.resolve_config_id(config_id)
        db = self._session()
        try:
            from backend_api.models import GMSStrategyConfig

            row = db.query(GMSStrategyConfig).filter(GMSStrategyConfig.id == cid).first()
            if not row:
                return False
            return bool(row.is_default or row.precompute_enabled)
        finally:
            db.close()

    def get_config_row(self, config_id: int):
        from backend_api.models import GMSStrategyConfig

        db = self._session()
        try:
            return db.query(GMSStrategyConfig).filter(GMSStrategyConfig.id == config_id).first()
        finally:
            db.close()

    def get_config_row_by_name(self, name: str):
        from backend_api.models import GMSStrategyConfig

        db = self._session()
        try:
            return db.query(GMSStrategyConfig).filter(GMSStrategyConfig.name == name.strip()).first()
        finally:
            db.close()

    def get_config(self, config_id: Optional[int] = None) -> Dict:
        cid = self.resolve_config_id(config_id)
        if cid in _CACHE:
            return copy.deepcopy(_CACHE[cid])

        db = self._session()
        try:
            from backend_api.models import GMSStrategyConfig

            row = db.query(GMSStrategyConfig).filter(GMSStrategyConfig.id == cid).first()
            if not row or row.config_params is None:
                if config_id is None:
                    cid = self._ensure_default_row_exists(db)
                    row = db.query(GMSStrategyConfig).filter(GMSStrategyConfig.id == cid).first()
                if not row or row.config_params is None:
                    merged = self.get_default_config()
                    _CACHE[cid] = merged
                    return copy.deepcopy(merged)

            merged = self._deep_merge(self.get_default_config(), dict(row.config_params))
            _CACHE[cid] = merged
            return copy.deepcopy(merged)
        finally:
            db.close()

    def list_configs(self, active_only: bool = False, canonical_only: bool = False) -> List[Dict[str, Any]]:
        if canonical_only:
            return self.list_canonical_configs(active_only=active_only)
        from backend_api.models import GMSStrategyConfig

        db = self._session()
        try:
            q = db.query(GMSStrategyConfig).order_by(
                GMSStrategyConfig.is_default.desc(),
                GMSStrategyConfig.id.asc(),
            )
            if active_only:
                q = q.filter(GMSStrategyConfig.is_active == True)  # noqa: E712
            return [self._serialize_config_row(r) for r in q.all()]
        finally:
            db.close()

    def is_canonical_config(self, config_id: Optional[int]) -> bool:
        if not config_id:
            return False
        row = self.get_config_row(int(config_id))
        return bool(row and row.name in CANONICAL_CONFIG_NAMES)

    def resolve_canonical_config_id(self, mechanism: Optional[str] = None) -> int:
        """按打分机制返回共享参数版本：标准版 default / 减分版 gms_penalty。"""
        ids = self.ensure_canonical_configs()
        mech = (mechanism or "tiered_dual_max").strip()
        if mech == "tiered_dual_penalty":
            return int(ids[GMS_CANONICAL_PENALTY_NAME])
        return int(ids[GMS_CANONICAL_STANDARD_NAME])

    def ensure_canonical_configs(self) -> Dict[str, int]:
        """确保 default 与 gms_penalty 两个共享参数版本存在。"""
        db = self._session()
        try:
            default_id = self._ensure_default_row_exists(db)
        finally:
            db.close()

        penalty_row = self.get_config_row_by_name(GMS_CANONICAL_PENALTY_NAME)
        if penalty_row:
            penalty_id = int(penalty_row.id)
            if not penalty_row.is_active:
                self.update_config(penalty_id, {}, is_active=True, change_note="reactivate_canonical_penalty")
            self._ensure_poor_structure_rr_penalty_rule(penalty_id)
            return {GMS_CANONICAL_STANDARD_NAME: default_id, GMS_CANONICAL_PENALTY_NAME: penalty_id}

        legacy = self.get_config_row_by_name("auto_gms_v901")
        if legacy and legacy.config_params:
            params = copy.deepcopy(dict(legacy.config_params))
        else:
            params = self.get_default_config()
        scoring = dict(params.get("scoring") or {})
        scoring["mechanism"] = "tiered_dual_penalty"
        scoring.setdefault("ma60_flat_tol", 0.015)
        obs = int(params.get("observation_period") or 20)
        if scoring.get("ma60_flat_lookback_days") is None:
            scoring["ma60_flat_lookback_days"] = obs
        if not scoring.get("penalty_rules"):
            scoring["penalty_rules"] = [
                {
                    "id": "close_below_ma60",
                    "enabled": True,
                    "points": 10,
                    "label": "收盘低于60日均线",
                    "half_when_ma60_flat": True,
                },
                {
                    "id": "observation_range_amplitude",
                    "enabled": True,
                    "points": 10,
                    "label": "观察周期振幅过大",
                    "amplitude_threshold_pct": 0.30,
                },
                dict(self._default_poor_structure_rr_rule()),
            ]
        else:
            scoring["penalty_rules"] = self._merge_poor_structure_rr_into_rules(
                list(scoring.get("penalty_rules") or [])
            )
        params["scoring"] = scoring
        penalty_id = self.create_config(
            name=GMS_CANONICAL_PENALTY_NAME,
            config_params=params,
            version_label="1.0.0",
            description="GMS 增强版（阶梯+减分）共享参数",
            precompute_enabled=True,
            created_by="system",
        )
        return {GMS_CANONICAL_STANDARD_NAME: default_id, GMS_CANONICAL_PENALTY_NAME: penalty_id}

    @staticmethod
    def _default_poor_structure_rr_rule() -> Dict:
        return {
            "id": "poor_structure_rr",
            "enabled": True,
            "points": 10,
            "label": "结构盈亏比偏低",
            "min_rr": 1.5,
        }

    @classmethod
    def _merge_poor_structure_rr_into_rules(cls, rules: List) -> List:
        """缺省追加 poor_structure_rr，不覆盖已有同 id 规则。"""
        out = [r for r in (rules or []) if isinstance(r, dict)]
        if any(r.get("id") == "poor_structure_rr" for r in out):
            return out
        out.append(dict(cls._default_poor_structure_rr_rule()))
        return out

    def _ensure_poor_structure_rr_penalty_rule(self, penalty_id: int) -> None:
        """已有 gms_penalty 配置缺少结构盈亏比规则时合并写入（不改其它规则）。"""
        try:
            params = self.get_config(penalty_id)
            scoring = dict(params.get("scoring") or {})
            if (scoring.get("mechanism") or "").strip() != "tiered_dual_penalty":
                return
            rules = list(scoring.get("penalty_rules") or [])
            merged = self._merge_poor_structure_rr_into_rules(rules)
            if len(merged) == len(rules) and any(
                isinstance(r, dict) and r.get("id") == "poor_structure_rr" for r in rules
            ):
                return
            scoring["penalty_rules"] = merged
            self.update_config(
                penalty_id,
                {"scoring": scoring},
                change_note="add_poor_structure_rr_penalty",
            )
        except Exception as e:
            logger.warning("合并 poor_structure_rr 减分规则失败 config_id=%s: %s", penalty_id, e)

    def list_canonical_configs(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """仅返回选股/管理端使用的两个共享参数版本。"""
        from backend_core.strategies.gms.scoring import get_mechanism_meta

        ids = self.ensure_canonical_configs()
        out: List[Dict[str, Any]] = []
        for name in (GMS_CANONICAL_STANDARD_NAME, GMS_CANONICAL_PENALTY_NAME):
            row = self.get_config_row(ids[name])
            if not row:
                continue
            if active_only and not row.is_active:
                continue
            item = self._serialize_config_row(row)
            try:
                cfg = self.get_config(int(row.id))
                mechanism = (cfg.get("scoring") or {}).get("mechanism") or "tiered_dual_max"
                meta = get_mechanism_meta(mechanism)
                item["scoring_mechanism"] = mechanism
                item["scoring_mechanism_label"] = meta.get("label")
            except Exception:
                pass
            out.append(item)
        return out

    def deactivate_non_canonical_configs(self) -> int:
        """停用历史 auto_gms_* 等冗余参数版本（保留 default / gms_penalty）。"""
        from backend_api.models import GMSStrategyConfig

        db = self._session()
        try:
            rows = (
                db.query(GMSStrategyConfig)
                .filter(
                    GMSStrategyConfig.is_active == True,  # noqa: E712
                    ~GMSStrategyConfig.name.in_(list(CANONICAL_CONFIG_NAMES)),
                )
                .all()
            )
            n = 0
            for row in rows:
                if row.is_default:
                    continue
                row.is_active = False
                row.updated_at = datetime.now()
                n += 1
            db.commit()
            self._invalidate_cache()
            return n
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def list_precompute_config_ids(self) -> List[int]:
        from backend_api.models import GMSStrategyConfig

        db = self._session()
        try:
            rows = (
                db.query(GMSStrategyConfig.id)
                .filter(
                    GMSStrategyConfig.is_active == True,  # noqa: E712
                    (GMSStrategyConfig.is_default == True)  # noqa: E712
                    | (GMSStrategyConfig.precompute_enabled == True),  # noqa: E712
                )
                .order_by(GMSStrategyConfig.id.asc())
                .all()
            )
            return [int(r[0]) for r in rows]
        finally:
            db.close()

    @staticmethod
    def _serialize_config_row(row) -> Dict[str, Any]:
        return {
            "id": row.id,
            "name": row.name,
            "version_label": row.version_label,
            "description": row.description,
            "config_params": row.config_params,
            "is_active": bool(row.is_active),
            "is_default": bool(row.is_default),
            "precompute_enabled": bool(row.precompute_enabled),
            "parent_id": row.parent_id,
            "created_by": row.created_by,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    def create_config(
        self,
        name: str,
        config_params: Dict,
        *,
        version_label: Optional[str] = None,
        description: Optional[str] = None,
        is_active: bool = True,
        is_default: bool = False,
        precompute_enabled: bool = False,
        parent_id: Optional[int] = None,
        created_by: Optional[str] = None,
    ) -> int:
        from backend_api.models import GMSStrategyConfig

        db = self._session()
        try:
            merged = self._deep_merge(self.get_default_config(), config_params or {})
            scoring = merged.get("scoring") or {}
            from backend_core.strategies.gms.scoring import validate_scoring_config, normalize_scoring_defaults

            merged["scoring"] = normalize_scoring_defaults(scoring)
            errs = validate_scoring_config(merged["scoring"])
            if errs:
                raise ValueError("; ".join(errs))
            row = GMSStrategyConfig(
                name=name.strip(),
                version_label=version_label,
                description=description,
                config_params=merged,
                is_active=is_active,
                is_default=False,
                precompute_enabled=precompute_enabled,
                parent_id=parent_id,
                created_by=created_by,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            db.add(row)
            db.flush()
            if is_default:
                self._set_default_in_tx(db, int(row.id))
            db.commit()
            self._invalidate_cache()
            return int(row.id)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def update_config(
        self,
        config_id: int,
        partial: Dict,
        *,
        name: Optional[str] = None,
        version_label: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
        precompute_enabled: Optional[bool] = None,
        change_note: Optional[str] = None,
    ) -> bool:
        from backend_api.models import GMSStrategyConfig

        db = self._session()
        try:
            row = db.query(GMSStrategyConfig).filter(GMSStrategyConfig.id == config_id).first()
            if not row:
                return False
            if name is not None:
                row.name = name.strip()
            if version_label is not None:
                row.version_label = version_label
            if description is not None:
                row.description = description
            if is_active is not None:
                if row.is_default and not is_active:
                    raise ValueError("不能禁用默认版本，请先指定新的默认版本")
                row.is_active = is_active
            if precompute_enabled is not None:
                row.precompute_enabled = precompute_enabled
            if partial:
                current = dict(row.config_params or {})
                merged = self._deep_merge(current, partial)
                scoring = merged.get("scoring") or {}
                from backend_core.strategies.gms.scoring import validate_scoring_config, normalize_scoring_defaults

                merged["scoring"] = normalize_scoring_defaults(scoring)
                errs = validate_scoring_config(merged["scoring"])
                if errs:
                    raise ValueError("; ".join(errs))
                row.config_params = merged
            row.updated_at = datetime.now()
            if row.is_default:
                self._sync_runtime_config_mirror(db, dict(row.config_params or {}))
            db.commit()
            self._invalidate_cache(config_id)
            if change_note:
                logger.info("GMS config %s updated: %s", config_id, change_note)
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def clone_config(
        self,
        config_id: int,
        new_name: str,
        *,
        created_by: Optional[str] = None,
        precompute_enabled: bool = False,
    ) -> int:
        row = self.get_config_row(config_id)
        if not row:
            raise ValueError("源配置不存在")
        return self.create_config(
            name=new_name,
            config_params=copy.deepcopy(row.config_params or {}),
            version_label=row.version_label,
            description=(row.description or "") + "（克隆）",
            is_active=True,
            is_default=False,
            precompute_enabled=precompute_enabled,
            parent_id=config_id,
            created_by=created_by,
        )

    def _set_default_in_tx(self, db, config_id: int) -> None:
        from backend_api.models import GMSStrategyConfig

        db.query(GMSStrategyConfig).filter(GMSStrategyConfig.is_default == True).update(  # noqa: E712
            {"is_default": False},
            synchronize_session=False,
        )
        row = db.query(GMSStrategyConfig).filter(GMSStrategyConfig.id == config_id).first()
        if not row:
            raise ValueError("配置不存在")
        row.is_default = True
        row.is_active = True
        row.precompute_enabled = True
        self._sync_runtime_config_mirror(db, dict(row.config_params or {}))

    def set_default(self, config_id: int) -> bool:
        db = self._session()
        try:
            self._set_default_in_tx(db, config_id)
            db.commit()
            self._invalidate_cache()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def deactivate_config(self, config_id: int) -> bool:
        row = self.get_config_row(config_id)
        if not row:
            return False
        if row.is_default:
            raise ValueError("不能禁用默认版本")
        return self.update_config(config_id, {}, is_active=False)

    def save_config(self, config: Dict) -> bool:
        """保存到默认版本（兼容旧 /api/admin/gms/config 接口）。"""
        default_id = self.resolve_config_id(None)
        return self.update_config(default_id, config, change_note="save_config compat")

    def load_config(self) -> Dict:
        """兼容旧接口：返回默认版本配置。"""
        return self.get_config(None)

    def compare_configs(self, config_id_a: int, config_id_b: int) -> Dict[str, Any]:
        cfg_a = self.get_config(config_id_a)
        cfg_b = self.get_config(config_id_b)
        diffs: List[Dict[str, Any]] = []

        def _walk(path: str, a: Any, b: Any) -> None:
            if isinstance(a, dict) and isinstance(b, dict):
                keys = set(a.keys()) | set(b.keys())
                for k in sorted(keys):
                    _walk(f"{path}.{k}" if path else k, a.get(k), b.get(k))
                return
            if a != b:
                diffs.append({"path": path, "a": a, "b": b})

        _walk("", cfg_a, cfg_b)
        return {"config_id_a": config_id_a, "config_id_b": config_id_b, "diffs": diffs}

    @staticmethod
    def config_to_flat_form(config: Dict) -> Dict[str, Any]:
        """将嵌套 config_params 转为网站/管理端选股表单使用的扁平字段。"""
        scoring = config.get("scoring") or {}
        left = config.get("left_buy") or {}
        right = config.get("right_buy") or {}
        exit_ = config.get("exit") or {}
        return {
            "observation_period": config.get("observation_period", 20),
            "scoring_mechanism": scoring.get("mechanism", "tiered_dual_max"),
            "penalty_rules": scoring.get("penalty_rules") or [],
            "ratio_d20_max": left.get("ratio_d20_abs_max"),
            "volume_ratio_max": left.get("volume_ratio_max"),
            "left_buy_min_accumulation": left.get("min_accumulation_score", 0),
            "volume_ratio_min": right.get("volume_ratio_min", scoring.get("momentum_volume_ratio_min")),
            "accumulation_fz_min": scoring.get("accumulation_fz_min"),
            "balance_ratio_max": scoring.get("balance_ratio_max"),
            "watch_threshold": scoring.get("watch_threshold"),
            "alert_threshold": scoring.get("alert_threshold"),
            "overbought_ratio": exit_.get("overbought_ratio"),
            "accumulation_s_threshold": scoring.get("accumulation_s_threshold"),
            "accumulation_a_threshold": scoring.get("accumulation_a_threshold"),
            "momentum_full_threshold": scoring.get("momentum_full_threshold"),
            "momentum_batch_threshold": scoring.get("momentum_batch_threshold"),
            "instant_deviation_stable_days": scoring.get("instant_deviation_stable_days"),
            "weight_acc_fz": scoring.get("weight_acc_fz"),
            "weight_acc_balance": scoring.get("weight_acc_balance"),
            "weight_acc_volume": scoring.get("weight_acc_volume"),
            "weight_mom_ratio_d1": scoring.get("weight_mom_ratio_d1"),
            "weight_mom_deviation": scoring.get("weight_mom_deviation"),
            "weight_mom_volume": scoring.get("weight_mom_volume"),
            "ma60_flat_lookback_days": scoring.get("ma60_flat_lookback_days"),
            "ma60_flat_tol": scoring.get("ma60_flat_tol"),
        }

    @staticmethod
    def flat_form_to_config_patch(flat: Dict[str, Any]) -> Dict[str, Any]:
        """扁平表单字段 → 嵌套 config 片段（用于深度合并）。"""
        patch: Dict[str, Any] = {}
        if flat.get("observation_period") is not None:
            patch["observation_period"] = flat["observation_period"]
        left: Dict[str, Any] = {}
        if flat.get("ratio_d20_max") is not None:
            left["ratio_d20_abs_max"] = flat["ratio_d20_max"]
        if flat.get("volume_ratio_max") is not None:
            left["volume_ratio_max"] = flat["volume_ratio_max"]
        if flat.get("left_buy_min_accumulation") is not None:
            left["min_accumulation_score"] = flat["left_buy_min_accumulation"]
        if left:
            patch["left_buy"] = left
        if flat.get("volume_ratio_min") is not None:
            patch["right_buy"] = {"volume_ratio_min": flat["volume_ratio_min"]}
        scoring: Dict[str, Any] = {}
        if flat.get("scoring_mechanism") is not None:
            scoring["mechanism"] = flat["scoring_mechanism"]
        if flat.get("penalty_rules") is not None:
            scoring["penalty_rules"] = flat["penalty_rules"]
        for fk, sk in (
            ("accumulation_fz_min", "accumulation_fz_min"),
            ("balance_ratio_max", "balance_ratio_max"),
            ("watch_threshold", "watch_threshold"),
            ("alert_threshold", "alert_threshold"),
            ("accumulation_s_threshold", "accumulation_s_threshold"),
            ("accumulation_a_threshold", "accumulation_a_threshold"),
            ("momentum_full_threshold", "momentum_full_threshold"),
            ("momentum_batch_threshold", "momentum_batch_threshold"),
            ("instant_deviation_stable_days", "instant_deviation_stable_days"),
            ("weight_acc_fz", "weight_acc_fz"),
            ("weight_acc_balance", "weight_acc_balance"),
            ("weight_acc_volume", "weight_acc_volume"),
            ("weight_mom_ratio_d1", "weight_mom_ratio_d1"),
            ("weight_mom_deviation", "weight_mom_deviation"),
            ("weight_mom_volume", "weight_mom_volume"),
            ("ma60_flat_lookback_days", "ma60_flat_lookback_days"),
            ("ma60_flat_tol", "ma60_flat_tol"),
        ):
            if flat.get(fk) is not None:
                scoring[sk] = flat[fk]
        if flat.get("volume_ratio_min") is not None:
            scoring["momentum_volume_ratio_min"] = flat["volume_ratio_min"]
        if scoring:
            patch["scoring"] = scoring
        if flat.get("overbought_ratio") is not None:
            patch["exit"] = {"overbought_ratio": flat["overbought_ratio"]}
        return patch
