# -*- coding: utf-8 -*-
"""同步编排：export / import 多模块（支持细粒度资源勾选 + 行情日期范围）。"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend_api.env_sync import expand_modules, needs_date_range, split_resources
from backend_api.env_sync.services.market_data import (
    export_board_data,
    export_quotes,
    export_stock_basic,
    import_board_data,
    import_quotes,
    import_stock_basic,
    validate_date_range,
)
from backend_api.env_sync.services.strategy_configs import (
    export_strategy_configs,
    import_strategy_configs,
)
from backend_api.env_sync.services.trade_observe import (
    export_trade_observe,
    import_trade_observe,
)


def _env_label() -> str:
    return (os.getenv("ENVIRONMENT") or "unknown").strip() or "unknown"


def normalize_modules(modules: List[str] | None) -> List[str]:
    """兼容旧接口名：展开为细粒度资源列表。"""
    return expand_modules(modules)


def export_modules(
    db: Session,
    modules: List[str] | None = None,
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    resources = expand_modules(modules)
    parts = split_resources(resources)
    date_range = validate_date_range(
        start_date,
        end_date,
        require=needs_date_range(resources),
    )
    bundles: Dict[str, Any] = {}
    label = _env_label()

    def _stage(name: str, fn):
        try:
            return fn()
        except Exception as e:
            # 确保调用方可 rollback；附带阶段名便于排查
            raise RuntimeError(f"export 阶段 [{name}] 失败: {type(e).__name__}: {e}") from e

    if parts["strategy"]:
        bundles["strategy_configs"] = _stage(
            "strategy_configs",
            lambda: export_strategy_configs(
                db, env_label=label, tables=parts["strategy"]
            ),
        )
    if parts["observe"]:
        bundles["trade_observe"] = _stage(
            "trade_observe",
            lambda: export_trade_observe(
                db, env_label=label, tables=parts["observe"]
            ),
        )
    if parts["basic"]:
        bundles["stock_basic"] = _stage(
            "stock_basic",
            lambda: export_stock_basic(
                db, env_label=label, tables=set(parts["basic"])
            ),
        )
    if parts["board"]:
        bundles["board_data"] = _stage(
            "board_data",
            lambda: export_board_data(
                db, env_label=label, tables=set(parts["board"])
            ),
        )
    if parts["quotes"]:
        bundles["quotes"] = _stage(
            "quotes",
            lambda: export_quotes(
                db,
                start=date_range["start"],
                end=date_range["end"],
                tables=set(parts["quotes"]),
                env_label=label,
            ),
        )

    out: Dict[str, Any] = {"success": True, "modules": resources, "bundles": bundles}
    if date_range["start"] and date_range["end"]:
        out["date_range"] = {
            "start_date": date_range["start"].isoformat(),
            "end_date": date_range["end"].isoformat(),
        }
    return out


def import_modules(
    db: Session,
    bundles: Dict[str, Any],
    *,
    modules: List[str] | None = None,
) -> Dict[str, Any]:
    """
    bundles: { strategy_configs|trade_observe|stock_basic|board_data|quotes: SyncBundle }
    modules: 可选，限制导入细项；为空则导入包内全部 items。
    """
    results: Dict[str, Any] = {}
    selected = expand_modules(modules) if modules else None
    parts = split_resources(selected) if selected else None

    if "strategy_configs" in (bundles or {}):
        tables = parts["strategy"] if parts else None
        results["strategy_configs"] = import_strategy_configs(
            db, bundles["strategy_configs"], tables=tables
        )
    if "trade_observe" in (bundles or {}):
        tables = parts["observe"] if parts else None
        results["trade_observe"] = import_trade_observe(
            db, bundles["trade_observe"], tables=tables
        )
    if "stock_basic" in (bundles or {}):
        tables = set(parts["basic"]) if parts else None
        results["stock_basic"] = import_stock_basic(
            db, bundles["stock_basic"], tables=tables
        )
    if "board_data" in (bundles or {}):
        tables = set(parts["board"]) if parts else None
        results["board_data"] = import_board_data(
            db, bundles["board_data"], tables=tables
        )
    if "quotes" in (bundles or {}):
        tables = set(parts["quotes"]) if parts else None
        results["quotes"] = import_quotes(db, bundles["quotes"], tables=tables)
    return {"success": True, "results": results}
