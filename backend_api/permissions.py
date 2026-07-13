"""
前端权限查询与校验
"""

from typing import List, Optional, Callable, Set

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend_api.database import get_db
from backend_api.models import (
    User,
    FrontendRole,
    FrontendPermission,
    RolePermission,
    UserPermission,
    UserRoleInfo,
    PermissionsResponse,
    UserPermissionsDetail,
)
from backend_api.auth import get_current_user_optional


def get_standard_role(db: Session) -> Optional[FrontendRole]:
    return db.query(FrontendRole).filter(FrontendRole.code == "standard").first()


def resolve_user_role(db: Session, user: Optional[User]) -> FrontendRole:
    if user and user.role_id:
        role = db.query(FrontendRole).filter(FrontendRole.id == user.role_id).first()
        if role:
            return role
    if user and user.role:
        role = db.query(FrontendRole).filter(FrontendRole.code == user.role).first()
        if role:
            return role
    role = get_standard_role(db)
    if not role:
        raise HTTPException(status_code=500, detail="标准角色未配置，请先执行权限迁移")
    return role


def get_role_permission_codes(db: Session, role: FrontendRole) -> List[str]:
    perms = (
        db.query(FrontendPermission)
        .join(RolePermission, RolePermission.permission_id == FrontendPermission.id)
        .filter(
            RolePermission.role_id == role.id,
            FrontendPermission.is_active.is_(True),
        )
        .order_by(FrontendPermission.sort_order, FrontendPermission.code)
        .all()
    )
    return [p.code for p in perms]


def get_user_override_map(db: Session, user_id: int) -> dict:
    """返回 {permission_code: granted}，granted=True 额外授予，False 撤销"""
    rows = (
        db.query(FrontendPermission.code, UserPermission.granted)
        .join(UserPermission, UserPermission.permission_id == FrontendPermission.id)
        .filter(UserPermission.user_id == user_id, FrontendPermission.is_active.is_(True))
        .all()
    )
    return {code: granted for code, granted in rows}


def get_effective_permission_codes(db: Session, user: Optional[User]) -> List[str]:
    role = resolve_user_role(db, user)
    effective: Set[str] = set(get_role_permission_codes(db, role))
    if user and user.id:
        for code, granted in get_user_override_map(db, user.id).items():
            if granted:
                effective.add(code)
            else:
                effective.discard(code)
    return sorted(effective)


def has_custom_permissions(db: Session, user: Optional[User]) -> bool:
    if not user or not user.id:
        return False
    return db.query(UserPermission.user_id).filter(UserPermission.user_id == user.id).first() is not None


def build_permissions_response(db: Session, user: Optional[User]) -> PermissionsResponse:
    role = resolve_user_role(db, user)
    codes = get_effective_permission_codes(db, user)
    return PermissionsResponse(
        permissions=codes,
        role=UserRoleInfo(code=role.code, name=role.name),
        has_custom_permissions=has_custom_permissions(db, user),
    )


def build_user_permissions_detail(db: Session, user: User) -> UserPermissionsDetail:
    role = resolve_user_role(db, user)
    role_codes = get_role_permission_codes(db, role)
    effective = get_effective_permission_codes(db, user)
    override_count = (
        db.query(UserPermission).filter(UserPermission.user_id == user.id).count()
    )
    return UserPermissionsDetail(
        role=UserRoleInfo(code=role.code, name=role.name),
        role_permission_codes=role_codes,
        effective_permission_codes=effective,
        override_count=override_count,
    )


def set_user_effective_permissions(db: Session, user: User, effective_codes: List[str]) -> int:
    """保存用户最终生效权限，自动计算相对角色的 grant/deny 覆盖"""
    role = resolve_user_role(db, user)
    role_codes = set(get_role_permission_codes(db, role))
    effective = set(effective_codes)

    all_perms = (
        db.query(FrontendPermission)
        .filter(FrontendPermission.is_active.is_(True))
        .all()
    )
    code_to_id = {p.code: p.id for p in all_perms}

    db.query(UserPermission).filter(UserPermission.user_id == user.id).delete()

    override_count = 0
    for perm in all_perms:
        in_role = perm.code in role_codes
        in_effective = perm.code in effective
        if in_effective and not in_role:
            db.add(UserPermission(user_id=user.id, permission_id=perm.id, granted=True))
            override_count += 1
        elif not in_effective and in_role:
            db.add(UserPermission(user_id=user.id, permission_id=perm.id, granted=False))
            override_count += 1

    db.commit()
    return override_count


