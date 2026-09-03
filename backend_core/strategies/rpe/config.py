"""RPE 策略配置管理。"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_CACHE: Dict[int, Dict] = {}


def get_default_rpe_config() -> Dict[str, Any]:
    return {
        "lookback_days": 250,
        "z_window": 40,
        "z_lead": 2.0,
        "z_catch_up": -1.5,
        "sector_slope_window": 60,
        # 与行情板块详情 / GMS 入库一致：对 ln(I_t) 回归（跨板可比）；none 为历史绝对价位斜率
        "sector_slope_transform": "log",
        "enable_trend_veto": True,
        "enable_lead_trade": False,
        "kde_base_factor": 1.0,
        "kde_grid_points": 200,
        # 带宽上限与扩窗衰减：打断「抹平→扩窗→更平滑」；max_bw≤0 表示不设上限
        "kde_min_bw": 0.01,
        "kde_max_bw": 0.08,
        "kde_expand_factor_decay": 0.85,
        # 支撑缺失时 KDE 回看：250 → +250 → +250，上限约 3 年交易日
        "kde_lookback_step": 250,
        "kde_lookback_max": 750,
        "min_rr_to_resistance": 1.5,
        "liquidity": {
            "lookback_days": 20,
            # 兼容旧配置：无 by_board 时全市场回退该值（元）
            "min_avg_amount": 5_000_000.0,
            "min_avg_turnover_rate": 0.8,
            # 分层绝对均额门槛（人民币元，非手数）
            "min_avg_amount_by_board": {
                "MAIN": 30_000_000.0,
                "SZ_SME": 20_000_000.0,
                "CYB": 15_000_000.0,
                "KCB": 15_000_000.0,
                "BJ": 5_000_000.0,
                "DEFAULT": 5_000_000.0,
            },
        },
        "scan": {
            "max_results": 200,
            "min_sector_members": 5,
            "max_boards": None,
        },
        "backtest": {
            "horizon_days": 40,
            "target_relative_pct": 0.08,
            "commission_bps": 5.0,
            "slippage_bps": 5.0,
        },
    }


class RPEConfigManager:
    def get_default_config(self) -> Dict:
        return get_default_rpe_config()

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
        from backend_api.models import RPEStrategyConfig

        row = (
            db.query(RPEStrategyConfig)
            .filter(RPEStrategyConfig.is_default.is_(True))
            .order_by(RPEStrategyConfig.id.asc())
            .first()
        )
        if row:
            return int(row.id)
        row = RPEStrategyConfig(
            name="default",
            description="RPE 默认参数",
            config_params=self.get_default_config(),
            is_default=True,
            is_active=True,
            precompute_enabled=True,
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
            from backend_api.models import RPEStrategyConfig

            if config_id is None:
                cid = self._ensure_default_row_exists(db)
                row = db.query(RPEStrategyConfig).filter(RPEStrategyConfig.id == cid).first()
            else:
                row = db.query(RPEStrategyConfig).filter(RPEStrategyConfig.id == int(config_id)).first()
            if not row:
                return self.get_default_config()
            merged = self._deep_merge(self.get_default_config(), dict(row.config_params or {}))
            _CACHE[int(row.id)] = copy.deepcopy(merged)
            merged["_config_id"] = int(row.id)
            return merged
        except Exception as e:
            logger.warning("读取 RPE 配置失败，使用默认: %s", e)
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
            from backend_api.models import RPEStrategyConfig

            self._ensure_default_row_exists(db)
            q = db.query(RPEStrategyConfig)
            if active_only:
                q = q.filter(RPEStrategyConfig.is_active.is_(True))
            rows = q.order_by(RPEStrategyConfig.is_default.desc(), RPEStrategyConfig.id.asc()).all()
            return [
                {
                    "id": int(r.id),
                    "name": r.name,
                    "description": r.description,
                    "is_default": bool(r.is_default),
                    "is_active": bool(r.is_active),
                    "precompute_enabled": bool(getattr(r, "precompute_enabled", False)),
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
            from backend_api.models import RPEStrategyConfig

            params = self._deep_merge(self.get_default_config(), config_params or {})
            if set_default:
                db.query(RPEStrategyConfig).update({"is_default": False})
            row = RPEStrategyConfig(
                name=name,
                description=description or "",
                config_params=params,
                is_default=bool(set_default),
                is_active=True,
                precompute_enabled=False,
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
            from backend_api.models import RPEStrategyConfig

            row = db.query(RPEStrategyConfig).filter(RPEStrategyConfig.id == int(config_id)).first()
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
            if "precompute_enabled" in patch:
                row.precompute_enabled = bool(patch["precompute_enabled"])
            db.commit()
            self._invalidate_cache(int(config_id))
            return {"id": int(row.id), "ok": True}
        finally:
            db.close()

    def set_default(self, config_id: int) -> Dict:
        db = self._session()
        try:
            from backend_api.models import RPEStrategyConfig

            row = db.query(RPEStrategyConfig).filter(RPEStrategyConfig.id == int(config_id)).first()
            if not row:
                raise ValueError(f"config_id={config_id} not found")
            db.query(RPEStrategyConfig).update({"is_default": False})
            row.is_default = True
            db.commit()
            self._invalidate_cache()
            return {"id": int(row.id), "is_default": True}
        finally:
            db.close()

    def list_precompute_config_ids(self) -> List[int]:
        try:
            configs = self.list_configs(active_only=True)
            ids = [
                int(c["id"])
                for c in configs
                if c.get("is_default") or c.get("precompute_enabled")
            ]
            return list(dict.fromkeys(ids)) or [self.get_default_config_id()]
        except Exception:
            return [self.get_default_config_id()]
