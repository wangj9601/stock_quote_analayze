"""
用户认证相关的路由
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel
import logging
from typing import Optional
import traceback
import json
import time
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .models import User, Token, UserInDB
from .database import get_db, SessionLocal
from .auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('auth.log', encoding='utf-8', mode='a'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 请求日志中间件
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # 获取请求信息
        client_host = request.client.host if request.client else "unknown"
        method = request.method
        url = str(request.url)
        
        # 记录请求开始
        logger.info(f"请求开始 - {method} {url} - IP: {client_host}")
        
        try:
            # 获取请求体（如果是POST请求）
            body = None
            if method == "POST":
                try:
                    body = await request.body()
                    body_str = body.decode()
                    # 如果是登录请求，隐藏密码
                    if "password" in body_str:
                        body_dict = json.loads(body_str)
                        body_dict["password"] = "******"
                        body_str = json.dumps(body_dict)
                    logger.debug(f"请求体: {body_str}")
                except:
                    pass
            
            # 处理请求
            response = await call_next(request)
            
            # 计算处理时间
            process_time = time.time() - start_time
            
            # 记录请求完成
            logger.info(
                f"请求完成 - {method} {url} - "
                f"状态码: {response.status_code} - "
                f"处理时间: {process_time:.3f}秒 - "
                f"IP: {client_host}"
            )
            
            return response
            
        except Exception as e:
            # 记录请求异常
            process_time = time.time() - start_time
            logger.error(
                f"请求异常 - {method} {url} - "
                f"错误: {str(e)} - "
                f"处理时间: {process_time:.3f}秒 - "
                f"IP: {client_host}\n"
                f"{traceback.format_exc()}"
            )
            raise

router = APIRouter(prefix="/api/auth", tags=["auth"])

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)

class LoginRequest(BaseModel):
    """登录请求数据模型"""
    username: str
    password: str

async def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """获取当前用户（可选）"""
    if not token:
        logger.debug("未提供认证令牌")
        return None
    try:
        user = await get_current_user(token, db)
        logger.debug(f"成功获取当前用户: {user.username} (ID: {user.id})")
        return user
    except Exception as e:
        logger.warning(f"获取当前用户失败: {str(e)}")
        return None

@router.post("/login", response_model=Token)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """用户登录"""
    start_time = time.time()
    client_host = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    
    # 记录请求信息
    logger.info(
        f"收到登录请求 - "
        f"用户名: {login_data.username}, "
        f"IP: {client_host}, "
        f"User-Agent: {user_agent}"
    )
    
    try:
        # 验证用户名和密码
        logger.info(f"开始验证用户: {login_data.username}")
        user = authenticate_user(db, login_data.username, login_data.password)
        
        if not user:
            logger.warning(
                f"登录失败: 用户名或密码错误 - "
                f"用户名: {login_data.username}, "
                f"IP: {client_host}, "
                f"User-Agent: {user_agent}"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        logger.info(f"用户验证成功: {login_data.username} (ID: {user.id})")
        
        # 检查用户状态
        logger.info(f"检查用户状态: {login_data.username} - 当前状态: {user.status}")
        if user.status != "active":
            logger.warning(
                f"登录失败: 账号已被禁用 - "
                f"用户名: {login_data.username}, "
                f"IP: {client_host}, "
                f"User-Agent: {user_agent}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账号已被禁用"
            )
        
        # 更新最后登录时间
        try:
            old_login_time = user.last_login
            user.last_login = datetime.now()
            db.commit()
            logger.info(
                f"更新最后登录时间成功 - "
                f"用户: {login_data.username}, "
                f"上次登录: {old_login_time}, "
                f"本次登录: {user.last_login}"
            )
        except Exception as e:
            logger.error(f"更新最后登录时间失败: {str(e)}")
            # 这里不抛出异常，因为更新登录时间不是关键操作
        
        # 创建访问令牌
        try:
            logger.info(f"开始创建访问令牌 - 用户: {login_data.username}")
            access_token = create_access_token(
                data={"sub": user.username, "user_id": user.id}
            )
            logger.info(f"访问令牌创建成功 - 用户: {login_data.username}")
        except Exception as e:
            logger.error(f"创建访问令牌失败: {str(e)}\n{traceback.format_exc()}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="创建访问令牌失败"
            )
        
        # 创建响应
        try:
            logger.info(f"开始创建登录响应 - 用户: {login_data.username}")
            response = {
                "access_token": access_token,
                "token_type": "bearer",
                "user": UserInDB.from_orm(user)
            }
            
            # 计算总处理时间
            process_time = time.time() - start_time
            
            logger.info(
                f"登录成功 - "
                f"用户: {login_data.username}, "
                f"ID: {user.id}, "
                f"IP: {client_host}, "
                f"User-Agent: {user_agent}, "
                f"处理时间: {process_time:.3f}秒"
            )
            return response
        except Exception as e:
            logger.error(f"创建响应失败: {str(e)}\n{traceback.format_exc()}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="创建响应失败"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        error_detail = f"登录过程发生错误: {str(e)}\n{traceback.format_exc()}"
        process_time = time.time() - start_time
        logger.error(
            f"{error_detail} - "
            f"用户: {login_data.username}, "
            f"IP: {client_host}, "
            f"User-Agent: {user_agent}, "
            f"处理时间: {process_time:.3f}秒"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail
        )

@router.get("/status")
async def get_auth_status(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """获取认证状态"""
    start_time = time.time()
    client_host = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    
    try:
        if current_user:
            process_time = time.time() - start_time
            logger.info(
                f"获取认证状态: 用户已登录 - "
                f"用户: {current_user.username}, "
                f"ID: {current_user.id}, "
                f"IP: {client_host}, "
                f"User-Agent: {user_agent}, "
                f"处理时间: {process_time:.3f}秒"
            )
            return {
                "success": True,
                "logged_in": True,
                "user": UserInDB.from_orm(current_user)
            }
        else:
            process_time = time.time() - start_time
            logger.info(
                f"获取认证状态: 用户未登录 - "
                f"IP: {client_host}, "
                f"User-Agent: {user_agent}, "
                f"处理时间: {process_time:.3f}秒"
            )
            return {
                "success": True,
                "logged_in": False,
                "user": None
            }
    except Exception as e:
        error_detail = f"获取认证状态时发生错误: {str(e)}\n{traceback.format_exc()}"
        process_time = time.time() - start_time
        logger.error(
            f"{error_detail} - "
            f"IP: {client_host}, "
            f"User-Agent: {user_agent}, "
            f"处理时间: {process_time:.3f}秒"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail
        )

@router.post("/logout")
async def logout(request: Request):
    """用户登出"""
    start_time = time.time()
    client_host = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    
    try:
        process_time = time.time() - start_time
        logger.info(
            f"用户登出请求 - "
            f"IP: {client_host}, "
            f"User-Agent: {user_agent}, "
            f"处理时间: {process_time:.3f}秒"
        )
        return {
            "success": True,
            "message": "已成功登出"
        }
    except Exception as e:
        error_detail = f"登出过程发生错误: {str(e)}\n{traceback.format_exc()}"
        process_time = time.time() - start_time
        logger.error(
            f"{error_detail} - "
            f"IP: {client_host}, "
            f"User-Agent: {user_agent}, "
            f"处理时间: {process_time:.3f}秒"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail
        )