"""
用户管理相关的路由
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..models import UserCreate, UserUpdate, UserInDB
from ..database import get_db
from ..auth import get_current_admin, get_password_hash
from ..models import User

router = APIRouter(prefix="/api/admin/users", tags=["admin"])

@router.get("", response_model=List[UserInDB])
async def get_users(
    skip: int = 0,
    limit: int = 100,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取用户列表"""
    users = db.query(User).order_by(desc(User.created_at)).offset(skip).limit(limit).all()
    return users

@router.post("", response_model=UserInDB)
async def create_user(
    user: UserCreate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """创建新用户"""
    # 检查用户名和邮箱是否已存在
    db_user = db.query(User).filter(
        (User.username == user.username) | (User.email == user.email)
    ).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名或邮箱已存在"
        )
    
    # 创建新用户
    db_user = User(
        username=user.username,
        email=user.email,
        password_hash=get_password_hash(user.password),
        status="active"
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.put("/{user_id}", response_model=UserInDB)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_admin: User = Depends(get_current_admin),
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
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """更新用户状态"""
    if status not in ["active", "disabled"]:
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
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """删除用户"""
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 删除用户相关的所有数据
    db.query(Watchlist).filter(Watchlist.user_id == user_id).delete()
    db.query(WatchlistGroup).filter(WatchlistGroup.user_id == user_id).delete()
    db.delete(db_user)
    db.commit()
    
    return {"message": "用户删除成功"} 