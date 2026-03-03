"""
用户管理相关的路由
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from pydantic import BaseModel

from backend_api.models import UserCreate, UserUpdate, UserInDB
from backend_api.database import get_db
from backend_api.auth import get_password_hash
from backend_api.auth import get_current_admin
from backend_api.models import User

router = APIRouter(prefix="/api/admin/users", tags=["admin"])

class UsersResponse(BaseModel):
    data: List[UserInDB]
    total: int
    page: int
    pageSize: int

class ChangePasswordRequest(BaseModel):
    """管理员修改用户密码请求体"""
    new_password: str

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
        db_user = User(
            username=user.username,
            email=user.email,
            password_hash=get_password_hash(user.password),
            role=user.role,
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

@router.put("/{user_id}", response_model=UserInDB)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """更新用户信息"""
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 更新用户信息
    update_data = user_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_user, field, value)
    
    db.commit()
    db.refresh(db_user)
    return db_user

@router.put("/{user_id}/status")
async def update_user_status(
    user_id: int,
    status: str,
    current_user = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """更新用户状态"""
    if status not in ["active", "disabled", "suspended"]:
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
    
    db_user.status = status
    db.commit()
    return {"message": f"用户状态已更新为{status}"}

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

@router.put("/{user_id}/password")
async def change_user_password(
    user_id: int,
    body: ChangePasswordRequest,
    current_user = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """管理员直接修改指定用户密码"""
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    if not body.new_password or len(body.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新密码长度不能少于6位"
        )

    db_user.password_hash = get_password_hash(body.new_password)
    db.commit()

    return {"message": "密码修改成功"}

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
        "message": "用户管理API正常工作",
        "timestamp": "2024-01-01T00:00:00Z",
        "data": [
            {
                "id": 1,
                "username": "test_user",
                "email": "test@example.com",
                "role": "user",
                "status": "active",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z"
            }
        ],
        "total": 1,
        "page": 1,
        "pageSize": 20
    } 