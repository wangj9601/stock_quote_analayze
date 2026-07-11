"""
用户管理相关的路由
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from pydantic import BaseModel

from backend_api.models import UserCreate, UserUpdate, UserInDB, FrontendRole, User
from backend_api.database import get_db
from backend_api.auth import get_password_hash, get_current_admin

router = APIRouter(prefix="/api/admin/users", tags=["admin"])

class UsersResponse(BaseModel):
    data: List[UserInDB]
    total: int
    page: int
    pageSize: int

class ChangePasswordRequest(BaseModel):
    """管理员修改用户密码请求体"""
    new_password: str


class StatusUpdateRequest(BaseModel):
    """更新用户状态请求体"""
    status: str

@router.get("", response_model=UsersResponse)
async def get_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=500),
    search: Optional[str] = Query(None),
    current_user = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取用户列表"""
    query = db.query(User)
    
    # 搜索功能
    if search:
        query = query.filter(
            or_(
                User.username.contains(search),
                User.email.contains(search)
            )
        )
    
    # 获取总数
    total = query.count()
    
    # 分页和排序
    users = query.order_by(desc(User.created_at)).offset(skip).limit(limit).all()
    
    # 计算当前页
    page = (skip // limit) + 1
    
    return UsersResponse(
        data=users,
        total=total,
        page=page,
        pageSize=limit
    )

@router.post("", response_model=UserInDB)
async def create_user(
    user: UserCreate,
    current_user = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """创建新用户"""
    try:
        # 检查用户名和邮箱是否已存在
        db_user = db.query(User).filter(
            (User.username == user.username) | (User.email == user.email)
        ).first()
        if db_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名或邮箱已存在"
            )
        
        # 验证密码长度（前端可能没有验证）
        if not user.password or len(user.password) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="密码长度不能少于6位"
            )
        
        # 创建新用户
        role_id = user.role_id
        if role_id is None and user.role:
            role_obj = db.query(FrontendRole).filter(FrontendRole.code == user.role).first()
            if role_obj:
                role_id = role_obj.id
            else:
                standard = db.query(FrontendRole).filter(FrontendRole.code == "standard").first()
                role_id = standard.id if standard else None

        db_user = User(
            username=user.username,
            email=user.email,
            password_hash=get_password_hash(user.password),
            role=user.role or "user",
            role_id=role_id,
            status="active"
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        import traceback
        error_msg = f"创建用户失败: {str(e)}"
        print(f"[create_user] {error_msg}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )

def _update_user_impl(user_id: int, user_update: UserUpdate, db: Session) -> User:
    """更新用户信息实现，供 PUT/POST 共用"""
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    update_data = user_update.dict(exclude_unset=True)
    if "role_id" in update_data and update_data["role_id"] is not None:
        role_obj = db.query(FrontendRole).filter(FrontendRole.id == update_data["role_id"]).first()
        if role_obj:
            update_data["role"] = role_obj.code
    for field, value in update_data.items():
        setattr(db_user, field, value)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.get("/stats")
async def get_user_stats(
    current_user = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取用户统计信息"""
    total = db.query(User).count()
    active = db.query(User).filter(User.status == "active").count()
    disabled = db.query(User).filter(User.status == "disabled").count()
    suspended = db.query(User).filter(User.status == "suspended").count()
    
    return {
        "total": total,
        "active": active,
        "disabled": disabled,
        "suspended": suspended
    }


@router.get("/test")
async def test_users_api():
    """测试用户API是否正常工作"""
    return {
        "message": "Users API is working",
        "timestamp": "2024-01-01T00:00:00"
    }


class UserRoleUpdate(BaseModel):
    role_id: int


@router.put("/{user_id}/role", response_model=UserInDB)
async def update_user_role(
    user_id: int,
    payload: UserRoleUpdate,
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="用户不存在")
    role_obj = db.query(FrontendRole).filter(FrontendRole.id == payload.role_id).first()
    if not role_obj:
        raise HTTPException(status_code=404, detail="角色不存在")
    db_user.role_id = role_obj.id
    db_user.role = role_obj.code
    db.commit()
    db.refresh(db_user)
    return db_user


@router.put("/{user_id}", response_model=UserInDB)
async def update_user_put(
    user_id: int,
    user_update: UserUpdate,
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """更新用户信息（PUT）。"""
    return _update_user_impl(user_id, user_update, db)


@router.post("/{user_id}", response_model=UserInDB)
async def update_user_post(
    user_id: int,
    user_update: UserUpdate,
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """更新用户信息（POST）；与 PUT 行为一致。"""
    return _update_user_impl(user_id, user_update, db)


def _update_user_status_impl(user_id: int, new_status: str, db: Session) -> dict:
    """更新用户状态实现，供 PUT/POST 共用"""
    if new_status not in ["active", "disabled", "suspended"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的状态值"
        )
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    db_user.status = new_status
    db.commit()
    return {"message": f"用户状态已更新为{new_status}"}


@router.put("/{user_id}/status")
@router.post("/{user_id}/status")
async def update_user_status(
    user_id: int,
    body: StatusUpdateRequest,
    current_user = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """更新用户状态。支持 PUT 与 POST，请求体为 { \"status\": \"active\"|\"disabled\"|\"suspended\" }。"""
    return _update_user_status_impl(user_id, body.status, db)

@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    current_user = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """删除用户"""
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 删除用户（这里假设已经处理了外键约束或级联删除）
    db.delete(db_user)
    db.commit()
    
    return {"message": "用户删除成功"}

def _change_user_password_impl(user_id: int, new_password: str, db: Session) -> dict:
    """管理员修改用户密码实现，供 PUT/POST 共用"""
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    if not new_password or len(new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新密码长度不能少于6位"
        )
    db_user.password_hash = get_password_hash(new_password)
    db.commit()
    return {"message": "密码修改成功"}


@router.put("/{user_id}/password")
async def change_user_password_put(
    user_id: int,
    body: ChangePasswordRequest,
    current_user = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """管理员直接修改指定用户密码（PUT）。"""
    return _change_user_password_impl(user_id, body.new_password, db)


@router.post("/{user_id}/password")
async def change_user_password_post(
    user_id: int,
    body: ChangePasswordRequest,
    current_user = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """管理员直接修改指定用户密码（POST）；与 PUT 行为一致。"""
    return _change_user_password_impl(user_id, body.new_password, db)

@router.post("/{user_id}/password/reset")
async def reset_user_password(
    user_id: int,
    current_user = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """管理员重置指定用户密码为系统默认值"""
    DEFAULT_PASSWORD = "bingfengtang$91"
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    db_user.password_hash = get_password_hash(DEFAULT_PASSWORD)
    db.commit()

    return {"message": "密码已重置为默认值", "default": DEFAULT_PASSWORD}