def clear_user_permission_overrides(db: Session, user_id: int) -> None:
    db.query(UserPermission).filter(UserPermission.user_id == user_id).delete()
    db.commit()


def user_has_permission(db: Session, user: Optional[User], code: str) -> bool:
    return code in get_effective_permission_codes(db, user)


def require_permission(code: str) -> Callable:
    async def _checker(
        current_user: Optional[User] = Depends(get_current_user_optional),
        db: Session = Depends(get_db),
    ) -> None:
        if not user_has_permission(db, current_user, code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"无权限: {code}",
            )

    return _checker


def build_permission_tree(db: Session) -> list:
    perms = (
        db.query(FrontendPermission)
        .filter(FrontendPermission.is_active.is_(True))
        .order_by(FrontendPermission.sort_order, FrontendPermission.code)
        .all()
    )
    nodes = {}
    roots = []
    for p in perms:
        nodes[p.code] = {
            "id": p.id,
            "code": p.code,
            "name": p.name,
            "level": p.level,
            "parent_code": p.parent_code,
            "channel_code": p.channel_code,
            "sort_order": p.sort_order,
            "children": [],
        }
    for p in perms:
        node = nodes[p.code]
        if p.parent_code and p.parent_code in nodes:
            nodes[p.parent_code]["children"].append(node)
        else:
            roots.append(node)
    return roots


def sync_permissions_from_registry(db: Session) -> dict:
    from backend_api.permission_registry_data import PERMISSION_REGISTRY

    created = 0
    updated = 0
    for item in PERMISSION_REGISTRY:
        existing = db.query(FrontendPermission).filter(FrontendPermission.code == item["code"]).first()
        if existing:
            for key, value in item.items():
                setattr(existing, key, value)
            existing.is_active = True
            updated += 1
        else:
            db.add(FrontendPermission(**item))
            created += 1
    db.commit()

    standard = get_standard_role(db)
    admin_role = db.query(FrontendRole).filter(FrontendRole.code == "admin").first()
    all_perms = db.query(FrontendPermission).filter(FrontendPermission.is_active.is_(True)).all()
    for role in filter(None, [standard, admin_role]):
        role.permissions = all_perms
    db.commit()
    return {"created": created, "updated": updated, "total": len(PERMISSION_REGISTRY)}


def ensure_permissions_from_registry(db: Session) -> dict:
    """
    增量同步注册表权限：写入/更新注册表项；把 admin/standard 缺少的注册表权限补上。
    不覆盖自定义角色已有授权（与全量 sync 不同）。
    """
    from backend_api.permission_registry_data import PERMISSION_REGISTRY

    created_codes: List[str] = []
    updated = 0
    for item in PERMISSION_REGISTRY:
        existing = db.query(FrontendPermission).filter(FrontendPermission.code == item["code"]).first()
        if existing:
            for key, value in item.items():
                setattr(existing, key, value)
            existing.is_active = True
            updated += 1
        else:
            db.add(FrontendPermission(**item))
            created_codes.append(item["code"])
    db.commit()

    registry_codes = {item["code"] for item in PERMISSION_REGISTRY}
    registry_perms = (
        db.query(FrontendPermission)
        .filter(FrontendPermission.code.in_(registry_codes), FrontendPermission.is_active.is_(True))
        .all()
    )
    standard = get_standard_role(db)
    admin_role = db.query(FrontendRole).filter(FrontendRole.code == "admin").first()
    granted = 0
    for role in filter(None, [standard, admin_role]):
        existing_ids = {p.id for p in (role.permissions or [])}
        for perm in registry_perms:
            if perm.id not in existing_ids:
                role.permissions.append(perm)
                granted += 1
    db.commit()

    return {
        "created": len(created_codes),
        "updated": updated,
        "granted_to_builtin_roles": granted,
        "created_codes": created_codes,
        "total": len(PERMISSION_REGISTRY),
    }
