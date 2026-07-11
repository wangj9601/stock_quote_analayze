"""
管理端 - 前端角色管理
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend_api.auth import get_current_admin
from backend_api.database import get_db
from backend_api.models import (
    FrontendRole,
    FrontendRoleCreate,
    FrontendRoleUpdate,
    FrontendRoleInDB,
    RolePermissionsUpdate,
)
from backend_api.permissions import get_role_permission_codes, sync_permissions_from_registry

router = APIRouter(prefix="/api/admin/roles", tags=["admin-roles"])


@router.get("", response_model=List[FrontendRoleInDB])
async def list_roles(
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return db.query(FrontendRole).order_by(FrontendRole.id).all()


@router.post("", response_model=FrontendRoleInDB, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: FrontendRoleCreate,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    exists = db.query(FrontendRole).filter(FrontendRole.code == payload.code).first()
    if exists:
        raise HTTPException(status_code=400, detail="角色 code 已存在")
    role = FrontendRole(**payload.dict())
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


@router.put("/{role_id}", response_model=FrontendRoleInDB)
async def update_role(
    role_id: int,
    payload: FrontendRoleUpdate,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    role = db.query(FrontendRole).filter(FrontendRole.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(role, field, value)
    db.commit()
    db.refresh(role)
    return role


@router.delete("/{role_id}")
async def delete_role(
    role_id: int,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    role = db.query(FrontendRole).filter(FrontendRole.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.is_system:
        raise HTTPException(status_code=400, detail="系统内置角色不可删除")
    db.delete(role)
    db.commit()
    return {"success": True}


@router.get("/{role_id}/permissions")
async def get_role_permissions(
    role_id: int,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    role = db.query(FrontendRole).filter(FrontendRole.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    return {"permission_codes": get_role_permission_codes(db, role)}


@router.put("/{role_id}/permissions")
async def set_role_permissions(
    role_id: int,
    payload: RolePermissionsUpdate,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    from backend_api.models import FrontendPermission

    role = db.query(FrontendRole).filter(FrontendRole.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    perms = (
        db.query(FrontendPermission)
        .filter(
            FrontendPermission.code.in_(payload.permission_codes),
            FrontendPermission.is_active.is_(True),
        )
        .all()
    )
    role.permissions = perms
    db.commit()
    return {"success": True, "count": len(perms)}
