# -*- coding: utf-8 -*-
"""同步包结构与序列化辅助。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional


SCHEMA_VERSION = 1


def table_exists(db: Any, table_name: str) -> bool:
    """当前库是否存在物理表（缺迁移时 export 可跳过，避免整单 500）。"""
    from sqlalchemy import inspect

    bind = db.get_bind() if hasattr(db, "get_bind") else getattr(db, "bind", None)
    if bind is None:
        return False
    return bool(inspect(bind).has_table(table_name))


def json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


def parse_dt(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:26], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(str(value).replace("Z", ""))
    except Exception:
        return None


def parse_date(value: Any) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def make_bundle(
    *,
    module: str,
    items: Dict[str, Any],
    env_label: str = "unknown",
) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "module": module,
        "exported_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
        "env_label": env_label,
        "items": items,
    }


def empty_result() -> Dict[str, Any]:
    return {"created": 0, "updated": 0, "skipped": 0, "errors": []}


def merge_results(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "created": int(a.get("created", 0)) + int(b.get("created", 0)),
        "updated": int(a.get("updated", 0)) + int(b.get("updated", 0)),
        "skipped": int(a.get("skipped", 0)) + int(b.get("skipped", 0)),
        "errors": list(a.get("errors") or []) + list(b.get("errors") or []),
    }
