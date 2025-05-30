"""
认证相关的工具函数
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import hashlib
import logging

from .models import User, Admin, TokenData
from .database import get_db, SessionLocal
from .config import JWT_CONFIG

# 配置日志
logger = logging.getLogger(__name__)

# 密码加密上下文
pwd_context = CryptContext(
    schemes=["bcrypt", "sha256_crypt"],  # 支持 bcrypt 和 sha256_crypt
    deprecated="auto",
    sha256_crypt__default_rounds=50000  # 设置 SHA-256 的迭代次数
)

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

# JWT配置
SECRET_KEY = JWT_CONFIG["secret_key"]
ALGORITHM = JWT_CONFIG["algorithm"]
ACCESS_TOKEN_EXPIRE_MINUTES = JWT_CONFIG["access_token_expire_minutes"]

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    try:
        # 尝试使用 passlib 验证
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.debug(f"passlib 验证失败: {str(e)}")
        try:
            # 如果是旧的 SHA-256 哈希，直接比较
            if len(hashed_password) == 64:  # SHA-256 哈希长度
                sha256_hash = hashlib.sha256(plain_password.encode()).hexdigest()
                if sha256_hash == hashed_password:
                    # 密码验证成功，返回 True 以便后续迁移到 bcrypt
                    logger.info("使用旧 SHA-256 哈希验证成功")
                    return True
        except Exception as e:
            logger.debug(f"SHA-256 验证失败: {str(e)}")
        return False

def get_password_hash(password: str) -> str:
    """获取密码哈希值"""
    return pwd_context.hash(password)

def migrate_password_hash(db: Session, user: User, plain_password: str) -> None:
    """迁移密码哈希到新的算法"""
    try:
        logger.info(f"开始迁移用户 {user.username} 的密码哈希")
        # 使用 bcrypt 生成新的哈希值
        new_hash = pwd_context.hash(plain_password)
        # 更新用户的密码哈希
        user.password_hash = new_hash
        db.commit()
        logger.info(f"用户 {user.username} 的密码哈希迁移成功")
    except Exception as e:
        db.rollback()
        logger.error(f"用户 {user.username} 的密码哈希迁移失败: {str(e)}")
        raise e

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """获取当前用户"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user

async def get_current_admin(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Admin:
    """获取当前管理员"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的管理员认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        is_admin: bool = payload.get("is_admin", False)
        if username is None or not is_admin:
            raise credentials_exception
        token_data = TokenData(username=username, is_admin=True)
    except JWTError:
        raise credentials_exception
    
    admin = db.query(Admin).filter(Admin.username == token_data.username).first()
    if admin is None:
        raise credentials_exception
    return admin

def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """验证用户"""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        logger.warning(f"用户不存在: {username}")
        return None
    
    # 验证密码
    if verify_password(password, user.password_hash):
        # 如果是旧的 SHA-256 哈希，迁移到 bcrypt
        if len(user.password_hash) == 64:  # SHA-256 哈希长度
            try:
                logger.info(f"检测到用户 {username} 使用旧密码哈希，开始迁移")
                migrate_password_hash(db, user, password)
            except Exception as e:
                # 记录错误但不影响登录
                logger.error(f"用户 {username} 的密码迁移失败: {str(e)}")
        return user
    
    logger.warning(f"用户 {username} 密码验证失败")
    return None

def authenticate_admin(db: Session, username: str, password: str) -> Optional[Admin]:
    """验证管理员"""
    admin = db.query(Admin).filter(Admin.username == username).first()
    if not admin:
        return None
    if not verify_password(password, admin.password_hash):
        return None
    return admin

async def get_current_admin_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """获取当前管理员用户
    
    这个函数用于验证当前用户是否是管理员，并返回用户对象。
    它首先验证JWT令牌，然后检查用户是否具有管理员权限。
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的管理员认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        is_admin: bool = payload.get("is_admin", False)
        
        if username is None or not is_admin:
            raise credentials_exception
            
        token_data = TokenData(username=username, is_admin=True)
    except JWTError:
        raise credentials_exception
    
    # 获取用户对象
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
        
    # 验证用户是否是管理员
    admin = db.query(Admin).filter(Admin.username == token_data.username).first()
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    return user 