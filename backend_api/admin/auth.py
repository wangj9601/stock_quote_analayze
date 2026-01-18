"""
管理员认证相关的路由
"""

from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel
from backend_api.models import Token, AdminInDB, Admin
from backend_api.database import get_db
from backend_api.auth import (
    authenticate_admin,
    create_access_token,
    get_current_admin,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

class LoginRequest(BaseModel):
    username: str
    password: str

# 修改路由前缀以匹配前端请求路径
router = APIRouter(prefix="/api/admin/auth", tags=["admin-auth"])

@router.post("/login", response_model=Token)
async def login_for_access_token(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """管理员登录"""
    admin = authenticate_admin(db, username, password)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 更新最后登录时间
    admin.last_login = datetime.now()
    db.commit()
    
    # 创建访问令牌
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": admin.username, "is_admin": True},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "admin": AdminInDB.from_orm(admin)
    }

@router.get("/verify")
async def verify_token(
    current_admin: Admin = Depends(get_current_admin)
):
    """验证管理员token"""
    return {
        "valid": True,
        "admin": AdminInDB.from_orm(current_admin)
    }

@router.get("/me", response_model=AdminInDB)
async def read_admin_me(current_admin: Admin = Depends(get_current_admin)):
    """获取当前管理员信息"""
    return current_admin

@router.post("/logout")
async def logout(current_admin: Admin = Depends(get_current_admin)):
    """管理员登出"""
    # 在实际应用中，这里可以将token加入黑名单
    # 或者执行其他登出逻辑
    return {"message": "登出成功"} 