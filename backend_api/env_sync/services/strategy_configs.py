# -*- coding: utf-8 -*-
"""策略参数版本 export / import（按 name upsert）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Type

from sqlalchemy.orm import Session

from backend_api.env_sync.bundle import empty_result, json_safe, make_bundle, table_exists
from backend_api.models import (
    GMSRuntimeConfig,
    GMSStrategyConfig,
    RPEStrategyConfig,
    SBBRStrategyConfig,
    URTStrategyConfig,
)

import logging

logger = logging.getLogger(__name__)

STRATEGY_TABLES = {
    "gms_strategy_configs": GMSStrategyConfig,
    "urt_strategy_configs": URTStrategyConfig,
    "rpe_strategy_configs": RPEStrategyConfig,
    "sbbr_strategy_configs": SBBRStrategyConfig,
    "gms_runtime_config": GMSRuntimeConfig,
}


def _row_to_dict(row: Any, fields: List[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for f in fields:
        if hasattr(row, f):
            out[f] = json_safe(getattr(row, f))
    return out


def _strategy_fields(model: Type) -> List[str]:
    base = ["name", "description", "config_params", "is_active", "is_default"]
    optional = [
        "version_label",
        "precompute_enabled",
        "created_by",
        "parent_id",
    ]
    cols = {c.name for c in model.__table__.columns}
    return [f for f in base + optional if f in cols]


def export_strategy_configs(
    db: Session,
    *,
    env_label: str = "local",
    tables: Optional[List[str]] = None,
) -> Dict[str, Any]:
    selected = set(tables) if tables else set(STRATEGY_TABLES.keys())
    items: Dict[str, Any] = {}
    for key, model in STRATEGY_TABLES.items():
        if key not in selected:
            continue
        tname = getattr(model, "__tablename__", "") or ""
        if tname and not table_exists(db, tname):
            logger.warning("env_sync export skip missing table: %s", tname)
            items[key] = []
            continue
        fields = _strategy_fields(model)
        rows = db.query(model).order_by(model.id.asc()).all()
        packed = []
        for r in rows:
            d = _row_to_dict(r, fields)
            d["_source_id"] = r.id
            packed.append(d)
        items[key] = packed
    return make_bundle(module="strategy_configs", items=items, env_label=env_label)


def import_strategy_configs(
    db: Session,
    bundle: Dict[str, Any],
    *,
    tables: Optional[List[str]] = None,
) -> Dict[str, Any]:
    result = empty_result()
    items = (bundle or {}).get("items") or {}
    id_maps: Dict[str, Dict[str, int]] = {}
    selected = set(tables) if tables else set(STRATEGY_TABLES.keys())

    for key, model in STRATEGY_TABLES.items():
        if key not in selected:
            continue
        rows = items.get(key) or []
        name_to_id: Dict[str, int] = {}
        fields = _strategy_fields(model)
        for raw in rows:
            try:
                name = str(raw.get("name") or "").strip()
                if not name:
                    result["skipped"] += 1
                    result["errors"].append(f"{key}: missing name")
                    continue
                with db.begin_nested():
                    existing = db.query(model).filter(model.name == name).first()
                    payload = {f: raw.get(f) for f in fields if f in raw and f != "parent_id"}
                    if existing:
                        for f, v in payload.items():
                            if f in ("name",):
                                continue
                            setattr(existing, f, v)
                        if hasattr(existing, "updated_at"):
                            existing.updated_at = datetime.now()
                        db.flush()
                        name_to_id[name] = int(existing.id)
                        result["updated"] += 1
                    else:
                        obj = model(**{k: v for k, v in payload.items() if k != "parent_id"})
                        db.add(obj)
                        db.flush()
                        name_to_id[name] = int(obj.id)
                        result["created"] += 1
            except Exception as e:
                result["errors"].append(f"{key}/{raw.get('name')}: {e}")
        id_maps[key] = name_to_id

    # 保证各策略至多一个 is_default
    for key, model in STRATEGY_TABLES.items():
        if key not in selected:
            continue
        if "is_default" not in {c.name for c in model.__table__.columns}:
            continue
        defaults = (
            db.query(model)
            .filter(model.is_default.is_(True))
            .order_by(model.id.asc())
            .all()
        )
        if len(defaults) > 1:
            for extra in defaults[1:]:
                extra.is_default = False

    db.commit()
    result["id_maps"] = id_maps
    return result
