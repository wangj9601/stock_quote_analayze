# -*- coding: utf-8 -*-
"""权限资源 / 角色 / 角色-权限映射 export·import（按 code upsert）。

不含用户表与用户级权限覆盖（user_permissions）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from backend_api.env_sync.bundle import empty_result, json_safe, make_bundle, table_exists
from backend_api.models import FrontendPermission, FrontendRole, RolePermission

logger = logging.getLogger(__name__)

PERMISSION_TABLES = (
    "frontend_permissions",
    "frontend_roles",
    "role_permissions",
)

_PERM_FIELDS = [
    "code",
    "name",
    "level",
    "parent_code",
    "channel_code",
    "sort_order",
    "is_active",
]

_ROLE_FIELDS = [
    "code",
    "name",
    "description",
    "is_system",
]


def _row_dict(row: Any, fields: List[str]) -> Dict[str, Any]:
    return {f: json_safe(getattr(row, f, None)) for f in fields}


def export_permissions_resources(
    db: Session,
    *,
    env_label: str = "local",
    tables: Optional[List[str]] = None,
) -> Dict[str, Any]:
    selected = set(tables) if tables else set(PERMISSION_TABLES)
    items: Dict[str, Any] = {}

    if "frontend_permissions" in selected:
        if not table_exists(db, "frontend_permissions"):
            logger.warning("env_sync export skip missing table: frontend_permissions")
            items["frontend_permissions"] = []
        else:
            rows = (
                db.query(FrontendPermission)
                .order_by(FrontendPermission.sort_order.asc(), FrontendPermission.code.asc())
                .all()
            )
            packed = []
            for r in rows:
                d = _row_dict(r, _PERM_FIELDS)
                d["_source_id"] = r.id
                packed.append(d)
            items["frontend_permissions"] = packed

    if "frontend_roles" in selected:
        if not table_exists(db, "frontend_roles"):
            logger.warning("env_sync export skip missing table: frontend_roles")
            items["frontend_roles"] = []
        else:
            rows = db.query(FrontendRole).order_by(FrontendRole.id.asc()).all()
            packed = []
            for r in rows:
                d = _row_dict(r, _ROLE_FIELDS)
                d["_source_id"] = r.id
                packed.append(d)
            items["frontend_roles"] = packed

    if "role_permissions" in selected:
        if not table_exists(db, "role_permissions") or not table_exists(
            db, "frontend_roles"
        ) or not table_exists(db, "frontend_permissions"):
            logger.warning("env_sync export skip missing table: role_permissions")
            items["role_permissions"] = []
        else:
            rows = (
                db.query(
                    FrontendRole.code,
                    FrontendPermission.code,
                )
                .select_from(RolePermission)
                .join(FrontendRole, FrontendRole.id == RolePermission.role_id)
                .join(
                    FrontendPermission,
                    FrontendPermission.id == RolePermission.permission_id,
                )
                .order_by(FrontendRole.code.asc(), FrontendPermission.code.asc())
                .all()
            )
            items["role_permissions"] = [
                {"role_code": rc, "permission_code": pc} for rc, pc in rows
            ]

    return make_bundle(module="permissions_resources", items=items, env_label=env_label)


def _import_permissions(
    db: Session,
    rows: List[Dict[str, Any]],
    result: Dict[str, Any],
) -> None:
    for raw in rows:
        try:
            code = str(raw.get("code") or "").strip()
            if not code:
                result["skipped"] += 1
                result["errors"].append("frontend_permissions: missing code")
                continue
            with db.begin_nested():
                existing = (
                    db.query(FrontendPermission)
                    .filter(FrontendPermission.code == code)
                    .first()
                )
                payload = {
                    f: raw.get(f)
                    for f in _PERM_FIELDS
                    if f in raw and f != "code"
                }
                if existing:
                    for f, v in payload.items():
                        setattr(existing, f, v)
                    db.flush()
                    result["updated"] += 1
                else:
                    obj = FrontendPermission(code=code, **payload)
                    db.add(obj)
                    db.flush()
                    result["created"] += 1
        except Exception as e:
            result["errors"].append(f"frontend_permissions/{raw.get('code')}: {e}")


def _import_roles(
    db: Session,
    rows: List[Dict[str, Any]],
    result: Dict[str, Any],
) -> None:
    for raw in rows:
        try:
            code = str(raw.get("code") or "").strip()
            if not code:
                result["skipped"] += 1
                result["errors"].append("frontend_roles: missing code")
                continue
            with db.begin_nested():
                existing = (
                    db.query(FrontendRole).filter(FrontendRole.code == code).first()
                )
                payload = {
                    f: raw.get(f) for f in _ROLE_FIELDS if f in raw and f != "code"
                }
                if existing:
                    for f, v in payload.items():
                        setattr(existing, f, v)
                    db.flush()
                    result["updated"] += 1
                else:
                    obj = FrontendRole(code=code, **payload)
                    db.add(obj)
                    db.flush()
                    result["created"] += 1
        except Exception as e:
            result["errors"].append(f"frontend_roles/{raw.get('code')}: {e}")


def _import_role_permissions(
    db: Session,
    rows: List[Dict[str, Any]],
    result: Dict[str, Any],
) -> None:
    """按角色覆盖映射：导出包中出现的角色，其权限集合替换为包内集合。"""
    by_role: Dict[str, Set[str]] = {}
    for raw in rows:
        role_code = str(raw.get("role_code") or "").strip()
        perm_code = str(raw.get("permission_code") or "").strip()
        if not role_code or not perm_code:
            result["skipped"] += 1
            result["errors"].append("role_permissions: missing role_code/permission_code")
            continue
        by_role.setdefault(role_code, set()).add(perm_code)

    if not by_role:
        return

    all_roles = {
        r.code: r
        for r in db.query(FrontendRole)
        .filter(FrontendRole.code.in_(list(by_role.keys())))
        .all()
    }
    all_perms = {
        p.code: p
        for p in db.query(FrontendPermission)
        .filter(
            FrontendPermission.code.in_(
                list({pc for pcs in by_role.values() for pc in pcs})
            )
        )
        .all()
    }

    for role_code, perm_codes in by_role.items():
        role = all_roles.get(role_code)
        if not role:
            result["skipped"] += 1
            result["errors"].append(f"role_permissions: role not found: {role_code}")
            continue
        try:
            with db.begin_nested():
                db.query(RolePermission).filter(
                    RolePermission.role_id == role.id
                ).delete(synchronize_session=False)
                created_here = 0
                for pc in sorted(perm_codes):
                    perm = all_perms.get(pc)
                    if not perm:
                        result["skipped"] += 1
                        result["errors"].append(
                            f"role_permissions: permission not found: {pc}"
                        )
                        continue
                    db.add(
                        RolePermission(role_id=role.id, permission_id=perm.id)
                    )
                    created_here += 1
                db.flush()
                # 覆盖导入：整角色映射计为 updated；新建链接计入 created
                result["updated"] += 1
                result["created"] += created_here
        except Exception as e:
            result["errors"].append(f"role_permissions/{role_code}: {e}")


def import_permissions_resources(
    db: Session,
    bundle: Dict[str, Any],
    *,
    tables: Optional[List[str]] = None,
) -> Dict[str, Any]:
    result = empty_result()
    items = (bundle or {}).get("items") or {}
    selected = set(tables) if tables else set(PERMISSION_TABLES)

    # 顺序：权限树 → 角色 → 映射
    if "frontend_permissions" in selected:
        _import_permissions(db, items.get("frontend_permissions") or [], result)
    if "frontend_roles" in selected:
        _import_roles(db, items.get("frontend_roles") or [], result)
    if "role_permissions" in selected:
        _import_role_permissions(db, items.get("role_permissions") or [], result)

    db.commit()
    return result
