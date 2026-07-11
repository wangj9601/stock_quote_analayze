"""
管理端 - 前端权限资源管理
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend_api.auth import get_current_admin
from backend_api.database import get_db
from backend_api.models import FrontendPermissionInDB, FrontendPermission
from backend_api.permissions import build_permission_tree, sync_permissions_from_registry

router = APIRouter(prefix="/api/admin/permissions", tags=["admin-permissions"])


@router.get("/tree")
async def get_permissions_tree(
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return {"tree": build_permission_tree(db)}


@router.get("", response_model=list[FrontendPermissionInDB])
async def list_permissions(
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return (
        db.query(FrontendPermission)
        .filter(FrontendPermission.is_active.is_(True))
        .order_by(FrontendPermission.sort_order, FrontendPermission.code)
        .all()
    )


@router.post("/sync")
async def sync_permissions(
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    result = sync_permissions_from_registry(db)
    return {"success": True, **result}
