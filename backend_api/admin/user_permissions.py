"""
管理端 - 用户级权限覆盖（独立路由模块，与 users.py 解耦便于部署识别）
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend_api.auth import get_current_admin
from backend_api.database import get_db
from backend_api.models import User, UserPermissionsUpdate, UserPermissionsDetail
from backend_api.permissions import (
    build_user_permissions_detail,
    set_user_effective_permissions,
    clear_user_permission_overrides,
)

router = APIRouter(prefix="/api/admin/users", tags=["admin-user-permissions"])


@router.get("/{user_id}/permissions", response_model=UserPermissionsDetail)
async def get_user_permissions(
    user_id: int,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return build_user_permissions_detail(db, db_user)


@router.put("/{user_id}/permissions")
@router.post("/{user_id}/permissions")
async def set_user_permissions(
    user_id: int,
    payload: UserPermissionsUpdate,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="用户不存在")
    override_count = set_user_effective_permissions(db, db_user, payload.permission_codes)
    return {"success": True, "override_count": override_count}


@router.delete("/{user_id}/permissions")
async def reset_user_permissions(
    user_id: int,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="用户不存在")
    clear_user_permission_overrides(db, user_id)
    return {"success": True, "message": "已恢复为角色默认权限"}
